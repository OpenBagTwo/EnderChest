"""Non-implementation-specific syncing utilities"""
import getpass
import os
import socket
import stat
from pathlib import Path
from typing import Iterable, NamedTuple, Protocol
from urllib.parse import ParseResult, unquote
from urllib.request import url2pathname


def get_default_netloc() -> str:
    """Compile a netloc from environment variables, etc.

    Returns
    -------
    str
        The default netloc, which is {user}@{hostname}
    """
    return f"{getpass.getuser()}@{socket.gethostname()}".lower()


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


class StatLike(Protocol):
    st_mode: int | None
    st_size: int | None
    st_mtime: int | None


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


class ContentSummary(NamedTuple):
    files: int
    folders: int
    links: int


def summarize_contents(file_stats: Iterable[StatLike]) -> ContentSummary:
    """Summarize a collection of file statistics, reporting on the number
    of files, folders and links

    Parameters
    ----------
    file_stats : list of os.stat_result or similar
        The contents to summarize

    Returns
    -------
    A dict reporting the number of files, folders and lints
    """
    counter = {"files": 0, "folders": 0, "links": 0}
    for file_object in file_stats:
        st_mode = file_object.st_mode
        if not st_mode:
            raise ValueError("One or more files don't have a valid st_mode")
        if stat.S_ISDIR(st_mode):
            counter["folders"] += 1
        elif stat.S_ISLNK(st_mode):
            counter["links"] += 1
        elif stat.S_ISREG(st_mode):
            counter["files"] += 1
        else:
            raise NotImplementedError(
                f"Don't know what an st_mode of {st_mode} represents"
            )
    return ContentSummary(**counter)
