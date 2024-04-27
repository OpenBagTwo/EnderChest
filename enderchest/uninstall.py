"""Functionality for copying all files into their instances"""

import logging
import os
import shutil
from pathlib import Path
from typing import Iterable

from . import filesystem as fs
from .enderchest import create_ender_chest
from .instance import InstanceSpec
from .inventory import load_ender_chest, load_ender_chest_instances
from .loggers import BREAK_LOGGER, IMPORTANT
from .prompt import confirm


def break_ender_chest(minecraft_root: Path) -> None:
    """Replace all instance symlinks with their actual targets, effectively
    "uninstalling" EnderChest

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    """
    instances = load_ender_chest_instances(minecraft_root, log_level=IMPORTANT)
    if not instances:
        BREAK_LOGGER.error("Aborting.")
        return

    BREAK_LOGGER.warning(
        "Are you sure you want to uninstall this EnderChest?"
        "\nDoing so will replace ALL the symlinks in each of the above instances"
        "\nwith copies of their EnderChest-linked targets."
        "\n\nTHIS CANNOT EASILY BE UNDONE!!"
    )
    if not confirm(default=False):
        BREAK_LOGGER.error("Aborting.")
        return

    chest_folder = fs.ender_chest_folder(minecraft_root)
    _break(chest_folder, instances)

    BREAK_LOGGER.log(
        IMPORTANT,
        "EnderChest has been uninstalled."
        "\nYou may now delete %s"
        "\nand uninstall the EnderChest package",
        chest_folder,
    )


def break_instances(minecraft_root: Path, instance_names: Iterable[str]) -> None:
    """Deregister the specified instances from EnderChest, replacing all
    instance symlinks with their actual targets, and then removing those
    instances from the enderchest.cfg

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    instance_names : list of str
        The names of the instances to break
    """
    ender_chest = load_ender_chest(minecraft_root)

    instance_lookup = {instance.name: instance for instance in ender_chest.instances}
    instances: list[InstanceSpec] = []
    for name in instance_names:
        try:
            instances.append(instance_lookup[name])
        except KeyError:
            BREAK_LOGGER.warning(
                f'No instance named "{name}" is registered to this EnderChest.'
                "\nSkipping."
            )
    if len(instances) == 0:
        BREAK_LOGGER.error("No valid instances specified.\nAborting.")
        return

    BREAK_LOGGER.warning(
        "Are you sure you want to remove the following instances from your EnderChest?"
        + "\n"
        + "\n".join((f"  - {instance.name}" for instance in instances))
        + "\nDoing so will replace ALL the symlinks in each of the above instances"
        "\nwith copies of their EnderChest-linked targets."
        "\n\nTHIS CANNOT EASILY BE UNDONE!!"
    )
    if not confirm(default=False):
        BREAK_LOGGER.error("Aborting.")
        return

    _break(fs.ender_chest_folder(minecraft_root), instances)
    for instance in instances:
        ender_chest._instances.remove(instance)
    create_ender_chest(minecraft_root, ender_chest)


def _break(
    chest_folder: Path,
    instances: Iterable[InstanceSpec],
) -> None:
    """Actually perform the uninstallation

    Parameters
    ----------
    chest_folder : Path
        The path of the EnderChest folder that's being "broken"
    instances : list of InstanceSpec
        The instances to clear of EnderChest links
    """
    chest_folder = chest_folder.expanduser().resolve()

    for instance in instances:
        BREAK_LOGGER.info("Copying files into %s", instance.name)
        for resource_path in instance.root.expanduser().rglob("*"):
            if not resource_path.is_symlink():
                continue

            literal_target = resource_path.readlink()

            direct_target = Path(
                os.path.normpath(resource_path.readlink().expanduser().absolute())
            )

            final_target = resource_path.resolve().expanduser()

            if not direct_target.is_relative_to(
                chest_folder
            ) and not final_target.is_relative_to(chest_folder):
                # note: there's a pathological case where someone does something
                # silly like:
                # ~/.minecraft/options.txt -> ~/options.txt
                #    -> EnderChest/options.txt -> /configs/minecraft_options.txt
                # where deleting your EnderChest folder would break the chain,
                # but EnderChest wouldn't have ever created that chain, so that
                # person is on their own.
                continue

            try:
                resource_path.unlink()
                BREAK_LOGGER.debug(
                    "Removed link: %s -> %s", resource_path, literal_target
                )
                if final_target.is_relative_to(chest_folder):
                    if final_target.is_dir():
                        shutil.copytree(
                            final_target,
                            resource_path,
                            symlinks=True,
                            dirs_exist_ok=True,
                        )
                    else:
                        shutil.copy2(
                            final_target,
                            resource_path,
                            follow_symlinks=False,
                        )
                else:
                    resource_path.symlink_to(final_target)

                BREAK_LOGGER.debug("Copied %s to %s", final_target, resource_path)
            except OSError as copy_fail:
                BREAK_LOGGER.warning(
                    "Failed to copy %s to %s:\n  %s",
                    final_target,
                    resource_path,
                    copy_fail,
                )
