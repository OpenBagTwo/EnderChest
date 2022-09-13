"""Command-line interface"""
import argparse
import os
from pathlib import Path
from typing import Callable

from . import __version__
from .craft import craft_ender_chest
from .place import place_enderchest

_Action = Callable[[str | os.PathLike], None]


ACTIONS: tuple[tuple[str, str, _Action], ...] = (
    # action name, action description, action method
    ("craft", "initialize the EnderChest folder structure", craft_ender_chest),
    ("place", "create or update the symlinks", place_enderchest),
)


def parse_args(argv=None) -> tuple[_Action, Path]:

    actions: dict[str, _Action] = {}
    descriptions: str = ""
    for name, description, method in ACTIONS:
        actions[name] = method
        descriptions += f"\n\t{name}: to {description}"

    parser = argparse.ArgumentParser(
        prog=f"enderchest",
        description=f"v{__version__}\n\nsyncing and linking for all your Minecraft instances",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "action",
        help=f"the action to perform. Options are:{descriptions}",
        type=str,
        choices=actions.keys(),
    )
    parser.add_argument(
        "root",
        nargs="?",
        help=(
            "optionally specify your root minecraft directory. If no path is given,"
            " the current working directory will be used."
        ),
        type=str,
        default=os.getcwd(),
    )
    args = parser.parse_args(argv)
    return actions[args.action], Path(args.root)


def main():
    action, root = parse_args()
    action(root)
