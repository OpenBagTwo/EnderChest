"""Functionality for finding, resolving and parsing local installations and instances"""
import json
import logging
from configparser import ConfigParser, ParsingError
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import ParseResult

from enderchest.sync import render_remote

from . import filesystem as fs
from .enderchest import EnderChest, create_ender_chest
from .instance import InstanceSpec
from .loggers import GATHER_LOGGER
from .shulker_box import ShulkerBox


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
    GATHER_LOGGER.debug(f"Loading {config_path}")
    ender_chest = EnderChest.from_cfg(config_path)
    GATHER_LOGGER.debug(f"Parsed EnderChest installation from {minecraft_root}")
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
        GATHER_LOGGER.error(
            f"Could not load EnderChest from {minecraft_root}:\n  {bad_chest}"
        )
        instances = []
    if len(instances) == 0:
        GATHER_LOGGER.warning(
            f"There are no instances registered to the {minecraft_root} EnderChest",
        )
    else:
        GATHER_LOGGER.log(
            log_level,
            "These are the instances that are currently registered"
            f" to the {minecraft_root} EnderChest:\n"
            + "\n".join(
                [
                    f"  {i + 1}. {_render_instance(instance)})"
                    for i, instance in enumerate(instances)
                ]
            ),
        )
    return instances


def _render_instance(instance: InstanceSpec) -> str:
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
                GATHER_LOGGER.warning(
                    f"{bad_shulker}\n  Skipping shulker box {shulker_config.parent.name}"
                )

    except FileNotFoundError:
        GATHER_LOGGER.error(f"There is no EnderChest installed within {minecraft_root}")
        return []

    shulker_boxes = sorted(shulker_boxes)

    if len(shulker_boxes) == 0:
        if log_level >= logging.INFO:
            GATHER_LOGGER.warning(
                f"There are no shulker boxes within the {minecraft_root} EnderChest"
            )
    else:
        _report_shulker_boxes(
            shulker_boxes, log_level, f"the {minecraft_root} EnderChest"
        )
    return shulker_boxes


def _report_shulker_boxes(
    shulker_boxes: Iterable[ShulkerBox], log_level: int, ender_chest_name: str
) -> None:
    """Log the list of shulker boxes in the order they'll be linked"""
    GATHER_LOGGER.log(
        log_level,
        f"These are the shulker boxes within {ender_chest_name}"
        "\nlisted in the order in which they are linked:\n"
        + "\n".join(
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
    GATHER_LOGGER.debug(f"Attempting to parse {config_file}")
    shulker_box = ShulkerBox.from_cfg(config_file)
    GATHER_LOGGER.debug(f"Successfully parsed {_render_shulker_box(shulker_box)}")
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
    if shulker_box.root.name != shulker_box.name:
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
        GATHER_LOGGER.error(
            f"Could not load EnderChest from {minecraft_root}:\n  {bad_chest}"
        )
        remotes = ()

    if len(remotes) == 0:
        if log_level >= logging.INFO:
            GATHER_LOGGER.warning(
                f"There are no remotes registered to the {minecraft_root} EnderChest"
            )
        return []

    report = (
        "These are the remote EnderChest installations registered"
        f" to the one installed at {minecraft_root}"
    )
    remote_list: list[tuple[ParseResult, str]] = []
    for remote, alias in remotes:
        report += f"\n  - {render_remote(alias, remote)}"
        remote_list.append((remote, alias))
    GATHER_LOGGER.log(log_level, report)
    return remote_list


def load_shulker_box_matches(
    minecraft_root: Path, shulker_box_name: str
) -> Sequence[InstanceSpec]:
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
        GATHER_LOGGER.error(f"No EnderChest is installed in {minecraft_root}")
        return ()
    try:
        shulker_box = _load_shulker_box(config_file)
    except (FileNotFoundError, ValueError) as bad_box:
        GATHER_LOGGER.error(
            f"Could not load shulker box {shulker_box_name}\n  {bad_box}"
        )
        return ()

    instances = load_ender_chest_instances(minecraft_root, log_level=logging.DEBUG)
    if not instances:
        return instances

    if shulker_box is None:
        return ()
    matches = [instance for instance in instances if shulker_box.matches(instance)]

    if len(matches) == 0:
        report = "does not link to by any registered instances"
    else:
        report = "is linked to by the following instancs:\n" + "\n".join(
            f"  - {_render_instance(instance)}" for instance in matches
        )

    GATHER_LOGGER.info(f"The shulker box {_render_shulker_box(shulker_box)} {report}")

    return matches


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
                root=mc_instance.root.relative_to(minecraft_root)
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
        GATHER_LOGGER.warn(
            f"{version_manifest_file} has no latest-version lookup."
            "\nPlease check the parsed metadata to ensure that it's accurate.",
        )
        version_lookup = {}

    versions: list[str] = []
    tags: list[str] = ["vanilla"]
    for version in raw_versions:
        if version.startswith("latest-"):
            mapped_version = version_lookup.get(version[len("latest-") :])
            if mapped_version is not None:
                versions.append(mapped_version)
                tags.append(version)
                continue
        versions.append(version)

    return InstanceSpec(name, minecraft_folder, tuple(versions), None, tuple(tags))


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
                    version = component["version"]
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

    tags: list[str] = []

    if name == "":
        GATHER_LOGGER.warn(
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
            for tag, metadata in groups.items():
                # interestingly this comes from the folder name, not the actual name
                if name in metadata.get("instances", ()):
                    tags.append(tag)

        except FileNotFoundError as no_json:
            GATHER_LOGGER.warn(
                f"Could not find {instgroups_file} and thus could not load tags"
            )
        except json.JSONDecodeError as bad_json:
            GATHER_LOGGER.warn(
                f"{instgroups_file} is corrupt and could not be parsed for tags"
            )
        except KeyError as weird_json:
            GATHER_LOGGER.warn(f"Could not parse tags from {instgroups_file}")

    instance_cfg = minecraft_folder.parent / "instance.cfg"

    try:
        parser = ConfigParser(allow_no_value=True, interpolation=None)
        parser.read_string("[instance]\n" + instance_cfg.read_text())
        name = parser["instance"]["name"]
    except FileNotFoundError as no_cfg:
        GATHER_LOGGER.warn(
            f"Could not find {instance_cfg} and thus could not load the instance name"
        )
    except ParsingError as no_cfg:
        GATHER_LOGGER.warn(
            f"{instance_cfg} is corrupt and could not be parsed the instance name"
        )
    except KeyError as weird_json:
        GATHER_LOGGER.warn(f"Could not parse instance name from {instance_cfg}")

    if name == "":
        raise ValueError("Could not determine the name of the instance.")

    return InstanceSpec(name, minecraft_folder, (version,), modloader, tuple(tags))


def update_ender_chest(
    minecraft_root: Path,
    search_paths: Iterable[str | Path] | None = None,
    official: bool | None = None,
    remotes: Iterable[str | ParseResult | tuple[str, str] | tuple[ParseResult, str]]
    | None = None,
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
