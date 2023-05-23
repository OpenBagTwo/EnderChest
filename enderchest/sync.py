"""Low-level functionality for synchronizing across different machines"""
import getpass
import socket
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import ParseResult

SUPPORTED_PROTOCOLS = ("rsync",)

DEFAULT_PROTOCOL = "rsync"


def get_default_netloc() -> str:
    """Compile a netloc from environment variables, etc.

    Returns
    -------
    str
        The default netloc, which is {user}@{hostname}
    """
    return f"{getpass.getuser()}@{socket.gethostname()}"


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
    raise NotImplementedError("Remote file access is not currently implemented")


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
