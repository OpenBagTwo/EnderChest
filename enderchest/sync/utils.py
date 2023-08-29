"""Non-implementation-specific syncing utilities"""
import getpass
import os
import socket
import stat
from collections import defaultdict
from enum import Enum, auto
from pathlib import Path
from typing import Generator, Iterable, Protocol
from urllib.parse import ParseResult, unquote
from urllib.request import url2pathname

from ..loggers import SYNC_LOGGER


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
    @property
    def st_mode(self) -> int | None:
        ...

    @property
    def st_size(self) -> float | None:
        ...

    @property
    def st_mtime(self) -> float | None:
        ...


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

    if stat.S_ISLNK(object_one.st_mode or 0):
        # there's no way from the stat to tell if two links have the same target
        # so err on the side of "nope"
        return False

    if stat.S_ISREG(object_one.st_mode or 0):
        # these comparisons should only be run on files
        if object_one.st_size != object_two.st_size:
            return False
        if object_one.st_mtime != object_two.st_mtime:
            return False
    return True


class Operation(Enum):
    CREATE = auto()
    REPLACE = auto()
    DELETE = auto()


def diff(
    source_files: Iterable[tuple[Path, StatLike]],
    destination_files: Iterable[tuple[Path, StatLike]],
) -> Generator[tuple[Path, StatLike, Operation], None, None]:
    """Compute the "diff" between the source and destination, enumerating
    all the operations that should be performed so that the destination
    matches the source

    Parameters
    ----------
    source_files : list of (Path, stat_result) tuples
        The files and file attributes at the source
    destination_files : list of (Path, stat_result) tuples
        The files and file attributes at the destination

    Returns
    -------
    Generator of (Path, stat_result, Operation) tuples
        The files, their attributes and the operations that should be performed on each file

    Notes
    -----
    - The order of paths returned will match the order provided by the `source_files`
      except for the deletions, which will all come at the end and will be sorted
      from longest to shortest path (so that individual files are marked for deletion
      before their parent folders).
    - The attributes of each path will correspond to the *source* attributes for
      creations and replacements and to the *destination* attributes for the deletions
    """
    destination_lookup: dict[Path, StatLike] = dict(destination_files)
    for file, source_stat in source_files:
        if file not in destination_lookup:
            yield file, source_stat, Operation.CREATE
        else:
            destination_stat = destination_lookup.pop(file)
            if not is_identical(source_stat, destination_stat):
                yield file, source_stat, Operation.REPLACE
            # else: continue

    for file, destination_stat in sorted(
        destination_lookup.items(), key=lambda x: -len(str(x[0]))
    ):
        yield file, destination_stat, Operation.DELETE


def generate_sync_report(
    content_diff: Iterable[tuple[Path, StatLike, Operation]], depth: int = 2
) -> None:
    """Compile a high-level summary of the outcome of the `diff` method
    and report it to the logging.INFO level

    Parameters
    ----------
    content_diff : list of (Path, Operation) tuples
        The files and the operations that are to be performed on each file, as
        generated by the `diff` method
    depth : int, optional
     How many directories to go down from the root to generate the summary.
        Default is 2 (just report on top-level files and folders within the
        source folder).

    Returns
    -------
    None
    """
    summary: dict[Path, dict[Operation, int] | Operation] = defaultdict(
        lambda: {Operation.CREATE: 0, Operation.REPLACE: 0, Operation.DELETE: 0}
    )

    for full_path, path_stat, operation in content_diff:
        try:
            path_key = full_path.parents[-depth]
        except IndexError:  # then this doesn't go in a subdirectory
            summary[full_path] = operation
            continue

        entry = summary[path_key]
        if isinstance(entry, Operation):
            # then this is described by the top-level op
            continue
        if operation == Operation.CREATE and stat.S_ISDIR(path_stat.st_mode or 0):
            # don't count folder creations
            continue

        entry[operation] += 1

    for path_key, report in sorted(summary.items()):
        if isinstance(report, Operation):
            # nice that these verbs follow the same pattern
            SYNC_LOGGER.info(f"{report.name[:-1].title()}ing {path_key}")
        else:
            SYNC_LOGGER.info(
                f"Within {path_key}...\n%s",
                "\n".join(
                    f"  - {op.name[:-1].title()}ing {count} file{'' if count == 1 else 's'}"
                    for op, count in report.items()
                ),
            )
