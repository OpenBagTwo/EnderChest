"""Test the command-line interface"""
import logging
import os
from pathlib import Path

import pytest

import enderchest
from enderchest import cli, place


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
        *_, options = cli.parse_args(
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
        *_, options = cli.parse_args(
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


class TestCraftShulker(ActionTestSuite):
    action = "craft shulker_box"
    required_args = ("nombre",)

    @pytest.mark.parametrize("instance_flag", ("-i", "--instance"))
    def test_passing_in_a_single_instance(self, instance_flag):
        *_, options = cli.parse_args(
            ["enderchest", "craft", "shulker_box", instance_flag, "endcity", "spitty"]
        )

        # remove unset stuff
        options = {key: value for key, value in options.items() if value}
        assert options == {
            "instances": ["endcity"],
            "name": "spitty",
        }

    def test_passing_in_a_mix_of_multi_kwargs(
        self,
    ):
        _, root, _, options = cli.parse_args(
            [
                "enderchest",
                "craft",
                "shulker_box",
                "--overwrite",
                "--instance",
                "onion",
                "rooty",
                "-t",
                "allium*" "rutabaga",
                "--instance",
                "turnip",
                "--enderchest",
                "farm",
            ]
        )

        # remove unset stuff
        options = {key: value for key, value in options.items() if value}
        assert root, options == (
            "rooty",
            {
                "name": "rutabaga",
                "instances": ["onion", "turnip"],
                "tags": ["allium"],
                "hosts": ["farm"],
                "overwrite": True,
            },
        )


class TestPlace(ActionTestSuite):
    action = "place"

    @pytest.fixture
    def place_log(self, monkeypatch):
        place_log: list[tuple[Path, dict]] = []

        def mock_place(path, **kwargs):
            place_log.append((path, kwargs))

        monkeypatch.setattr(place, "place_ender_chest", mock_place)

        yield place_log

    def test_remove_broken_links_by_default(self):
        *_, options = cli.parse_args(["enderchest", "place", "/home"])
        assert options["cleanup"] is True

    @pytest.mark.parametrize("flag", ("-k", "--keep-broken"))
    def test_keep_broken_links(self, flag):
        *_, options = cli.parse_args(["enderchest", "place", "/home", flag])
        assert options["cleanup"] is False

    def test_prompt_on_error_by_default(self):
        *_, options = cli.parse_args(["enderchest", "place"])
        assert (
            options["errors"],
            options["stop_at_first_failure"],
            options["ignore_errors"],
        ) == ("prompt", False, False)

    @pytest.mark.parametrize(
        "flags",
        (("-x",), ("--stop-at-first-failure",), ("--errors", "abort")),
        ids=("-x", "--stop-at-first-failure", "--errors=abort"),
    )
    def test_stop_on_error(self, place_log, flags):
        action, *_, options = cli.parse_args(["enderchest", "place", *flags])
        action(Path(), **options)
        assert place_log[0][1]["error_handling"] == "abort"

    @pytest.mark.parametrize(
        "flags",
        (("--ignore-errors",), ("--errors", "ignore")),
        ids=("--ignore-errors", "--errors=ignore"),
    )
    def test_ignore_errors(self, place_log, flags):
        action, *_, options = cli.parse_args(["enderchest", "place", *flags])
        action(Path(), **options)
        assert place_log[0][1]["error_handling"] == "ignore"


class TestShulkerInventory(ActionTestSuite):
    action = "inventory shulker_box"
    required_args = ("nombre",)


class TestOpen:
    action = "open"


class TestClose:
    action = "close"
