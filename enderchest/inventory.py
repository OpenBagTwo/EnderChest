"""Functionality for resolving EnderChest and shulker box states"""

import logging
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import ParseResult

from enderchest.sync import render_remote

from . import EnderChest, InstanceSpec, ShulkerBox
from . import filesystem as fs
from .loggers import INVENTORY_LOGGER


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
    ValueError
        If the EnderChest configuration is invalid and could not be parsed
    """
    config_path = fs.ender_chest_config(minecraft_root)
    INVENTORY_LOGGER.debug(f"Loading {config_path}")
    ender_chest = EnderChest.from_cfg(config_path)
    INVENTORY_LOGGER.debug(f"Parsed EnderChest installation from {minecraft_root}")
    return ender_chest


def load_ender_chest_instances(
    minecraft_root: Path, log_level: int = logging.INFO
) -> Sequence[InstanceSpec]:
    """Get the list of instances registered with the EnderChest located in the
    minecraft root

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    log_level : int, optional
        By default, this method will report out the minecraft instances it
        finds at the INFO level. You can optionally pass in a lower (or higher)
        level if this method is being called from another method where that
        information is redundant or overly verbose.

    Returns
    -------
    list of InstanceSpec
        The instances registered with the EnderChest

    Notes
    -----
    If no EnderChest is installed in the given location, then this will return
    an empty list rather than failing outright.
    """
    try:
        ender_chest = load_ender_chest(minecraft_root)
        instances: Sequence[InstanceSpec] = ender_chest.instances
    except (FileNotFoundError, ValueError) as bad_chest:
        INVENTORY_LOGGER.error(
            f"Could not load EnderChest from {minecraft_root}:\n  {bad_chest}"
        )
        instances = []
    if len(instances) == 0:
        INVENTORY_LOGGER.warning(
            f"There are no instances registered to the {minecraft_root} EnderChest",
        )
    else:
        INVENTORY_LOGGER.log(
            log_level,
            "These are the instances that are currently registered"
            f" to the {minecraft_root} EnderChest:\n%s",
            "\n".join(
                [
                    f"  {i + 1}. {render_instance(instance)}"
                    for i, instance in enumerate(instances)
                ]
            ),
        )
    return instances


def render_instance(instance: InstanceSpec) -> str:
    """Render an instance spec to a descriptive string

    Parameters
    ----------
    instance : InstanceSpec
        The instance spec to render

    Returns
    -------
    str
        {instance.name} ({instance.root})
    """
    return f"{instance.name} ({instance.root})"


def load_shulker_boxes(
    minecraft_root: Path, log_level: int = logging.INFO
) -> list[ShulkerBox]:
    """Load all shulker boxes in the EnderChest folder and return them in the
    order in which they should be linked.

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    log_level : int, optional
        By default, this method will report out the minecraft instances it
        finds at the INFO level. You can optionally pass in a lower (or higher)
        level if this method is being called from another method where that
        information is redundant or overly verbose.

    Returns
    -------
    list of ShulkerBoxes
        The shulker boxes found in the EnderChest folder, ordered in terms of
        the sequence in which they should be linked

    Notes
    -----
    If no EnderChest is installed in the given location, then this will return
    an empty list rather than failing outright.
    """
    shulker_boxes: list[ShulkerBox] = []

    try:
        for shulker_config in fs.shulker_box_configs(minecraft_root):
            try:
                shulker_boxes.append(_load_shulker_box(shulker_config))
            except (FileNotFoundError, ValueError) as bad_shulker:
                INVENTORY_LOGGER.warning(
                    f"{bad_shulker}\n  Skipping shulker box {shulker_config.parent.name}"
                )

    except FileNotFoundError:
        INVENTORY_LOGGER.error(
            f"There is no EnderChest installed within {minecraft_root}"
        )
        return []

    shulker_boxes = sorted(shulker_boxes)

    if len(shulker_boxes) == 0:
        if log_level >= logging.INFO:
            INVENTORY_LOGGER.warning(
                f"There are no shulker boxes within the {minecraft_root} EnderChest"
            )
    else:
        report_shulker_boxes(
            shulker_boxes, log_level, f"the {minecraft_root} EnderChest"
        )
    return shulker_boxes


def report_shulker_boxes(
    shulker_boxes: Iterable[ShulkerBox], log_level: int, ender_chest_name: str
) -> None:
    """Log the list of shulker boxes in the order they'll be linked"""
    INVENTORY_LOGGER.log(
        log_level,
        f"These are the shulker boxes within {ender_chest_name}"
        "\nlisted in the order in which they are linked:\n%s",
        "\n".join(
            f"  {shulker_box.priority}. {_render_shulker_box(shulker_box)}"
            for shulker_box in shulker_boxes
        ),
    )


def _load_shulker_box(config_file: Path) -> ShulkerBox:
    """Attempt to load a shulker box from a config file, and if you can't,
    at least log why the loading failed.

    Parameters
    ----------
    config_file : Path
        Path to the config file

    Returns
    -------
    ShulkerBox | None
        The parsed shulker box or None, if the shulker box couldn't be parsed

    Raises
    ------
    FileNotFoundError
        If the given config file could not be found
    ValueError
        If there was a problem parsing the config file
    """
    INVENTORY_LOGGER.debug(f"Attempting to parse {config_file}")
    shulker_box = ShulkerBox.from_cfg(config_file)
    INVENTORY_LOGGER.debug(f"Successfully parsed {_render_shulker_box(shulker_box)}")
    return shulker_box


def _render_shulker_box(shulker_box: ShulkerBox) -> str:
    """Render a shulker box to a descriptive string

    Parameters
    ----------
    shulker_box : ShulkerBox
        The shulker box spec to render

    Returns
    -------
    str
        {priority}. {folder_name} [({name})]
            (if different from folder name)
    """
    stringified = f"{shulker_box.root.name}"
    if shulker_box.root.name != shulker_box.name:  # pragma: no cover
        # note: this is not a thing
        stringified += f" ({shulker_box.name})"
    return stringified


def load_ender_chest_remotes(
    minecraft_root: Path, log_level: int = logging.INFO
) -> list[tuple[ParseResult, str]]:
    """Load all remote EnderChest installations registered with this one

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    log_level : int, optional
        By default, this method will report out the minecraft instances it
        finds at the INFO level. You can optionally pass in a lower (or higher)
        level if this method is being called from another method where that
        information is redundant or overly verbose.

    Returns
    -------
    list of (URI, str) tuples
        The URIs of the remote EnderChests, paired with their aliases

    Notes
    -----
    If no EnderChest is installed in the given location, then this will return
    an empty list rather than failing outright.
    """
    try:
        ender_chest = load_ender_chest(minecraft_root)
        remotes: Sequence[tuple[ParseResult, str]] = ender_chest.remotes
    except (FileNotFoundError, ValueError) as bad_chest:
        INVENTORY_LOGGER.error(
            f"Could not load EnderChest from {minecraft_root}:\n  {bad_chest}"
        )
        remotes = ()

    if len(remotes) == 0:
        if log_level >= logging.INFO:
            INVENTORY_LOGGER.warning(
                f"There are no remotes registered to the {minecraft_root} EnderChest"
            )
        return []

    report = (
        "These are the remote EnderChest installations registered"
        f" to the one installed at {minecraft_root}"
    )
    remote_list: list[tuple[ParseResult, str]] = []
    log_args: list[str] = []
    for remote, alias in remotes:
        report += "\n  - %s"
        log_args.append(render_remote(alias, remote))
        remote_list.append((remote, alias))
    INVENTORY_LOGGER.log(log_level, report, *log_args)
    return remote_list


def get_shulker_boxes_matching_instance(
    minecraft_root: Path, instance_name: str
) -> list[ShulkerBox]:
    """Get the list of shulker boxes that the specified instance links to

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    instance_name : str
        The name of the instance you're asking about

    Returns
    -------
    list of ShulkerBox
        The shulker boxes that are linked to by the specified instance
    """
    try:
        chest = load_ender_chest(minecraft_root)
    except (FileNotFoundError, ValueError) as bad_chest:
        INVENTORY_LOGGER.error(
            f"Could not load EnderChest from {minecraft_root}:\n  {bad_chest}"
        )
        return []
    for mc in chest.instances:
        if mc.name == instance_name:
            break
    else:
        INVENTORY_LOGGER.error(
            "No instance named %s is registered to this EnderChest", instance_name
        )
        return []

    matches = [
        box
        for box in load_shulker_boxes(minecraft_root, log_level=logging.DEBUG)
        if box.matches(mc) and box.matches_host(chest.name)
    ]

    if len(matches) == 0:
        report = "does not link to any shulker boxes in this chest"
    else:
        report = "links to the following shulker boxes:\n" + "\n".join(
            f"  - {_render_shulker_box(box)}" for box in matches
        )

    INVENTORY_LOGGER.info(f"The instance {render_instance(mc)} {report}")

    return matches


def get_instances_matching_shulker_box(
    minecraft_root: Path, shulker_box_name: str
) -> list[InstanceSpec]:
    """Get the list of registered instances that link to the specified shulker box

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    shulker_box_name : str
        The name of the shulker box you're asking about

    Returns
    -------
    list of InstanceSpec
        The instances that are / should be linked to the specified shulker box
    """
    try:
        config_file = fs.shulker_box_config(minecraft_root, shulker_box_name)
    except FileNotFoundError:
        INVENTORY_LOGGER.error(f"No EnderChest is installed in {minecraft_root}")
        return []
    try:
        shulker_box = _load_shulker_box(config_file)
    except (FileNotFoundError, ValueError) as bad_box:
        INVENTORY_LOGGER.error(
            f"Could not load shulker box {shulker_box_name}\n  {bad_box}"
        )
        return []

    chest = load_ender_chest(minecraft_root)

    if not shulker_box.matches_host(chest.name):
        INVENTORY_LOGGER.warning(
            "This shulker box will not link to any instances on this machine"
        )
        return []

    if not chest.instances:
        INVENTORY_LOGGER.warning(
            "This EnderChest does not have any instances registered."
            " To register some, run the command:"
            "\nenderchest gather minecraft",
        )
        return []

    INVENTORY_LOGGER.debug(
        "These are the instances that are currently registered"
        f" to the {minecraft_root} EnderChest:\n%s",
        "\n".join(
            [
                f"  {i + 1}. {render_instance(instance)}"
                for i, instance in enumerate(chest.instances)
            ]
        ),
    )

    matches = [
        instance for instance in chest.instances if shulker_box.matches(instance)
    ]

    if len(matches) == 0:
        report = "is not linked to by any registered instances"
    else:
        report = "is linked to by the following instances:\n" + "\n".join(
            f"  - {render_instance(instance)}" for instance in matches
        )

    INVENTORY_LOGGER.info(
        f"The shulker box {_render_shulker_box(shulker_box)} {report}"
    )

    return matches
