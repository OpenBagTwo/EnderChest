import os
from pathlib import Path

from . import contexts


def place_enderchest(root: str | os.PathLike) -> None:
    """Link all instance files and folders

    Parameters
    ----------
    root : path
        The root directory that contains both the EnderChest directory, instances and servers
    """
    instances = Path(root) / "instances"
    servers = Path(root) / "servers"
    for context_type, context_root in contexts(root)._asdict().items():
        make_server_links = context_type in ("universal", "server_only")
        make_instance_links = context_type in ("universal", "client_only", "local_only")

        links = sorted(context_root.rglob("*@*"))
        for link in links:
            path, *tags = str(link.relative_to(context_root)).split("@")
            for tag in tags:
                if make_instance_links:
                    link_instance(path, instances / tag, link)
                # if make_server_links:
                #     link_server(path, instances / tag, link)


def link_instance(resource_path: str, instance_folder: Path, destination: Path) -> None:
    """Create a symlink for the specified resource from an instance's space pointing to the
    tagged file / folder living in the EnderChest folder.

    Parameters
    ----------
    resource_path : str
        Location of the resource relative to the instance's ".minecraft" folder
    instance_folder : Path
        the instance's folder (parent of ".minecraft")
    destination : Path
        the location to link, where the file or older actually lives (inside the EnderChest folder)

    Returns
    -------
    None

    Notes
    -----
    This method will create any folders that do not existc
    """
    instance_file = instance_folder / ".minecraft" / resource_path
    instance_file.parent.mkdir(parents=True, exist_ok=True)
    relative_path = os.path.relpath(instance_file, destination)
    os.symlink(instance_file, relative_path)


def link_server(resource_path: str, server_folder: Path, destination: Path) -> None:
    """Create a symlink for the specified resource from an server's space pointing to the
    tagged file / folder living in the EnderChest folder.

    Parameters
    ----------
    resource_path : str
        Location of the resource relative to the instance's ".minecraft" folder
    server_folder : Path
        the server's  folder
    destination : Path
        the location to link, where the file or older actually lives (inside the EnderChest folder)

    Returns
    -------
    None

    Notes
    -----
    This method will create any folders that do not existc
    """
    raise NotImplementedError
