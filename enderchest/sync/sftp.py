"""paramiko-based sftp sync implementation"""
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Iterable
from urllib.parse import ParseResult

import paramiko

from ..prompt import prompt
from . import SYNC_LOGGER


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
            username=uri.username or None,
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
                username=uri.username or None,
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


def get_contents(
    client: paramiko.sftp_client.SFTPClient, path: str
) -> list[paramiko.sftp_attr.SFTPAttributes]:
    """Recursively fetch the contents of a remote directory

    Parameters
    ----------
    client : Paramiko SFTP client
        An authenticated client connected to the remote server
    path : str
        The path to scan

    Returns
    -------
    list of SFTPAttributes
        The attributes of all files, folders and symlinks found under the
        specified path
    """
    SYNC_LOGGER.debug(f"ls {path}")
    top_level = client.listdir_attr(path)
    contents: list[paramiko.sftp_attr.SFTPAttributes] = []
    for remote_object in top_level:
        remote_object.filename = "/".join((path, remote_object.filename))
        contents.append(remote_object)
        if stat.S_ISDIR(remote_object.st_mode or 0):
            contents.extend(get_contents(client, remote_object.filename))
    return contents


def pull(
    remote_uri: ParseResult,
    local_path: Path,
    exclude: Iterable[str],
    dry_run: bool,
    timeout: int | None = None,
    delete: bool = True,
    verbosity: int = 0,
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

    Raises
    ------
    FileNotFoundError
        If the destination folder does not exist

    Notes
    -----
    - If the destination folder does not already exist, this method will not
      create it or its parent directories.
    """
    raise NotImplementedError


def push(
    local_path: Path,
    remote_uri: ParseResult,
    exclude: Iterable[str],
    dry_run: bool,
    timeout: int | None = None,
    delete: bool = True,
    verbosity: int = 0,
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

    Notes
    -----
    - If the destination folder does not already exist, this method will very
      likely fail.
    """
    raise NotImplementedError
