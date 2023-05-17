"""Symlinking functionality"""
import os
from pathlib import Path

from . import load_instance_metadata, load_shulker_boxes


def place_enderchest(
    minecraft_root: Path, cleanup: bool = True, stop_at_first_failure: bool = True
) -> None:
    """Link all instance files and folders

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    cleanup : bool, optional
        By default, this method will remove any broken links in your instances
        and servers folders. To disable this behavior, pass in `cleanup=False`
    stop_at_first_failure : bool, optional
        By default, if a linking failure occurs, this method will terminate
        immediately. In the future, passing in `stop_at_first_failure=False`
        will lead this method to continue linking and then raise all failures
        at the end.

    Raises
    ------
    RuntimeError
        If creating a link would overwrite a file or non-empty folder
    """
    if stop_at_first_failure is not True:
        raise NotImplementedError

    instances = load_instance_metadata(minecraft_root)

    shulker_boxes = load_shulker_boxes(minecraft_root)

    for shulker_box in shulker_boxes:
        for instance in instances:
            if not shulker_box.matches(instance):
                continue

            if instance.root.expanduser().is_absolute():
                instance_root = instance.root
            else:
                instance_root = minecraft_root / instance.root

            resources = set(shulker_box.root.expanduser().absolute().rglob("*"))
            for link_folder in shulker_box.link_folders:
                resources -= {shulker_box.root / link_folder}
                resources -= set((shulker_box.root / link_folder).rglob("*"))
                try:
                    link_resource(link_folder, shulker_box.root, instance_root)
                except (OSError, NotADirectoryError) as oh_no:
                    failure_message = (
                        f"Error linking shulker box {shulker_box.name}"
                        f" to instance {instance.name}:"
                        f"\n{link_folder} is a non-empty directory."
                    )
                    # TODO: option to record failure but keep going
                    raise RuntimeError(failure_message) from oh_no
            for resource in resources:
                if not resource.is_file():  # also excludes broken links
                    continue
                resource_path = resource.relative_to(
                    shulker_box.root.expanduser().absolute()
                )
                try:
                    link_resource(
                        resource_path,
                        shulker_box.root,
                        instance_root,
                    )
                except (OSError, NotADirectoryError) as oh_no:
                    failure_message = (
                        f"Error linking shulker box {shulker_box.name}"
                        f" to instance {instance.name}:"
                        f"\n{resource_path} already exists."
                    )
                    # TODO: optiuon to record failure but keep going
                    raise RuntimeError(failure_message) from oh_no


def link_resource(
    resource_path: str | Path, shulker_root: Path, instance_root: Path
) -> None:
    """Create a symlink for the specified resource from an instance's space
    pointing to the tagged file / folder living inside a shulker box.

    Parameters
    ----------
    resource_path : str or Path
        Location of the resource relative to the instance's ".minecraft" folder
    shulker_root : Path
        The path to the shulker box
    instance_root : Path
        The path to the instance's ".minecraft" folder

    Raises
    ------
    NotADirectoryError
        If a file already exists where you're attempting to place the symlink
    OSError
        If a non-empty directory already exists where you're attempting to
        place the symlink

    Notes
    -----
    - This method will create any folders that do not exist within an instance
    - This method will overwrite existing symlinks and empty folders
      but will not overwrite or delete any actual files.
    """
    instance_path = (instance_root / resource_path).expanduser().absolute()
    instance_path.parent.mkdir(parents=True, exist_ok=True)

    relative_path = os.path.relpath(
        (shulker_root / resource_path).expanduser().absolute(), instance_path.parent
    )

    if instance_path.is_symlink():
        # remove previous symlink in this spot
        instance_path.unlink()
    else:
        try:
            os.rmdir(instance_path)
        except FileNotFoundError:
            pass  # A-OK

    os.symlink(
        relative_path,
        instance_path,
        target_is_directory=(shulker_root / resource_path).is_dir(),
    )
