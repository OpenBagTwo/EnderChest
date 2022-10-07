"""Test functionality around rsync script generation"""
import os
import shutil
import sys
from pathlib import Path

import pytest

from enderchest import sync
from enderchest.cli import _run_bash
from enderchest.craft import craft_ender_chest
from enderchest.place import place_enderchest
from enderchest.sync import Remote, RemoteSync

remotes = (
    Remote("localhost", "~/minecraft", "openbagtwo", "Not Actually Remote"),
    Remote("8.8.8.8", "/root/minecraft", "sergey", "Not-Bing"),
    RemoteSync(
        Remote("spare-pi", "/opt/minecraft", "pi"),
        pre_open=[
            "wakeonlan bigmac",
            "ssh pi@sparepi"
            ' "cd /opt/minecraft/EnderChest'
            " && git add ."
            ' && git commit -m "Process local changes"',
        ],
        pre_close=["wakeonlan bigmac"],
        post_close=[
            "ssh pi@sparepi"
            ' "cd /opt/minecraft/EnderChest'
            " && git add ."
            ' && git commit -m "Process downstream changes"'
        ],
    ),
    Remote("steamdeck.local", "~/minecraft"),
)


class TestRemote:
    @pytest.mark.parametrize("remote", remotes)
    def test_remote_is_trivially_serializable(self, remote):
        remote_as_str = str(remote)
        remote_from_str = eval(remote_as_str)  # not that you should ever use eval

        assert remote == remote_from_str

    @pytest.mark.parametrize(
        "remote, expected",
        zip(
            remotes, ("Not Actually Remote", "Not-Bing", "spare-pi", "steamdeck.local")
        ),
    )
    def test_alias_fallback(self, remote, expected):
        if isinstance(remote, RemoteSync):
            remote = remote.remote
        assert remote.alias == expected

    @pytest.mark.parametrize(
        "remote, expected",
        zip(
            remotes,
            (
                "openbagtwo@localhost:~/minecraft",
                "sergey@8.8.8.8:/root/minecraft",
                "pi@spare-pi:/opt/minecraft",
                "steamdeck.local:~/minecraft",
            ),
        ),
    )
    def test_remote_folder(self, remote, expected):
        if isinstance(remote, RemoteSync):
            remote = remote.remote
        assert remote.remote_folder == expected


class TestCommandBuilding:
    def test_simple_mirror(self):
        yeet, yoink = sync._build_rsync_scripts(
            "~/minecraft", "this", Remote("there", "/home/me/minecraft", "me", "that")
        )

        assert (yeet.strip(), yoink.strip()) == (
            rf'''# sync changes from this EnderChest to that
rsync -az --delete \
    {Path.home().as_posix()}/minecraft/EnderChest/ \
    me@there:/home/me/minecraft/EnderChest/ \
    --exclude=".git" --exclude="local-only" --exclude="other-locals" \
    "$@"
# backup local settings to that
rsync -az --delete \
    {Path.home().as_posix()}/minecraft/EnderChest/local-only/ \
    me@there:/home/me/minecraft/EnderChest/other-locals/this \
    "$@"''',
            rf'''# sync changes from that to this EnderChest
rsync -az --delete \
    me@there:/home/me/minecraft/EnderChest/ \
    {Path.home().as_posix()}/minecraft/EnderChest/ \
    --exclude=".git" --exclude="local-only" --exclude="other-locals" \
    "$@"''',
        )

    def test_local_sync(self):
        yeet, yoink = sync._build_rsync_scripts(
            "~/minecraft", "local", Remote(None, "~/minecraft2", "me", "next door")
        )

        assert (yeet.strip(), yoink.strip()) == (
            rf'''# sync changes from this EnderChest to next door
rsync -az --delete \
    {Path.home().as_posix()}/minecraft/EnderChest/ \
    ~/minecraft2/EnderChest/ \
    --exclude=".git" --exclude="local-only" --exclude="other-locals" \
    "$@"
# backup local settings to next door
rsync -az --delete \
    {Path.home().as_posix()}/minecraft/EnderChest/local-only/ \
    ~/minecraft2/EnderChest/other-locals/local \
    "$@"''',
            rf'''# sync changes from next door to this EnderChest
rsync -az --delete \
    ~/minecraft2/EnderChest/ \
    {Path.home().as_posix()}/minecraft/EnderChest/ \
    --exclude=".git" --exclude="local-only" --exclude="other-locals" \
    "$@"''',
        )

    def test_escaping_special_characters(self):
        yeet, yoink = sync._build_rsync_scripts(
            "C Drive/Games (and other stuff)/minecr@ft",
            "source",
            Remote("faraway", 'maybe here?/definitely+not+"here"/$$$'),
        )
        cwd = Path(os.getcwd()).as_posix()
        assert (yeet.strip(), yoink.strip()) == (
            rf'''# sync changes from this EnderChest to faraway
rsync -az --delete \
    '{cwd}/C Drive/Games (and other stuff)/minecr@ft'/EnderChest/ \
    faraway:'maybe here?/definitely+not+"here"/$$$'/EnderChest/ \
    --exclude=".git" --exclude="local-only" --exclude="other-locals" \
    "$@"
# backup local settings to faraway
rsync -az --delete \
    '{cwd}/C Drive/Games (and other stuff)/minecr@ft'/EnderChest/local-only/ \
    faraway:'maybe here?/definitely+not+"here"/$$$'/EnderChest/other-locals/source \
    "$@"''',
            rf'''# sync changes from faraway to this EnderChest
rsync -az --delete \
    faraway:'maybe here?/definitely+not+"here"/$$$'/EnderChest/ \
    '{cwd}/C Drive/Games (and other stuff)/minecr@ft'/EnderChest/ \
    --exclude=".git" --exclude="local-only" --exclude="other-locals" \
    "$@"''',
        )


class TestScriptGeneration:

    # TODO: test that script generation expands ~ when generating local root

    @pytest.mark.parametrize("script", ("open.sh", "close.sh"))
    def test_link_to_other_chests_generates_executable_scripts(
        self, script, local_enderchest
    ):
        assert list((local_enderchest / "local-only").glob("*.sh")) == []

        sync.link_to_other_chests(local_enderchest / "..", *remotes)

        assert os.access(local_enderchest / "local-only" / script, os.X_OK)

    @pytest.mark.parametrize("script", ("open.sh", "close.sh"))
    def test_link_by_default_does_not_overwrite_scripts(self, script, local_enderchest):
        (local_enderchest / "local-only" / script).write_text("echo hello\n")

        with pytest.warns() as warning_log:
            sync.link_to_other_chests(local_enderchest / "..", *remotes)

        assert len(warning_log) == 1
        assert "skipping" in warning_log[0].message.args[0].lower()

        assert (local_enderchest / "local-only" / script).read_text() == "echo hello\n"

    def test_link_can_be_made_to_overwrite_scripts(self, local_enderchest):
        for script in ("open.sh", "close.sh"):
            (local_enderchest / "local-only" / script).write_text("echo hello\n")

        with pytest.warns() as warning_log:
            sync.link_to_other_chests(local_enderchest / "..", *remotes, overwrite=True)

        assert len(warning_log) == 2
        assert all(
            (
                "overwriting" in warning_message.message.args[0].lower()
                for warning_message in warning_log
            )
        )

        assert not any(
            (
                (local_enderchest / "local-only" / script).read_text() == "echo hello\n"
                for script in ("open.sh", "close.sh")
            )
        )

    @pytest.mark.parametrize("script", ("open.sh", "close.sh"))
    def test_scripts_just_scare_and_quit_by_default(self, script, local_enderchest):
        sync.link_to_other_chests(
            local_enderchest / ".."
        )  # no remotes means shouldn't do anything even if test fails

        script_path = local_enderchest / "local-only" / script
        with script_path.open("a") as script_file:
            script_file.write('echo "I should not be reachable"\n')

        result = _run_bash(
            local_enderchest,
            script_path,
            "--dry-run",  # out of an overabundance of caution)
            capture_output=True,
        )

        assert result.returncode == 1
        assert "DELETE AFTER READING" in result.stdout.decode()
        if script == "open.sh":
            assert "Could not pull changes" not in result.stdout.decode()
        assert "I should not be reachable" not in result.stdout.decode()

    @pytest.mark.parametrize("script", ("open.sh", "close.sh"))
    def test_yes_you_can_disable_the_scare_warning(self, script, local_enderchest):
        sync.link_to_other_chests(local_enderchest / "..", omit_scare_message=True)

        script_path = local_enderchest / "local-only" / script
        with script_path.open("a") as script_file:
            script_file.write('echo "You made it"\n')

        result = _run_bash(
            local_enderchest,
            script_path,
            "--dry-run",  # out of an overabundance of caution
            capture_output=True,
        )

        if script == "open.sh":
            assert result.returncode == 1
            assert "Could not pull changes" in result.stdout.decode()
        else:
            assert result.returncode == 0
            assert "You made it" in result.stdout.decode()


@pytest.mark.xfail(
    sys.platform.startswith("win"), reason="shlex is only guaranteed for posix"
)
class TestSyncing:
    """This is only going to cover syncing locally"""

    # TODO: add tests for rsync over ssh

    @pytest.fixture
    def remote(self, tmp_path, local_enderchest):
        another_root = tmp_path / "not-so-remote"
        craft_ender_chest(another_root)

        ender_chest = another_root / "EnderChest"

        shutil.copy(
            (local_enderchest / "client-only" / "resourcepacks" / "stuff.zip@axolotl"),
            (ender_chest / "client-only" / "resourcepacks" / "stuff.zip@axolotl"),
            follow_symlinks=False,
        )

        shutil.copy(
            (local_enderchest / "client-only" / "saves" / "olam@axolotl@bee@cow"),
            (ender_chest / "client-only" / "saves" / "olam@axolotl@bee@cow"),
            follow_symlinks=False,
        )

        for instance in ("axolotl", "bee", "cow"):
            shutil.copy(
                (local_enderchest / "global" / "mods" / f"BME.jar@{instance}"),
                (ender_chest / "global" / "mods" / f"BME.jar@{instance}"),
                follow_symlinks=False,
            )

        (another_root / "AnOkayMod.jar").write_bytes(b"beep")
        (ender_chest / "global" / "mods" / "AnOkayMod.jar@bee").symlink_to(
            (another_root / "AnOkayMod.jar")
        )

        (
            ender_chest
            / "local-only"
            / "shaderpacks"
            / "SildursMonochromeShaders.zip@axolotl@bee@cow@dolphin"
        ).touch()
        (ender_chest / "local-only" / "BME_indev.jar@axolotl").write_bytes(
            b"alltheboops"
        )
        (
            ender_chest / "client-only" / "config" / "pupil.properties@axolotl@bee@cow"
        ).write_text("dilated\n")

        yield Remote(None, ender_chest / "..", None, "behind_the_door")

        assert list(ender_chest.glob(".git")) == []
        assert (another_root / "AnOkayMod.jar").read_bytes() == b"beep"

    def test_open_grabs_changes_from_upstream(self, local_enderchest, remote):
        (local_enderchest / ".." / "instances" / "bee" / ".minecraft").mkdir(
            parents=True
        )

        sync.link_to_other_chests(
            local_enderchest / "..", remote, omit_scare_message=True
        )

        result = _run_bash(
            local_enderchest,
            local_enderchest / "local-only" / "open.sh",
            "--verbose",
            capture_output=True,
        )

        assert result.returncode == 0

        place_enderchest(local_enderchest / "..")

        assert sorted(
            (
                path.name
                for path in (
                    local_enderchest
                    / ".."
                    / "instances"
                    / "bee"
                    / ".minecraft"
                    / "mods"
                ).glob("*")
            )
        ) == ["AnOkayMod.jar", "BME.jar"]

    def test_open_processes_deletions_from_upstream(self, local_enderchest, remote):
        (local_enderchest / ".." / "instances" / "bee" / ".minecraft").mkdir(
            parents=True
        )

        sync.link_to_other_chests(
            local_enderchest / "..", remote, omit_scare_message=True
        )

        result = _run_bash(
            local_enderchest,
            local_enderchest / "local-only" / "open.sh",
            "--verbose",
            capture_output=True,
        )

        assert result.returncode == 0

        place_enderchest(local_enderchest / "..")

        assert (
            list(
                (
                    local_enderchest
                    / ".."
                    / "instances"
                    / "bee"
                    / ".minecraft"
                    / "resourcepacks"
                ).glob("*")
            )
            == []
        )

    def test_close_overwrites_with_changes_from_local(self, local_enderchest, remote):
        (
            local_enderchest
            / "client-only"
            / "config"
            / "pupil.properties@axolotl@bee@cow"
        ).write_text("constricted\n")

        remote_config = (
            remote.root
            / "EnderChest"
            / "client-only"
            / "config"
            / "pupil.properties@axolotl@bee@cow"
        )
        assert remote_config.read_text() == "dilated\n"

        sync.link_to_other_chests(
            local_enderchest / "..", remote, omit_scare_message=True
        )

        result = _run_bash(
            local_enderchest,
            local_enderchest / "local-only" / "close.sh",
            "--verbose",
            capture_output=True,
        )

        assert result.returncode == 0

        assert remote_config.read_text() == "constricted\n"

    def test_close_deletes_remote_copies_when_locals_are_deleted(
        self, local_enderchest, remote
    ):
        file_to_be_removed = (
            remote.root
            / "EnderChest"
            / "client-only"
            / "config"
            / "pupil.properties@axolotl@bee@cow"
        )
        link_to_be_removed = (
            remote.root / "EnderChest" / "global" / "mods" / "AnOkayMod.jar@bee"
        )

        for object_to_be_removed in (file_to_be_removed, link_to_be_removed):
            assert list(
                object_to_be_removed.parent.glob(object_to_be_removed.name)
            ) == [object_to_be_removed]

        sync.link_to_other_chests(
            local_enderchest / "..", remote, omit_scare_message=True
        )

        result = _run_bash(
            local_enderchest,
            local_enderchest / "local-only" / "close.sh",
            "--verbose",
            capture_output=True,
        )

        assert result.returncode == 0

        for object_to_be_removed in (file_to_be_removed, link_to_be_removed):
            assert (
                list(object_to_be_removed.parent.glob(object_to_be_removed.name)) == []
            )

    def test_close_backs_up_this_local(self, local_enderchest, remote):

        sync.link_to_other_chests(
            local_enderchest / "..", remote, local_alias="this", omit_scare_message=True
        )

        result = _run_bash(
            local_enderchest,
            local_enderchest / "local-only" / "close.sh",
            "--verbose",
            capture_output=True,
        )

        assert result.returncode == 0

        assert sorted(
            [
                file.relative_to(local_enderchest / "local-only")
                for file in (local_enderchest / "local-only").rglob("*")
            ]
        ) == sorted(
            [
                file.relative_to(remote.root / "EnderChest" / "other-locals" / "this")
                for file in (
                    remote.root / "EnderChest" / "other-locals" / "this"
                ).rglob("*")
            ]
        )

    @pytest.mark.parametrize("operation", ("open", "close"))
    def test_wrapper_commands(self, local_enderchest, remote, operation):

        remote_sync = RemoteSync(
            remote,
            pre_open=["echo 1"],
            pre_close=["echo 2"],
            post_open=["echo 3"],
            post_close=["echo 4"],
        )

        sync.link_to_other_chests(
            local_enderchest / "..",
            remote_sync,
            local_alias="this",
            omit_scare_message=True,
            pre_open=["echo open start"],
            pre_close=["echo close start"],
            post_open=["echo open end"],
            post_close=["# all done", "echo close end"],
        )

        result = _run_bash(
            local_enderchest,
            local_enderchest / "local-only" / f"{operation}.sh",
            "--verbose",
            capture_output=True,
        )

        assert result.returncode == 0

        output = result.stdout.decode().splitlines()

        assert (output[0], int(output[1]), int(output[-2]), output[-1]) == (
            f"{operation} start",
            1 + (operation == "close"),
            3 + (operation == "close"),
            f"{operation} end",
        )
