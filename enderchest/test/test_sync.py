"""Tests around file transfer functionality."""
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

    def test_create_from_remote_chest(self, remote, minecraft_root):
        craft.craft_ender_chest(
            minecraft_root, copy_from=remote.geturl(), overwrite=True
        )

        assert gather.load_ender_chest_remotes(minecraft_root) == [
            (remote, "closer than you think"),
            (urlparse("ipoac://yoursoul@birdhouse/minecraft"), "birdhouse"),
        ]

    def test_open_grabs_files_from_upstream(self, minecraft_root, remote):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "pull")
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
        r.sync_with_remotes(minecraft_root, "pull")
        assert (
            minecraft_root / "EnderChest" / "vanilla" / "conflict" / "diamond.png"
        ).read_text() == "lab-grown!"
        assert not (
            minecraft_root / "EnderChest" / "vanilla" / "conflict" / "diamond.png"
        ).is_symlink()

    def test_open_copies_over_symlinks(self, minecraft_root, remote):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "pull")
        assert (
            minecraft_root / "EnderChest" / "1.19" / "saves" / "olam"
        ).resolve() != (minecraft_root / "worlds" / "olam")

    def test_open_processes_deletions_from_upstream(self, minecraft_root, remote):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "pull")
        assert not (minecraft_root / "EnderChest" / "global").exists()

    def test_open_does_not_overwrite_enderchest(self, minecraft_root, remote):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        original_config = fs.ender_chest_config(minecraft_root).read_text()
        r.sync_with_remotes(minecraft_root, "pull")
        assert original_config == fs.ender_chest_config(minecraft_root).read_text()

    def test_open_not_touch_top_level_dot_folders(self, minecraft_root, remote):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "pull")
        assert (
            minecraft_root / "EnderChest" / ".git" / "log"
        ).read_text() == "i committed some stuff\n"

    def test_open_will_sync_dot_folders_within_a_shulker_box(
        self, minecraft_root, remote
    ):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "pull")
        assert (
            minecraft_root / "EnderChest" / "1.19" / ".bobby" / "chunk"
        ).read_text() == "chunky\n"

    def test_close_overwrites_with_changes_from_local(self, minecraft_root, remote):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "push")
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
        r.sync_with_remotes(minecraft_root, "push")
        assert not (path_from_uri(remote) / "EnderChest" / "optifine").exists()

    def test_open_stops_at_first_successful_sync(self, minecraft_root, remote, caplog):
        gather.update_ender_chest(
            minecraft_root, remotes=(remote, "prayer://unreachable")
        )
        r.sync_with_remotes(minecraft_root, "pull")
        warnings = [
            record.msg for record in caplog.records if record.levelname == "WARNING"
        ]

        assert len(warnings) == 0

    def test_close_will_attempt_to_push_to_all(self, minecraft_root, remote, caplog):
        gather.update_ender_chest(
            minecraft_root, remotes=(remote, "prayer://unreachable")
        )
        r.sync_with_remotes(minecraft_root, "push")
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
