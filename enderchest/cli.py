"""Command-line interface"""
import argparse
import os
import sys
from pathlib import Path
from typing import Any, Protocol, Sequence

from . import __version__
from .craft import craft_ender_chest, craft_ender_chest_from_config
from .place import place_enderchest
from .sync import Remote


class _Action(Protocol):
    def __call__(self, root: str | os.PathLike, /) -> None:
        ...


def _dispatch_craft(root: str | os.PathLike, **kwargs) -> None:
    """Call the correct craft command based on the arguments passed"""
    if config_path := kwargs.pop("config_file", None):
        craft_ender_chest_from_config(config_path)
    else:
        remotes = [Remote.from_string(spec) for spec in kwargs.pop("remotes", [])]
        craft_ender_chest(root, *remotes, **kwargs)


ACTIONS: tuple[tuple[str, str, _Action], ...] = (
    # action name, action description, action method
    (
        "craft",
        "initialize the EnderChest folder structure and sync scripts",
        _dispatch_craft,
    ),
    (
        "place",
        "create/update the links into the EnderChest folder from your"
        " instances and servers",
        place_enderchest,
    ),
)


def parse_args(argv: Sequence[str]) -> tuple[_Action, str, dict[str, Any]]:
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
        where the action will be perfomed
    dict
        Any additional options that will be given to the action method

    """
    actions: dict[str, _Action] = {}
    descriptions: dict[str, str] = {}
    root_description: str = ""
    for name, description, method in ACTIONS:
        actions[name] = method
        descriptions[name] = description
        root_description += f"\n\t{name}: to {description}"

    enderchest_parser = argparse.ArgumentParser(
        prog="enderchest",
        description=(
            f"v{__version__}\n" "\nsyncing and linking for all your Minecraft instances"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    enderchest_parser.add_argument(
        "action",
        help=f"the action to perform. Options are:{root_description}",
        type=str,
        choices=actions.keys(),
    )
    enderchest_parser.add_argument(
        "arguments",
        nargs="*",
        help="any additional arguments for the specific action."
        " To learn more, try: enderchest {action} -h",
    )

    action_parsers: dict[str, argparse.ArgumentParser] = {}
    for command in actions.keys():
        parser = argparse.ArgumentParser(
            prog=f"enderchest {command}", description=descriptions[command]
        )
        parser.add_argument(
            "root",
            nargs="?",
            help=(
                "optionally specify your root minecraft directory. If no path is given,"
                " the current working directory will be used."
            ),
            type=Path,
            default=Path(os.getcwd()),
        )
        action_parsers[command] = parser

    action_parsers["craft"].add_argument(
        "-r",
        "--remote",
        dest="remotes",
        action="append",
        help="specify a remote enderchest installation using the syntax"
        " [user@]addreess:/path/to/enderchest",
    )

    action_parsers["craft"].add_argument(
        "-f",
        "--file",
        dest="config_file",
        action="store",
        type=Path,
        help="parse the enderchest installations to sync with from"
        " the specified config file",
    )

    action_parsers["craft"].add_argument(
        "--overwrite",
        action="store_true",
        help="overwrite any existing sync scripts",
    )

    action_parsers["place"].add_argument(
        "-k",
        "--keep-broken",
        action="store_true",
        dest="cleanup",
        help="do not remove broken links when performing place",
    )
    root_args = enderchest_parser.parse_args(argv[1:2])
    action: _Action = actions[root_args.action]
    action_kwargs = vars(action_parsers[root_args.action].parse_args(argv[2:]))
    root = action_kwargs.pop("root")

    return action, root, action_kwargs


def main():
    action, root, kwargs = parse_args(sys.argv)
    action(root, **kwargs)
