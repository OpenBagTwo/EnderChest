import logging
import warnings
from pathlib import Path
from typing import Sequence

from . import _version, loggers
from .enderchest import EnderChest
from .instance import (
    InstanceSpec,
    gather_metadata_for_mmc_instance,
    gather_metadata_for_official_instance,
)

__version__ = _version.get_versions()["version"]


from .filesystem import ender_chest_config, minecraft_folders, shulker_box_configs
from .shulker_box import ShulkerBox


def gather_minecraft_instances(
    minecraft_root: Path, search_path: Path, official: bool | None
) -> list[InstanceSpec]:
    """Search the specified directory for Minecraft installations

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder). This will be used to
        construct relative paths.
    search_path : Path
        The path to search
    official : bool or None
        Whether we expect that the instances found in this location will be:
          - from the official launcher (official=True)
          - from a MultiMC-style launcher (official=False)
          - a mix / unsure (official=None)

    Returns
    -------
    list of InstanceSpec
        A list of parsed instances
    """
    instances: list[InstanceSpec] = []
    for folder in minecraft_folders(search_path):
        folder_path = folder.absolute()
        loggers.GATHER_LOGGER.info(f"Found {folder}")
        if official is not False:
            try:
                instances.append(gather_metadata_for_official_instance(folder_path))
                continue
            except ValueError as not_official:
                loggers.GATHER_LOGGER.log(
                    logging.INFO if official is None else logging.WARNING,
                    (f"{folder} is not an official instance:" f"\n{not_official}",),
                )
        if official is not True:
            try:
                instances.append(gather_metadata_for_mmc_instance(folder_path))
                continue
            except ValueError as not_mmc:
                loggers.GATHER_LOGGER.log(
                    logging.INFO if official is None else logging.WARNING,
                    f"{folder} is not an MMC-like instance:\n{not_mmc}",
                )
        loggers.GATHER_LOGGER.warn(
            f"{folder_path} does not appear to be a valid Minecraft instance"
        )
    official_count = 0
    for i, instance in enumerate(instances):
        if instance.name == "official":
            if official_count > 0:
                instances[i] = instance._replace(name=f"official.{official_count}")
            official_count += 1
        try:
            instances[i] = instance._replace(
                root=instance.root.relative_to(minecraft_root)
            )
        except ValueError:
            # TODO: if not Windows, try making relative to "~"
            pass  # instance isn't inside the minecraft root
    return instances


def load_instance_metadata(minecraft_root: Path) -> Sequence[InstanceSpec]:
    """Load the instance metadata from the enderchest.cfg file in the EnderChest
    folder.

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)

    Returns
    -------
    list-like of InstanceSpec
        The instance metadata loaded from the enderchest config

    Raises
    ------
    FileNotFoundError
        If no EnderChest folder exists in the given minecraft root or if no
        enderchest.cfg file exists within that EnderChest folder
    """
    return EnderChest.from_cfg(ender_chest_config(minecraft_root)).instances


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
    for shulker_config in shulker_box_configs(minecraft_root):
        shulker_boxes.append(ShulkerBox.from_cfg(shulker_config))

    return sorted(shulker_boxes)


__all__ = [
    "EnderChest",
    "InstanceSpec",
    "ShulkerBox",
    "gather_minecraft_instances",
    "load_instance_metadata",
    "load_shulker_boxes",
]
