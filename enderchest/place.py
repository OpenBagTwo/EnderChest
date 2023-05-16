"""Symlinking functionality"""
from pathlib import Path


def place_enderchest(minecraft_root: Path, cleanup: bool = True) -> None:
    """Link all instance files and folders

    Parameters
    ----------
    minecraft_root : path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    cleanup : bool, optional
        By default, this method will remove any broken links in your instances and
        servers folders. To disable this behavior, pass in `cleanup=False`

    Raises
    ------
    RuntimeError
        If creating the link would overwrite a file or non-empty folder
    """
    ...
