"""paramiko-based sftp sync implementation"""
import os
import posixpath
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Collection, Generator
from urllib.parse import ParseResult, unquote
from urllib.request import url2pathname

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
)


@contextmanager
def connect(
    uri: ParseResult, timeout: float | None = None
) -> Generator[paramiko.sftp_client.SFTPClient, None, None]:
    """Yield an SFTPClient connected to the server specified by the given URI

    Parameters
    ----------
    uri : ParseResult
        The URI of the EnderChest to connect to
    timeout : float, optional
        The number of seconds to wait before timing out the sync operation.
        If None is provided, no explicit timeout value will be set.

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

    extra_kwargs: dict[str, Any] = {}
    if timeout is not None:
        extra_kwargs["timeout"] = timeout

    try:
        ssh_client.connect(
            uri.hostname or "localhost",
            port=uri.port or 22,
            username=uri.username,
            # note: passing in password is explicitly unsupported
            **extra_kwargs,
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
                **extra_kwargs,
            )
        except paramiko.AuthenticationException as bad_login:
            raise ValueError(
                "Authentication failed."
                " Did you supply the correct username and password?"
            ) from bad_login

    try:
        sftp_client = ssh_client.open_sftp()
        yield sftp_client
        sftp_client.close()
    finally:
        ssh_client.close()


def download_file(
    client: paramiko.sftp_client.SFTPClient,
    remote_loc: str,
    local_path: Path,
    remote_stat: paramiko.SFTPAttributes,
) -> None:
    """Download a file from a remote SFTP server and save it at the specified
    location.

    Parameters
    ----------
    client : Paramiko SFTP client
        An authenticated client connected to the remote server
    remote_loc : str
        The POSIX path of the file to download
    local_path : Path
        The path to locally save the file
    remote_stat : stat-like
        The `os.stat_result`-like properties of the remote object

    Notes
    -----
    This is a wrapper around `client.get()` that can handle symlinks and
    updating timestamps. It does not check if either path is valid, points
    to a file, lives in an existing folder, etc.
    """
    if stat.S_ISLNK(remote_stat.st_mode or 0):
        local_path.symlink_to(Path((client.readlink(remote_loc) or "")))
    else:
        client.get(remote_loc, local_path)
        if remote_stat.st_atime and remote_stat.st_mtime:
            os.utime(
                local_path,
                times=(remote_stat.st_atime, remote_stat.st_mtime),
            )


def upload_file(
    client: paramiko.sftp_client.SFTPClient,
    local_path: Path,
    remote_loc: str,
) -> None:
    """Upload a local file to a remote SFTP server

    Parameters
    ----------
    client : Paramiko SFTP client
        An authenticated client connected to the remote server
    local_path : Path
        The path of the file to upload
    remote_loc : str
        The POSIX path for the remote location to save the file

    Notes
    -----
    This is just a wrapper around `client.put()` that can handle symlinks.
    It does not check if either path is valid, points to a file, lives in an
    existing folder, etc.
    """
    if local_path.is_symlink():
        client.symlink(local_path.readlink().as_posix(), remote_loc)
    else:
        client.put(local_path, remote_loc)
        client.utime(
            remote_loc, times=(local_path.stat().st_atime, local_path.stat().st_mtime)
        )


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
        remote_object.filename = posixpath.join(path, remote_object.filename)
        contents.append((Path(url2pathname(remote_object.filename)), remote_object))
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
    return [
        (p.relative_to(url2pathname(path)), path_stat)
        for p, path_stat in rglob(client, path)
    ]


def pull(
    remote_uri: ParseResult,
    local_path: Path,
    exclude: Collection[str],
    dry_run: bool,
    timeout: float | None = None,
    delete: bool = True,
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
    timeout : float, optional
        The number of seconds to wait before timing out the sync operation.
        If None is provided, no explicit timeout value will be set.
    delete : bool
        Whether part of the syncing should include deleting files at the destination
        that aren't at the source. Default is True.
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
    """
    if not local_path.exists():
        raise FileNotFoundError(f"{local_path} does not exist")
    if unsupported_kwargs:
        SYNC_LOGGER.debug(
            "The following command-line options are ignored for this protocol:\n%s",
            "\n".join("  {}: {}".format(*item) for item in unsupported_kwargs.items()),
        )

    remote_loc = posixpath.normpath(unquote(remote_uri.path))
    destination_path = local_path / posixpath.basename(remote_loc)

    if destination_path.is_symlink() and not destination_path.is_dir():
        SYNC_LOGGER.warning("Removing symlink %s", destination_path)
        if not dry_run:
            destination_path.unlink()
        else:
            SYNC_LOGGER.debug(
                "And replacing it entirely with the remote's %s", remote_loc
            )
            return
    elif destination_path.exists() and not destination_path.is_dir():
        SYNC_LOGGER.warning("Deleting file %s", destination_path)
        if not dry_run:
            destination_path.unlink()
        else:
            SYNC_LOGGER.debug(
                "And replacing it entirely with the remote's %s", remote_loc
            )
            return

    with connect(uri=remote_uri, timeout=timeout) as remote:
        try:
            source_target = remote.lstat(remote_loc)
        except OSError as bad_target:
            raise type(bad_target)(
                f"Could not access {remote_loc} on remote: {bad_target}"
            )
        if not stat.S_ISDIR(source_target.st_mode or 0):
            if destination_path.exists() and is_identical(
                source_target, destination_path.stat()
            ):
                SYNC_LOGGER.warning(
                    "Remote file matches %s. No transfer needed.",
                    destination_path,
                )
                return
            SYNC_LOGGER.debug(
                "Downloading file %s from remote",
                destination_path,
            )
            if not dry_run:
                download_file(
                    remote,
                    remote_loc,
                    destination_path,
                    source_target,
                )
            return

        if not destination_path.exists():
            SYNC_LOGGER.debug(
                "Downloading the entire contents of the remote's %s", remote_loc
            )
            if dry_run:
                return
            destination_path.mkdir()

        source_contents = filter_contents(
            get_contents(remote, remote_loc),
            exclude,
            prefix=remote_loc,
        )
        destination_contents = filter_contents(
            file.get_contents(destination_path),
            exclude,
            prefix=destination_path,
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
                    download_file(
                        remote,
                        posixpath.join(remote_loc, path.as_posix()),
                        destination_path / path,
                        path_stat,  # type: ignore[arg-type]
                    )
                case (Op.DELETE, True):
                    # recall that for deletions, it's the *destination's* stats
                    if delete:
                        file.clean(destination_path / path, ignore, dry_run)
                case (Op.DELETE, False):
                    SYNC_LOGGER.debug("Deleting file %s", destination_path / path)
                    if delete:
                        (destination_path / path).unlink()
                case op, is_dir:  # pragma: no cover
                    raise NotImplementedError(
                        f"Don't know how to handle {op} of {'directory' if is_dir else 'file'}"
                    )


def push(
    local_path: Path,
    remote_uri: ParseResult,
    exclude: Collection[str],
    dry_run: bool,
    timeout: float | None = None,
    delete: bool = True,
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
    timeout : float, optional
        The number of seconds to wait before timing out the sync operation.
        If None is provided, no explicit timeout value will be set.
    delete : bool, optional
        Whether part of the syncing should include deleting files at the destination
        that aren't at the source. Default is True.
    **unsupported_kwargs
        Any other provided options will be ignored

    Notes
    -----
    - If the destination folder does not already exist, this method will not
      create it or its parent directories.
    """
    if not local_path.exists():
        raise FileNotFoundError(f"{local_path} does not exist.")
    if unsupported_kwargs:
        SYNC_LOGGER.debug(
            "The following command-line options are ignored for this protocol:\n%s",
            "\n".join("  {}: {}".format(*item) for item in unsupported_kwargs.items()),
        )

    remote_parent = posixpath.normpath(unquote(remote_uri.path))

    with connect(uri=remote_uri, timeout=timeout) as remote:
        try:
            remote_folder_stat = remote.lstat(remote_parent)
        except OSError as bad_target:
            raise type(bad_target)(
                f"Could not access {remote_parent} on remote: {bad_target}"
            )
        if not stat.S_ISDIR(remote_folder_stat.st_mode or 0):
            raise NotADirectoryError(f"{remote_parent} on remote is not a directory.")

        remote_loc = posixpath.join(remote_parent, local_path.name)
        try:
            target_stat = remote.lstat(remote_loc)
        except FileNotFoundError:
            target_stat = None
        if not stat.S_ISDIR(local_path.stat().st_mode or 0):
            if target_stat and is_identical(local_path.stat(), target_stat):
                SYNC_LOGGER.warning("Remote file matches %s", local_path)
                return

            SYNC_LOGGER.debug(
                "Uploading file %s to remote",
                local_path,
            )
            if not dry_run:
                upload_file(remote, local_path, remote_loc)
            return
        if not target_stat:
            SYNC_LOGGER.debug("Uploading the entire contents %s", local_path)
            if dry_run:
                return
            remote.mkdir(remote_loc)
        elif not stat.S_ISDIR(target_stat.st_mode or 0):
            SYNC_LOGGER.warning(
                "Deleting remote file or symlink %s",
                remote_loc,
            )
            if dry_run:
                SYNC_LOGGER.debug("And replacing it entirely with %s", local_path)
                return
            remote.remove(remote_loc)
            remote.mkdir(remote_loc)

        source_contents = filter_contents(
            file.get_contents(local_path), exclude, prefix=local_path
        )
        destination_contents = filter_contents(
            get_contents(remote, remote_loc),
            exclude,
            prefix=remote_loc,
        )

        sync_diff = diff(source_contents, destination_contents)

        if dry_run:
            generate_sync_report(sync_diff)
            return

        for path, path_stat, operation in sync_diff:
            posix_path = posixpath.join(remote_loc, path.as_posix())
            match (operation, stat.S_ISDIR(path_stat.st_mode or 0)):
                case (Op.CREATE, True):
                    SYNC_LOGGER.debug("Creating remote directory %s", posix_path)
                    remote.mkdir(posix_path)
                case (Op.CREATE, False) | (Op.REPLACE, False):
                    SYNC_LOGGER.debug(
                        "Uploading file %s to remote",
                        local_path / path,
                    )
                    try:
                        remote.remove(posix_path)
                    except FileNotFoundError:
                        pass
                    upload_file(
                        remote,
                        local_path / path,
                        posix_path,
                    )
                case (Op.DELETE, True):
                    # recall that for deletions, it's the *destination's* stats
                    if delete:
                        remote.rmdir(posix_path)
                case (Op.DELETE, False):
                    if delete:
                        SYNC_LOGGER.debug("Deleting remote file %s", posix_path)
                        remote.remove(posix_path)
                case op, is_dir:  # pragma: no cover
                    raise NotImplementedError(
                        f"Don't know how to handle {op} of {'directory' if is_dir else 'file'}"
                    )
