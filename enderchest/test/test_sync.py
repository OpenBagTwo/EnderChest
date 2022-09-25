"""Test functionality around rsync script generation"""
import os
import subprocess

import pytest

from enderchest import sync
from enderchest.sync import Remote

remotes = (
    Remote("localhost", "~/minecraft", "openbagtwo", "Not Actually Remote"),
    Remote("8.8.8.8", "/root/minecraft", "sergey", "Not-Bing"),
    Remote("spare-pi", "/opt/minecraft", "pi"),
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
        assert remote.remote_folder == expected


class TestLinkToOtherChests:
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

        result = subprocess.run(
            [script_path, "--dry-run"],  # out of an overabundance of caution
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

        result = subprocess.run(
            [script_path, "--dry-run"],  # out of an overabundance of caution
            capture_output=True,
        )

        if script == "open.sh":
            assert result.returncode == 1
            assert "Could not pull changes" in result.stdout.decode()
        else:
            assert result.returncode == 0
            assert "You made it" in result.stdout.decode()
