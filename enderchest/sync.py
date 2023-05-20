"""Functionality for synchronizing chests across different machines"""
import getpass
import socket
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

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
def remote_file(uri: str) -> Generator[Path, None, None]:
    """Grab a file from a remote filesystem by its URI and read its contents

    Parameters
    ----------
    uri : str
        The URI of the file to read

    Yields
    ------
    Path
        A path to a local (temp) copy of the file
    """
    raise NotImplementedError
