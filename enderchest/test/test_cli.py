"""Test the command-line interface"""
import logging
import os
from pathlib import Path

import pytest

import enderchest
from enderchest import cli
from enderchest import filesystem as fs

from . import utils


class TestHelp:
    @pytest.mark.parametrize("help_flag", ("-h", "--help"))
    def test_help_displays_version(self, capsys, help_flag):
        with pytest.raises(SystemExit):
            cli.parse_args(["enderchest", help_flag])

        assert enderchest.__version__ in capsys.readouterr().out

    @pytest.mark.parametrize("help_flag", ("-h", "--help"))
    def test_help_ignores_arguments_that_follow(self, capsys, help_flag):
        with pytest.raises(SystemExit):
            cli.parse_args(["enderchest", help_flag, "foo"])

        assert "foo" not in capsys.readouterr().out
        assert "foo" not in capsys.readouterr().err


class TestVersion:
    @pytest.mark.parametrize("version_flag", ("-v", "--version"))
    def test_version_displays_version(self, capsys, version_flag):
        with pytest.raises(SystemExit):
            cli.parse_args(["enderchest", version_flag])

        assert enderchest.__version__ in capsys.readouterr().out

    @pytest.mark.parametrize("version_flag", ("-v", "--version"))
    def test_help_ignores_arguments_that_follow(self, capsys, version_flag):
        with pytest.raises(SystemExit):
            cli.parse_args(["enderchest", version_flag, "foo"])

        assert "foo" not in capsys.readouterr().out
        assert "foo" not in capsys.readouterr().err


class ActionTestSuite:
    required_args: tuple[str, ...] = ()

    @pytest.mark.parametrize("help_flag", ("-h", "--help"))
    def test_help_gives_action_specific_help(
        self,
        capsys,
        help_flag,
    ):
        with pytest.raises(SystemExit):
            cli.parse_args(["enderchest", *self.action.split(), help_flag])

        stdout = capsys.readouterr().out
        assert f"enderchest {self.action} [-h]" in stdout

    def test_default_root_is_cwd(self, monkeypatch):
        monkeypatch.setattr(os, "getcwd", lambda: "~~dummy~~")
        _, root, _, _ = cli.parse_args(
            ["enderchest", *self.action.split(), *self.required_args]
        )
        assert root == Path("~~dummy~~")

    def test_first_argument_is_root(self):
        _, root, _, _ = cli.parse_args(
            ["enderchest", *self.action.split(), "/home", *self.required_args]
        )
        assert root == Path("/home")

    def test_root_can_also_be_provided_by_flag(self):
        _, root, _, _ = cli.parse_args(
            ["enderchest", *self.action.split(), *self.required_args, "--root", "/home"]
        )
        assert root == Path("/home")

    @pytest.mark.parametrize(
        "verbosity_flag, expected_verbosity",
        (
            ("-v", logging.DEBUG),
            ("-q", logging.WARNING),
            ("--verbose", logging.DEBUG),
            ("--quiet", logging.WARNING),
            ("-vv", -1),
            ("-qq", logging.ERROR),
            ("-vvqvqqvqv", logging.DEBUG),
        ),
    )
    def test_altering_verbosity(self, verbosity_flag, expected_verbosity):
        _, _, log_level, _ = cli.parse_args(
            ["enderchest", *self.action.split(), verbosity_flag, *self.required_args]
        )

        assert log_level == expected_verbosity


class TestCraft(ActionTestSuite):
    action = "craft"

    @pytest.mark.parametrize("remote_flag", ("-r", "--remote"))
    def test_passing_in_a_single_remote(self, remote_flag):
        _, _, _, options = cli.parse_args(
            [
                "enderchest",
                "craft",
                remote_flag,
                "sftp://openbagtwo@mirror/home/openbagtwo/minecraft",
            ]
        )

        assert options["remotes"] == [
            "sftp://openbagtwo@mirror/home/openbagtwo/minecraft"
        ]

    @pytest.mark.parametrize("remote_flag_1", ("-r", "--remote"))
    @pytest.mark.parametrize("remote_flag_2", ("-r", "--remote"))
    @pytest.mark.parametrize("remote_flag_3", ("-r", "--remote"))
    def test_passing_in_a_multiple_remotes_plus_other_kwargs(
        self, remote_flag_1, remote_flag_2, remote_flag_3
    ):
        _, _, _, options = cli.parse_args(
            [
                "enderchest",
                "craft",
                remote_flag_1,
                "sftp://openbagtwo@mirror/home/openbagtwo/minecraft",
                remote_flag_2,
                "file://~/minecraft2",
                "--overwrite",
                remote_flag_3,
                "sftp://pie/opt/run/minecraft",
            ]
        )

        assert options["remotes"] == [
            "sftp://openbagtwo@mirror/home/openbagtwo/minecraft",
            "file://~/minecraft2",
            "sftp://pie/opt/run/minecraft",
        ]


class TestPlace(ActionTestSuite):
    action = "place"

    def test_remove_broken_links_by_default(self):
        _, _, _, options = cli.parse_args(["enderchest", "place", "/home"])
        assert options["cleanup"] is True

    @pytest.mark.parametrize("flag", ("-k", "--keep-broken"))
    def test_keep_broken_links(self, flag):
        _, root, _, options = cli.parse_args(["enderchest", "place", "/home", flag])
        assert (root, options["cleanup"]) == (Path("/home"), False)


class TestShulkerInventory(ActionTestSuite):
    action = "inventory shulker_box"
    required_args = ("nombre",)


class TestOpen:
    action = "open"


class TestClose:
    action = "close"
