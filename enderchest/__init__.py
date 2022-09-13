import os
from pathlib import Path
from typing import NamedTuple

from . import _version

__version__ = _version.get_versions()["version"]


class Contexts(NamedTuple):
    universal: Path
    client_only: Path
    local_only: Path
    server_only: Path


def contexts(root: str | os.PathLike) -> Contexts:
    """Centrally define context directories based on the root folder

    Returns
    -------
    Tuple of Paths
        The contexts, in order,
        - global
        - client-only
        - local-only
        - server-only
    """
    ender_chest = Path(root) / "EnderChest"

    return Contexts(
        ender_chest / "global",
        ender_chest / "client-only",
        ender_chest / "local-only",
        ender_chest / "server-only",
    )


from .craft import craft_ender_chest
from .place import place_enderchest

__all__ = ["craft_ender_chest", "place_enderchest", "__version__"]
