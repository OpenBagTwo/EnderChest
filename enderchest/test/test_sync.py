"""Tests around file transfer functionality."""
import logging
import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

import pytest

from enderchest import craft
from enderchest import filesystem as fs
from enderchest import gather
from enderchest import remote as r
from enderchest.sync import file, path_from_uri

from . import utils


class TestPathFromURI:
    def test_roundtrip(self, tmpdir):
        original_path = Path(tmpdir) / "this has a space in it" / "(="
        assert path_from_uri(urlparse(original_path.as_uri())) == original_path


@pytest.mark.xfail(
    not shutil.which("rsync"), reason="rsync is not installed on this system"
)  # TODO: remove xfail once this method has been moved to a different module
class TestURIToSSH:
    @pytest.fixture(scope="class")
    def rsync_module(self):
        from enderchest.sync import rsync

        yield rsync

    def test_simple_parse(self, rsync_module):
        address = rsync_module.uri_to_ssh(
            urlparse("rsync://openbagtwo@couchgaming:22/home/openbagtwo/minecraft")
        )
        assert address == "openbagtwo@couchgaming:22:/home/openbagtwo/minecraft"

    def test_no_username_parse(self, rsync_module):
        address = rsync_module.uri_to_ssh(
            urlparse("rsync://steamdeck/home/openbagtwo/minecraft")
        )
        assert address == "steamdeck:/home/openbagtwo/minecraft"

    def test_no_netloc_parse(self, rsync_module):
        address = rsync_module.uri_to_ssh(
            urlparse("rsync:///mnt/external/minecraft-bkp")
        )
        assert address == "localhost:/mnt/external/minecraft-bkp"

    def test_no_hostname_parse(self, rsync_module):
        """Can't believe this is a valid URI"""
        address = rsync_module.uri_to_ssh(urlparse("rsync://nugget@/home/nugget/"))
        assert address == "nugget@localhost:/home/nugget"


class TestFileIgnorePatternBuilder:
    def test_simple_match(self):
        assert file.ignore_patterns("hello")(
            "greetings", ("bonjour", "hello", "hellooooo")
        ) == {"hello"}

    def test_wildcard(self):
        assert file.ignore_patterns("hel*")(
            "responses", ("como sa va", "hello", "hell no", "help")
        ) == {"hello", "hell no", "help"}

    def test_multi_pattern_match(self):
        assert file.ignore_patterns("hel*", "bye")(
            "responses", ("hello", "goodbye", "hellooo", "bye")
        ) == {"hello", "hellooo", "bye"}

    def test_full_path_check(self):
        ignore = file.ignore_patterns(os.path.join("root", "branch"))
        assert (
            ignore("root", ("branch", "trunk")),
            ignore("trunk", ("branch", "leaf")),
        ) == ({"branch"}, set())

    def test_match_is_performed_on_the_end(self):
        ignore = file.ignore_patterns(os.path.join("root", "branch"), "leaf")
        assert (
            ignore(os.path.join("tree", "root"), ("branch", "trunk")),
            ignore("wind", ("leaf", "blows")),
        ) == ({"branch"}, {"leaf"})


class TestFileSync:
    protocol = "file"

    @pytest.fixture(autouse=True)
    def check_output_suppression(self, capfd):
        # teardown that helps me figure out where I need to add a -q flag
        yield
        assert capfd.readouterr().out == ""

    @pytest.fixture
    def remote(self, tmp_path, minecraft_root, home):
        utils.pre_populate_enderchest(
            minecraft_root / "EnderChest", *utils.TESTING_SHULKER_CONFIGS
        )

        local = gather.load_ender_chest(minecraft_root)
        local.sync_confirm_wait = False
        local.write_to_cfg(fs.ender_chest_config(minecraft_root))

        another_root = tmp_path / "not so remote"

        (another_root / "EnderChest").mkdir(parents=True)

        for folder_name, _ in utils.TESTING_SHULKER_CONFIGS[1:]:
            shutil.copytree(
                minecraft_root / "EnderChest" / folder_name,
                another_root / "EnderChest" / folder_name,
                symlinks=True,
            )

        (minecraft_root / "safe_keeping").mkdir()
        for folder_name, _ in utils.TESTING_SHULKER_CONFIGS[:-2]:
            shutil.copytree(
                minecraft_root / "EnderChest" / folder_name,
                minecraft_root / "safe_keeping" / folder_name,
                symlinks=True,
            )
        for folder_name, _ in utils.TESTING_SHULKER_CONFIGS[-2:]:
            shutil.move(
                minecraft_root / "EnderChest" / folder_name,
                minecraft_root / "safe_keeping" / folder_name,
            )

        utils.pre_populate_enderchest(
            another_root / "EnderChest", *utils.TESTING_SHULKER_CONFIGS[1:]
        )

        not_so_remote = gather.load_ender_chest(another_root)
        not_so_remote.name = "closer than you think"
        not_so_remote._uri = not_so_remote._uri._replace(scheme=self.protocol)
        not_so_remote.register_remote(local._uri)
        not_so_remote.register_remote("ipoac://yoursoul@birdhouse/minecraft")
        not_so_remote.write_to_cfg(another_root / "EnderChest" / "enderchest.cfg")

        (another_root / "chest monster" / "worlds" / "olam").mkdir(parents=True)
        (another_root / "chest monster" / "worlds" / "olam" / "level.dat").write_text(
            "dootdootdoot"
        )

        (another_root / "EnderChest" / "1.19" / "saves" / "olam").unlink()
        (another_root / "EnderChest" / "1.19" / "saves" / "olam").symlink_to(
            another_root / "chest monster" / "worlds" / "olam", target_is_directory=True
        )

        (another_root / "EnderChest" / "1.19" / ".bobby").mkdir(exist_ok=True)
        (another_root / "EnderChest" / "1.19" / ".bobby" / "chunk").write_text(
            "chunky\n"
        )

        for root in (minecraft_root, another_root):
            (root / "EnderChest" / "vanilla" / "conflict").mkdir()

        (
            minecraft_root / "EnderChest" / "vanilla" / "conflict" / "diamond.png"
        ).write_text("sparkle")
        (
            another_root / "EnderChest" / "vanilla" / "conflict" / "diamond.png"
        ).write_text("lab-grown!")

        (another_root / "EnderChest" / "optifine" / "mods").mkdir(
            parents=True, exist_ok=True
        )
        (another_root / "EnderChest" / "optifine" / "mods" / "optifine.jar").write_text(
            "it's okay"
        )

        yield not_so_remote._uri

        assert (
            another_root / "chest monster" / "worlds" / "olam" / "level.dat"
        ).read_text() == "dootdootdoot"

        # now put everything local back the way it was supposed to be before
        # the conftest teardown freaks out

        for folder_name, _ in utils.TESTING_SHULKER_CONFIGS:
            shutil.move(
                minecraft_root / "safe_keeping" / folder_name,
                minecraft_root / "EnderChest" / folder_name,
            )

        # and then I apparently still need to redo some symlinks?
        for path, target in (
            (
                minecraft_root / "EnderChest" / "global" / "crash-reports",
                minecraft_root / "crash-reports",
            ),
            (
                minecraft_root / "EnderChest" / "global" / "resourcepacks",
                minecraft_root / "resourcepacks",
            ),
            (
                minecraft_root / "EnderChest" / "global" / "screenshots",
                home / "Pictures" / "Screenshots",
            ),
            (
                minecraft_root / "EnderChest" / "global" / "saves" / "test",
                minecraft_root / "worlds" / "testbench",
            ),
            (
                minecraft_root / "EnderChest" / "1.19" / "saves" / "olam",
                minecraft_root / "worlds" / "olam",
            ),
        ):
            path.unlink(missing_ok=True)
            path.symlink_to(target, target_is_directory=target.is_dir())

    @pytest.mark.parametrize("root_type", ("absolute", "relative"))
    def test_create_from_remote_chest(
        self, remote, minecraft_root, monkeypatch, root_type, capfd
    ):
        if root_type == "absolute":
            root = minecraft_root
        else:
            root = Path(minecraft_root.name)
            monkeypatch.chdir(minecraft_root.parent)

        craft.craft_ender_chest(root, copy_from=remote.geturl(), overwrite=True)

        assert gather.load_ender_chest_remotes(minecraft_root) == [
            (remote, "closer than you think"),
            (urlparse("ipoac://yoursoul@birdhouse/minecraft"), "birdhouse"),
        ]

        # test that the enderchest spec-fetch is quiet by default
        assert capfd.readouterr().out == ""

    @pytest.mark.parametrize("root_type", ("absolute", "relative"))
    def test_open_grabs_files_from_upstream(
        self, minecraft_root, remote, monkeypatch, root_type
    ):
        if root_type == "absolute":
            root = minecraft_root
        else:
            root = Path(minecraft_root.name)
            monkeypatch.chdir(minecraft_root.parent)

        gather.update_ender_chest(root, remotes=(remote,))
        r.sync_with_remotes(root, "pull", verbosity=-1)
        assert (
            minecraft_root / "EnderChest" / "optifine" / "mods" / "optifine.jar"
        ).read_text() == "it's okay"
        assert not (
            minecraft_root / "EnderChest" / "optifine" / "mods" / "optifine.jar"
        ).is_symlink()

    def test_open_dry_run_does_nothing(self, minecraft_root, remote):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "pull", dry_run=True)
        assert not (
            minecraft_root / "EnderChest" / "optifine" / "mods" / "optifine.jar"
        ).exists()

    def test_open_overwrites_local_files(self, minecraft_root, remote):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "pull", verbosity=-1)
        assert (
            minecraft_root / "EnderChest" / "vanilla" / "conflict" / "diamond.png"
        ).read_text() == "lab-grown!"
        assert not (
            minecraft_root / "EnderChest" / "vanilla" / "conflict" / "diamond.png"
        ).is_symlink()

    def test_open_copies_over_symlinks(self, minecraft_root, remote):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "pull", verbosity=-1)
        assert (
            minecraft_root / "EnderChest" / "1.19" / "saves" / "olam"
        ).resolve() != (minecraft_root / "worlds" / "olam")

    def test_open_processes_deletions_from_upstream(self, minecraft_root, remote):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "pull", verbosity=-1)
        assert not (minecraft_root / "EnderChest" / "global").exists()

    def test_open_does_not_overwrite_enderchest_by_default(
        self, minecraft_root, remote
    ):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        original_config = fs.ender_chest_config(minecraft_root).read_text()
        r.sync_with_remotes(minecraft_root, "pull", verbosity=-1)
        assert original_config == fs.ender_chest_config(minecraft_root).read_text()

    def test_open_not_touch_top_level_dot_folders_by_default(
        self, minecraft_root, remote
    ):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "pull", verbosity=-1)
        assert (
            minecraft_root / "EnderChest" / ".git" / "log"
        ).read_text() == "i committed some stuff\n"

    def test_open_will_sync_dot_folders_within_a_shulker_box(
        self, minecraft_root, remote
    ):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "pull", verbosity=-1)
        assert (
            minecraft_root / "EnderChest" / "1.19" / ".bobby" / "chunk"
        ).read_text() == "chunky\n"

    @pytest.mark.parametrize("root_type", ("absolute", "relative"))
    def test_close_overwrites_with_changes_from_local(
        self, minecraft_root, remote, monkeypatch, root_type
    ):
        if root_type == "absolute":
            root = minecraft_root
        else:
            root = Path(minecraft_root.name)
            monkeypatch.chdir(minecraft_root.parent)

        gather.update_ender_chest(root, remotes=(remote,))
        r.sync_with_remotes(root, "push", verbosity=-1)
        assert (
            path_from_uri(remote)
            / "EnderChest"
            / "vanilla"
            / "conflict"
            / "diamond.png"
        ).read_text() == "sparkle"

    def test_close_dry_run_does_nothing(self, minecraft_root, remote):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "push", dry_run=True)
        assert (
            path_from_uri(remote)
            / "EnderChest"
            / "vanilla"
            / "conflict"
            / "diamond.png"
        ).read_text() == "lab-grown!"

    def test_close_deletes_remote_copies_when_locals_are_deleted(
        self, minecraft_root, remote
    ):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "push", verbosity=-1)
        assert not (path_from_uri(remote) / "EnderChest" / "optifine").exists()

    def test_close_not_touch_top_level_dot_folders_by_default(
        self, minecraft_root, remote
    ):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "push", verbosity=-1)
        assert not (path_from_uri(remote) / "EnderChest" / ".git").exists()

    def test_chest_obeys_its_own_ignore_list(self, minecraft_root, remote):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))

        chest = gather.load_ender_chest(minecraft_root)
        chest.do_not_sync = ["EnderChest/enderchest.cfg"]
        chest.write_to_cfg(fs.ender_chest_config(minecraft_root))

        r.sync_with_remotes(minecraft_root, "push", verbosity=-1)
        assert (
            path_from_uri(remote) / "EnderChest" / ".git" / "log"
        ).read_text() == "i committed some stuff\n"

    def test_open_stops_at_first_successful_sync(self, minecraft_root, remote, caplog):
        gather.update_ender_chest(
            minecraft_root, remotes=(remote, "prayer://unreachable")
        )
        r.sync_with_remotes(minecraft_root, "pull", verbosity=-1)
        warnings = [
            record.msg for record in caplog.records if record.levelname == "WARNING"
        ]

        assert len(warnings) == 0

    def test_close_will_attempt_to_push_to_all(self, minecraft_root, remote, caplog):
        gather.update_ender_chest(
            minecraft_root, remotes=(remote, "prayer://unreachable")
        )
        r.sync_with_remotes(minecraft_root, "push", verbosity=-1)
        warnings = [
            record.msg for record in caplog.records if record.levelname == "WARNING"
        ]

        assert len(warnings) == 1
        assert "Could not sync changes with prayer://unreachable" in warnings[0]


@pytest.mark.xfail(
    not shutil.which("rsync"), reason="rsync is not installed on this system"
)
class TestRsyncSync(TestFileSync):
    protocol = "rsync"

    def test_rsync_summary_summarizes_at_the_shulker_box_level(
        self, minecraft_root, remote, caplog
    ):
        caplog.set_level(logging.DEBUG)
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "pull", dry_run=True)
        info_log = ""
        debug_log = ""
        for record in caplog.records:
            if record.levelname == "INFO":
                info_log += record.msg % record.args + "\n"
            elif record.levelname == "DEBUG":
                debug_log += record.msg % record.args + "\n"

        # meta-test--make sure that the creation is actually happening
        assert (
            "+++ " + os.path.sep.join(("EnderChest", "1.19", ".bobby", "chunk"))
            in debug_log
        )

        # meta-test--make sure nothing in the report at the shulker+1 level
        assert os.path.sep.join(("EnderChest", "1.19", ".bobby")) not in info_log

        assert (
            f"Within EnderChest{os.path.sep}1.19..."
            "\n  - Creating 1 file"
            "\n  - Updating 1 file"  # there's also the save symlink
            "\n  - Deleting 0 files"
        ) in info_log

    def test_rsync_summary_doesnt_report_details_if_the_whole_shulker_is_being_created(
        self, minecraft_root, remote, caplog
    ):
        caplog.set_level(logging.DEBUG)
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "pull", dry_run=True)
        info_log = ""
        debug_log = ""
        for record in caplog.records:
            if record.levelname == "INFO":
                info_log += record.msg + "\n"
            elif record.levelname == "DEBUG":
                debug_log += record.msg + "\n"

        # meta-test--make sure that the creation is actually happening
        assert (
            "+++ "
            + os.path.sep.join(("EnderChest", "optifine", "mods", "optifine.jar"))
            in debug_log
        )

        # meta-test--make sure nothing in the report at the shulker+1 level
        assert os.path.sep.join(("EnderChest", "optifine", "mods")) not in info_log

        assert f"Creating EnderChest{os.path.sep}optifine" in info_log

    @pytest.mark.parametrize("verbosity", ("v", "vv", "vvv"))
    @pytest.mark.parametrize("op", ("pull", "push"))
    def test_verbose_dry_run_doesnt_summarize(
        self, monkeypatch, minecraft_root, remote, caplog, op, verbosity
    ):
        def mock_summarize(*args, **kwargs):
            raise AssertionError("I was not to be called")

        from enderchest.sync import rsync

        monkeypatch.setattr(rsync, "summarize_rsync_report", mock_summarize)

        caplog.set_level(logging.DEBUG)
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, op, dry_run=True, verbosity=len(verbosity))

        debug_log = "\n".join(
            record.msg for record in caplog.records if record.levelname == "DEBUG"
        )

        # this wouldn't be in the summary
        assert f"EnderChest{os.sep}global{os.sep}config" in debug_log

    @pytest.mark.parametrize("op", ("pull", "push"))
    def test_quiet_dry_run_still_reports_stats(
        self, minecraft_root, remote, caplog, op
    ):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, op, dry_run=True, verbosity=-1)

        printed_log = "\n".join(
            record.msg for record in caplog.records if record.levelno > logging.INFO
        )

        assert "Number of created files" in printed_log

    @pytest.mark.parametrize("op", ("pull", "push"))
    def test_super_quiet_dry_run_still_reports_stats(
        self, minecraft_root, remote, caplog, op
    ):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, op, dry_run=True, verbosity=-1)

        printed_log = "\n".join(
            record.msg for record in caplog.records if record.levelno > logging.INFO
        )

        assert "Number of created files" in printed_log

    @pytest.mark.parametrize("op", ("pull", "push"))
    def test_regular_sync_only_reports_overall_progress(
        self, minecraft_root, remote, capfd, op
    ):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, op)

        printed_log = capfd.readouterr().out

        assert f"EnderChest{os.sep}global" not in printed_log

        # but, like, make sure that it prints *something*
        assert "Number of created files" in printed_log

    @pytest.mark.parametrize("verbosity", ("v", "vv", "vvv"))
    @pytest.mark.parametrize("op", ("pull", "push"))
    def test_verbose_sync_reports_file_level_progress(
        self, minecraft_root, remote, capfd, op, verbosity
    ):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, op, verbosity=len(verbosity))

        printed_log = capfd.readouterr().out

        assert f"EnderChest{os.sep}global" in printed_log
        assert "xfr#2, to-chk=" in printed_log

    @pytest.mark.parametrize("quietude", ("q", "qq", "qqq"))
    @pytest.mark.parametrize("op", ("pull", "push"))
    def test_quiet_sync_is_silent(self, minecraft_root, remote, capfd, op, quietude):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, op, verbosity=-len(quietude))

        printed_log = capfd.readouterr().out

        assert printed_log == ""
