"""Implementation of common workflows"""
import logging
from pathlib import Path
from typing import Any, Protocol

from . import filesystem as fs
from . import instance, loggers
from .enderchest import EnderChest
from .instance import InstanceSpec
from .shulker_box import ShulkerBox


class Action(Protocol):
    def __call__(self, minecraft_root: Path, /) -> Any:
        ...


def load_ender_chest(minecraft_root: Path) -> EnderChest:
    """Load the configuration from the enderchest.cfg file in the EnderChest
    folder.
    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    Returns
    -------
    EnderChest
        The EnderChest configuration
    Raises
    ------
    FileNotFoundError
        If no EnderChest folder exists in the given minecraft root or if no
        enderchest.cfg file exists within that EnderChest folder
    """
    return EnderChest.from_cfg(fs.ender_chest_config(minecraft_root))


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
    for shulker_config in fs.shulker_box_configs(minecraft_root):
        loggers.GATHER_LOGGER.debug(f"Found {shulker_config}")
        try:
            shulker_boxes.append(ShulkerBox.from_cfg(shulker_config))
            loggers.GATHER_LOGGER.debug(
                f"Successfully parsed {_render_shulker_box(shulker_boxes[-1])}"
            )
        except ValueError as bad_cfg:
            loggers.GATHER_LOGGER.warning(
                f"{shulker_config} is not a valid shulker config:\n  {bad_cfg}"
            )

    shulker_boxes = sorted(shulker_boxes)

    if len(shulker_boxes) == 0:
        loggers.GATHER_LOGGER.info(
            f"There are no shulker boxes within the {minecraft_root} EnderChest"
        )
    else:
        loggers.GATHER_LOGGER.info(
            f"These are the list of shulker boxes within the {minecraft_root} EnderChest,"
            "\nlisted in the order in which they are linked:\n"
            + "\n".join(
                f"  {_render_shulker_box(shulker_box)}" for shulker_box in shulker_boxes
            )
        )
    return shulker_boxes


def _render_shulker_box(shulker_box: ShulkerBox) -> str:
    """Render a shulker box to a descriptive string

    Parameters
    ----------
    shulker_box : ShulkerBox
        shulker box spec

    Returns
    -------
    str
        {priority}. {folder_name} [({name})]
            (if different from folder name)
    """
    stringified = f"{shulker_box.priority}. {shulker_box.root.name}"
    if shulker_box.root.name != shulker_box.name:
        # note: this is not a thing
        stringified += f" ({shulker_box.name})"
    return stringified


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
    for folder in fs.minecraft_folders(search_path):
        folder_path = folder.absolute()
        loggers.GATHER_LOGGER.info(f"Found {folder}")
        if official is not False:
            try:
                instances.append(
                    instance.gather_metadata_for_official_instance(folder_path)
                )
                continue
            except ValueError as not_official:
                loggers.GATHER_LOGGER.log(
                    logging.INFO if official is None else logging.WARNING,
                    (f"{folder} is not an official instance:" f"\n{not_official}",),
                )
        if official is not True:
            try:
                instances.append(instance.gather_metadata_for_mmc_instance(folder_path))
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
    for i, mc_instance in enumerate(instances):
        if mc_instance.name == "official":
            if official_count > 0:
                instances[i] = mc_instance._replace(name=f"official.{official_count}")
            official_count += 1
        try:
            instances[i] = mc_instance._replace(
                root=mc_instance.root.relative_to(minecraft_root)
            )
        except ValueError:
            # TODO: if not Windows, try making relative to "~"
            pass  # instance isn't inside the minecraft root
    return instances
