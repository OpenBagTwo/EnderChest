"""rsync sync implementation. Relies on the user having rsync installed on their system"""
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Iterable
from urllib.parse import ParseResult

from . import SYNC_LOGGER, get_default_netloc, path_from_uri

RSYNC = shutil.which("rsync")
if RSYNC is None:
    raise RuntimeError("No rsync executable found on your system. Cannot sync using.")


def run_rsync(
    working_directory: Path,
    source: str,
    destination_folder: str,
    delete: bool,
    dry_run: bool,
    exclude: Iterable[str],
    *additional_args: str,
    timeout: int | None = None,
    rsync_flags: str | None = None,
) -> None:
    """Run an operation with rsync

    Parameters
    ----------
    working_directory : Path
        The working directory to run the sync command from
    source : str
        The source file or folder to sync, specified as either a URI string,
        an ssh address or a path relative to the working directory
    destination_folder : str
        The destination folder where the file or folder should be synced to,
        with the same formats available as for source
    delete : bool
        Whether part of the syncing should include deleting files at the destination
        that aren't at the source
    dry_run : bool
        Whether to only simulate this sync (report the operations to be performed
        but not actually perform them)
    exclude : list of str
        Any patterns that should be excluded from the sync (and sync)
    *additional_args : str
        Any additional arguments to pass into the rsync command
    timeout : int, optional
        The number of seconds to wait before timing out the sync operation.
        If None is provided, no explicit timeout value will be set.
    rsync_flags : str, optional
        By default, rsync will be run using the flags "avzs" which means:

          - archive mode
          - verbose
          - use compression
          - no space splitting

        Advanced users may choose to override these options, but **you do so
        at your own peril**.

    Notes
    -----
    This method does not perform any validation or normalization of the source,
    destination, exclude-list, additional arguments or rsync options.
    """
    rsync_flags = rsync_flags or "avzs"
    log_level = logging.INFO if dry_run else logging.DEBUG

    args: list[str] = [RSYNC, f"-{rsync_flags}"]  # type: ignore[list-item]
    if delete:
        args.append("--delete")
    if dry_run:
        args.append("--dry-run")
    for pattern in exclude:
        args.extend(("--exclude", pattern))
    args.extend(additional_args)
    args.extend((source, destination_folder))

    SYNC_LOGGER.log(log_level, f"Executing the following command:\n  {' '.join(args)}")

    with subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=working_directory,
    ) as proc:
        if timeout:
            try:
                proc.wait(timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                SYNC_LOGGER.warning(
                    proc.stdout.read().decode("UTF-8")  # type: ignore[union-attr]
                )
                raise TimeoutError("Timeout reached.")

        SYNC_LOGGER.log(
            log_level,
            proc.stdout.read().decode("UTF-8"),  # type: ignore[union-attr]
        )


def pull(
    remote_uri: ParseResult,
    local_path: Path,
    exclude: Iterable[str],
    dry_run: bool,
    use_daemon: bool = False,
    timeout: int | None = None,
    delete: bool = True,
    rsync_flags: str | None = None,
    rsync_args: Iterable[str] | None = None,
) -> None:
    """Sync an upstream file or folder into the specified location using rsync.
    This will overwrite any files and folders already at the destination.

    Parameters
    ----------
    remote_uri : ParseResult
        The URI for the remote resource to copy from
    local_path : Path
        The destination folder
    exclude : list of str
        Any patterns that should be excluded from the sync
    dry_run : bool
        Whether to only simulate this sync (report the operations to be performed
        but not actually perform them)
    use_daemon : bool, optional
        By default, the rsync is performed over ssh. If you happen to have an
        rsync daemon running on your system, however, you're welcome to leverage
        it instead by passing in `use_daemon=True`
    timeout : int, optional
        The number of seconds to wait before timing out the sync operation.
        If None is provided, no explicit timeout value will be set.
    delete : bool
        Whether part of the syncing should include deleting files at the destination
        that aren't at the source. Default is True.
    rsync_flags : str, optional
        By default, rsync will be run using the flags "avzs" which means:

          - archive mode
          - verbose
          - use compression
          - no space splitting

        Advanced users may choose to override these options, but **you do so
        at your own peril**.
    rsync_args: list of str, optional
        Any additional arguments to pass into rsync

    Raises
    ------
    FileNotFoundError
        If the destination folder does not exist

    Notes
    -----
    - This method does not provide for interactive authentication. If using
      rsync over SSH, you'll need to be set up for password-less (key-based)
      access.
    - If the destination folder does not already exist, this method will not
      create it or its parent directories.
    """
    if not local_path.exists():
        raise FileNotFoundError(f"{local_path} does not exist")

    if remote_uri.netloc == get_default_netloc():
        SYNC_LOGGER.debug("Performing sync as a local transfer")
        remote_path: str = path_from_uri(remote_uri).as_posix()
    elif use_daemon:
        remote_path = remote_uri.geturl()
    else:
        remote_path = uri_to_ssh(remote_uri)

    run_rsync(
        local_path.parent,
        remote_path,
        local_path.name,
        delete,
        dry_run,
        exclude,
        *(rsync_args or ()),
        timeout=timeout,
        rsync_flags=rsync_flags,
    )


def push(
    local_path: Path,
    remote_uri: ParseResult,
    exclude: Iterable[str],
    dry_run: bool,
    use_daemon: bool = False,
    timeout: int | None = None,
    delete: bool = True,
    rsync_flags: str | None = None,
    rsync_args: Iterable[str] | None = None,
) -> None:
    """Sync a local file or folder into the specified location using rsync.
    This will overwrite any files and folders already at the destination.

    Parameters
    ----------
    local_path : Path
        The file or folder to copy
    remote_uri : ParseResult
        The URI for the remote location to copy into
    exclude : list of str
        Any patterns that should be excluded from the sync
    dry_run : bool
        Whether to only simulate this sync (report the operations to be performed
        but not actually perform them)
    use_daemon : bool, optional
        By default, the rsync is performed over ssh. If you happen to have an
        rsync daemon running on your system, however, you're welcome to leverage
        it instead by passing in `use_daemon=True`
    timeout : int, optional
        The number of seconds to wait before timing out the sync operation.
        If None is provided, no explicit timeout value will be set.
    delete : bool
        Whether part of the syncing should include deleting files at the destination
        that aren't at the source. Default is True.
    rsync_flags : str, optional
        By default, rsync will be run using the flags "avzs" which means:

          - archive mode
          - verbose
          - use compression
          - no space splitting

        Advanced users may choose to override these options, but **you do so
        at your own peril**.
    rsync_args: list of str, optional
        Any additional arguments to pass into rsync

    Notes
    -----
    - This method does not provide for interactive authentication. If using
      rsync over SSH, you'll need to be set up for password-less (key-based)
      access.
    - If the destination folder does not already exist, this method will very
      likely fail.
    """
    if remote_uri.netloc == get_default_netloc():
        SYNC_LOGGER.debug("Performing sync as a local transfer")
        remote_path: str = path_from_uri(remote_uri).as_posix()
    elif use_daemon:
        remote_path = remote_uri.geturl()
    else:
        remote_path = uri_to_ssh(remote_uri)

    run_rsync(
        local_path.parent,
        local_path.name,
        remote_path,
        delete,
        dry_run,
        exclude,
        *(rsync_args or ()),
        timeout=timeout,
        rsync_flags=rsync_flags,
    )


# TODO: this will eventually go in the SFTP module or be replaced by Paramiko
def uri_to_ssh(uri: ParseResult) -> str:
    """Convert a URI to an SSH address

    Parameters
    ----------
    uri: ParseResult
        The URI to convert

    Returns
    -------
    str
        The SSH-format address
    """
    return "{user}{host}:{path}".format(
        user=f"{uri.username}@" if uri.username else "",
        host=(uri.hostname or "localhost") + (f":{uri.port}" if uri.port else ""),
        path=path_from_uri(uri).as_posix(),
    )
