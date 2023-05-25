"""shutil-based sync implementation"""
import logging
import shutil
from pathlib import Path
from urllib.parse import ParseResult

from . import SYNC_LOGGER


def copy(source_path: Path, destination_folder: Path, dry_run: bool) -> None:
    """Copy the specified source file or folder to the provided destination,
    overwriting any existing files

    Parameters
    ----------
    source_path : ParseResult
        The file or folder to copy
    destination_folder : Path
        The destination to put the source file(s)
    dry_run : bool
        If `dry_run=True` is passed in, the sync won't actually be performed,
        and instead the operations that would have been carried out will be
        reported at the INFO level (instead of the DEBUG level)

    """
    log_level = logging.INFO if dry_run else logging.DEBUG

    destination_path = destination_folder / source_path.name
    if destination_path.exists():
        if destination_path.is_symlink():
            SYNC_LOGGER.log(log_level, f"Removing symlink {destination_path}")
            if not dry_run:
                destination_path.unlink()
        elif destination_path.is_file():
            SYNC_LOGGER.log(log_level, f"Deleting {destination_path}")
            if not dry_run:
                destination_path.unlink()
        else:  # it's gotta be a dir, right?
            SYNC_LOGGER.log(log_level, f"Deleting {destination_path} and its contents")
            if not dry_run:
                shutil.rmtree(destination_path)

    if source_path.exists():
        SYNC_LOGGER.log(log_level, f"Copying {source_path} to {destination_folder}")
        if not dry_run:
            if source_path.is_dir():
                shutil.copytree(source_path, destination_folder, symlinks=True)
            else:
                shutil.copy(source_path, destination_folder, follow_symlinks=False)


def pull(remote_uri: ParseResult, local_path: Path, dry_run: bool = False) -> None:
    """Copy an upstream file or folder into the specified location, where the remote
    is another folder on this machine. This will overwrite any files and folders
    already at the destination.

    Parameters
    ----------
    remote_uri : ParseResult
        The URI for the remote resource to copy from. See notes.
    local_path : Path
        The destination folder
    dry_run : bool, optional
         If `dry_run=True` is passed in, the sync won't actually be performed,
         and instead the operations that would have been carried out will be
         reported at the INFO level (instead of the DEBUG level)

    Raises
    ------
    FileNotFoundError
        If either the source path or the destination folder do not exist

    Notes
    -----
    - This method is only meant to be used for local files specified using
      the file:// protocol, but it does not perform any validation on the URI to
      ensure that the schema is correct or that the hostname corresponds to this
      machine. This method does not support user authentication
      (running the copy as a different user).
    - If the destination folder does not already exist, this method wil not
      create it or its parent directories.
    """
    source_path = Path(remote_uri.path).expanduser()
    destination_folder = local_path

    if not destination_folder.exists():
        raise FileNotFoundError(f"{local_path} does not exist")
    if not source_path.exists():
        raise FileNotFoundError(f"{remote_uri.geturl()} does not exist")

    copy(source_path, destination_folder, dry_run)


def push(local_path: Path, remote_uri: ParseResult, dry_run=False) -> None:
    """Copy a local file or folder into the specified location, where the remote
    is another folder on this machine. This will overwrite any files and folders
    already at the destination.

    Parameters
    ----------
    local_path : Path
        The file or folder to copy
    remote_uri : ParseResult
        The URI for the remote location to copy into. See notes.
    dry_run : bool, optional
         If `dry_run=True` is passed in, the sync won't actually be performed,
         and instead the operations that would have been carried out will be
         reported at the INFO level (instead of the DEBUG level)

     Raises
    ------
    FileNotFoundError
        If either the source path or the destination folder do not exist

    Notes
    -----
    - This method is only meant to be used for local files specified using
      the file:// protocol, but it does not perform any validation on the URI to
      ensure that the schema is correct or that the hostname corresponds to this
      machine. This method does not support user authentication
      (running the copy as a different user).
    - If the destination folder does not already exist, this method wil not
      create it or its parent directories.
    """
    source_path = local_path
    destination_folder = Path(remote_uri.path).expanduser()

    if not destination_folder.exists():
        raise FileNotFoundError(f"{remote_uri.geturl()} does not exist")
    if not source_path.exists():
        raise FileNotFoundError(f"{local_path} does not exist")

    copy(source_path, destination_folder, dry_run)
