"""Test the command-line interface"""
import logging
import os
from pathlib import Path
from typing import Generator

import pytest

import enderchest
from enderchest import cli, gather, place, remote


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
        monkeypatch.delenv("MINECRAFT_ROOT", raising=False)
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

    def test_root_can_also_be_provided_by_systemenv(self, monkeypatch):
        monkeypatch.setenv("MINECRAFT_ROOT", "/mnt/drive/minecraft/")
        _, root, _, _ = cli.parse_args(
            ["enderchest", *self.action.split(), *self.required_args]
        )
        assert root == Path("/mnt/drive/minecraft/")

    @pytest.mark.parametrize(
        "verbosity_flag, expected_verbosity",
        (
            ("-v", logging.DEBUG - 9),
            ("-q", logging.WARNING - 9),
            ("--verbose", logging.DEBUG - 9),
            ("--quiet", logging.WARNING - 9),
            ("-vv", -9),
            ("-qq", logging.ERROR - 9),
            ("-vvqvqqvqv", logging.DEBUG - 9),
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
    def place_log(self, monkeypatch) -> Generator[list[tuple[Path, dict]], None, None]:
        place_log: list[tuple[Path, dict]] = []

        def mock_place(path, **kwargs):
            place_log.append((path, kwargs))

        monkeypatch.setattr(place, "place_ender_chest", mock_place)
        monkeypatch.setattr(place, "cache_placements", lambda *args, **kwargs: None)
        yield place_log

    @pytest.mark.parametrize("option", ("keep_broken_links", "keep_stale_links"))
    def test_remove_broken_links_by_default(self, option, place_log):
        action, minecraft_root, _, options = cli.parse_args(
            ["enderchest", "place", "/home"]
        )
        action(minecraft_root, **options)
        assert len(place_log) == 1
        assert place_log[0][1][option] is False

    @pytest.mark.parametrize("flag", ("-k", "--keep-stale-links"))
    def test_keep_stale_links(self, flag, place_log):
        action, minecraft_root, _, options = cli.parse_args(
            ["enderchest", "place", "/home", flag]
        )
        action(minecraft_root, **options)
        assert len(place_log) == 1
        assert place_log[0][1]["keep_stale_links"] is True

    @pytest.mark.parametrize("flag", ("-kk", "--keep-broken-links"))
    def test_keep_broken_links(self, flag, place_log):
        action, minecraft_root, _, options = cli.parse_args(
            ["enderchest", "place", "/home", flag]
        )
        action(minecraft_root, **options)
        assert len(place_log) == 1
        assert place_log[0][1]["keep_broken_links"] is True

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

    def test_absolute_path_links_is_the_default(self, place_log):
        action, *_, options = cli.parse_args(["enderchest", "place"])
        action(Path(), **options)
        assert place_log[0][1]["relative"] is False

    @pytest.mark.parametrize(
        "flag, expected",
        (("-a", False), ("--absolute", False), ("-r", True), ("--relative", True)),
    )
    def test_explicitly_specify_abs_or_rel(self, place_log, flag, expected):
        action, *_, options = cli.parse_args(["enderchest", "place"])
        action(Path(), **options)
        assert place_log[0][1]["relative"] is False


class TestGather(ActionTestSuite):
    action = "gather instance"
    required_args = ("~",)

    @pytest.mark.parametrize("with_root", (False, True), ids=("no_root", "with-root"))
    def test_gather_requires_at_least_one_search_path(self, with_root, capsys):
        more_args = ("--root", "/minecraft") if with_root else ()
        with pytest.raises(SystemExit):
            cli.parse_args(["enderchest", *self.action.split(), *more_args])

        _ = capsys.readouterr()  # suppress outputs

    @pytest.mark.parametrize("with_root", (False, True), ids=("no_root", "with-root"))
    def test_single_arg_interpreted_as_search_path(
        self, with_root, capsys, monkeypatch
    ):
        monkeypatch.delenv("MINECRAFT_ROOT", raising=False)
        more_args = ("--root", ".") if with_root else ()

        _, root, _, options = cli.parse_args(
            ["enderchest", *self.action.split(), *more_args, "~"]
        )

        _ = capsys.readouterr()  # suppress outputs

        assert (root.resolve(), options["search_paths"]) == (
            Path(".").resolve(),
            [Path("~")],
        )

    def test_first_arg_interpreted_as_root(self):  # I actually really don't like this
        _, root, _, options = cli.parse_args(
            [
                "enderchest",
                *self.action.split(),
                ".",
                "~",
                "/here",
                "/there",
                "everywhere",
            ]
        )
        assert (root.resolve(), options["search_paths"]) == (
            Path(".").resolve(),
            [Path("~"), Path("/here"), Path("/there"), Path("everywhere")],
        )


class TestGatherRemote(ActionTestSuite):
    action = "gather enderchests"
    required_args = ("sftp://openbagtwo@steamdeck/home/deck",)

    @pytest.mark.parametrize("with_root", (False, True), ids=("no_root", "with-root"))
    def test_gather_requires_at_least_one_remote(self, with_root, capsys):
        more_args = ("--root", "/minecraft") if with_root else ()
        with pytest.raises(SystemExit):
            cli.parse_args(["enderchest", *self.action.split(), *more_args])

        _ = capsys.readouterr()  # suppress outputs

    @pytest.mark.parametrize("with_root", (False, True), ids=("no_root", "with-root"))
    def test_single_arg_interpreted_as_remote(self, with_root, monkeypatch):
        monkeypatch.delenv("MINECRAFT_ROOT", raising=False)
        more_args = ("--root", ".") if with_root else ()

        _, root, _, options = cli.parse_args(
            [
                "enderchest",
                *self.action.split(),
                *more_args,
                "sftp://openbagtwo@steamdeck:~",
            ]
        )
        assert (root.resolve(), options["remotes"]) == (
            Path(".").resolve(),
            ["sftp://openbagtwo@steamdeck:~"],
        )

    def test_first_arg_interpreted_as_root(self):  # I actually really don't like this
        _, root, _, options = cli.parse_args(
            [
                "enderchest",
                *self.action.split(),
                "~",
                "sftp://openbagtwo@steamdeck/home/deck",
                "ipoac://birdhouse/your/soul",
                "sneakernet://123.fake.street/mailbox",
            ]
        )
        assert (root.expanduser().resolve(), options["remotes"]) == (
            Path("~").expanduser().resolve(),
            [
                "sftp://openbagtwo@steamdeck/home/deck",
                "ipoac://birdhouse/your/soul",
                "sneakernet://123.fake.street/mailbox",
            ],
        )


class TestInventory(ActionTestSuite):
    action = "inventory"

    def test_no_args_routes_to_load_shulker_boxes(self, monkeypatch) -> None:
        gather_log: list[tuple[str, dict]] = []

        def mock_load_shulker_boxes(root, **kwargs) -> None:
            gather_log.append((root, kwargs))

        monkeypatch.setattr(gather, "load_shulker_boxes", mock_load_shulker_boxes)

        action, root, _, kwargs = cli.parse_args(["enderchest", *self.action.split()])
        action(root, **kwargs)

        assert len(gather_log) == 1
        assert gather_log[0][1] == {}

    @pytest.mark.parametrize("action_version", ("short", "long"))
    def test_no_path_routes_to_boxes_matching_instance(
        self, monkeypatch, action_version
    ) -> None:
        gather_log: list[tuple[str, str, dict]] = []

        def mock_get_shulker_boxes_matching_instance(root, name, **kwargs) -> None:
            gather_log.append((root, name, kwargs))

        monkeypatch.setattr(
            gather,
            "get_shulker_boxes_matching_instance",
            mock_get_shulker_boxes_matching_instance,
        )

        if action_version == "short":
            instance_args = ("--instance", "cherry grove")
        else:  # if action_version == "long":
            instance_args = ("minecraft", "cherry grove")

        action, root, _, kwargs = cli.parse_args(
            ["enderchest", *self.action.split(), *instance_args]
        )
        action(root, **kwargs)

        assert len(gather_log) == 1
        assert gather_log[0][1:] == ("cherry grove", {})

    def test_long_action_requires_instance_name(self):
        with pytest.raises(SystemExit):
            _ = cli.parse_args(["enderchest", *self.action.split(), "minecraft"])

    @pytest.mark.parametrize(
        "instance_how", ("no_instance", "long_action", "short_action")
    )
    def test_providing_a_path_always_routes_to_list_placements(
        self, monkeypatch, instance_how
    ) -> None:
        def mock_get_shulker_boxes_matching_instance(*args, **kwargs) -> None:
            raise AssertionError("I should not have been called!")

        monkeypatch.setattr(
            gather,
            "get_shulker_boxes_matching_instance",
            mock_get_shulker_boxes_matching_instance,
        )

        list_log: list[tuple[str, str, dict]] = []

        def mock_list_placements(root, pattern, **kwargs) -> None:
            list_log.append((root, pattern, kwargs))

        monkeypatch.setattr(
            place,
            "list_placements",
            mock_list_placements,
        )

        if instance_how == "no_instance":
            instance = None
            instance_args: list[str] = []
        else:
            instance = "cherry grove"
            if instance_how == "long_action":
                instance_args = ["instance", instance]
            else:  # if instance_how == "short_action":
                instance_args = ["-i", instance]

        action, root, _, kwargs = cli.parse_args(
            ["enderchest", *self.action.split(), *instance_args, "-p", "of_jelly.jar"]
        )
        action(root, **kwargs)

        assert len(list_log) == 1
        assert list_log[0][1:] == ("of_jelly.jar", {"instance_name": instance})


class TestShulkerInventory(ActionTestSuite):
    action = "inventory shulker_box"
    required_args = ("nombre",)


class TestOpen:
    action = "open"
    op = "pull"

    def test_op_is_routed_successfully(self, monkeypatch) -> None:
        sync_log: list[tuple[str, str, dict]] = []

        def mock_sync(root, op, **kwargs) -> None:
            sync_log.append((root, op, kwargs))

        monkeypatch.setattr(remote, "sync_with_remotes", mock_sync)

        action, root, _, kwargs = cli.parse_args(["enderchest", *self.action.split()])
        action(root, **kwargs)

        assert len(sync_log) == 1
        assert sync_log[0][1] == self.op

    @pytest.mark.parametrize(
        "verbosity_flag, expected_verbosity",
        (
            ("-v", 1),
            ("-q", -1),
            ("--verbose", 1),
            ("--quiet", -1),
            ("-vv", 2),
            ("-qq", -2),
            ("-vvqvqqvqv", 1),
        ),
    )
    def test_verbosity_modifier_is_passed_to_op(
        self, monkeypatch, verbosity_flag, expected_verbosity
    ) -> None:
        sync_log: list[tuple[str, str, dict]] = []

        def mock_sync(root, op, **kwargs) -> None:
            sync_log.append((root, op, kwargs))

        monkeypatch.setattr(remote, "sync_with_remotes", mock_sync)

        action, root, _, kwargs = cli.parse_args(
            ["enderchest", *self.action.split(), verbosity_flag]
        )
        action(root, **kwargs)

        assert len(sync_log) == 1
        assert sync_log[0][2]["verbosity"] == expected_verbosity

    def test_sync_confirm_wait_is_none_by_default(self, monkeypatch) -> None:
        sync_log: list[tuple[str, str, dict]] = []

        def mock_sync(root, op, **kwargs) -> None:
            sync_log.append((root, op, kwargs))

        monkeypatch.setattr(remote, "sync_with_remotes", mock_sync)

        action, root, _, kwargs = cli.parse_args(["enderchest", *self.action.split()])
        action(root, **kwargs)

        assert len(sync_log) == 1
        assert sync_log[0][2]["sync_confirm_wait"] is None

    @pytest.mark.parametrize(
        "arguments, expected_value",
        (
            (("--wait", "5"), 5),
            (("-w0",), 0),
            (("--confirm",), True),
            (("-c",), True),
        ),
    )
    def test_sync_confirm_wait(
        self,
        monkeypatch,
        arguments: tuple[str, ...],
        expected_value: int | bool,
    ) -> None:
        sync_log: list[tuple[str, str, dict]] = []

        def mock_sync(root, op, **kwargs) -> None:
            sync_log.append((root, op, kwargs))

        monkeypatch.setattr(remote, "sync_with_remotes", mock_sync)

        action, root, _, kwargs = cli.parse_args(
            ["enderchest", *self.action.split(), *arguments]
        )
        action(root, **kwargs)

        assert len(sync_log) == 1
        assert sync_log[0][2]["sync_confirm_wait"] == expected_value

    def test_raise_if_wait_and_confirm_are_both_provided(self, monkeypatch) -> None:
        def mock_sync(root, op, **kwargs) -> None:
            raise AssertionError("I should not have been called!")

        monkeypatch.setattr(remote, "sync_with_remotes", mock_sync)

        with pytest.raises(SystemExit):
            action, root, _, kwargs = cli.parse_args(
                ["enderchest", *self.action.split(), "--confirm", "-w0"]
            )

    def test_dry_run_is_false_by_default(self, monkeypatch) -> None:
        sync_log: list[tuple[str, str, dict]] = []

        def mock_sync(root, op, **kwargs) -> None:
            sync_log.append((root, op, kwargs))

        monkeypatch.setattr(remote, "sync_with_remotes", mock_sync)

        action, root, _, kwargs = cli.parse_args(["enderchest", *self.action.split()])
        action(root, **kwargs)

        assert len(sync_log) == 1
        assert sync_log[0][2]["dry_run"] is False

    def test_passing_a_bunch_of_args(self, monkeypatch) -> None:
        sync_log: list[tuple[str, str, dict]] = []

        def mock_sync(root, op, **kwargs) -> None:
            sync_log.append((root, op, kwargs))

        monkeypatch.setattr(remote, "sync_with_remotes", mock_sync)

        action, root, _, kwargs = cli.parse_args(
            [
                "enderchest",
                *self.action.split(),
                "--root",
                ".",
                "--dry-run",
                "-t",
                "15",
                "-w",
                "0",
                "-e",
                "private",
                "*.secret",
            ]
        )
        action(root, **kwargs)

        assert len(sync_log) == 1
        assert sync_log[0][2] == {
            "dry_run": True,
            "timeout": 15,
            "sync_confirm_wait": 0,
            "exclude": ["private", "*.secret"],
            "verbosity": 0,
        }

    def test_passing_in_multiple_exclude_flags(self, monkeypatch) -> None:
        sync_log: list[tuple[str, str, dict]] = []

        def mock_sync(root, op, **kwargs) -> None:
            sync_log.append((root, op, kwargs))

        monkeypatch.setattr(remote, "sync_with_remotes", mock_sync)

        action, root, _, kwargs = cli.parse_args(
            [
                "enderchest",
                *self.action.split(),
                "--exclude",
                "*.secret",
                "--dry-run",
                "-e",
                "private",
                "super-private",
                "--confirm",
                "--exclude",
                "do-not-sync",
                "-vv",
            ]
        )
        action(root, **kwargs)

        assert len(sync_log) == 1
        assert sync_log[0][2] == {
            "dry_run": True,
            "sync_confirm_wait": True,
            "exclude": ["*.secret", "private", "super-private", "do-not-sync"],
            "verbosity": 2,
            "timeout": None,
        }


class TestClose(TestOpen):
    action = "close"
    op = "push"


class TestBreak(ActionTestSuite):
    action = "break"
