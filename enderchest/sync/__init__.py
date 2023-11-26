"""Low-level functionality for synchronizing across different machines"""
import importlib
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Collection, Generator
from urllib.parse import ParseResult

from ..loggers import SYNC_LOGGER
from .utils import Operation as Op
from .utils import (
    abspath_from_uri,
    diff,
    filter_contents,
    generate_sync_report,
    get_default_netloc,
    is_identical,
    render_remote,
    uri_to_ssh,
)

PROTOCOLS = ("rsync", "sftp", "file")


def _determine_available_protocols() -> tuple[str, ...]:
    """Determine which protocols are available on this system"""
    available_protocols: list[str] = []
    for protocol in PROTOCOLS:
        try:
            _ = importlib.import_module(f"{__package__}.{protocol}")
            available_protocols.append(protocol)
        except (ModuleNotFoundError, RuntimeError):
            pass
    return tuple(available_protocols)


SUPPORTED_PROTOCOLS = _determine_available_protocols()

DEFAULT_PROTOCOL = SUPPORTED_PROTOCOLS[0]


def pull(
    remote_uri: ParseResult,
    local_path: Path,
    exclude: Collection[str] | None = None,
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
    except ModuleNotFoundError as not_installed:  # pragma: no cover
        raise NotImplementedError(
            f"Protocol {remote_uri.scheme} is not currently implemented"
        ) from not_installed


def push(
    local_path: Path,
    remote_uri: ParseResult,
    exclude: Collection[str] | None = None,
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
    except ModuleNotFoundError as not_installed:
        raise NotImplementedError(
            f"Protocol {remote_uri.scheme} is not currently implemented"
        ) from not_installed


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
        pull(uri, Path(tmpdir), verbosity=-1)
        yield Path(tmpdir) / Path(uri.path).name


__all__ = [
    "SYNC_LOGGER",
    "PROTOCOLS",
    "DEFAULT_PROTOCOL",
    "get_default_netloc",
    "render_remote",
    "remote_file",
    "abspath_from_uri",
    "pull",
    "push",
    "uri_to_ssh",
]
