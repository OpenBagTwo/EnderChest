from pathlib import Path

from . import _version

__version__ = _version.get_versions()["version"]


from .config import InstanceSpec, ShulkerBox, parse_instance_metadata


def load_instance_metadata(minecraft_root: Path) -> dict[str, InstanceSpec]:
    """Load the instance metadata from the enderchest.cfg file in the EnderChest
    folder.

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)

    Returns
    -------
    dict of str to InstanceSpec
        The map of instance names to their metadata

    Raises
    ------
    FileNotFoundError
        If no EnderChest folder exists in the given minecraft root or if no
        enderchest.cfg file exists within that EnderChest folder
    """
    return parse_instance_metadata(minecraft_root / "EnderChest" / "enderchest.cfg")


def load_shulker_boxes(minecraft_root: Path) -> list[ShulkerBox]:
    """Load all shulker boxes in the EnderChest folder and return them in the
    order in which they should be linked.

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)

    Returns
    -------
    list of ShulkerBoxes
        The shulker boxes found in the EnderChest folder, ordered in terms of
        the sequence in which they should be linked
    """
    shulker_boxes: list[ShulkerBox] = []
    for shulker_config in (minecraft_root / "EnderChest").glob("*/shulkerbox.cfg"):
        shulker_boxes.append(ShulkerBox.from_cfg(shulker_config))

    return sorted(shulker_boxes)
