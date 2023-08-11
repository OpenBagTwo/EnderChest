"""paramiko-based sftp sync implementation"""
import os
import stat
from contextlib import contextmanager
from typing import Generator, TypeAlias
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


# TODO: if this moves into sync.file, replace with a Protocol
StatLike: TypeAlias = os.stat_result | paramiko.sftp_attr.SFTPAttributes


def is_identical(object_one: StatLike, object_two: StatLike) -> bool:
    """Determine if two objects are identical (meaning: skip when syncing)

    Parameters
    ----------
    object_one : os.stat_result or similar
        The first object to compare
    object_two : os.stat_result or similar
        The second object to compare

    Returns
    -------
    bool
        False if the objects are conclusively different, True otherwise.

    Notes
    -----
    As most implementations of the SFTP protocol do not include the check-file
    extension, this method is limited in what it can compare. Use with caution.
    """
    if stat.S_ISDIR(object_one.st_mode or 0) != stat.S_ISDIR(object_two.st_mode or 0):
        return False
    if stat.S_ISLNK(object_one.st_mode or 0) != stat.S_ISLNK(object_two.st_mode or 0):
        return False
    if object_one.st_size != object_two.st_size:
        return False
    if object_one.st_mtime != object_two.st_mtime:
        return False
    return True
