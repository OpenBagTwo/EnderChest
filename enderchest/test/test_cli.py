"""Test the command-line interface"""
import os
from pathlib import Path

import pytest

import enderchest
from enderchest import cli, place
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
    @pytest.fixture
    def place_log(self, monkeypatch):
        place_log: list[tuple[Path, bool]] = []

        def mock_place(path, cleanup):
            place_log.append((path, cleanup))

        patched_actions = []
        for action in cli.ACTIONS:
            if action[0] != "place":
                patched_actions.append(action)
            else:
                patched_actions.append((action[0], action[1], mock_place))

        monkeypatch.setattr(cli, "ACTIONS", tuple(patched_actions))

        yield place_log

    def test_default_root_is_cwd(self, monkeypatch):
        monkeypatch.setattr(os, "getcwd", lambda: "~~dummy~~")
        _, root, _ = cli.parse_args(["enderchest", "place"])
        assert root == Path("~~dummy~~")

    def test_dispatches_to_place_method(self):
        action, _, _ = cli.parse_args(["enderchest", "place"])
        assert action == place.place_enderchest

    def test_first_argument_is_root(self):
        _, root, _ = cli.parse_args(["enderchest", "place", "/home"])
        assert root == Path("/home")

    def test_remove_broken_links_by_default(self, place_log):
        action, root, options = cli.parse_args(["enderchest", "place", "/home"])
        action(root, **options)
        assert place_log == [(Path("/home"), True)]

    @pytest.mark.parametrize("flag", ("-k", "--keep-broken"))
    def test_keep_broken_links(self, place_log, flag):
        action, root, options = cli.parse_args(["enderchest", "place", "/home", flag])
        action(root, **options)
        assert place_log == [(Path("/home"), False)]


@pytest.mark.parametrize("command", ("open", "close"))
class TestOpenAndClose:
    def test_default_root_is_cwd(self, monkeypatch, command):
        monkeypatch.setattr(os, "getcwd", lambda: "~~dummy~~")
        _, root, _ = cli.parse_args(["enderchest", command])
        assert root == Path("~~dummy~~")

    def test_first_argument_is_root(self, command):
        _, root, _ = cli.parse_args(["enderchest", command, "/home"])
        assert root == Path("/home")

    def test_dispatcher_expands_the_correct_script(self, monkeypatch, command):
        bash_run_commands = []

        def mock_run_bash(root, command, *args):
            bash_run_commands.append(command)

        monkeypatch.setattr(cli, "_run_bash", mock_run_bash)

        action, root, options = cli.parse_args(["enderchest", command])
        action(root, **options)

        assert bash_run_commands == [f"./EnderChest/local-only/{command}.sh"]

    def test_dispatcher_passes_default_root(self, monkeypatch, command):
        monkeypatch.setattr(os, "getcwd", lambda: "~~dummy~~")

        roots = []

        def mock_run_bash(root, command, *args):
            roots.append(root)

        monkeypatch.setattr(cli, "_run_bash", mock_run_bash)

        action, root, options = cli.parse_args(["enderchest", command])
        action(root, **options)

        assert roots == [Path("~~dummy~~")]

    def test_dispatcher_passes_provided_root(self, monkeypatch, command):
        roots = []

        def mock_run_bash(root, command, *args):
            roots.append(root)

        monkeypatch.setattr(cli, "_run_bash", mock_run_bash)

        action, root, options = cli.parse_args(["enderchest", command, "~/minecraft"])
        action(root, **options)

        assert roots == [Path("~/minecraft")]

    def test_dispatcher_passes_through_script_flags(self, monkeypatch, command):
        roots = []
        flags = []

        def mock_run_bash(root, command, *args):
            roots.append(root)
            flags.extend(args)

        monkeypatch.setattr(cli, "_run_bash", mock_run_bash)

        action, root, options = cli.parse_args(
            [
                "enderchest",
                command,
                "~/minecraft",
                "--verbose",
                "--dry-run",
                "# blahblah",
            ]
        )
        action(root, **options)

        assert (roots, flags) == (
            [Path("~/minecraft")],
            ["--verbose", "--dry-run", "# blahblah"],
        )

    def test_dispatcher_doesnt_confuse_a_flag_for_a_root(self, monkeypatch, command):
        monkeypatch.setattr(os, "getcwd", lambda: "~~dummy~~")

        roots = []
        flags = []

        def mock_run_bash(root, command, *args):
            roots.append(root)
            flags.extend(args)

        monkeypatch.setattr(cli, "_run_bash", mock_run_bash)

        action, root, options = cli.parse_args(["enderchest", command, "--verbose"])
        action(root, **options)

        assert (roots, flags) == ([Path("~~dummy~~")], ["--verbose"])
