"""Utilities for performing the linking"""
import os
from pathlib import Path

from . import contexts


def _tokenize_server_name(tag: str) -> str:
    """For easier integration into systemd, and because spaces in paths are a hassle
    in general, assume (enforce?) that server folders will have "tokenized" names and
    thus map any tags (where spaces are fine) to the correct server folder.

    Parameters
    ----------
    tag : str
        The unprocessed tag value, which can have spaces and capital letters

    Returns
    -------
    str
        The expected "tokenized" server folder name, which:
          - will be all lowercase
          - has all spaces replaced with periods

    Examples
    --------
    >>> _tokenize_server_name("Chaos Awakening")
    'chaos.awakening'
    """
    return tag.lower().replace(" ", ".")


def place_enderchest(root: str | os.PathLike, cleanup: bool = True) -> None:
    """Link all instance files and folders

    Parameters
    ----------
    root : path
        The root directory that contains the EnderChest directory, instances and servers
    cleanup : bool, optional
        By default, this method will remove any broken links in your instances and
        servers folders. To disable this behavior, pass in cleanup=False
    """
    instances = Path(root) / "instances"
    servers = Path(root) / "servers"
    for context_type, context_root in contexts(root)._asdict().items():
        make_server_links = context_type in ("universal", "server_only")
        make_instance_links = context_type in ("universal", "client_only", "local_only")
        assets = sorted(context_root.rglob("*@*"))
        for asset in assets:
            if not asset.exists():
                continue
            path, *tags = str(asset.relative_to(context_root)).split("@")
            for tag in tags:
                if make_instance_links:
                    link_instance(path, instances / tag, asset)
                if make_server_links:
                    link_server(path, servers / _tokenize_server_name(tag), asset)
    if cleanup:
        for file in (*instances.rglob("*"), *servers.rglob("*")):
            if not file.exists():
                file.unlink()


def link_instance(
    resource_path: str, instance_folder: Path, destination: Path, check_exists=True
) -> None:
    """Create a symlink for the specified resource from an instance's space pointing to
    the tagged file / folder living in the EnderChest folder.

    Parameters
    ----------
    resource_path : str
        Location of the resource relative to the instance's ".minecraft" folder
    instance_folder : Path
        the instance's folder (parent of ".minecraft")
    destination : Path
        the location to link, where the file or older actually lives (inside the
        EnderChest folder)
    check_exists : bool, optional
        By default, this method will only create links if a ".minecraft" folder exists
        in the instance_folder. To create links regardless, pass check_exists=False

    Returns
    -------
    None

    Notes
    -----
    - This method will create any folders that do not exist within an instance, but only
      if the instance folder exists and has contains a ".minecraft" folder *or* if
      check_exists is set to False
    - This method will overwrite existing symlinks but will not overwrite any actual
      files.
    """
    if not (instance_folder / ".minecraft").exists() and check_exists:
        return

    instance_file = instance_folder / ".minecraft" / resource_path
    instance_file.parent.mkdir(parents=True, exist_ok=True)
    relative_path = os.path.relpath(destination, instance_file.parent)
    if instance_file.is_symlink():
        # remove previous symlink in this spot
        instance_file.unlink()
    os.symlink(relative_path, instance_file)


def link_server(
    resource_path: str, server_folder: Path, destination: Path, check_exists=True
) -> None:
    """Create a symlink for the specified resource from an server's space pointing to
    the tagged file / folder living in the EnderChest folder.

    Parameters
    ----------
    resource_path : str
        Location of the resource relative to the instance's ".minecraft" folder
    server_folder : Path
        the server's  folder
    destination : Path
        the location to link, where the file or older actually lives (inside the
        EnderChest folder)
    check_exists : bool, optional
        By default, this method will only create links if the server_folder exists.
        To create links regardless, pass check_exists=False

    Returns
    -------
    None

    Notes
    -----
    - This method will create any folders that do not exist within a server folder
    - This method will overwrite existing symlinks but will not overwrite any actual
      files
    """
    if not server_folder.exists() and check_exists:
        return
    server_file = server_folder / resource_path
    server_file.parent.mkdir(parents=True, exist_ok=True)
    relative_path = os.path.relpath(destination, server_file.parent)
    if server_file.is_symlink():
        # remove previous symlink in this spot
        server_file.unlink()
    os.symlink(relative_path, server_file)
