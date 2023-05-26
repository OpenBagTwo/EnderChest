"""Command-line interface"""
import logging
import os
import sys
from argparse import ArgumentParser, RawTextHelpFormatter
from pathlib import Path
from typing import Any, Protocol, Sequence

from . import craft, gather, loggers, place, remote
from ._version import get_versions

# mainly because I think I'm gonna forget what names are canonical (it's the first ones)
_create_aliases = ("craft", "create")
_instance_aliases = tuple(
    alias + plural for alias in ("minecraft", "instance") for plural in ("s", "")
)
_shulker_aliases = ("shulker_box", "shulkerbox", "shulker")
_remote_aliases = tuple(
    alias + plural for alias in ("enderchest", "remote") for plural in ("s", "")
)
_list_aliases = ("inventory", "list")


def _place(
    minecraft_root: Path,
    errors: str = "prompt",
    cleanup: bool = False,
    stop_at_first_failure: bool = False,
    ignore_errors: bool = False,
) -> None:
    """Wrapper to coalesce error-handling flags"""

    if stop_at_first_failure:
        errors = "abort"
    if ignore_errors:  # elif?
        errors = "ignore"
    # else: errors = errors
    place.place_ender_chest(minecraft_root, cleanup=cleanup, error_handling=errors)


def _craft_shulker_box(minecraft_root: Path, name: str | None = None, **kwargs):
    """Wrapper to handle the fact that name is a required argument"""
    assert name  # it's required by the parser, so this should be fine
    craft.craft_shulker_box(minecraft_root, name, **kwargs)


def _list_shulker_box(
    minecraft_root: Path, shulker_box_name: str | None = None, **kwargs
):
    """Wrapper to handle the fact that name is a required argument"""
    assert shulker_box_name  # it's required by the parser, so this should be fine
    gather.load_shulker_box_matches(minecraft_root, shulker_box_name, **kwargs)


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


def _open(minecraft_root, **kwargs):
    """Router for open verb"""
    remote.sync_with_remotes(minecraft_root, "pull", **kwargs)


def _close(minecraft_root, **kwargs):
    """Router for close verb"""
    remote.sync_with_remotes(minecraft_root, "push", **kwargs)


class Action(Protocol):
    def __call__(self, minecraft_root: Path, /) -> Any:
        ...


ACTIONS: tuple[tuple[tuple[str, ...], str, Action], ...] = (
    # action names (first one is canonical), action description, action method
    (
        sum(((verb, verb + " enderchest") for verb in _create_aliases), ()),
        "create and configure a new EnderChest installation",
        craft.craft_ender_chest,
    ),
    (
        tuple(
            f"{verb} {alias}" for verb in _create_aliases for alias in _shulker_aliases
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
        ("gather",) + tuple("gather " + alias for alias in _instance_aliases),
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
                (verb, *(f"{verb} {alias}" for alias in _instance_aliases))
                for verb in _list_aliases
            ),
            (),
        ),
        "list the minecraft instances registered with your Enderchest",
        gather.load_ender_chest_instances,
    ),
    (
        tuple(
            f"{verb} {alias}"
            for verb in _list_aliases
            # pluralization is hard
            for alias in ("shulker_boxes", "shulkerboxes", "shulkers")
        ),
        "list the shulker boxes inside your Enderchest",
        gather.load_shulker_boxes,
    ),
    (
        tuple(
            f"{verb} {alias}" for verb in _list_aliases for alias in _shulker_aliases
        ),
        "list the instances that match the specified shulker box",
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
    for commands, description, method in ACTIONS:
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
        "--version",
        action="version",
        version=f"%(prog)s v{get_versions()['version']}",
    )

    # these are really just for the sake of --help
    # (the parsed args aren't actually used)
    enderchest_parser.add_argument(
        "action",
        help=f"the action to perform. Options are:{root_description}",
        type=str,
    )
    enderchest_parser.add_argument(
        "arguments",
        nargs="*",
        help="any additional arguments for the specific action."
        " To learn more, try: enderchest {action} -h",
    )

    action_parsers: dict[str, ArgumentParser] = {}
    for verb, description in descriptions.items():
        parser = ArgumentParser(
            prog=f"enderchest {verb}",
            description=description,
        )
        root = parser.add_mutually_exclusive_group()
        root.add_argument(
            "root",
            nargs="?",
            help=(
                "optionally specify your root minecraft directory."
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
    shulker_craft_parser = action_parsers[f"{_create_aliases[0]} {_shulker_aliases[0]}"]
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
    place_parser.add_argument(
        "-k",
        "--keep-broken-links",
        action="store_false",
        dest="cleanup",
        help="do not remove broken links from instances",
    )
    error_handling = place_parser.add_mutually_exclusive_group()
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
        help="specify how to handle linking errors (default behavior is to prompt after every error)",
    )

    # gather instance options
    gather_instance_parser = action_parsers[f"gather"]
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
            "provide URIs (e.g. rsync://deck@my-steam-deck/home/deck/) of any"
            " remote EnderChest installation to register with this one."
            "Note: you should not use this method if the alias (name) of the"
            "remote does not match the remote's hostname (in this example,"
            '"my-steam-deck").'
        ),
    )

    # list instances options

    # list shulkers options

    # list shulker options
    list_shulker_parser = action_parsers[f"{_list_aliases[0]} {_shulker_aliases[0]}"]
    list_shulker_parser.add_argument(
        "shulker_box_name", help="The name of the shulker box to query"
    )

    # open / close options
    for action in ("open", "close"):
        sync_parser = action_parsers[action]

        sync_parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Perform a dry run of the sync operation,"
                " reporting the operations that will be performed"
                " but not actually carrying them out"
            ),
        )
        sync_parser.add_argument(
            "--exclude",
            "-e",
            nargs="+",
            help="Provide any file patterns you would like to skip syncing",
        )
        sync_parser.add_argument(
            "--timeout",
            "-t",
            type=int,
            help=(
                "Set a maximum number of seconds to try to sync to a remote chest"
                " before giving up and going on to the next one"
            ),
        )
        sync_confirm_wait = sync_parser.add_mutually_exclusive_group()
        sync_confirm_wait.add_argument(
            "--wait",
            "-w",
            dest="sync_confirm_wait",
            type=int,
            help=(
                "The default behavior when syncing EnderChests is to first perform a"
                " dry run of every sync operation and then wait 5 seconds before"
                " proceeding with the real sync. The idea is to give you time to"
                " interrupt the sync if the dry run looks wrong. You can raise or"
                " lower that wait time through this flag. You can also modify it"
                " by editing the enderchest.cfg file."
            ),
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
    for commands, description, method in ACTIONS:
        for command in commands:
            aliases[command] = commands[0]
        actions[commands[0]] = method

    enderchest_parser, action_parsers = generate_parsers()

    _ = enderchest_parser.parse_args(argv[1:2])  # check for --help and --version

    for command in sorted(aliases.keys(), key=lambda x: -len(x)):  # longest first
        if " ".join((*argv[1:], "")).startswith(command + " "):
            action_kwargs = vars(
                action_parsers[aliases[command]].parse_args(
                    argv[1 + len(command.split()) :]
                )
            )
            root_arg = action_kwargs.pop("root")
            root_flag = action_kwargs.pop("root_flag")

            verbosity = action_kwargs.pop("verbose") - action_kwargs.pop("quiet")

            log_level = logging.INFO - 10 * verbosity
            if log_level == logging.NOTSET:  # that's 0, annoyingly enough
                log_level -= 1

            return (
                actions[aliases[command]],
                Path(root_arg or root_flag or os.getcwd()),
                log_level,
                action_kwargs,
            )
    else:
        enderchest_parser.print_help(sys.stderr)
        sys.exit(1)


def main():
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
