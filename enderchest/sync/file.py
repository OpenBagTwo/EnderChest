"""shutil-based sync implementation"""
import fnmatch
import logging
import os
import shutil
from pathlib import Path
from typing import Collection, Iterable
from urllib.parse import ParseResult

from . import SYNC_LOGGER, path_from_uri


def copy(
    source_path: Path, destination_folder: Path, exclude: Iterable[str], dry_run: bool
) -> None:
    """Copy the specified source file or folder to the provided destination,
    overwriting any existing files and deleting any that weren't in the source

    Parameters
    ----------
    source_path : ParseResult
        The file or folder to copy
    destination_folder : Path
        The destination to put the source file(s)
    exclude : list of str
        Any patterns that should be excluded from the sync (and sync)
    dry_run : bool
        Whether to only simulate this sync (report the operations to be performed
        but not actually perform them)

    Notes
    -----
    If the source file does not exist, the destination file will simply be deleted
    (if it exists)
    """
    log_level = logging.INFO if dry_run else logging.DEBUG

    ignore = ignore_patterns(*exclude)
    SYNC_LOGGER.debug(f"Ignoring patterns: {exclude}")

    destination_path = destination_folder / source_path.name
    if destination_path.exists():
        if destination_path.is_symlink():
            SYNC_LOGGER.log(log_level, "Removing symlink %s", destination_path)
            if not dry_run:
                destination_path.unlink()
        elif destination_path.is_dir():
            clean(destination_path, ignore, dry_run)
        else:
            SYNC_LOGGER.log(log_level, "Deleting %s", destination_path)
            if not dry_run:
                destination_path.unlink()

    if source_path.exists():
        SYNC_LOGGER.log(log_level, f"Copying {source_path} into {destination_folder}")
        if not dry_run:
            if source_path.is_dir():
                shutil.copytree(
                    source_path,
                    destination_path,
                    symlinks=True,
                    ignore=ignore,
                    dirs_exist_ok=True,
                )
            else:
                shutil.copy(source_path, destination_path, follow_symlinks=False)


def clean(root: Path, ignore, dry_run: bool) -> None:
    """Recursively remove all files and symlinks from the root path while
    respecting the provided ignore pattern

    Parameters
    ----------
    root : Path
        The root directory. And this should absolutely be a directory.
    ignore : Callable
        The ignore pattern created by `ignore_pattern` that specifies
        which files to ignore.
    dry_run : bool
        Whether to only simulate this sync (report the operations to be performed
        but not actually perform them)
    """
    log_level = logging.INFO if dry_run else logging.DEBUG
    contents = list(root.iterdir())
    ignore_me = ignore(
        os.fspath(root),
        [path.name for path in contents],
    )

    for path in contents:
        if path.name in ignore_me:
            SYNC_LOGGER.debug(f"Skipping {path}")
            continue
        if path.is_symlink():
            SYNC_LOGGER.log(log_level, f"Removing symlink {path}")
            if not dry_run:
                path.unlink()
        elif path.is_dir():
            clean(path, ignore, dry_run)
        else:
            SYNC_LOGGER.log(log_level, f"Deleting {path}")
            if not dry_run:
                path.unlink()

    # check if folder is now empty
    if not list(root.iterdir()):
        SYNC_LOGGER.log(log_level, f"Removing empty {root}")
        if not dry_run:
            root.rmdir()


def ignore_patterns(*patterns: str):
    """shutil.ignore_patterns doesn't support checking absolute paths,
    so we gotta roll our own.

    This implementation is adapted from
    https://github.com/python/cpython/blob/3.11/Lib/shutil.py#L440-L450 and
    https://stackoverflow.com/a/7842224

    Parameters
    ----------
    *patterns : str
        The patterns to match

    Returns
    -------
    Callable
        An "ignore" filter suitable for use in `shutil.copytree`
    """

    def _ignore_patterns(path: str, names: Collection[str]) -> set[str]:
        ignored_names: set[str] = set()
        for pattern in patterns:
            path_parts: list[str] = os.path.normpath(path).split(os.sep)
            pattern_depth = len(os.path.normpath(pattern).split(os.sep)) - 1
            if pattern_depth == 0:
                match_paths: Collection[str] = names
            else:
                match_paths = [
                    os.path.join(*path_parts[-pattern_depth:], name) for name in names
                ]
            ignored_names.update(
                os.path.split(match)[-1]
                for match in fnmatch.filter(match_paths, pattern)
            )
        return ignored_names

    return _ignore_patterns


def pull(
    remote_uri: ParseResult,
    local_path: Path,
    exclude: Iterable[str],
    dry_run: bool,
    **unsupported_kwargs,
) -> None:
    """Copy an upstream file or folder into the specified location, where the remote
    is another folder on this machine. This will overwrite any files and folders
    already at the destination.

    Parameters
    ----------
    remote_uri : ParseResult
        The URI for the remote resource to copy from. See notes.
    local_path : Path
        The destination folder
    exclude : list of str
        Any patterns that should be excluded from the sync
    dry_run : bool
        Whether to only simulate this sync (report the operations to be performed
        but not actually perform them)
    **unsupported_kwargs
        Any other provided options will be ignored

    Raises
    ------
    FileNotFoundError
        If the destination folder does not exist

    Notes
    -----
    - This method is only meant to be used for local files specified using
      the file:// protocol, but it does not perform any validation on the URI to
      ensure that the schema is correct or that the hostname corresponds to this
      machine. This method does not support user authentication
      (running the copy as a different user).
    - If the destination folder does not already exist, this method will not
      create it or its parent directories.
    """
    source_path = path_from_uri(remote_uri).expanduser()
    destination_folder = local_path

    if not destination_folder.exists():
        raise FileNotFoundError(f"{local_path} does not exist")
    if not source_path.exists():
        SYNC_LOGGER.warning(
            f"{source_path} does not exist"
            " this will end up just deleting the local copy."
        )
    if unsupported_kwargs:
        SYNC_LOGGER.debug(
            "The following command-line options are ignored for this protocol:\n%s",
            "\n".join("  {}: {}".format(*item) for item in unsupported_kwargs.items()),
        )

    copy(source_path, destination_folder, exclude, dry_run)


def push(
    local_path: Path,
    remote_uri: ParseResult,
    exclude: Iterable[str],
    dry_run: bool,
    **unsupported_kwargs,
) -> None:
    """Copy a local file or folder into the specified location, where the remote
    is another folder on this machine. This will overwrite any files and folders
    already at the destination.

    Parameters
    ----------
    local_path : Path
        The file or folder to copy
    remote_uri : ParseResult
        The URI for the remote location to copy into. See notes.
    exclude : list of str
        Any patterns that should be excluded from the sync
    dry_run : bool
        Whether to only simulate this sync (report the operations to be performed
        but not actually perform them)
    **unsupported_kwargs
        Any other provided options will be ignored

    Raises
    ------
    FileNotFoundError
        If the destination folder does not exist

    Notes
    -----
    - This method is only meant to be used for local files specified using
      the file:// protocol, but it does not perform any validation on the URI to
      ensure that the schema is correct or that the hostname corresponds to this
      machine. This method does not support user authentication
      (running the copy as a different user).
    - If the destination folder does not already exist, this method will not
      create it or its parent directories.
    """
    source_path = local_path
    destination_folder = path_from_uri(remote_uri).expanduser()

    if not destination_folder.exists():
        raise FileNotFoundError(f"{remote_uri.geturl()} does not exist")
    if not source_path.exists():
        SYNC_LOGGER.warning(
            f"{source_path} does not exist:"
            " this will end up just deleting the remote copy."
        )
    if unsupported_kwargs:
        SYNC_LOGGER.debug(
            "The following command-line options are ignored for this protocol:\n%s",
            "\n".join("  {}: {}".format(*item) for item in unsupported_kwargs.items()),
        )

    copy(source_path, destination_folder, exclude, dry_run)
