"""A mock Paramiko SFTP client to be used for testing on systems without local SSH"""
import json
import shutil
from contextlib import contextmanager
from importlib.resources import as_file
from pathlib import Path
from typing import Callable, Generator, NamedTuple
from urllib.parse import ParseResult

from .testing_files import LSTAT_CACHE


class CachedStat(NamedTuple):
    """Stat-like loaded from a file cache"""

    filename: str
    st_mode: int
    st_size: float
    st_mtime: float


class MockSFTP:
    """Create a mock SFTP client suitable for testing

    Parameters
    ----------
    root : Path
        The top-most directory that will be accessed by this client (this
        corresponds to the path in the remote URI for the EnderChest)
    """

    def __init__(self, root: Path):
        with as_file(LSTAT_CACHE) as lstat_cache_file:
            cached_lstats: list[dict] = json.loads(lstat_cache_file.read_text("UTF-8"))

        self.lstat_cache: dict[Path, CachedStat] = {
            root / stat["filename"]: CachedStat(**stat) for stat in cached_lstats
        }

    def lstat(self, path: str) -> CachedStat:
        """Return the cached file attributes for the specified path"""
        try:
            return self.lstat_cache[Path(path)]
        except KeyError:
            # In a few places we get an lstat on a directory (that's not included
            # in the rglob). Rather than including them in the cache, we're just
            # going to mock out that they're directories.
            return CachedStat(filename="", st_mode=16877, st_size=-1, st_mtime=-1)

    def mkdir(self, path: str) -> None:
        """Make a directory on the "remote" file system"""
        Path(path).mkdir()

    def symlink(self, target: str, path: str) -> None:
        """Create a symlink at the path pointing to the target"""
        Path(path).symlink_to(Path(target))

    def readlink(self, path: str) -> str:
        """Get the target of the "remote" symlink"""
        return Path(path).readlink().as_posix()

    def get(self, path: str, destination: Path) -> None:
        """ "Download" the "remote" file to the specified destination"""
        shutil.copy2(
            Path(path),
            destination,
            follow_symlinks=False,
        )

    def put(self, source: Path, path: str) -> None:
        """ "Upload" the "remote" file to the specified destination"""
        shutil.copy2(
            source,
            Path(path),
            follow_symlinks=False,
        )

    def remove(self, path: str) -> None:
        """Delete a file on the "remote" file system"""
        Path(path).unlink()

    def rmdir(self, path: str) -> None:
        """Delete an empty folder on the "remote" file system"""
        Path(path).rmdir()


def generate_mock_connect(mock_sftp: MockSFTP) -> Callable:
    """Create a method suitable to be used as a monkeypatch for `sync.sftp.connect`
    that instead yields the provided MockSFTP instance

    Parameters
    ----------
    mock_sftp : MockSFTP
        The mock SFTP client the method should connect to instead

    Returns
    -------
    Method
        A method suitable for use in monkeypatching `sync.sftp.connect`
    """

    @contextmanager
    def connect(
        uri: ParseResult, timeout: float | None = None
    ) -> Generator[MockSFTP, None, None]:
        yield mock_sftp

    return connect


def mock_rglob(client: MockSFTP, path: str) -> list[tuple[Path, CachedStat]]:
    """A method that simulates `sync.sftp.rglob` by relying on the
    `lstat_cache` of the client instead of actually recursively getting the
    file attributes of the given path

    Parameters
    ----------
    client : MockSFTP
        The mock SFTP client
    path : str
        This parameter is ignored

    Returns
    -------
    list of (Path, SFTPAttributes-like) tuples
        The cached file attributes
    """
    return list(client.lstat_cache.items())
