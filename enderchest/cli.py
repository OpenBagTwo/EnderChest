"""Command-line interface"""
import argparse
import os
import shlex
import shutil
import subprocess
import sys
from functools import partial
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


def _dispatch_open_and_close(
    root: str | os.PathLike, action: str, command_line_args: list[str]
) -> None:
    """Run the open / close script"""
    if action == "open":
        command = "./EnderChest/local-only/open.sh"
    elif action == "close":
        command = "./EnderChest/local-only/close.sh"
    else:
        raise ValueError(f"Unrecognized action {action}")
    _run_bash(root, command, *command_line_args)


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
    (
        "open",
        "pull changes from other EnderChests",
        partial(_dispatch_open_and_close, action="open"),
    ),
    (
        "close",
        "push changes to other EnderChests",
        partial(_dispatch_open_and_close, action="close"),
    ),
)


def _run_bash(
    root: str | os.PathLike, *args: Any, **subproccess_kwargs
) -> subprocess.CompletedProcess[str]:
    """Run a bash command

    Parameters
    ----------
    root : path-like
        The working directory in which the command should be run
    *args : Any
        The command to run and any additional command-line flags to pass through
    **subprocess_kwargs
        Any keyword arguments to pass to subprocess.run

    Returns
    -------
    None

    Notes
    -----
    The commands will be executed in a subshell as the current user and should source
    any `.bashrc` / `.bash_profile` files that would usually be sourced upon starting
    a new shell

    The intention of allowing subprocess kwargs and returning the process is that it
    turns out this method is really useful for writing OS-agnostic CLI tests!
    """
    bash = shutil.which("bash")
    if bash is None:
        raise RuntimeError("This command requires bash to run. Please install bash.")

    command = " ".join((shlex.quote(str(arg)) for arg in args))
    return subprocess.run(
        [bash, "-c", command],
        cwd=Path(root).expanduser().resolve(),
        **subproccess_kwargs,
    )


class PassThroughParser:
    """Command-line argument parser that just collects any (non --help) flags
    into a list of arguments"""

    def __init__(self, **argparse_kwargs):
        self._parser = argparse.ArgumentParser(**argparse_kwargs)

    def add_argument(self, *args, **kwargs):
        self._parser.add_argument(*args, **kwargs)

    def parse_args(self, args) -> argparse.Namespace:
        if "-h" in args or "--help" in args:
            return self._parser.parse_args(["--help"])

        root: Path | None = None
        if len(args) > 0 and not args[0].startswith("-"):
            try:
                root = Path(args[0])
                args = args[1:]
            except (TypeError, AttributeError):
                # then hopefully it wasn't intended to be a path
                pass

        root = root or Path(os.getcwd())
        dummy_namespace = argparse.Namespace()
        dummy_namespace.__dict__ = {"root": root, "command_line_args": args}
        return dummy_namespace


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

    action_parsers: dict[str, argparse.ArgumentParser | PassThroughParser] = {}
    for command in actions.keys():
        if command in ("open", "close"):
            parser: argparse.ArgumentParser | PassThroughParser = PassThroughParser(
                prog=f"enderchest {command}", description=descriptions[command]
            )
        else:
            parser = argparse.ArgumentParser(
                prog=f"enderchest {command}", description=descriptions[command]
            )
        parser.add_argument(
            "root",
            nargs="?",
            help=(
                "optionally specify your root minecraft directory."
                "  If no path is given, the current working directory will be used."
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
        action="store_false",
        dest="cleanup",
        help="do not remove broken links when performing place",
    )

    for command in ("open", "close"):
        action_parsers[command].add_argument(
            "command_line_args",
            nargs="*",
            help="any additional arguments to pass through to the script",
        )

    root_args = enderchest_parser.parse_args(argv[1:2])
    action: _Action = actions[root_args.action]
    action_kwargs = vars(action_parsers[root_args.action].parse_args(argv[2:]))
    root = action_kwargs.pop("root")
    return action, root, action_kwargs


def main():
    action, root, kwargs = parse_args(sys.argv)
    action(root, **kwargs)
