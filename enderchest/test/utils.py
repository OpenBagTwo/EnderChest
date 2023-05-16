"""Testing utilities"""
import configparser
import json
import shutil
from importlib.resources import as_file
from pathlib import Path
from typing import Mapping, NamedTuple

from . import testing_files

# folders common to both official and MMC-derived .minecraft folders
COMMON_FOLDERS: tuple[str, ...] = (
    "backups",
    "crash_reports",
    "logs",
    "resourcepacks",
    "saves",
    "screenshots",
)

# folders found in the official launcher's .minecraft folder
OFFICIAL_FOLDERS: tuple[str, ...] = (
    *COMMON_FOLDERS,
    "assets",
    "bin",
    "versions",
)

# folders commonly found in the .minecraft folder of MMC-derived instances
MMC_FOLDERS: tuple[str, ...] = (
    *COMMON_FOLDERS,
    "config",
    "coremods",
    "data",
    "patchouli-books",
    "replay_recordings",
    "server-resource-packs",
    "shaderpacks",
    "texturepacks",
    ".bobby",
)


# TODO: the next few methods / classes are almost certainly going in enderchest proper
class InstanceSpec(NamedTuple):
    """Specification of a Minecraft instance

    Parameters
    ----------
    root : Path
        The path to its ".minecraft" folder
    minecraft_versions : list-like of str
        The minecraft versions of this instance. This is typically a 1-tuple,
        but some loaders (such as the official one) will just comingle all
        your assets together across all profiles
    modloader : str or None
        The (display) name of the modloader, or None if this is a vanilla
        instance
    tags : list-like of str
        The tags assigned to this instance
    """

    root: Path
    minecraft_versions: tuple[str, ...]
    modloader: str | None
    tags: tuple[str, ...]

    @classmethod
    def from_cfg(cls, section: Mapping[str, str]) -> "InstanceSpec":
        """Parse an instance spec as read in from an enderchest.cfg file

        Parameters
        ----------
        section : dict-like of str to str
            The section in the enderchest.cfg file parsed from an
            enderchest.cfg file by a ConfigParser

        Returns
        -------
        InstanceSpec
            The resulting InstanceSpec

        Raises
        ------
        KeyError
            If a required key is absent
        ValueError
            If a required entry cannot be parsed
        """
        return cls(
            Path(section["root"]),
            tuple(section["minecraft_version"].strip().split()),
            section.get("modloader", None),
            tuple(section.get("tags", "").strip().split()),
        )


def get_instance_metadata(enderchest_cfg: Path) -> dict[str, InstanceSpec]:
    """Parse an enderchest.cfg file to get the relevant instance metadata.

    Parameters
    ----------
    enderchest_cfg : Path
        The enderchest config file to read

    Returns
    -------
    dict of str to InstanceSpec
        The map of instance names to their metadata
    """
    instances = configparser.ConfigParser()
    instances.read(enderchest_cfg)
    return {
        instance_name: InstanceSpec.from_cfg(instances[instance_name])
        for instance_name in instances.sections()
    }


with as_file(testing_files.ENDERCHEST_CONFIG) as enderchest_cfg:
    TESTING_INSTANCES: tuple[tuple[str, InstanceSpec], ...] = tuple(
        get_instance_metadata(enderchest_cfg).items()
    )


def create_mmc_pack_file(
    instance_folder: Path, minecraft_version: str, loader: str | None
) -> None:
    """Generate an MMC pack file and write it to file

    Parameters
    ----------
    instance_folder : Path
        The folder where the pack file should be generated (the parent of
        the .minecraft folder)
    minecraft_version : str
        The minecraft version
    loader : str | None
        The loader (None if it's a vanilla instance)
    """

    components: list[dict[str, str]] = [
        {
            "cachedName": "Minecraft",
            "cachedRequires": "dontreadme",
            "cachedVersion": "dontreadme",
            "important": "dontreadme",
            "uid": "net.minecraft",
            "version": minecraft_version,
        },
    ]

    if loader is not None:
        match loader:
            case "Forge":
                loader_display_name = "Forge"
                loader_uid = "net.minecraftforge"
            case "Fabric":
                loader_display_name = "Fabric Loader"
                loader_uid = "net.fabricmc.fabric-loader"
            case "Quilt":
                loader_display_name = "Quilt"
                loader_uid = "org.quiltmc.quilt-loader"
            case _:
                loader_display_name = loader
                loader_uid = "xxx." + loader.lower().replace(" ", "-")

        components.append(
            {
                "cachedName": loader_display_name,
                "uid": loader_uid,
            }
        )

    instance_folder.mkdir(parents=True, exist_ok=True)

    with (instance_folder / "mmc_pack.json").open("w") as pack_file:
        json.dump(
            {"components": components, "formatVersion": 1},
            pack_file,
            indent=4,
        )


def _set_up_minecraft_folder(minecraft_folder: Path, official: bool) -> None:
    """Populate a minecraft folder with a bunch of dummy folders. You probably
    want to use `populate_official_minecraft_folder` or `populate_mmc_instance`
    rather than calling this directly.

    Parameters
    ----------
    minecraft_folder : Path
        Path of the .minecraft folder
    official : bool
        To mimic an MMC-style instance folder, pass in `official=False`. To
        mimic an installation from the official launcher instead, pass in
        `official=True`.
    """
    for folder in OFFICIAL_FOLDERS if official else MMC_FOLDERS:
        (minecraft_folder / folder).mkdir(parents=True)
    with as_file(testing_files.CLIENT_OPTIONS) as options_txt:
        # this is silly, as shutil.copy would accept the Traversable,
        # but mypy complains, so eh.
        shutil.copy(options_txt, minecraft_folder)


def populate_official_minecraft_folder(minecraft_folder: Path) -> None:
    """Populate the .minecraft folder created by the official launcher

    Parameters
    ----------
    minecraft_folder : Path
        Path of the .minecraft folder
    """
    _set_up_minecraft_folder(minecraft_folder, official=True)
    with as_file(testing_files.LAUNCHER_PROFILES) as launcher_profiles:
        shutil.copy(launcher_profiles, minecraft_folder)
    with as_file(testing_files.VERSION_MANIFEST) as version_manifest:
        shutil.copy(version_manifest, minecraft_folder)


def populate_mmc_instance_folder(
    instance_folder: Path, minecraft_version: str, loader: str | None
) -> None:
    """Populate the .minecraft folder created by an MMC-like launcher

    Parameters
    ----------
    instance_folder : Path
        The folder containing the MMC-like instance's files (the parent of
        the .minecraft folder)
    minecraft_version : str
        The minecraft version
    loader : str | None
        The loader (if vanilla this will be None)
    """
    _set_up_minecraft_folder(instance_folder / ".minecraft", official=False)
    create_mmc_pack_file(
        instance_folder, minecraft_version=minecraft_version, loader=loader
    )


def populate_instances_folder(instances_folder: Path) -> None:
    """Populate an MMC-style "instances" folder according to what's already in
    enderchest.cfg

    Parameters
    ----------
    instances_folder : Path
        The path of the instances folder
    """
    instances_folder.mkdir(parents=True)
    for instance_name, instance_spec in TESTING_INSTANCES:
        if instance_name == "official":
            continue

        populate_mmc_instance_folder(
            instances_folder / instance_name,
            instance_spec.minecraft_versions[0],
            instance_spec.modloader,
        )
    with as_file(testing_files.INSTGROUPS) as instgroups:
        shutil.copy(instgroups, instances_folder)


def pre_populate_enderchest(
    enderchest_folder: Path,
    *shulkers: tuple[str, str],
) -> None:
    """Create an EnderChest folder, pre-populated with the testing enderchest.cfg
    folder and the specified shulker boxes

    Parameters
    ----------
    enderchest_folder : Path
        The path of the EnderChest folder
    *shulkers : 2-tuple of str
        Shulker boxes to populate, with tuple members of:
          - name : the folder name of the shulker
          - config : the contents of the config file
    """
    enderchest_folder.mkdir(parents=True, exist_ok=True)
    with as_file(testing_files.ENDERCHEST_CONFIG) as enderchest_cfg:
        shutil.copy(enderchest_cfg, enderchest_folder)
    for shulker_name, shulker_config in shulkers:
        (enderchest_folder / shulker_name).mkdir(parents=True, exist_ok=True)
        with (enderchest_folder / "shulker.cfg").open("w") as config_file:
            config_file.write(shulker_config)
