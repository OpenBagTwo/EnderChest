"""Symlinking functionality"""
import itertools
import logging
import os
from pathlib import Path
from typing import Iterable

from . import filesystem as fs
from .gather import load_ender_chest, load_ender_chest_instances, load_shulker_boxes
from .instance import InstanceSpec
from .loggers import PLACE_LOGGER
from .prompt import prompt
from .shulker_box import ShulkerBox


def place_ender_chest(
    minecraft_root: Path,
    cleanup: bool = True,
    error_handling: str = "abort",
    rollback=False,
) -> None:
    """Link all instance files and folders to all shulker boxes

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    cleanup : bool, optional
        By default, this method will remove any broken links in your instances
        and servers folders. To disable this behavior, pass in `cleanup=False`
    error_handling : str, optional
        By default, if a linking failure occurs, this method will terminate
        immediately (`error_handling=abort`). Alternatively,
          - pass in `error_handling="ignore"` to continue as if the link failure
            hadn't occurred
          - pass in `error_handling="skip"` to abort linking the current instance
            to the current shulker box but otherwise continue on
          - pass in `error_handling="skip-instance"` to abort linking the current
            instance altogether but to otherwise continue on with other instances
          - pass in `error_handling="skip-shulker-box"` to abort linking to the current
            shulker box altogether but to otherwise continue on with other boxes
          - pass in `error_handling="prompt"` to ask what to do on each failure
    rollback: bool, optional
        In the future in the event of linking errors passing in `rollback=True`
        can be used to roll back any changes that have already been applied
        based on the error-handling method specified.
    """
    if rollback is not False:
        raise NotImplementedError("Rollbacks are not currently supported")

    try:
        host = load_ender_chest(minecraft_root).name
    except (FileNotFoundError, ValueError) as bad_chest:
        PLACE_LOGGER.error(
            f"Could not load EnderChest from {minecraft_root}:\n  {bad_chest}"
        )
        return

    instances = load_ender_chest_instances(minecraft_root, log_level=logging.DEBUG)

    shulker_boxes: list[ShulkerBox] = []

    for shulker_box in load_shulker_boxes(minecraft_root, log_level=logging.DEBUG):
        if not shulker_box.matches_host(host):
            PLACE_LOGGER.debug(
                f"{shulker_box.name} is not intended for linking to this host ({host})"
            )
            continue
        else:
            shulker_boxes.append(shulker_box)

    skip_instances: list[InstanceSpec] = []

    def handle_error(instance: InstanceSpec) -> str:
        """Centralized error-handling

        Parameters
        ----------
        instance:
            The current instance (in case it needs to be added to the skip list)

        Returns
        -------
        str
            Instructions on what to do next. Options are:
              - return
              - break
              - coninue
              - pass
        """
        if error_handling == "prompt":
            proceed_how = (
                prompt(
                    "How would you like to proceed?"
                    "\n[Q]uit, [C]ontinue, abort linking the rest of this shulker/instance [M]atch?"
                    "\nskip the rest of this [I]nstance, skip the rest of this [S]hulker box?",
                    suggestion="I",  # TODO: reevaluate default (it's 50/50 due to link folders)
                )
                .lower()
                .replace(" ", "")
                .replace("-", "")
                .replace("_", "")
            )
            match proceed_how:
                case "" | "i" | "instance" | "skipinstance":
                    proceed_how = "skip-instance"
                case "q" | "quit" | "abort" | "exit" | "stop":
                    proceed_how = "abort"
                case "c" | "continue" | "ignore":
                    proceed_how = "ignore"
                case "m" | "match" | "skip":
                    proceed_how = "skip"
                case "s" | "shulker" | "shulkerbox" | "skipshulker":
                    proceed_how = "skip-shulker"
                case _:
                    PLACE_LOGGER.error("Invalid selection.")
                    return handle_error(instance)
        else:
            proceed_how = error_handling

        match proceed_how:
            case "abort" | "stop" | "quit" | "exit":
                PLACE_LOGGER.error("Aborting")
                return "return"
            case "ignore":
                PLACE_LOGGER.debug("Ignoring")
                return "pass"
            case "skip":
                PLACE_LOGGER.warning("Skipping the rest of this match")
                return "continue"
            case "skip-instance":
                PLACE_LOGGER.warning("Skipping any more linking from this instance")
                skip_instances.append(instance)
                return "continue"
            case "skip-shulker-box" | "skip-shulkerbox" | "skip-shulker":
                PLACE_LOGGER.warning("Skipping any more linking into this shulker box")
                return "break"
            case _:
                raise ValueError(
                    f"Unrecognized error-handling method: {error_handling}"
                )

    for shulker_box in shulker_boxes:
        for instance in instances:
            if not shulker_box.matches(instance):
                continue
            if instance in skip_instances:
                continue

            instance_root = (minecraft_root / instance.root.expanduser()).expanduser()
            box_root = shulker_box.root.expanduser().absolute()

            if not instance_root.exists():
                PLACE_LOGGER.error(
                    f"No minecraft instance exists at {instance_root.expanduser().absolute()}"
                )
                match handle_error(instance):
                    case "return":
                        return
                    case "break":
                        break
                    case _:  # nothing to link, so might as well skip the rest
                        continue

            PLACE_LOGGER.info(f"Linking {instance.root} to {shulker_box.name}")

            resources = set(_rglob(box_root, shulker_box.max_link_depth))
            resources.remove(fs.shulker_box_config(minecraft_root, shulker_box.name))

            match_exit = "pass"
            for link_folder in shulker_box.link_folders:
                resources -= {box_root / link_folder}
                resources -= set((box_root / link_folder).rglob("*"))
                try:
                    link_resource(link_folder, box_root, instance_root)
                except (OSError, NotADirectoryError) as oh_no:
                    PLACE_LOGGER.error(
                        f"Error linking shulker box {shulker_box.name}"
                        f" to instance {instance.name}:"
                        f"\n  {(instance.root / link_folder)} is a"
                        " non-empty directory"
                    )
                    match handle_error(instance):
                        case "return":
                            return
                        case "break":
                            match_exit = "break"
                            break
                        case "continue":
                            match_exit = "continue"
                            break
                        case "pass":
                            continue  # or pass--it's the end of the loop

            if match_exit not in ("break", "continue"):
                for resource in resources:
                    resource_path = resource.relative_to(box_root)
                    try:
                        link_resource(
                            resource_path,
                            box_root,
                            instance_root,
                        )
                    except (OSError, NotADirectoryError) as oh_no:
                        PLACE_LOGGER.error(
                            f"Error linking shulker box {shulker_box.name}"
                            f" to instance {instance.name}:"
                            f"\n  {(instance.root / resource_path)}"
                            " already exists"
                        )
                        match handle_error(instance):
                            case "return":
                                return
                            case "break":
                                match_exit = "break"
                                break
                            case "continue":
                                match_exit = "continue"  # technically does nothing
                                break
                            case "pass":
                                continue  # or pass--it's the end of the loop

            if cleanup:  # consider this a "finally"
                # we clean up as we go, just in case of a failure
                for file in instance_root.rglob("*"):
                    if not file.exists():
                        PLACE_LOGGER.debug(f"Removing broken link: {file}")
                        file.unlink()

            if match_exit == "break":
                break


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
        PLACE_LOGGER.debug(f"Removing old link at {instance_path}")
        instance_path.unlink()
    else:
        try:
            os.rmdir(instance_path)
            PLACE_LOGGER.debug(f"Removed empty diretory at {instance_path}")
        except FileNotFoundError:
            pass  # A-OK

    PLACE_LOGGER.debug(f"Linking {instance_path} to {relative_path}")
    os.symlink(
        relative_path,
        instance_path,
        target_is_directory=(shulker_root / resource_path).is_dir(),
    )


def _rglob(root: Path, max_depth: int) -> Iterable[Path]:
    """Find all files (and directories* and symlinks) in the path up to the
    specified depth

    Parameters
    ----------
    root : Path
        The path to search
    max_depth : int
        The maximum number of levels to go

    Returns
    -------
    list-like of paths
        The files (and directories and symlinks) in the path up to that depth

    Notes
    -----
    - Unlike an actual rglob, this method does not return any directories that
      are not at the maximum depth
    - Setting max_depth to 0 (or below) will return all files in the root, but
      ***be warned*** that because this method follows symlinks, you can very
      easily find yourself in an infinite loop
    """
    top_level = root.iterdir()
    if max_depth == 1:
        return top_level
    return itertools.chain(
        *(
            _rglob(path, max_depth - 1) if path.is_dir() else (path,)
            for path in top_level
        )
    )
