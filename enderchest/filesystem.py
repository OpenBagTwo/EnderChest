"""Functionality for managing the EnderChest and shulker box config files and folders"""
from pathlib import Path
from typing import Iterable

from .loggers import GATHER_LOGGER

ENDER_CHEST_FOLDER_NAME = "EnderChest"

ENDER_CHEST_CONFIG_NAME = "enderchest.cfg"

SHULKER_BOX_CONFIG_NAME = "shulkerbox.cfg"


def ender_chest_folder(minecraft_root: Path, check_exists: bool = True) -> Path:
    """Given a minecraft root directory, return the path to the EnderChest
    folder

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    check_exists : bool, optional
        By default, this method will raise an error if no EnderChest exists
        at that location (meaning no folder or no enderchest config file in
        that folder). To disable that check, call this method with
        `check_exists=False`

    Returns
    -------
    Path
        The path to the EnderChest folder

    Raises
    ------
    FileNotFoundError
        If no valid EnderChest installation exists within the given
        minecraft root (and checking hasn't been disabled)
    """
    return ender_chest_config(minecraft_root, check_exists=check_exists).parent


def ender_chest_config(minecraft_root, check_exists: bool = True) -> Path:
    """Given a minecraft root directory, return the path to the EnderChest
    config file

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    check_exists : bool, optional
        By default, this method will raise an error if the enderchest config
        file does not already exist. To disable that check, call this method
        with `check_exists=False`

    Returns
    -------
    Path
        The path to the EnderChest config file

    Raises
    ------
    FileNotFoundError
        If the EnderChest config file isn't where it's supposed to be (and
        checking hasn't been disabled)

    Notes
    -----
    This method does not check if the config file is valid
    """
    config_path = minecraft_root / ENDER_CHEST_FOLDER_NAME / ENDER_CHEST_CONFIG_NAME

    if check_exists and not config_path.exists():
        raise FileNotFoundError(
            f"No valid EnderChest installation exists within {minecraft_root}"
        )
    return config_path


def shulker_box_root(minecraft_root: Path, shulker_box_name: str) -> Path:
    """Generate the path to the root of a shulker box, given its name and the
    minecraft root directory

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)

    Returns
    -------
    Path
        The path to the shulker box folder

    Notes
    -----
    This method does not check if a shulker box exists at that location
    """
    return ender_chest_folder(minecraft_root) / shulker_box_name


def shulker_box_config(minecraft_root: Path, shulker_box_name: str) -> Path:
    """Generate the path to a shulker box config file, given its name and
    the minecraft root directory

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)

    Returns
    -------
    Path
        The path to the shulker box folder

    Notes
    -----
    This method does not check if a shulker box config exists at that location
    """
    return shulker_box_root(minecraft_root, shulker_box_name) / SHULKER_BOX_CONFIG_NAME


def shulker_box_configs(minecraft_root: Path) -> Iterable[Path]:
    """Find all shulker box configs on the system

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)

    Returns
    -------
    list-like of paths
        The paths to all the shulker box configs on the system

    Notes
    -----
    This method does not check to make sure those config files are valid,
    just that they exist
    """
    GATHER_LOGGER.debug(f"Searching for shulker configs within {minecraft_root}")
    return ender_chest_folder(minecraft_root).glob(f"*/{SHULKER_BOX_CONFIG_NAME}")


def minecraft_folders(search_path: Path) -> Iterable[Path]:
    """Find all .minecraft folders within a given search path

    Parameters
    ----------
    search_path : Path
        The directory to search

    Returns
    -------
    list-like of paths
        The paths to all the .minecraft folders this method could find

    Notes
    -----
    This method does not check to make sure that those .minecraft folders
    contain valid minecraft instances, just that they exist
    """
    return search_path.rglob(".minecraft")
