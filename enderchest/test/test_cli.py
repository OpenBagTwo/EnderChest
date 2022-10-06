"""Test the command-line interface"""
import os
from pathlib import Path

import pytest

import enderchest
from enderchest import cli
from enderchest.sync import Remote


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

    @pytest.mark.parametrize("help_flag", ("-h", "--help"))
    @pytest.mark.parametrize("action, description, method", cli.ACTIONS)
    def test_help_gives_action_specific_help(
        self, capsys, help_flag, action, description, method
    ):
        with pytest.raises(SystemExit):
            cli.parse_args(["enderchest", action, help_flag])

        stdout = capsys.readouterr().out
        assert f"enderchest {action} [-h]" in stdout


class TestCraft:
    def test_default_root_is_cwd(self, monkeypatch):
        monkeypatch.setattr(os, "getcwd", lambda: "~~dummy~~")
        _, root, _ = cli.parse_args(["enderchest", "craft"])
        assert root == Path("~~dummy~~")

    def test_default_dispatch_is_to_non_config_craft(self, monkeypatch, capsys):
        def wrong_method(*args, **kwargs):
            assert False, "Wrong method"

        def correct_method(*args, **kwargs):
            print("You chose correctly")

        monkeypatch.setattr(cli, "craft_ender_chest_from_config", wrong_method)
        monkeypatch.setattr(cli, "craft_ender_chest", correct_method)
        action, root, _ = cli.parse_args(["enderchest", "craft"])
        action(root)
        assert capsys.readouterr().out == "You chose correctly\n"

    def test_first_argument_is_root(self, capsys):
        _, root, _ = cli.parse_args(["enderchest", "craft", "/home"])
        assert root == Path("/home")

    @pytest.mark.parametrize("config_flag", ("-f", "--file"))
    def test_passing_a_config_switches_to_the_config_craft(
        self, monkeypatch, capsys, config_flag
    ):
        def wrong_method(*args, **kwargs):
            assert False, "Wrong method"

        def correct_method(path):
            print(path)

        monkeypatch.setattr(cli, "craft_ender_chest_from_config", correct_method)
        monkeypatch.setattr(cli, "craft_ender_chest", wrong_method)
        action, root, options = cli.parse_args(
            ["enderchest", "craft", config_flag, "blah.cfg"]
        )

        action(root, **options)
        assert capsys.readouterr().out == "blah.cfg\n"

    @pytest.mark.parametrize("remote_flag", ("-r", "--remote"))
    def test_passing_in_a_single_remote(self, monkeypatch, remote_flag):

        remotes = []

        def wrong_method(*args, **kwargs):
            assert False, "Wrong method"

        def correct_method(path, *parsed_remotes, **kwargs):
            remotes.extend(parsed_remotes)

        monkeypatch.setattr(cli, "craft_ender_chest_from_config", wrong_method)
        monkeypatch.setattr(cli, "craft_ender_chest", correct_method)

        action, root, options = cli.parse_args(
            ["enderchest", "craft", remote_flag, "openbagtwo@mirror:~/minecraft"]
        )
        action(root, **options)

        assert remotes == [Remote("mirror", "~/minecraft", "openbagtwo")]

    @pytest.mark.parametrize("remote_flag_1", ("-r", "--remote"))
    @pytest.mark.parametrize("remote_flag_2", ("-r", "--remote"))
    @pytest.mark.parametrize("remote_flag_3", ("-r", "--remote"))
    def test_passing_in_a_multiple_remotes_plus_other_kwargs(
        self, monkeypatch, remote_flag_1, remote_flag_2, remote_flag_3
    ):
        remotes = []

        def wrong_method(*args, **kwargs):
            assert False, "Wrong method"

        def correct_method(path, *parsed_remotes, **kwargs):
            assert kwargs["overwrite"]
            remotes.extend(parsed_remotes)

        monkeypatch.setattr(cli, "craft_ender_chest_from_config", wrong_method)
        monkeypatch.setattr(cli, "craft_ender_chest", correct_method)

        action, root, options = cli.parse_args(
            [
                "enderchest",
                "craft",
                remote_flag_1,
                "openbagtwo@mirror:~/minecraft",
                remote_flag_2,
                "~/minecraft2",
                "--overwrite",
                remote_flag_3,
                "pie:/opt/run/minecraft",
            ]
        )
        action(root, **options)

        assert remotes == [
            Remote("mirror", "~/minecraft", "openbagtwo"),
            Remote(None, "~/minecraft2"),
            Remote("pie", "/opt/run/minecraft"),
        ]


class TestPlace:
    def test_default_root_is_cwd(self, monkeypatch):
        monkeypatch.setattr(os, "getcwd", lambda: "~~dummy~~")
        _, root, _ = cli.parse_args(["enderchest", "place"])
        assert root == Path("~~dummy~~")

    def test_first_argument_is_root(self):
        _, root, _ = cli.parse_args(["enderchest", "place", "/home"])
        assert root == Path("/home")
