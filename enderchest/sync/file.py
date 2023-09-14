"""shutil-based sync implementation"""
import fnmatch
import logging
import os
import shutil
import stat
from pathlib import Path
from typing import Callable, Collection
from urllib.parse import ParseResult

from . import (
    SYNC_LOGGER,
    Op,
    abspath_from_uri,
    diff,
    filter_contents,
    generate_sync_report,
    is_identical,
)


def get_contents(path: Path) -> list[tuple[Path, os.stat_result]]:
    """Recursively list the contents of a local directory

    Parameters
    ----------
    path : Path
        The path to scan

    Returns
    -------
    list of filenames and attributes
        The attributes of all files, folders and symlinks found under the
        specified path

    Notes
    -----
    - This list will be sorted from shortest path to longest (so that parent
      directories come before their children)
    - The paths returned are all relative to the provided path
    """
    SYNC_LOGGER.debug(f"Getting contents of {path}")
    return sorted(
        ((p.relative_to(path), p.lstat()) for p in path.rglob("**/*")),
        key=lambda x: len(str(x[0])),
    )


def copy(
    source_path: Path,
    destination_folder: Path,
    exclude: Collection[str],
    delete: bool,
    dry_run: bool,
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
    delete : bool
        Whether part of the syncing should include deleting files at the destination
        that aren't at the source.
    dry_run : bool
        Whether to only simulate this sync (report the operations to be performed
        but not actually perform them)

    Notes
    -----
    If the source file does not exist, the destination file will simply be deleted
    (if it exists)
    """

    ignore = ignore_patterns(*exclude)
    SYNC_LOGGER.debug(f"Ignoring patterns: {exclude}")

    destination_path = destination_folder / source_path.name
    if destination_path.is_symlink() and not destination_path.is_dir():
        SYNC_LOGGER.warning("Removing symlink %s", destination_path)
        if not dry_run:
            destination_path.unlink()
        else:
            SYNC_LOGGER.debug("And replacing it entirely with %s", source_path)
            return
    elif destination_path.exists() and not destination_path.is_dir():
        SYNC_LOGGER.warning("Deleting file %s", destination_path)
        if not dry_run:
            destination_path.unlink()
        else:
            SYNC_LOGGER.debug("And replacing it entirely with %s", source_path)
            return
    else:
        if not dry_run:
            destination_folder.mkdir(parents=True, exist_ok=True)

    SYNC_LOGGER.debug(f"Copying {source_path} into {destination_folder}")

    if source_path.exists() and not source_path.is_dir():
        if destination_path.exists() and is_identical(
            source_path.stat(), destination_path.stat()
        ):
            SYNC_LOGGER.warning(
                "%s and %s are identical. No copy needed.",
                source_path,
                destination_path,
            )
            return
        SYNC_LOGGER.debug(
            "Copying file %s to %s",
            source_path,
            destination_path,
        )
        if not dry_run:
            shutil.copy2(source_path, destination_path, follow_symlinks=False)
        return

    source_contents = filter_contents(
        get_contents(source_path), exclude, prefix=source_path
    )
    destination_contents = filter_contents(
        get_contents(destination_path), exclude, prefix=destination_path
    )

    sync_diff = diff(source_contents, destination_contents)

    if dry_run:
        generate_sync_report(sync_diff)
        return

    for path, path_stat, operation in sync_diff:
        match (operation, stat.S_ISDIR(path_stat.st_mode or 0)):
            case (Op.CREATE, True):
                SYNC_LOGGER.debug("Creating directory %s", destination_path / path)
                (destination_path / path).mkdir(parents=True, exist_ok=True)
            case (Op.CREATE, False) | (Op.REPLACE, False):
                SYNC_LOGGER.debug(
                    "Copying file %s to %s",
                    source_path / path,
                    destination_path / path,
                )
                (destination_path / path).unlink(missing_ok=True)
                if (source_path / path).is_symlink():
                    (destination_path / path).symlink_to(
                        (source_path / path).readlink()
                    )
                else:
                    shutil.copy2(
                        source_path / path,
                        destination_path / path,
                        follow_symlinks=False,
                    )
            case (Op.REPLACE, True):
                # this would be replacing a file with a directory
                SYNC_LOGGER.debug("Deleting file %s", destination_path / path)
                (destination_path / path).unlink()
                SYNC_LOGGER.debug(
                    "Copying directory %s to %s",
                    source_path / path,
                    destination_path / path,
                )
                shutil.copytree(
                    source_path / path,
                    destination_path / path,
                    symlinks=True,
                    ignore=ignore,
                    dirs_exist_ok=True,
                )
            case (Op.DELETE, True):
                # recall that for deletions, it's the *destination's* stats
                if delete:
                    clean(destination_path / path, ignore, dry_run)
            case (Op.DELETE, False):
                if delete:
                    SYNC_LOGGER.debug("Deleting file %s", destination_path / path)
                    (destination_path / path).unlink()
            case op, is_dir:  # pragma: no cover
                raise NotImplementedError(
                    f"Don't know how to handle {op} of {'directory' if is_dir else 'file'}"
                )


def clean(
    root: Path,
    ignore: Callable[[str, Collection[str]], set[str]],
    dry_run: bool,
) -> None:
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


def ignore_patterns(*patterns: str) -> Callable[[str, Collection[str]], set[str]]:
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
    exclude: Collection[str],
    dry_run: bool,
    delete: bool = True,
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
    delete : bool, optional
        Whether part of the syncing should include deleting files at the destination
        that aren't at the source. Default is True.
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
    source_path = abspath_from_uri(remote_uri).expanduser()
    destination_folder = local_path

    if not destination_folder.exists():
        raise FileNotFoundError(f"{local_path} does not exist")
    if not source_path.exists():
        raise FileNotFoundError(f"{remote_uri.geturl()} does not exist")
    if unsupported_kwargs:
        SYNC_LOGGER.debug(
            "The following command-line options are ignored for this protocol:\n%s",
            "\n".join("  {}: {}".format(*item) for item in unsupported_kwargs.items()),
        )

    copy(source_path, destination_folder, exclude, delete=delete, dry_run=dry_run)


def push(
    local_path: Path,
    remote_uri: ParseResult,
    exclude: Collection[str],
    dry_run: bool,
    delete: bool = True,
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
    delete : bool, optional
        Whether part of the syncing should include deleting files at the destination
        that aren't at the source. Default is True.
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
    destination_folder = abspath_from_uri(remote_uri).expanduser()

    if not destination_folder.exists():
        raise FileNotFoundError(f"{remote_uri.geturl()} does not exist")
    if not source_path.exists():
        raise FileNotFoundError(f"{source_path} does not exist")
    if unsupported_kwargs:
        SYNC_LOGGER.debug(
            "The following command-line options are ignored for this protocol:\n%s",
            "\n".join("  {}: {}".format(*item) for item in unsupported_kwargs.items()),
        )

    copy(source_path, destination_folder, exclude, delete=delete, dry_run=dry_run)
