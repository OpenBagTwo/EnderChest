"""Functionality for setting up the folder structure of both chests and shulker boxes"""
from pathlib import Path

from .config import ShulkerBox

DEFAULT_SHULKER_FOLDERS = (
    "config",
    "mods",
    "resourcepacks",
    "saves",
    "shaderpacks",
)


def craft_shulker_box(minecraft_root: Path, shulker_box: ShulkerBox) -> None:
    """Create a shulker box folder based on the provided configuratin

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    shulker_box : ShulkerBox
        The spec of the box to create

    Notes
    -----
    The "root" attribute of the ShulkerBox config will be ignored--instead the
    Shulker Box will be created at <minecraft_root>/EnderChest/<shulker box name>
    """
    shulker_root = minecraft_root / "EnderChest" / shulker_box.name

    (minecraft_root / "EnderChest" / shulker_box.name).mkdir(
        parents=True, exist_ok=True
    )
    for folder in (*DEFAULT_SHULKER_FOLDERS, *shulker_box.link_folders):
        (shulker_root / folder).mkdir(exist_ok=True)

    shulker_box.write_to_cfg(shulker_root / "shulkerbox.cfg")
