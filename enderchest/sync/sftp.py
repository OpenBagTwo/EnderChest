"""paramiko-based sftp sync implementation"""
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Collection, Generator
from urllib.parse import ParseResult

import paramiko

from ..prompt import prompt
from . import (
    SYNC_LOGGER,
    Op,
    diff,
    file,
    filter_contents,
    generate_sync_report,
    is_identical,
    path_from_uri,
)


@contextmanager
def connect(uri: ParseResult) -> Generator[paramiko.sftp_client.SFTPClient, None, None]:
    """Yield an SFTPClient connected to the server specified by the given URI

    Parameters
    ----------
    uri : ParseResult
        The URI of the EnderChest to connect to

    Yields
    ------
    SFTPClient
        A Paramiko SFTP client connected to the specified server

    Raises
    ------
    ValueError
        If the URI is invalid or the credentials are incorrect
    RuntimeError
        If the server cannot be reached
    """
    ssh_client = paramiko.client.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh_client.connect(
            uri.hostname or "localhost",
            port=uri.port or 22,
            username=uri.username,
            # note: passing in password is explicitly unsupported
        )
    except paramiko.AuthenticationException:
        target = ((uri.username + "@") if uri.username else "") + (
            uri.hostname or "localhost"
        )

        SYNC_LOGGER.warning(
            f"This machine is not set up for passwordless login to {target}"
            "\nFor instructions on setting up public key-based authentication,"
            " which is both"
            "\nmore convenient and more secure, see:"
            "\nhttps://openbagtwo.github.io/EnderChest"
            "/dev/suggestions/#passwordless-ssh-authentication"
        )
        password = prompt(f"Please enter the password for {target}", is_password=True)
        try:
            ssh_client.connect(
                uri.hostname or "localhost",
                port=uri.port or 22,
                username=uri.username,
                password=password,
            )
        except paramiko.AuthenticationException:
            raise ValueError(
                "Authentication failed."
                " Did you supply the correct username and password?"
            )

    try:
        sftp_client = ssh_client.open_sftp()
        yield sftp_client
        sftp_client.close()
    finally:
        ssh_client.close()


def rglob(
    client: paramiko.sftp_client.SFTPClient, path: str
) -> list[tuple[Path, paramiko.sftp_attr.SFTPAttributes]]:
    """Recursively enumerate the contents of a remote directory

    Parameters
    ----------
    client : Paramiko SFTP client
        An authenticated client connected to the remote server
    path : str
        The absolute path to scan

    Returns
    -------
    list of (Path, SFTPAttributes) tuples
        The attributes of all files, folders and symlinks found under the
        specified path

    Notes
    -----
    - The paths returned are *absolute*
    - The search is performed depth-first
    """
    SYNC_LOGGER.debug(f"ls {path}")
    top_level = client.listdir_attr(path)
    contents: list[tuple[Path, paramiko.sftp_attr.SFTPAttributes]] = []
    for remote_object in top_level:
        remote_object.filename = "/".join((path, remote_object.filename))
        contents.append((Path(remote_object.filename), remote_object))
        if stat.S_ISDIR(remote_object.st_mode or 0):
            contents.extend(rglob(client, remote_object.filename))
    return contents


def get_contents(
    client: paramiko.sftp_client.SFTPClient, path: str
) -> list[tuple[Path, paramiko.sftp_attr.SFTPAttributes]]:
    """Recursively fetch the contents of a remote directory

    Parameters
    ----------
    client : Paramiko SFTP client
        An authenticated client connected to the remote server
    path : str
        The absolute path to scan

    Returns
    -------
    list of (Path, SFTPAttributes) tuples
        The attributes of all files, folders and symlinks found under the
        specified path

    Notes
    -----
    - This list is generated via a depth-first search so that all parent
      directories appear before their children
    - The paths returned are relative to the provided path
    """
    return [(p.relative_to(path), path_stat) for p, path_stat in rglob(client, path)]


def pull(
    remote_uri: ParseResult,
    local_path: Path,
    exclude: Collection[str],
    dry_run: bool,
    timeout: int | None = None,
    delete: bool = True,
    verbosity: int = 0,
    **unsupported_kwargs,
) -> None:
    """Sync an upstream file or folder into the specified location SFTP.
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
    timeout : int, optional
        The number of seconds to wait before timing out the sync operation.
        If None is provided, no explicit timeout value will be set.
    delete : bool
        Whether part of the syncing should include deleting files at the destination
        that aren't at the source. Default is True.
    verbosity : int
        A modifier for how much info to output either to stdout or the INFO-level
        logs. Defaults to 0.
    **unsupported_kwargs
        Any other provided options will be ignored

    Raises
    ------
    FileNotFoundError
        If the destination folder does not exist, or if the remote path
        does not exist
    OSError
        If the remote path cannot be accessed for any other reason (permissions,
        most likely)

    Notes
    -----
    - If the destination folder does not already exist, this method will not
      create it or its parent directories.
    - Unlike `sync.file.copy`, this method will fail if the remote path does
      not exist
    """
    if not local_path.exists():
        raise FileNotFoundError(f"{local_path} does not exist")
    if unsupported_kwargs:
        SYNC_LOGGER.debug(
            "The following command-line options are ignored for this protocol:\n%s",
            "\n".join("  {}: {}".format(*item) for item in unsupported_kwargs.items()),
        )

    remote_path = path_from_uri(remote_uri)
    destination_path = local_path / remote_path.name

    with connect(uri=remote_uri) as remote:
        try:
            source_target = remote.lstat(remote_path.as_posix())
        except OSError as bad_target:
            raise type(bad_target)(
                f"Could not access {remote_path} on remote: {bad_target}"
            )
        if not stat.S_ISDIR(source_target.st_mode or 0):
            if destination_path.exists() and is_identical(
                source_target, destination_path.stat()
            ):
                SYNC_LOGGER.warning(
                    "Remote file matches %s. No copy needed.",
                    destination_path,
                )
                return
            SYNC_LOGGER.debug(
                "Downloading file %s from remote",
                destination_path,
            )
            if not dry_run:
                remote.get(remote_path.as_posix(), destination_path)
            return

        source_contents = filter_contents(
            get_contents(remote, remote_path.as_posix()),
            exclude,
            prefix=remote_path.as_posix(),
        )
        destination_contents = filter_contents(
            file.get_contents(destination_path), exclude, prefix=remote_path.as_posix()
        )

        sync_diff = diff(source_contents, destination_contents)

        if dry_run:
            generate_sync_report(sync_diff)
            return

        ignore = file.ignore_patterns(*exclude)
        for path, path_stat, operation in sync_diff:
            match (operation, stat.S_ISDIR(path_stat.st_mode or 0)):
                case (Op.CREATE, True):
                    SYNC_LOGGER.debug("Creating directory %s", destination_path / path)
                    (destination_path / path).mkdir(parents=True, exist_ok=True)
                case (Op.CREATE, False) | (Op.REPLACE, False):
                    SYNC_LOGGER.debug(
                        "Downloading file %s from remote",
                        destination_path / path,
                    )
                    (destination_path / path).unlink(missing_ok=True)
                    if stat.S_ISLNK(path_stat.st_mode or 0):
                        (destination_path / path).symlink_to(
                            Path(remote.readlink((remote_path / path).as_posix()) or "")
                        )
                    else:
                        remote.get(
                            (remote_path / path).as_posix(), destination_path / path
                        )
                case (Op.DELETE, True):
                    # recall that for deletions, it's the *destination's* stats
                    file.clean(destination_path / path, ignore, dry_run)
                case (Op.DELETE, False):
                    SYNC_LOGGER.debug("Deleting file %s", destination_path / path)
                    (destination_path / path).unlink()
                case op, is_dir:
                    raise NotImplementedError(
                        f"Don't know how to handle {op} of {'directory' if is_dir else 'file'}"
                    )


def push(
    local_path: Path,
    remote_uri: ParseResult,
    exclude: Collection[str],
    dry_run: bool,
    timeout: int | None = None,
    delete: bool = True,
    verbosity: int = 0,
    **unsupported_kwargs,
) -> None:
    """Sync a local file or folder into the specified location using SFTP.
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
    timeout : int, optional
        The number of seconds to wait before timing out the sync operation.
        If None is provided, no explicit timeout value will be set.
    delete : bool
        Whether part of the syncing should include deleting files at the destination
        that aren't at the source. Default is True.
    verbosity : int
        A modifier for how much info to output either to stdout or the INFO-level
        logs. Defaults to 0.
    **unsupported_kwargs
        Any other provided options will be ignored

    Notes
    -----
    - If the destination folder does not already exist, this method will very
      likely fail.
    """
    if not local_path.exists():
        SYNC_LOGGER.warning(
            f"{local_path} does not exist:"
            " this will end up just deleting the remote copy."
        )
    if unsupported_kwargs:
        SYNC_LOGGER.debug(
            "The following command-line options are ignored for this protocol:\n%s",
            "\n".join("  {}: {}".format(*item) for item in unsupported_kwargs.items()),
        )
