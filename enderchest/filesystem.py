"""Functionality for managing the EnderChest and shulker box config files and folders"""
import os
from pathlib import Path
from typing import Iterable

from .loggers import GATHER_LOGGER

ENDER_CHEST_FOLDER_NAME = "EnderChest"

ENDER_CHEST_CONFIG_NAME = "enderchest.cfg"

SHULKER_BOX_CONFIG_NAME = "shulkerbox.cfg"

PLACE_CACHE_NAME = ".place_cache.json"


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
        `check_exists=False`.

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
        with `check_exists=False`.

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
    shulker_box_name : str
        The name of the shulker box to resolve

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
    shulker_box_name : str
        The name of the shulker box to resolve

    Returns
    -------
    Path
        The path to the shulker box folder

    Notes
    -----
    This method does not check if a shulker box config exists at that location
    """
    return shulker_box_root(minecraft_root, shulker_box_name) / SHULKER_BOX_CONFIG_NAME


def place_cache(minecraft_root: Path) -> Path:
    """Given a minecraft root directory, return the path to the EnderChest
    place cache file

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)

    Returns
    -------
    Path
        The path to the place cache file

    Notes
    -----
    This method does not check if the cache file is valid or if it even exists
    """
    return ender_chest_folder(minecraft_root) / PLACE_CACHE_NAME


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


def links_into_enderchest(
    minecraft_root: Path, link: Path, check_exists: bool = True
) -> bool:
    """Determine whether a symlink's target is inside the EnderChest specified
    by the Minecraft root.

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    link : Path
        The link to check
    check_exists : bool, optional
        By default, this method will raise an error if no EnderChest exists
        at that location (meaning no folder or no enderchest config file in
        that folder). To disable that check, call this method with
        `check_exists=False`.

    Returns
    -------
    bool
        True if the path is inside of the EnderChest folder. False otherwise.

    Notes
    -----
    This method only checks the *direct target* of the link as opposed to the
    fully resolved path.

    Raises
    ------
    FileNotFoundError
        If no valid EnderChest installation exists within the given
        minecraft root (and checking hasn't been disabled)
    OSError
        If the link provided isn't actually a symbolic link
    """
    chest_folder = os.path.normpath(
        ender_chest_folder(minecraft_root, check_exists=check_exists)
        .expanduser()
        .absolute()
    )

    target = os.readlink(link)
    if not os.path.isabs(target):
        target = os.path.normpath(link.parent / target)

    # Windows shenanigans: https://bugs.python.org/issue42957
    if target.startswith(("\\\\?\\", "\\??\\")):  # pragma: no cover
        try:
            os.stat(target[4:])
            target = target[4:]
        except (OSError, FileNotFoundError):
            # then maybe this is somehow legit
            pass

    # there's probably a better way to check if a file is inside a sub-path
    try:
        common_root = os.path.commonpath([target, chest_folder])
    except ValueError:  # if they have no common root
        common_root = ""
    return common_root == chest_folder
