"""Test functionality around rsync script generation"""
import os

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
