"""Low-level functionality for synchronizing across different machines"""
import getpass
import importlib
import os
import socket
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable
from urllib.parse import ParseResult, unquote
from urllib.request import url2pathname

from ..loggers import SYNC_LOGGER

SUPPORTED_PROTOCOLS = ("rsync", "file")

DEFAULT_PROTOCOL = SUPPORTED_PROTOCOLS[0]


def get_default_netloc() -> str:
    """Compile a netloc from environment variables, etc.

    Returns
    -------
    str
        The default netloc, which is {user}@{hostname}
    """
    return f"{getpass.getuser()}@{socket.gethostname()}".lower()


def render_remote(alias: str, uri: ParseResult) -> str:
    """Render a remote to a descriptive string

    Parameters
    ----------
    alias : str
        The name of the remote
    uri : ParseResult
        The parsed URI for the remote

    Returns
    -------
    str
        {uri_string} [({alias})]}
            (if different from the URI hostname)
    """
    uri_string = uri.geturl()

    if uri.hostname != alias:
        uri_string += f" ({alias})"
    return uri_string


@contextmanager
def remote_file(uri: ParseResult) -> Generator[Path, None, None]:
    """Grab a file from a remote filesystem by its URI and read its contents

    Parameters
    ----------
    uri : parsed URI
        The URI of the file to read

    Yields
    ------
    Path
        A path to a local (temp) copy of the file
    """
    with TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        pull(uri, Path(tmpdir))
        yield Path(tmpdir) / Path(uri.path).name


def pull(
    remote_uri: ParseResult,
    local_path: Path,
    exclude: Iterable[str] | None = None,
    dry_run: bool = False,
    **kwargs,
) -> None:
    """Pull all upstream changes from a remote into the specified location

    Parameters
    ----------
    remote_uri : ParseResult
        The URI for the remote resource to pull
    local_path : Path
        The local destination
    exclude : list of str, optional
        Any patterns that should be excluded from the sync
    dry_run : bool, optional
        Whether to only simulate this sync (report the operations to be performed
        but not actually perform them). Default is False.
    **kwargs
        Any additional options to pass into the sync command
    """
    try:
        protocol = importlib.import_module(f"{__package__}.{remote_uri.scheme.lower()}")
        protocol.pull(remote_uri, local_path, exclude or (), dry_run, **kwargs)
    except ModuleNotFoundError:
        raise NotImplementedError(
            f"Protocol {remote_uri.scheme} is not currently implemented"
        )
    except TypeError as unknown_kwarg:
        raise NotImplementedError(
            f"Protocol {remote_uri.scheme} does not support that functionality:\n  {unknown_kwarg}"
        )


def push(
    local_path: Path,
    remote_uri: ParseResult,
    exclude: Iterable[str] | None = None,
    dry_run: bool = False,
    **kwargs,
) -> None:
    """Push all local changes in the specified directory into the specified remote

    Parameters
    ----------
    local_path
        The local path to push
    remote_uri : ParseResult
        The URI for the remote destination
    exclude : list of str, optional
        Any patterns that should be excluded from the sync
    dry_run : bool, optional
        Whether to only simulate this sync (report the operations to be performed
        but not actually perform them). Default is False.
    **kwargs
        Any additional options to pass into the sync command
    """
    try:
        protocol = importlib.import_module(f"{__package__}.{remote_uri.scheme.lower()}")
        protocol.push(local_path, remote_uri, exclude or (), dry_run, **kwargs)
    except ModuleNotFoundError:
        raise NotImplementedError(
            f"Protocol {remote_uri.scheme} is not currently implemented"
        )


def path_from_uri(uri: ParseResult) -> Path:
    """Extract and unquote the path component of a URI to turn it into a pathlib.Path

    h/t https://stackoverflow.com/a/61922504

    Parameters
    ----------
    uri : ParseResult
        The parsed URI to extract the path from

    Returns
    -------
    Path
        The path part of the URI as a Path
    """
    host = "{0}{0}{mnt}{0}".format(os.path.sep, mnt=uri.netloc)
    return Path(os.path.abspath(os.path.join(host, url2pathname(unquote(uri.path)))))


__all__ = [
    "SYNC_LOGGER",
    "SUPPORTED_PROTOCOLS",
    "DEFAULT_PROTOCOL",
    "render_remote",
    "remote_file",
    "path_from_uri",
    "pull",
    "push",
]
