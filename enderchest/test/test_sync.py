"""Tests around file transfer functionality"""

import itertools
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
from importlib.resources import as_file
from pathlib import Path
from urllib.parse import ParseResult, urlparse

import pytest

from enderchest import craft
from enderchest import filesystem as fs
from enderchest import gather, place
from enderchest import remote as r
from enderchest import sync
from enderchest.sync import utils as sync_utils

from . import mock_paramiko, utils
from .testing_files import LSTAT_CACHE


@pytest.fixture(autouse=True)
def force_hostname_to_be_localhost(monkeypatch):
    if sys.platform == "darwin":  # so far this is only needed for macOS
        monkeypatch.setattr(socket, "gethostname", lambda: "localhost")


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

        (minecraft_root / "EnderChest" / "1.19" / "resourcepacks").mkdir()
        (another_root / "EnderChest" / "1.19" / "resourcepacks").mkdir()
        (
            minecraft_root
            / "EnderChest"
            / "1.19"
            / "resourcepacks"
            / "TEAVSRP_lite.zip"
        ).write_text("I am haggling you\n")
        shutil.copy2(
            (
                minecraft_root
                / "EnderChest"
                / "1.19"
                / "resourcepacks"
                / "TEAVSRP_lite.zip"
            ),
            (
                another_root
                / "EnderChest"
                / "1.19"
                / "resourcepacks"
                / "TEAVSRP_lite.zip"
            ),
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

    @pytest.mark.parametrize("delete", (True, False), ids=("default", "do-not-delete"))
    def test_open_respects_delete_kwarg_when_processing_deletions_from_upstream(
        self, minecraft_root, remote, delete
    ):
        sync_kwargs = {"verbosity": -1}
        if not delete:
            sync_kwargs["delete"] = False
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "pull", **sync_kwargs)
        assert not (minecraft_root / "EnderChest" / "global").exists() == delete

    def test_open_does_not_overwrite_enderchest_by_default(
        self, minecraft_root, remote
    ):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        original_config = fs.ender_chest_config(minecraft_root).read_text()
        r.sync_with_remotes(minecraft_root, "pull", verbosity=-1)
        assert original_config == fs.ender_chest_config(minecraft_root).read_text()

    def test_open_does_not_touch_top_level_dot_folders_by_default(
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

    @pytest.mark.parametrize(
        "dry_run, place_after",
        (
            (False, False),
            (False, True),
            # no point in testing dry-run-False
            (True, True),
        ),
        ids=("False", "True", "dry-run"),
    )
    def test_place_after_open(self, minecraft_root, remote, dry_run, place_after):
        test_path = (
            minecraft_root
            / "instances"
            / "axolotl"
            / ".minecraft"
            / "conflict"
            / "diamond.png"
        )

        # meta-test
        place.place_ender_chest(minecraft_root)
        assert test_path.read_text("utf-8") == "sparkle"

        enderchest = gather.load_ender_chest(minecraft_root)
        enderchest.register_remote(remote, alias="not so remote")
        enderchest.place_after_open = place_after
        enderchest.write_to_cfg(fs.ender_chest_config(minecraft_root))

        r.sync_with_remotes(minecraft_root, "pull", dry_run=dry_run, verbosity=-1)
        assert (
            test_path.read_text("utf-8") == "lab-grown!"
            if place_after and not dry_run
            else "sparkle"
        )

    @pytest.mark.parametrize("fail_type", ("no_remotes", "bad_remotes"))
    def test_does_not_place_after_failed_open(
        self, minecraft_root, remote, fail_type, caplog
    ):
        # TODO: move this into TestFileSyncOnly as there is no value in testing
        #       this for multiple protocols

        test_path = (
            minecraft_root
            / "instances"
            / "axolotl"
            / ".minecraft"
            / "conflict"
            / "diamond.png"
        )
        enderchest = gather.load_ender_chest(minecraft_root)
        if fail_type == "bad_remotes":
            enderchest.register_remote("file://i/do/not/exist", "does not exist")
        enderchest.place_after_open = True
        enderchest.write_to_cfg(fs.ender_chest_config(minecraft_root))

        r.sync_with_remotes(minecraft_root, "pull", verbosity=-1)

        failure_messages = {
            "no_remotes": "EnderChest has no remotes. Aborting.",
            "bad_remotes": "Could not sync with any remote EnderChests",
        }

        assert [  # meta-test
            record.msg for record in caplog.records if record.levelno == logging.ERROR
        ] == [failure_messages[fail_type]]

        assert not test_path.exists()

    def test_does_not_place_after_dry_run(self, minecraft_root, remote, caplog):
        # TODO: move this into TestFileSyncOnly as there is no value in testing
        #       this for multiple protocols

        test_path = (
            minecraft_root
            / "instances"
            / "axolotl"
            / ".minecraft"
            / "conflict"
            / "diamond.png"
        )
        enderchest = gather.load_ender_chest(minecraft_root)
        enderchest.register_remote(remote, alias="not so remote")
        enderchest.place_after_open = True
        enderchest.write_to_cfg(fs.ender_chest_config(minecraft_root))

        r.sync_with_remotes(minecraft_root, "pull", verbosity=-1, dry_run=True)

        assert not test_path.exists()

    @pytest.mark.parametrize("operation", ("pull", "push"))
    def test_timeout_argument_doesnt_obviously_break_(
        self, minecraft_root, remote, operation
    ):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, operation, verbosity=-1, timeout=15)

    @pytest.mark.parametrize("operation", ("pull", "push"))
    def test_identical_objects_are_not_synced(
        self, minecraft_root, remote, caplog, operation
    ):
        caplog.set_level(logging.DEBUG)
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, operation, verbosity=-1)
        debug_logs = [
            record.msg % record.args
            for record in caplog.records
            if record.levelno == logging.DEBUG
        ]
        assert debug_logs  # meta-test
        assert not [message for message in debug_logs if "TEAVSRP_lite.zip" in message]

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
            sync.abspath_from_uri(remote)
            / "EnderChest"
            / "vanilla"
            / "conflict"
            / "diamond.png"
        ).read_text() == "sparkle"

    @pytest.mark.parametrize("operation", ("pull", "push"))
    def test_objects_are_identical_after_sync(
        self, minecraft_root, remote, caplog, operation
    ):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        time.sleep(1)  # ugh
        r.sync_with_remotes(minecraft_root, operation, verbosity=-1)
        assert sync_utils.is_identical(
            (
                minecraft_root / "EnderChest" / "vanilla" / "conflict" / "diamond.png"
            ).stat(),
            (
                sync.abspath_from_uri(remote)
                / "EnderChest"
                / "vanilla"
                / "conflict"
                / "diamond.png"
            ).stat(),
        )

    def test_close_dry_run_does_nothing(self, minecraft_root, remote):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "push", dry_run=True)
        assert (
            sync.abspath_from_uri(remote)
            / "EnderChest"
            / "vanilla"
            / "conflict"
            / "diamond.png"
        ).read_text() == "lab-grown!"

    @pytest.mark.parametrize("delete", (True, False), ids=("default", "do-not-delete"))
    def test_close_respects_delete_kwarg_remote_copies_when_locals_are_deleted(
        self,
        minecraft_root,
        remote,
        delete,
    ):
        sync_kwargs = {"verbosity": -1}
        if not delete:
            sync_kwargs["delete"] = False
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "push", **sync_kwargs)
        assert (
            not (sync.abspath_from_uri(remote) / "EnderChest" / "optifine").exists()
            == delete
        )

    def test_close_does_not_touch_top_level_dot_folders_by_default(
        self, minecraft_root, remote
    ):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))
        r.sync_with_remotes(minecraft_root, "push", verbosity=-1)
        assert not (sync.abspath_from_uri(remote) / "EnderChest" / ".git").exists()

    def test_chest_obeys_its_own_ignore_list(self, minecraft_root, remote):
        gather.update_ender_chest(minecraft_root, remotes=(remote,))

        chest = gather.load_ender_chest(minecraft_root)
        chest.do_not_sync = ["EnderChest/enderchest.cfg"]
        chest.write_to_cfg(fs.ender_chest_config(minecraft_root))

        r.sync_with_remotes(minecraft_root, "push", verbosity=-1)
        assert (
            sync.abspath_from_uri(remote) / "EnderChest" / ".git" / "log"
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

    def test_never_places_after_close(self, minecraft_root, remote):
        test_path = (
            minecraft_root
            / "instances"
            / "bee"
            / ".minecraft"
            / "mods"
            / "optifine.jar"
        )

        enderchest = gather.load_ender_chest(minecraft_root)
        enderchest.register_remote(remote, alias="not so remote")
        enderchest.place_after_open = True
        enderchest.write_to_cfg(fs.ender_chest_config(minecraft_root))

        r.sync_with_remotes(minecraft_root, "push", verbosity=-1)
        assert not test_path.exists()

    @pytest.mark.parametrize(
        "operation, mode",
        itertools.product(("pull", "push"), ("immediate", "dry_run_first")),
    )
    def test_sync_respects_exclude(
        self, minecraft_root, remote, caplog, operation, mode
    ):
        sync_confirm_wait = 1 if mode == "dry_run_first" else 0
        gather.update_ender_chest(minecraft_root, remotes=(remote,))

        r.sync_with_remotes(
            minecraft_root,
            operation,
            verbosity=-1,
            sync_confirm_wait=sync_confirm_wait,
            exclude="*/diamond.png",
        )
        assert (
            minecraft_root / "EnderChest" / "vanilla" / "conflict" / "diamond.png"
        ).read_text() != (
            sync.abspath_from_uri(remote)
            / "EnderChest"
            / "vanilla"
            / "conflict"
            / "diamond.png"
        ).read_text()

    ############################################################################
    # low-level tests                                                          #
    ############################################################################

    def test_reading_the_target_of_a_remote_symlink(self, remote):
        address = remote._replace(
            path=urlparse(
                (
                    sync.abspath_from_uri(remote)
                    / "EnderChest"
                    / "optifine"
                    / "mods"
                    / "BME.jar"
                ).as_uri()
            ).path,
        )
        with sync.remote_file(address) as remote_link:
            assert remote_link.readlink().name == "BME_1.19.2_nightly.jar"

    @pytest.mark.parametrize("target_type", ("file", "symlink", "nothing"))
    def test_pull_replaces_existing_(self, target_type, remote, tmp_path):
        remote_chest = remote._replace(
            path=urlparse((sync.abspath_from_uri(remote) / "EnderChest").as_uri()).path,
        )
        local_path = tmp_path / "somewhere_else" / "EnderChest"
        local_path.parent.mkdir(parents=True)
        if target_type == "file":
            local_path.write_text("Leave me alone!\n")
        elif target_type == "symlink":
            # shouldn't need to exist
            local_path.symlink_to(tmp_path / "aether", target_is_directory=False)

        sync.pull(remote_chest, local_path.parent, verbosity=-1)
        assert (local_path / "enderchest.cfg").exists()

    @pytest.mark.parametrize("target_type", ("file", "symlink"))
    def test_pull_dry_run_does_not_replace_existing_(
        self, target_type, remote, tmp_path
    ):
        remote_chest = remote._replace(
            path=urlparse((sync.abspath_from_uri(remote) / "EnderChest").as_uri()).path,
        )
        local_path = tmp_path / "somewhere_else" / "EnderChest"
        local_path.parent.mkdir(parents=True)
        if target_type == "file":
            local_path.write_text("Leave me alone!\n")
        elif target_type == "symlink":
            # shouldn't need to exist
            local_path.symlink_to(tmp_path / "aether", target_is_directory=False)

        sync.pull(remote_chest, local_path.parent, verbosity=-1, dry_run=True)
        if target_type == "file":
            assert local_path.read_text("UTF-8") == "Leave me alone!\n"
        elif target_type == "symlink":
            assert local_path.readlink().name == "aether"
        else:
            assert not local_path.exists()

    def test_pull_fails_if_local_parent_folder_does_not_exist(self, remote):
        remote_chest = remote._replace(
            path=urlparse((sync.abspath_from_uri(remote) / "EnderChest").as_uri()).path,
        )
        local_path = Path("i do not exist")

        with pytest.raises(FileNotFoundError):
            sync.pull(remote_chest, local_path)

    def test_pull_fails_if_remote_does_not_exist(self, tmp_path):
        local_path = tmp_path / "i do not exist" / "wait yes i do"
        local_path.parent.mkdir(parents=True)
        local_path.touch()

        remote_path = Path("i do not exist")
        remote = ParseResult(
            scheme=self.protocol,
            netloc=sync.get_default_netloc(),
            path=urlparse(remote_path.absolute().as_uri()).path,
            params="",
            query="",
            fragment="",
        )
        with pytest.raises(FileNotFoundError):
            sync.pull(remote, local_path.parent.parent, verbosity=-1)

        assert local_path.exists()

    @pytest.mark.parametrize("target_type", ("file", "symlink", "nothing"))
    def test_push_replaces_existing_(self, target_type, minecraft_root, tmp_path):
        remote_path = tmp_path / "somewhere_else" / "EnderChest"
        remote_path.parent.mkdir(parents=True)
        if target_type == "file":
            remote_path.write_text("Leave me alone!\n")
        elif target_type == "symlink":
            # shouldn't need to exist
            remote_path.symlink_to(tmp_path / "aether", target_is_directory=False)

        remote = ParseResult(
            scheme=self.protocol,
            netloc=sync.get_default_netloc(),
            path=urlparse(remote_path.absolute().parent.as_uri()).path,
            params="",
            query="",
            fragment="",
        )

        sync.push(minecraft_root / "EnderChest", remote, verbosity=-1)

        assert (remote_path / "global" / "usercache.json").exists()

    @pytest.mark.parametrize("target_type", ("file", "symlink", "nothing"))
    def test_push_dry_run_does_not_replace_existing_(
        self, target_type, minecraft_root, tmp_path
    ):
        remote_path = tmp_path / "somewhere_else" / "EnderChest"
        remote_path.parent.mkdir(parents=True)
        if target_type == "file":
            remote_path.write_text("Leave me alone!\n")
        elif target_type == "symlink":
            # shouldn't need to exist
            remote_path.symlink_to(tmp_path / "aether", target_is_directory=False)

        remote = ParseResult(
            scheme=self.protocol,
            netloc=sync.get_default_netloc(),
            path=urlparse(remote_path.absolute().parent.as_uri()).path,
            params="",
            query="",
            fragment="",
        )

        sync.push(minecraft_root / "EnderChest", remote, verbosity=-1, dry_run=True)

        if target_type == "file":
            assert remote_path.read_text("utf-8") == "Leave me alone!\n"
        elif target_type == "symlink":
            assert remote_path.readlink().name == "aether"
        else:
            assert not remote_path.exists()

    def test_push_fails_if_local_does_not_exist(self, tmp_path):
        remote_path = tmp_path / "i do not exist" / "wait yes i do"
        remote_path.parent.mkdir(parents=True)
        remote_path.touch()

        local_path = Path("i do not exist")
        remote = ParseResult(
            scheme=self.protocol,
            netloc=sync.get_default_netloc(),
            path=urlparse(remote_path.absolute().parent.parent.as_uri()).path,
            params="",
            query="",
            fragment="",
        )
        with pytest.raises(FileNotFoundError):
            sync.push(local_path, remote, verbosity=-1)

        assert remote_path.exists()


class TestFileSyncOnly:
    def test_push_fails_if_remote_parent_folder_does_not_exist(self, minecraft_root):
        remote_path = Path("i do not exist").absolute()
        remote = urlparse(remote_path.as_uri())

        with pytest.raises(FileNotFoundError):
            sync.push(minecraft_root / "EnderChest", remote)


@pytest.mark.skipif(
    not shutil.which("rsync"), reason="rsync module cannot be imported on this system"
)
class TestRsyncVersionChecking:
    class FakeSubprocessResult:
        def __init__(self, stdout: str, stderr: str):
            self.stdout = stdout.encode("utf-8")
            self.stderr = stderr.encode("utf-8")

    def test_raises_runtime_error_if_rsync_is_not_installed(self, monkeypatch):
        from enderchest.sync import rsync

        original_run = subprocess.run

        def run_something_else(commands, **kwargs) -> subprocess.CompletedProcess:
            return original_run(["adsqwcvqawf"], **kwargs)

        monkeypatch.setattr(subprocess, "run", run_something_else)

        with pytest.raises(RuntimeError, match="is not installed"):
            _ = rsync._get_rsync_version()

    def test_raises_runtime_error_if_rsync_v_produces_error_message(
        self, monkeypatch
    ) -> None:
        from enderchest.sync import rsync

        def mock_run(
            commands, **kwargs
        ) -> TestRsyncVersionChecking.FakeSubprocessResult:
            return TestRsyncVersionChecking.FakeSubprocessResult(
                "irrelephant", "Something bad!!"
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        with pytest.raises(RuntimeError, match="Something bad!!"):
            _ = rsync._get_rsync_version()

    def test_raises_runtime_error_if_rsync_v_produces_no_output(
        self, monkeypatch
    ) -> None:
        from enderchest.sync import rsync

        def mock_run(
            commands, **kwargs
        ) -> TestRsyncVersionChecking.FakeSubprocessResult:
            return TestRsyncVersionChecking.FakeSubprocessResult("", "")

        monkeypatch.setattr(subprocess, "run", mock_run)

        with pytest.raises(RuntimeError, match="could not be executed"):
            _ = rsync._get_rsync_version()

    def test_raises_runtime_error_if_head_doesnt_match_regex(self, monkeypatch) -> None:
        from enderchest.sync import rsync

        def mock_run(
            commands, **kwargs
        ) -> TestRsyncVersionChecking.FakeSubprocessResult:
            return TestRsyncVersionChecking.FakeSubprocessResult(
                "rsync is totally installed on this system", ""
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        with pytest.raises(RuntimeError, match="Could not parse version output"):
            _ = rsync._get_rsync_version()

    def test_correctly_parses_version_string(self, monkeypatch) -> None:
        from enderchest.sync import rsync

        def mock_run(
            commands, **kwargs
        ) -> TestRsyncVersionChecking.FakeSubprocessResult:
            return TestRsyncVersionChecking.FakeSubprocessResult(
                "rsync  version 1.20.78163  protocol version whateva", ""
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        assert rsync._get_rsync_version() == (1, 20)


@pytest.mark.skipif(
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


def _is_paramiko_installed() -> bool:
    try:
        import paramiko

        return True
    except ImportError:
        return False


PARAMIKO_INSTALLED = _is_paramiko_installed()


@pytest.mark.skipif(
    not PARAMIKO_INSTALLED, reason="EnderChest was not installed with SFTP support"
)
class TestSFTPSync(TestFileSync):
    protocol = "sftp"

    @pytest.fixture(autouse=True)
    def patch_paramiko(self, remote, monkeypatch, use_local_ssh):
        if not use_local_ssh:
            from enderchest.sync import sftp

            mock_sftp = mock_paramiko.MockSFTP(
                sync.abspath_from_uri(remote) / "EnderChest"
            )

            monkeypatch.setattr(
                sftp, "connect", mock_paramiko.generate_mock_connect(mock_sftp)
            )
            monkeypatch.setattr(sftp, "rglob", mock_paramiko.mock_rglob)

    @pytest.fixture(autouse=False)
    def generate_lstat_cache(self, remote):
        from enderchest.sync import sftp

        with sftp.connect(remote) as sftp_client:
            stats = sftp.get_contents(
                sftp_client, (sync.abspath_from_uri(remote) / "EnderChest").as_posix()
            )

        for path, sftp_attr in stats:
            sftp_attr.filename = path.as_posix()
        with as_file(LSTAT_CACHE) as cache_file:
            cache_file.write_text(
                json.dumps(
                    [
                        {
                            field: getattr(sftp_attr, field)
                            for field in mock_paramiko.CachedStat._fields
                        }
                        for path, sftp_attr in stats
                    ],
                    indent=4,
                )
            )

    # @pytest.mark.usefixtures("generate_lstat_cache")
    # def test_generate_lstat_cache(self):
    #     """Force cache gen, but just do it once"""
    #     pass

    def test_push_fails_if_remote_parent_folder_does_not_exist(self, minecraft_root):
        remote_path = Path("i do not exist").absolute()
        remote = ParseResult(
            scheme=self.protocol,
            netloc=sync.get_default_netloc(),
            path=urlparse(remote_path.absolute().as_uri()).path,
            params="",
            query="",
            fragment="",
        )
        with pytest.raises(FileNotFoundError):
            sync.push(minecraft_root / "EnderChest", remote)
