"""Test the command-line interface"""
import os
from pathlib import Path

import pytest

import enderchest
from enderchest import cli


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

    def test_default_dispatch_is_to_non_config_craft(self, monkeypatch):
        def wrong_method(*args, **kwargs):
            assert False, "Wrong method"

        def correct_method(*args, **kwargs):
            pass

        monkeypatch.setattr(cli, "craft_ender_chest_from_config", wrong_method)
        monkeypatch.setattr(cli, "craft_ender_chest", correct_method)
        action, _, _ = cli.parse_args(["enderchest", "craft"])

    def test_first_argument_is_root(self):
        _, root, _ = cli.parse_args(["enderchest", "craft", "/home"])
        assert root == Path("/home")


class TestPlace:
    def test_default_root_is_cwd(self, monkeypatch):
        monkeypatch.setattr(os, "getcwd", lambda: "~~dummy~~")
        _, root, _ = cli.parse_args(["enderchest", "place"])
        assert root == Path("~~dummy~~")

    def test_first_argument_is_root(self):
        _, root, _ = cli.parse_args(["enderchest", "place", "/home"])
        assert root == Path("/home")
