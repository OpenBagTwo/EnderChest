"""Command-line interface"""
import argparse
import inspect
import logging
import os
import sys
from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path
from typing import Any, Iterable, Protocol, Sequence

from . import craft, gather, loggers, place, remote, uninstall
from ._version import get_versions

# mainly because I think I'm gonna forget what names are canonical (it's the first ones)
_create_aliases = ("craft", "create")
_instance_aliases = tuple(
    alias + plural for alias in ("instance", "minecraft") for plural in ("", "s")
)
_shulker_box_aliases = ("shulker_box", "shulkerbox", "shulker")
_remote_aliases = tuple(
    alias + plural for alias in ("enderchest", "remote") for plural in ("s", "")
)
_list_aliases = ("inventory", "list")


class Action(Protocol):  # pragma: no cover
    """Common protocol for CLI actions"""

    def __call__(self, minecraft_root: Path, /) -> Any:
        ...


def _place(
    minecraft_root: Path,
    errors: str = "prompt",
    keep_broken_links: bool = False,
    keep_stale_links: bool = False,
    keep_level: int = 0,
    stop_at_first_failure: bool = False,
    ignore_errors: bool = False,
    absolute: bool = False,
    relative: bool = False,
) -> None:
    """Wrapper sort through all the various argument groups"""

    if stop_at_first_failure:
        errors = "abort"
    if ignore_errors:  # elif?
        errors = "ignore"
    # else: errors = errors

    if absolute is True:
        # technically we get this for free already
        relative = False

    if keep_level > 0:
        keep_stale_links = True
    if keep_level > 1:
        keep_broken_links = True

    place.cache_placements(
        minecraft_root,
        place.place_ender_chest(
            minecraft_root,
            keep_broken_links=keep_broken_links,
            keep_stale_links=keep_stale_links,
            error_handling=errors,
            relative=relative,
        ),
    )


def _craft_shulker_box(minecraft_root: Path, name: str | None = None, **kwargs):
    """Wrapper to handle the fact that name is a required argument"""
    assert name  # it's required by the parser, so this should be fine
    craft.craft_shulker_box(minecraft_root, name, **kwargs)


def _list_instance_boxes(
    minecraft_root: Path,
    instance_name: str | None = None,
    path: str | None = None,
    **kwargs,
):
    """Wrapper to route --path flag and instance_name arg"""
    if path is not None:
        place.list_placements(
            minecraft_root, pattern=path, instance_name=instance_name, **kwargs
        )
    elif instance_name is not None:
        gather.get_shulker_boxes_matching_instance(
            minecraft_root, instance_name, **kwargs
        )
    else:
        gather.load_shulker_boxes(minecraft_root, **kwargs)


def _list_shulker_box(
    minecraft_root: Path, shulker_box_name: str | None = None, **kwargs
):
    """Wrapper to handle the fact that name is a required argument"""
    assert shulker_box_name  # it's required by the parser, so this should be fine
    gather.get_instances_matching_shulker_box(
        minecraft_root, shulker_box_name, **kwargs
    )


def _update_ender_chest(
    minecraft_root: Path,
    official: bool | None = None,
    mmc: bool | None = None,
    **kwargs,
):
    """Wrapper to resolve the official vs. MultiMC flag"""
    if mmc:
        official = False
    gather.update_ender_chest(minecraft_root, official=official, **kwargs)


def _open(minecraft_root: Path, verbosity: int = 0, **kwargs):
    """Router for open verb"""
    remote.sync_with_remotes(minecraft_root, "pull", verbosity=verbosity, **kwargs)


def _close(minecraft_root: Path, verbosity: int = 0, **kwargs):
    """Router for close verb"""
    remote.sync_with_remotes(minecraft_root, "push", verbosity=verbosity, **kwargs)


def _test(
    minecraft_root: Path, use_local_ssh: bool = False, pytest_args: Iterable[str] = ()
):
    """Run the EnderChest test suite to ensure that it is running correctly on your
    system. Requires you to have installed GSB with the test extra
    (i.e. pipx install enderchest[test])."""
    import pytest

    from enderchest.test import plugin

    if use_local_ssh:
        pytest_args = ("--use-local-ssh", *pytest_args)
    if exit_code := pytest.main(
        ["--pyargs", "enderchest.test", *pytest_args],
        plugins=(plugin,),
    ):
        raise SystemExit(f"Tests Failed with exit code: {exit_code}")


ACTIONS: tuple[tuple[tuple[str, ...], str, Action], ...] = (
    # action names (first one is canonical), action description, action method
    (
        sum(((verb, verb + " enderchest") for verb in _create_aliases), ()),
        "create and configure a new EnderChest installation",
        craft.craft_ender_chest,
    ),
    (
        tuple(
            f"{verb} {alias}"
            for verb in _create_aliases
            for alias in _shulker_box_aliases
        ),
        "create and configure a new shulker box",
        _craft_shulker_box,
    ),
    (
        ("place",),
        "link (or update the links) from your instances to your EnderChest",
        _place,
    ),
    (
        tuple("gather " + alias for alias in _instance_aliases),
        "register (or update the registry of) a Minecraft installation",
        _update_ender_chest,
    ),
    (
        tuple("gather " + alias for alias in _remote_aliases),
        "register (or update the registry of) a remote EnderChest",
        _update_ender_chest,
    ),
    (
        # I freely admit this is ridiculous
        sum(
            (
                (
                    verb,
                    *(
                        f"{verb} {alias}"
                        # pluralization is hard
                        for alias in ("shulker_boxes", "shulkerboxes", "shulkers")
                    ),
                )
                for verb in _list_aliases
            ),
            (),
        ),
        "list the shulker boxes inside your Enderchest",
        _list_instance_boxes,
    ),
    (
        tuple(
            f"{verb} {alias}"
            for verb in _list_aliases
            for alias in _instance_aliases
            if alias.endswith("s")
        ),
        "list the minecraft instances registered with your Enderchest",
        gather.load_ender_chest_instances,
    ),
    (
        tuple(
            f"{verb} {alias}"
            for verb in _list_aliases
            for alias in _instance_aliases
            if not alias.endswith("s")
        ),
        "list the shulker boxes that the specified instance links into",
        _list_instance_boxes,
    ),
    (
        tuple(
            f"{verb} {alias}"
            for verb in _list_aliases
            for alias in _shulker_box_aliases
        ),
        "list the minecraft instances that match the specified shulker box",
        _list_shulker_box,
    ),
    (
        tuple(f"{verb} {alias}" for verb in _list_aliases for alias in _remote_aliases),
        "list the other EnderChest installations registered with this EnderChest",
        gather.load_ender_chest_remotes,
    ),
    (
        ("open",),
        "pull changes from other EnderChests",
        _open,
    ),
    (
        ("close",),
        "push changes to other EnderChests",
        _close,
    ),
    (
        ("break",),
        "uninstall EnderChest by copying all linked resources"
        " into its registered instances",
        uninstall.break_ender_chest,
    ),
    (
        ("test",),
        "run the EnderChest test suite",
        _test,
    ),
)


def generate_parsers() -> tuple[ArgumentParser, dict[str, ArgumentParser]]:
    """Generate the command-line parsers

    Returns
    -------
    enderchest_parser : ArgumentParser
        The top-level argument parser responsible for routing arguments to
        specific action parsers
    action_parsers : dict of str to ArgumentParser
        The verb-specific argument parsers
    """
    descriptions: dict[str, str] = {}
    root_description: str = ""
    for commands, description, _ in ACTIONS:
        descriptions[commands[0]] = description
        root_description += f"\n\t{commands[0]}\n\t\tto {description}"

    enderchest_parser = ArgumentParser(
        prog="enderchest",
        description=(
            f"v{get_versions()['version']}\n"
            "\nsyncing and linking for all your Minecraft instances"
        ),
        formatter_class=RawTextHelpFormatter,
    )

    enderchest_parser.add_argument(
        "-v",  # don't worry--this doesn't actually conflict with --verbose
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s v{get_versions()['version']}",
    )

    # these are really just for the sake of --help
    # (the parsed args aren't actually used)
    enderchest_parser.add_argument(
        "action",
        help=f"The action to perform. Options are:{root_description}",
        type=str,
    )
    enderchest_parser.add_argument(
        "arguments",
        nargs="*",
        help="Any additional arguments for the specific action."
        " To learn more, try: enderchest {action} -h",
    )

    action_parsers: dict[str, ArgumentParser] = {}
    for verb, description in descriptions.items():
        parser = ArgumentParser(
            prog=f"enderchest {verb}",
            description=description,
        )
        if verb != "test":
            root = parser.add_mutually_exclusive_group()
            root.add_argument(
                "root",
                nargs="?",
                help=(
                    "Optionally specify your root minecraft directory."
                    "  If no path is given, the current working directory will be used."
                ),
                type=Path,
            )
            root.add_argument(
                "--root",
                dest="root_flag",
                help="specify your root minecraft directory",
                type=Path,
            )

            # I'm actually okay with -vvqvqqv hilarity
            parser.add_argument(
                "--verbose",
                "-v",
                action="count",
                default=0,
                help="increase the amount of information that's printed",
            )
            parser.add_argument(
                "--quiet",
                "-q",
                action="count",
                default=0,
                help="decrease the amount of information that's printed",
            )
        action_parsers[verb] = parser

    # craft options
    craft_parser = action_parsers[_create_aliases[0]]
    craft_parser.add_argument(
        "--from",
        dest="copy_from",
        help=(
            "provide the URI (e.g. rsync://deck@my-steam-deck/home/deck/) of a"
            " remote EnderChest installation that can be used"
            " to boostrap the creation of this one."
        ),
    )
    craft_parser.add_argument(
        "-r",
        "--remote",
        dest="remotes",
        action="append",
        help=(
            "provide the URI (e.g. rsync://deck@my-steam-deck/home/deck/) of a"
            " remote EnderChest installation to register with this one"
        ),
    )
    craft_parser.add_argument(
        "-i",
        "--instance",
        dest="instance_search_paths",
        action="append",
        type=Path,
        help="specify a folder to search for Minecraft installations in",
    )
    craft_parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "if there's already an EnderChest installation in this location,"
            " overwrite its configuration"
        ),
    )

    # shulker box craft options
    shulker_craft_parser = action_parsers[
        f"{_create_aliases[0]} {_shulker_box_aliases[0]}"
    ]
    shulker_craft_parser.add_argument(
        "name",
        help="specify the name for this shulker box",
    )
    shulker_craft_parser.add_argument(
        "--priority",
        "-p",
        help="specify the link priority for this shulker box (higher = linked later)",
    )
    shulker_craft_parser.add_argument(
        "-i",
        "--instance",
        dest="instances",
        action="append",
        help="only link instances with one of the provided names to this shulker box",
    )
    shulker_craft_parser.add_argument(
        "-t",
        "--tag",
        dest="tags",
        action="append",
        help="only link instances with one of the provided tags to this shulker box",
    )
    shulker_craft_parser.add_argument(
        "-e",
        "--enderchest",
        dest="hosts",
        action="append",
        help=(
            "only link instances registered to one of the provided EnderChest"
            " installations with this shulker box"
        ),
    )
    shulker_craft_parser.add_argument(
        "-l",
        "--folder",
        dest="link_folders",
        action="append",
        help=(
            "specify the name of a folder inside this shulker box"
            " that should be linked completely"
        ),
    )
    shulker_craft_parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "if there's already a shulker box with the specified name,"
            " overwrite its configuration"
        ),
    )

    # place options
    place_parser = action_parsers["place"]
    cleanup = place_parser.add_argument_group()
    cleanup.add_argument(
        "--keep-broken-links",
        action="store_true",
        help="do not remove broken links from instances",
    )
    cleanup.add_argument(
        "--keep-stale-links",
        action="store_true",
        help=(
            "do not remove existing links into the EnderChest,"
            " even if the shulker box or instance spec has changed"
        ),
    )
    cleanup.add_argument(
        "-k",
        dest="keep_level",
        action="count",
        default=0,
        help=(
            "shorthand for the above cleanup options:"
            " -k will --keep-stale-links,"
            " and -kk will --keep-broken-links as well"
        ),
    )
    error_handling = place_parser.add_argument_group(
        title="error handling"
    ).add_mutually_exclusive_group()
    error_handling.add_argument(
        "--stop-at-first-failure",
        "-x",
        action="store_true",
        help="stop linking at the first issue",
    )
    error_handling.add_argument(
        "--ignore-errors", action="store_true", help="ignore any linking errors"
    )
    error_handling.add_argument(
        "--errors",
        "-e",
        choices=(
            "prompt",
            "ignore",
            "skip",
            "skip-instance",
            "skip-shulker-box",
            "abort",
        ),
        default="prompt",
        help=(
            "specify how to handle linking errors"
            " (default behavior is to prompt after every error)"
        ),
    )
    link_type = place_parser.add_mutually_exclusive_group()
    link_type.add_argument(
        "--absolute",
        "-a",
        action="store_true",
        help="use absolute paths for all link targets",
    )
    link_type.add_argument(
        "--relative",
        "-r",
        action="store_true",
        help="use relative paths for all link targets",
    )

    # gather instance options
    gather_instance_parser = action_parsers[f"gather {_instance_aliases[0]}"]
    gather_instance_parser.add_argument(
        "search_paths",
        nargs="+",
        action="extend",
        type=Path,
        help="specify a folder or folders to search for Minecraft installations",
    )
    instance_type = gather_instance_parser.add_mutually_exclusive_group()
    instance_type.add_argument(
        "--official",
        "-o",
        action="store_true",
        help="specify that these are instances managed by the official launcher",
    )
    instance_type.add_argument(
        "--mmc",
        "-m",
        action="store_true",
        help="specify that these are MultiMC-like instances",
    )

    # gather remote options
    gather_remote_parser = action_parsers[f"gather {_remote_aliases[0]}"]
    gather_remote_parser.add_argument(
        "remotes",
        nargs="+",
        action="extend",
        help=(
            "Provide URIs (e.g. rsync://deck@my-steam-deck/home/deck/) of any"
            " remote EnderChest installation to register with this one."
            "Note: you should not use this method if the alias (name) of the"
            "remote does not match the remote's hostname (in this example,"
            '"my-steam-deck").'
        ),
    )

    # list shulker box options

    # list [instance] boxes options
    list_boxes_parser = action_parsers[f"{_list_aliases[0]}"]
    list_instance_boxes_parser = action_parsers[
        f"{_list_aliases[0]} {_instance_aliases[0]}"
    ]

    instance_name_docs = "The name of the minecraft instance to query"
    list_boxes_parser.add_argument(
        "--instance", "-i", dest="instance_name", help=instance_name_docs
    )
    list_instance_boxes_parser.add_argument("instance_name", help=instance_name_docs)

    for parser in (list_boxes_parser, list_instance_boxes_parser):
        parser.add_argument(
            "--path",
            "-p",
            help=(
                "optionally, specify a specific path"
                " (absolute, relative, filename or glob pattern"
                " to get a report of the shulker box(es) that provide that resource"
            ),
        )

    # list shulker options
    list_shulker_box_parser = action_parsers[
        f"{_list_aliases[0]} {_shulker_box_aliases[0]}"
    ]
    list_shulker_box_parser.add_argument(
        "shulker_box_name", help="the name of the shulker box to query"
    )

    # open / close options
    for action in ("open", "close"):
        sync_parser = action_parsers[action]

        sync_parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "perform a dry run of the sync operation,"
                " reporting the operations that will be performed"
                " but not actually carrying them out"
            ),
        )
        sync_parser.add_argument(
            "--exclude",
            "-e",
            action="extend",
            nargs="+",
            help="Provide any file patterns you would like to skip syncing",
        )
        sync_parser.add_argument(
            "--timeout",
            "-t",
            type=int,
            help=(
                "set a maximum number of seconds to try to sync to a remote chest"
                " before giving up and going on to the next one"
            ),
        )
        sync_confirm_wait = sync_parser.add_argument_group(
            title="sync confirmation control",
            description=(
                "The default behavior when syncing EnderChests is to first perform a"
                " dry run of every sync operation and then wait 5 seconds before"
                " proceeding with the real sync. The idea is to give you time to"
                " interrupt the sync if the dry run looks wrong. You can raise or"
                " lower that wait time through these flags. You can also modify it"
                " by editing the enderchest.cfg file."
            ),
        ).add_mutually_exclusive_group()
        sync_confirm_wait.add_argument(
            "--wait",
            "-w",
            dest="sync_confirm_wait",
            type=int,
            help="set the time in seconds to wait after performing a dry run"
            " before the real sync is performed",
        )
        sync_confirm_wait.add_argument(
            "--confirm",
            "-c",
            dest="sync_confirm_wait",
            action="store_true",
            help="after performing the dry run, explicitly ask for confirmation"
            " before performing the real sync",
        )

    # test pass-through
    test_parser = action_parsers["test"]
    test_parser.add_argument(
        "--use-local-ssh",
        action="store_true",
        dest="use_local_ssh",
        help=(
            "By default, tests of SSH functionality will be run against a mock"
            " SSH server. If you are running EnderChest on a machine you can SSH"
            " into locally (by running `ssh localhost`) without requiring a password,"
            " running the tests with this flag will produce more accurate results."
        ),
    )
    test_parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="any additional arguments to pass through to py.test",
    )

    return enderchest_parser, action_parsers


def parse_args(argv: Sequence[str]) -> tuple[Action, Path, int, dict[str, Any]]:
    """Parse the provided command-line options to determine the action to perform and
    the arguments to pass to the action

    Parameters
    ----------
    argv : list-like of str (sys.argv)
        The options passed into the command line

    Returns
    -------
    Callable
        The action method that will be called
    str
        The root of the minecraft folder (parent of the EnderChest)
        where the action will be performed
    int
        The verbosity level of the operation (in terms of log levels)
    dict
        Any additional options that will be given to the action method

    """
    actions: dict[str, Action] = {}
    aliases: dict[str, str] = {}
    for commands, _, method in ACTIONS:
        for command in commands:
            aliases[command] = commands[0]
        actions[commands[0]] = method

    enderchest_parser, action_parsers = generate_parsers()

    _ = enderchest_parser.parse_args(argv[1:2])  # check for --help and --version

    for command in sorted(aliases.keys(), key=lambda x: -len(x)):  # longest first
        if " ".join((*argv[1:], "")).startswith(command + " "):
            if command == "test":
                parsed, extra = action_parsers["test"].parse_known_args(argv[2:])
                return (
                    actions["test"],
                    Path(),
                    0,
                    {
                        "use_local_ssh": parsed.use_local_ssh,
                        "pytest_args": [*parsed.pytest_args, *extra],
                    },
                )
            action_kwargs = vars(
                action_parsers[aliases[command]].parse_args(
                    argv[1 + len(command.split()) :]
                )
            )

            action = actions[aliases[command]]

            root_arg = action_kwargs.pop("root")
            root_flag = action_kwargs.pop("root_flag")

            verbosity = action_kwargs.pop("verbose") - action_kwargs.pop("quiet")

            argspec = inspect.getfullargspec(action)
            if "verbosity" in argspec.args + argspec.kwonlyargs:
                action_kwargs["verbosity"] = verbosity

            log_level = loggers.verbosity_to_log_level(verbosity)

            MINECRAFT_ROOT = os.getenv("MINECRAFT_ROOT")

            return (
                actions[aliases[command]],
                Path(root_arg or root_flag or MINECRAFT_ROOT or os.getcwd()),
                log_level,
                action_kwargs,
            )

    enderchest_parser.print_help(sys.stderr)
    sys.exit(1)


def main():
    """CLI Entrypoint"""
    logger = logging.getLogger(__package__)
    cli_handler = logging.StreamHandler()
    cli_handler.setFormatter(loggers.CLIFormatter())
    logger.addHandler(cli_handler)

    action, root, log_level, kwargs = parse_args(sys.argv)

    # TODO: set log levels per logger based on the command
    cli_handler.setLevel(log_level)

    # TODO: when we add log files, set this to minimum log level across all handlers
    logger.setLevel(log_level)

    action(root, **kwargs)
