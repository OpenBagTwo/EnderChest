import os
from pathlib import Path

from . import contexts


def craft_ender_chest(root: str | os.PathLike) -> None:
    """Create the EnderChest folder structure in the specified root directory

    Parameters
    ----------
    root : path
        The root directory to put the EnderChest folder structure into
    """
    for context in contexts(root):
        for folder in ("config", "mods", "saves", "shaderpacks", "resourcepacks"):
            (context / folder).mkdir(parents=True, exist_ok=True)
