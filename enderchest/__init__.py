import os
from pathlib import Path
from typing import NamedTuple

from . import _version

__version__ = _version.get_versions()["version"]


class Contexts(NamedTuple):
    universal: Path
    client_only: Path
    server_only: Path
    local_only: Path
    other_locals: Path


def contexts(root: str | os.PathLike) -> Contexts:
    """Centrally define context directories based on the root folder

    Returns
    -------
    Tuple of Paths
        The contexts, in order,
        - global : for syncing across all instances and servers
        - client-only : for syncing across all client instances
        - server-only : for syncing across all server instances
        - local-only : for local use only (don't sync)
        - other-locals : "local-only" folders from other installations
                         (for distributed backups)

    Notes
    -----
    - Because "global" is a restricted keyword in Python, the namedtuple key for
      this context is "universal"
    - For all other contexts, the namedtuple key replaces a dash (not a valid token
      character) with an underscore   `
    """
    ender_chest = Path(root) / "EnderChest"

    return Contexts(
        ender_chest / "global",
        ender_chest / "client-only",
        ender_chest / "server-only",
        ender_chest / "local-only",
        ender_chest / "other-locals",
    )
