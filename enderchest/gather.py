"""Functionality for onboarding and updating new installations and instances"""

import json
import logging
import os
import re
from configparser import ConfigParser, ParsingError
from pathlib import Path
from typing import Iterable
from urllib.parse import ParseResult

from . import filesystem as fs
from .enderchest import EnderChest, create_ender_chest
from .instance import InstanceSpec, normalize_modloader, parse_version
from .load import load_ender_chest
from .loggers import GATHER_LOGGER
from .prompt import prompt
from .shulker_box import _matches_version


def gather_minecraft_instances(
    minecraft_root: Path, search_path: Path, official: bool | None
) -> list[InstanceSpec]:
    """Search the specified directory for Minecraft installations and return
    any that are can be found and parsed

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

    Notes
    -----
    - If a minecraft installation is found but cannot be parsed
      (or parsed as specified) this method will report that failure but then
      continue on.
    - As a corollary, if _no_ valid Minecraft installations can be found, this
      method will return an empty list.
    """
    try:
        ender_chest = load_ender_chest(minecraft_root)
    except FileNotFoundError:
        # because this method can be called during crafting
        ender_chest = EnderChest(minecraft_root)
    GATHER_LOGGER.debug(f"Searching for Minecraft folders inside {search_path}")
    instances: list[InstanceSpec] = []
    for folder in fs.minecraft_folders(search_path):
        folder_path = folder.absolute()
        GATHER_LOGGER.debug(f"Found minecraft installation at {folder}")
        if official is not False:
            try:
                instances.append(gather_metadata_for_official_instance(folder_path))
                GATHER_LOGGER.info(
                    f"Gathered official Minecraft installation from {folder}"
                )
                _check_for_allowed_symlinks(ender_chest, instances[-1])
                continue
            except ValueError as not_official:
                GATHER_LOGGER.log(
                    logging.DEBUG if official is None else logging.WARNING,
                    (f"{folder} is not an official instance:" f"\n{not_official}",),
                )
        if official is not True:
            try:
                instances.append(gather_metadata_for_mmc_instance(folder_path))
                GATHER_LOGGER.info(
                    f"Gathered MMC-like Minecraft installation from {folder}"
                )
                _check_for_allowed_symlinks(ender_chest, instances[-1])
                continue
            except ValueError as not_mmc:
                GATHER_LOGGER.log(
                    logging.DEBUG if official is None else logging.WARNING,
                    f"{folder} is not an MMC-like instance:\n{not_mmc}",
                )
        GATHER_LOGGER.warning(
            f"{folder_path} does not appear to be a valid Minecraft instance"
        )
    for i, mc_instance in enumerate(instances):
        try:
            instances[i] = mc_instance._replace(
                root=mc_instance.root.relative_to(minecraft_root.resolve())
            )
        except ValueError:
            # TODO: if not Windows, try making relative to "~"
            pass  # instance isn't inside the minecraft root
    if not instances:
        GATHER_LOGGER.warning(
            f"Could not find any Minecraft instances inside {search_path}"
        )
    return instances


def gather_metadata_for_official_instance(
    minecraft_folder: Path, name: str = "official"
) -> InstanceSpec:
    """Parse files to generate metadata for an official Minecraft installation

    Parameters
    ----------
    minecraft_folder : Path
        The path to the installation's .minecraft folder
    name : str, optional
        A name or alias to give to the instance. If None is provided, the
        default name is "official"

    Returns
    -------
    InstanceSpec
        The metadata for this instance

    Raises
    ------
    ValueError
        If this is not a valid official Minecraft installation

    Notes
    -----
    This method will always consider this instance to be vanilla, with no
    modloader. If a Forge or Fabric executable is installed inside this
    instance, the precise name of that version of that modded minecraft
    will be included in the version list.
    """
    launcher_profile_file = minecraft_folder / "launcher_profiles.json"
    try:
        with launcher_profile_file.open() as lp_json:
            launcher_profiles = json.load(lp_json)
        raw_versions: list[str] = [
            profile["lastVersionId"]
            for profile in launcher_profiles["profiles"].values()
        ]
    except FileNotFoundError as no_json:
        raise ValueError(f"Could not find {launcher_profile_file}") from no_json
    except json.JSONDecodeError as bad_json:
        raise ValueError(
            f"{launcher_profile_file} is corrupt and could not be parsed"
        ) from bad_json
    except KeyError as weird_json:
        raise ValueError(
            f"Could not parse metadata from {launcher_profile_file}"
        ) from weird_json

    version_manifest_file = minecraft_folder / "versions" / "version_manifest_v2.json"
    try:
        with version_manifest_file.open() as vm_json:
            version_lookup: dict[str, str] = json.load(vm_json)["latest"]
    except FileNotFoundError as no_json:
        raise ValueError(f"Could not find {version_manifest_file}") from no_json
    except json.JSONDecodeError as bad_json:
        raise ValueError(
            f"{version_manifest_file} is corrupt and could not be parsed"
        ) from bad_json
    except KeyError as weird_json:
        GATHER_LOGGER.warning(
            f"{version_manifest_file} has no latest-version lookup."
            "\nPlease check the parsed metadata to ensure that it's accurate.",
        )
        version_lookup = {}

    versions: list[str] = []
    groups: list[str] = ["vanilla"]
    for version in raw_versions:
        if version.startswith("latest-"):
            mapped_version = version_lookup.get(version[len("latest-") :])
            if mapped_version is not None:
                versions.append(parse_version(mapped_version))
                groups.append(version)
                continue
        versions.append(parse_version(version))

    return InstanceSpec(name, minecraft_folder, tuple(versions), "", tuple(groups), ())


def gather_metadata_for_mmc_instance(
    minecraft_folder: Path, instgroups_file: Path | None = None
) -> InstanceSpec:
    """Parse files to generate metadata for a MultiMC-like instance

    Parameters
    ----------
    minecraft_folder : Path
        The path to the installation's .minecraft folder
    instgroups_file : Path
        The path to instgroups.json. If None is provided, this method will
        look for it two directories up from the minecraft folder

    Returns
    -------
    InstanceSpec
        The metadata for this instance

    Raises
    ------
    ValueError
        If this is not a valid MMC-like Minecraft instance

    Notes
    -----
    If this method is failing to find the appropriate files, you may want
    to try ensuring that minecraft_folder is an absolute path.
    """
    mmc_pack_file = minecraft_folder.parent / "mmc-pack.json"
    try:
        with mmc_pack_file.open() as mmc_json:
            components: list[dict] = json.load(mmc_json)["components"]

        version: str | None = None
        modloader: str | None = None

        for component in components:
            match component.get("uid"), component.get("cachedName", ""):
                case "net.minecraft", _:
                    version = parse_version(component["version"])
                case "net.fabricmc.fabric-loader", _:
                    modloader = "Fabric Loader"
                case "org.quiltmc.quilt-loader", _:
                    modloader = "Quilt Loader"
                case ("net.minecraftforge", _) | (_, "Forge"):
                    modloader = "Forge"
                case _, name if name.endswith("oader"):
                    modloader = name
                case _:
                    continue
            modloader = normalize_modloader(modloader)[0]
        if version is None:
            raise KeyError("Could not find a net.minecraft component")
    except FileNotFoundError as no_json:
        raise ValueError(f"Could not find {mmc_pack_file}") from no_json
    except json.JSONDecodeError as bad_json:
        raise ValueError(
            f"{mmc_pack_file} is corrupt and could not be parsed"
        ) from bad_json
    except KeyError as weird_json:
        raise ValueError(
            f"Could not parse metadata from {mmc_pack_file}"
        ) from weird_json

    name = minecraft_folder.parent.name

    instance_groups: list[str] = []

    if name == "":
        GATHER_LOGGER.warning(
            "Could not resolve the name of the parent folder"
            " and thus could not load tags."
        )
    else:
        instgroups_file = (
            instgroups_file or minecraft_folder.parent.parent / "instgroups.json"
        )

        try:
            with instgroups_file.open() as groups_json:
                groups: dict[str, dict] = json.load(groups_json)["groups"]
            for group, metadata in groups.items():
                # interestingly this comes from the folder name, not the actual name
                if name in metadata.get("instances", ()):
                    instance_groups.append(group)

        except FileNotFoundError as no_json:
            GATHER_LOGGER.warning(
                f"Could not find {instgroups_file} and thus could not load tags"
            )
        except json.JSONDecodeError as bad_json:
            GATHER_LOGGER.warning(
                f"{instgroups_file} is corrupt and could not be parsed for tags"
            )
        except KeyError as weird_json:
            GATHER_LOGGER.warning(f"Could not parse tags from {instgroups_file}")

    instance_cfg = minecraft_folder.parent / "instance.cfg"

    try:
        parser = ConfigParser(allow_no_value=True, interpolation=None)
        parser.read_string("[instance]\n" + instance_cfg.read_text())
        name = parser["instance"]["name"]
    except FileNotFoundError as no_cfg:
        GATHER_LOGGER.warning(
            f"Could not find {instance_cfg} and thus could not load the instance name"
        )
    except ParsingError as no_cfg:
        GATHER_LOGGER.warning(
            f"{instance_cfg} is corrupt and could not be parsed the instance name"
        )
    except KeyError as weird_json:
        GATHER_LOGGER.warning(f"Could not parse instance name from {instance_cfg}")

    if name == "":
        raise ValueError("Could not determine the name of the instance.")

    return InstanceSpec(
        name,
        minecraft_folder,
        (version,),
        modloader or "",
        tuple(instance_groups),
        (),
    )


def update_ender_chest(
    minecraft_root: Path,
    search_paths: Iterable[str | Path] | None = None,
    official: bool | None = None,
    remotes: (
        Iterable[str | ParseResult | tuple[str, str] | tuple[ParseResult, str]] | None
    ) = None,
) -> None:
    """Orchestration method that coordinates the onboarding of new instances or
    EnderChest installations

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder).
    search_paths : list of Paths, optional
        The local search paths to look for Minecraft installations within.
        Be warned that this search is performed recursively.
    official : bool | None, optional
        Optionally specify whether the Minecraft instances you expect to find
        are from the official launcher (`official=True`) or a MultiMC-derivative
        (`official=False`).
    remotes : list of URIs or (URI, str) tuples, optional
        Any remotes you wish to register to this instance. When a (URI, str) tuple
        is provided, the second value will be used as the name/alias of the remote.
        If there is already a remote specified with the given alias, this method will
        replace it.
    """
    try:
        ender_chest = load_ender_chest(minecraft_root)
    except (FileNotFoundError, ValueError) as bad_chest:
        GATHER_LOGGER.error(
            f"Could not load EnderChest from {minecraft_root}:\n  {bad_chest}"
        )
        return
    for search_path in search_paths or ():
        for instance in gather_minecraft_instances(
            minecraft_root, Path(search_path), official=official
        ):
            _ = ender_chest.register_instance(instance)
    for remote in remotes or ():
        try:
            if isinstance(remote, (str, ParseResult)):
                ender_chest.register_remote(remote)
            else:
                ender_chest.register_remote(*remote)
        except ValueError as bad_remote:
            GATHER_LOGGER.warning(bad_remote)

    create_ender_chest(minecraft_root, ender_chest)


def _check_for_allowed_symlinks(
    ender_chest: EnderChest, instance: InstanceSpec
) -> None:
    """Check if the instance:
        - is 1.20+
        - has not already blanket-allowed symlinks into the EnderChest

    and if it hasn't, offer to update the allow-list now *but only if* the user
    hasn't already told EnderChest "shut up I know what I'm doing."

    Parameters
    ----------
    ender_chest : EnderChest
        This EnderChest
    instance : InstanceSpec
        The instance spec to check
    """
    if ender_chest.offer_to_update_symlink_allowlist is False:
        return

    if not any(
        _needs_symlink_allowlist(version) for version in instance.minecraft_versions
    ):
        return
    ender_chest_abspath = os.path.realpath(ender_chest.root)

    symlink_allowlist = instance.root / "allowed_symlinks.txt"

    try:
        allowlist_contents = symlink_allowlist.read_text()
        already_allowed = ender_chest_abspath in allowlist_contents.splitlines()
        allowlist_needs_newline = not allowlist_contents.endswith("\n")
    except FileNotFoundError:
        already_allowed = False
        allowlist_needs_newline = False

    if already_allowed:
        return

    GATHER_LOGGER.warning(
        """
Starting with Minecraft 1.20, Mojang by default no longer allows worlds
to load if they are or if they contain symbolic links.
Read more: https://help.minecraft.net/hc/en-us/articles/16165590199181"""
    )

    response = prompt(
        f"Would you like EnderChest to add {ender_chest_abspath} to {symlink_allowlist}?",
        "Y/n",
    )

    if response.lower() not in ("y", "yes", ""):
        return

    with symlink_allowlist.open("a") as allow_file:
        if allowlist_needs_newline:
            allow_file.write("\n")
        allow_file.write(ender_chest_abspath + "\n")

    GATHER_LOGGER.info(f"{symlink_allowlist} updated.")


def _needs_symlink_allowlist(version: str) -> bool:
    """Determine if a version needs `allowed_symlinks.txt` in order to link
    to EnderChest. Note that this is going a little broader than is strictly
    necessary.

    Parameters
    ----------
    version: str
        The version string to check against

    Returns
    -------
    bool
        Returns False if the Minecraft version predates the symlink ban. Returns
        True if it doesn't (or is marginal).

    Notes
    -----
    Have I mentioned that parsing Minecraft version strings is a pain in the
    toucans?
    """
    # first see if it follows basic semver
    if _matches_version(">1.19", parse_version(version.split("-")[0])):
        return True
    if _matches_version("1.20.0*", parse_version(version.split("-")[0])):
        return True
    # is it a snapshot?
    if match := re.match("^([1-2][0-9])w([0-9]{1,2})", version.lower()):
        year, week = match.groups()
        if int(year) > 23:
            return True
        if int(year) == 23 and int(week) > 18:
            return True

    return False
