"""A mock Paramiko SFTP client to be used for testing on systems without local SSH"""
import json
import os
import shutil
from contextlib import contextmanager
from importlib.resources import as_file
from pathlib import Path
from typing import Callable, Generator, NamedTuple
from urllib.parse import ParseResult
from urllib.request import url2pathname

from .testing_files import LSTAT_CACHE


class CachedStat(NamedTuple):
    """Stat-like loaded from a file cache"""

    filename: str
    st_mode: int
    st_size: float
    st_atime: float
    st_mtime: float


A_DIRECTORY = CachedStat(
    filename="", st_mode=16877, st_size=-1, st_atime=-1, st_mtime=-1
)
A_FILE = CachedStat(filename="", st_mode=33188, st_size=-1, st_atime=-1, st_mtime=-1)
A_SYMLINK = CachedStat(filename="", st_mode=41471, st_size=-1, st_atime=-1, st_mtime=-1)


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
            root
            / stat["filename"]: CachedStat(**stat)._replace(
                st_size=(root / stat["filename"]).stat().st_size,
                st_mtime=(root / stat["filename"]).stat().st_mtime,
                st_atime=(root / stat["filename"]).stat().st_atime,
            )
            for stat in cached_lstats
        }

    def lstat(self, path: str) -> CachedStat:
        """Return the cached file attributes for the specified path"""
        try:
            return self.lstat_cache[Path(url2pathname(path))]
        except KeyError as not_in_cache:
            # In a few places we get an lstat on stuff that's outside of the
            # cache. In those scenarios, we want to return CacheStats matching
            # the type of the file
            if Path(url2pathname(path)).is_symlink():
                return A_SYMLINK
            if Path(url2pathname(path)).is_dir():
                return A_DIRECTORY
            if Path(url2pathname(path)).exists():
                return A_FILE
            raise FileNotFoundError from not_in_cache

    def mkdir(self, path: str) -> None:
        """Make a directory on the "remote" file system"""
        Path(url2pathname(path)).mkdir()

    def symlink(self, target: str, path: str) -> None:
        """Create a symlink at the path pointing to the target"""
        Path(url2pathname(path)).symlink_to(Path(target))

    def readlink(self, path: str) -> str:
        """Get the target of the "remote" symlink"""
        return Path(url2pathname(path)).readlink().as_posix()

    def get(self, path: str, destination: Path) -> None:
        """ "Download" the "remote" file to the specified destination"""
        shutil.copy2(
            Path(url2pathname(path)),
            destination,
            follow_symlinks=False,
        )

    def put(self, source: Path, path: str) -> None:
        """ "Upload" the "remote" file to the specified destination"""
        shutil.copy2(
            source,
            Path(url2pathname(path)),
            follow_symlinks=False,
        )

    def utime(self, path: str, times: tuple[float, float]) -> None:
        """Set the modification and access times of a remote file"""
        os.utime(Path(url2pathname(path)), times)

    def remove(self, path: str) -> None:
        """Delete a file on the "remote" file system"""
        Path(url2pathname(path)).unlink()

    def rmdir(self, path: str) -> None:
        """Delete an empty folder on the "remote" file system"""
        Path(url2pathname(path)).rmdir()


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
        This parameter is just used to determine which test is being run

    Returns
    -------
    list of (Path, SFTPAttributes-like) tuples
        The cached file attributes
    """
    if "somewhere_else" in Path(url2pathname(path)).parts:
        return []
    return list(client.lstat_cache.items())
