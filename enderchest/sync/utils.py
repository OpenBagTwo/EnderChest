"""Non-implementation-specific syncing utilities"""
import fnmatch
import getpass
import os
import socket
import stat
from collections import defaultdict
from enum import Enum, auto
from pathlib import Path
from typing import Any, Collection, Generator, Iterable, Protocol, TypeVar
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


def abspath_from_uri(uri: ParseResult) -> Path:
    """Extract and unquote the path component of a URI to turn it into an
    unambiguous absolute `pathlib.Path`

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
        path=uri.path,
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
        `{uri_string} [({alias})]}`
            (alias is omitted if it's the same as the URI's hostname)
    """
    uri_string = uri.geturl()

    if uri.hostname != alias:
        uri_string += f" ({alias})"
    return uri_string


class _StatLike(Protocol):  # pragma: no cover
    @property
    def st_mode(self) -> int | None:
        ...

    @property
    def st_size(self) -> float | None:
        ...

    @property
    def st_mtime(self) -> float | None:
        ...


def is_identical(object_one: _StatLike, object_two: _StatLike) -> bool:
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
        if int(object_one.st_size or 0) != int(object_two.st_size or 0):
            return False
        if int(object_one.st_mtime or 0) != int(object_two.st_mtime or 0):
            return False
    return True


class Operation(Enum):
    """The recognized sync operations

    Notes
    -----
    There's no `UPDATE` operation because so far this class isn't used by
    anything that _can_ perform a delta update on a file
    """

    CREATE = auto()
    REPLACE = auto()
    DELETE = auto()


PathInfo = TypeVar(
    "PathInfo",
    tuple[Path, Any],
    tuple[str, Any],
    # TODO: the proper type hint is tuple[Path, *tuple[Any, ...]]
    #       but that's not supported until Python 3.11
)


def filter_contents(
    contents: Iterable[PathInfo],
    exclude: Collection[str],
    prefix: Path | str | None = None,
) -> Generator[PathInfo, None, None]:
    """Apply an exclusion filter to a list of files

    Parameters
    ----------
    contents : list of (Path, ...) tuples
        The contents to filter
    exclude : list of str
        The patterns to exclude
    prefix : Path, optional
        If the contents are iterating over a subdirectory, providing the directory
        as the `prefix` will allow filtering to be performed on the full path.

    Yields
    ------
    (Path, ...) tuples
        The elements of the provided list, omitting the ones
        to be excluded
    """
    for path_info in contents:
        if not any(
            (
                fnmatch.fnmatch(
                    os.path.normpath(os.path.join(prefix or "", path_info[0])),
                    os.path.join("*", pattern),
                )
                for pattern in exclude
            )
        ):
            yield path_info


def diff(
    source_files: Iterable[tuple[Path, _StatLike]],
    destination_files: Iterable[tuple[Path, _StatLike]],
) -> Generator[tuple[Path, _StatLike, Operation], None, None]:
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
    destination_lookup: dict[Path, _StatLike] = dict(destination_files)
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
    content_diff: Iterable[tuple[Path, _StatLike, Operation]], depth: int = 2
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
