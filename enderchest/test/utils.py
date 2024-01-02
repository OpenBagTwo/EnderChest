"""Testing utilities"""
import json
import shutil
from importlib.resources import as_file
from pathlib import Path
from typing import Callable, Iterable

import pytest

from enderchest import EnderChest, InstanceSpec, ShulkerBox
from enderchest import filesystem as fs
from enderchest.instance import normalize_modloader

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

with as_file(testing_files.ENDERCHEST_CONFIG) as enderchest_cfg:
    TESTING_INSTANCES: tuple[InstanceSpec, ...] = tuple(
        EnderChest.from_cfg(enderchest_cfg).instances
    )


def create_mmc_pack_file(
    instance_folder: Path, minecraft_version: str, loader: str | None
) -> None:
    """Generate an MMC pack json and write it to file

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
    if minecraft_version.endswith(".0"):
        # learned the hard way that mmc-pack files don't have use ".0"
        minecraft_version = minecraft_version[:-2]

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

    with (instance_folder / "mmc-pack.json").open("w") as pack_file:
        json.dump(
            {"components": components, "formatVersion": 1},
            pack_file,
            indent=4,
        )


def create_instance_cfg(instance_folder: Path, name: str) -> None:
    """Generate a MultiMC instance config and write it to file

    Parameters
    ----------
    instance_folder : Path
        The folder where the pack file should be generated (the parent of
        the .minecraft folder)
    name : str
        The name of the instance
    """
    instance_folder.mkdir(parents=True, exist_ok=True)

    (instance_folder / "instance.cfg").write_text(
        f"""InstanceType=SevenEightNine
boring=blahblah
iconKey=iconlock
lastLaunchTime=1673878714535
lastTimePlayed=159
name={name}
notes=
totalTimePlayed=2552
"""
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
        (minecraft_folder / "versions").mkdir(exist_ok=True)
        shutil.copy(version_manifest, minecraft_folder / "versions")


def populate_mmc_instance_folder(
    instance_folder: Path,
    minecraft_version: str,
    loader: str | None,
    name: str | None = None,
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
    name : str, optional
        The name of the instance (if different from the name of the folder)
    """
    _set_up_minecraft_folder(instance_folder / ".minecraft", official=False)
    create_mmc_pack_file(
        instance_folder, minecraft_version=minecraft_version, loader=loader
    )
    create_instance_cfg(instance_folder, name or instance_folder.name)


def populate_instances_folder(instances_folder: Path) -> None:
    """Populate an MMC-style "instances" folder according to what's already in
    enderchest.cfg

    Parameters
    ----------
    instances_folder : Path
        The path of the instances folder
    """
    instances_folder.mkdir(parents=True)
    for instance_spec in TESTING_INSTANCES:
        if instance_spec.name == "official":
            continue

        populate_mmc_instance_folder(
            instances_folder / instance_spec.root.parent.name,
            instance_spec.minecraft_versions[0],
            instance_spec.modloader,
        )
    with as_file(testing_files.INSTGROUPS) as instgroups:
        shutil.copy(instgroups, instances_folder)


def pre_populate_enderchest(
    enderchest_folder: Path,
    *boxes: tuple[str, str],
) -> list[ShulkerBox]:
    """Create an EnderChest folder, pre-populated with the testing enderchest.cfg
    folder and the specified shulker boxes

    Parameters
    ----------
    enderchest_folder : Path
        The path of the EnderChest folder
    *boxes : 2-tuple of str
        Shulker boxes to populate, with tuple members of:
          - name : the folder name of the shulker
          - config : the contents of the config file

    Returns
    -------
    list of ShulkerBox
        A list of parsed shulker boxes corresponding to the ones rendered
        on the system
    """
    enderchest_folder.mkdir(parents=True, exist_ok=True)
    with as_file(testing_files.ENDERCHEST_CONFIG) as config_file:
        shutil.copy(config_file, enderchest_folder)
    shulker_boxes: list[ShulkerBox] = []
    for shulker_name, shulker_config in boxes:
        (enderchest_folder / shulker_name).mkdir(parents=True, exist_ok=True)
        config_path = enderchest_folder / shulker_name / fs.SHULKER_BOX_CONFIG_NAME
        with config_path.open("w") as config_file:
            config_file.write(shulker_config)
        shulker_box = ShulkerBox.from_cfg(config_path)
        for folder in shulker_box.link_folders:
            (shulker_box.root / folder).mkdir(parents=True, exist_ok=True)
        shulker_boxes.append(shulker_box)

    return shulker_boxes


# some sample shulker box configs to use with the above
GLOBAL_SHULKER = (
    "global",
    """; global/shulkerbox.cfg

; truly global--could even link to non-minecrafts (one day)
;[minecraft]
;*

[link-folders]
screenshots
backups
crash-reports
logs
""",
)

WILD_UPDATE_SHULKER = (
    "1.19",
    """; 1.19/shulkerbox.cfg
[properties]
name = wild update
priority = 1
notes = Writing it all down

[minecraft]
>=1.19.0,<1.20

[link-folders]
""",
)

VANILLA_SHULKER = (
    "vanilla",
    """; vanilla/shulkerbox.cfg

[properties]
priority = 2
last_modified = 1970-1-1 00:00:00.000000

[minecraft]
*

[modloader]
none
""",
)

OPTIFINE_SHULKER = (
    "optifine",
    """; optifine/shulkerbox.cfg
[properties]
priority = 3

[minecraft]
*

[modloader]
Forge

[link-folders]
shadercache  ; not that I think this is a thing

[do-not-link]
*.local
""",
)

STEAMDECK_SHULKER = (
    "steamdeck",
    """; steamdeck/shulkerbox.cfg
[properties]
priority = 20

[hosts]
steamdeck
""",
)


TESTING_SHULKER_CONFIGS = (
    GLOBAL_SHULKER,
    WILD_UPDATE_SHULKER,
    VANILLA_SHULKER,
    OPTIFINE_SHULKER,
    STEAMDECK_SHULKER,
)

# sometimes you just need a CSV
MATCH_CSV = """, global, 1.19, vanilla, optifine, steamdeck
~              ,   True, True,    True,    False,     False
axolotl        ,   True, False,   True,    False,     False
bee            ,   True, False,  False,     True,     False
chest-boat     ,   True, True,   False,    False,     False
drowned        ,   True, False,  False,    False,     False
"""


def _parse_match_csv() -> list[tuple[str, str, bool]]:
    """Parse the above table of shulker-to-instance matches"""
    matches: list[tuple[str, str, bool]] = []
    rows = MATCH_CSV.splitlines()
    header = rows.pop(0)
    shulker_boxes = [cell.strip() for cell in header.split(",")[1:]]
    for row in rows:
        cells = [cell.strip() for cell in row.split(",")]
        mc = cells.pop(0)
        for i, cell in enumerate(cells):
            matches.append((shulker_boxes[i], mc, cell == "True"))
    return matches


TESTING_SHULKER_INSTANCE_MATCHES = tuple(_parse_match_csv())


def resolve(path: Path, minecraft_root: Path) -> Path:
    """With all of this file system mocking, path resolution can be a pain
    in the toucans. This method means we should just have to solve for it
    once.

    Parameters
    ----------
    path : Path
        The path you're wanting to check
    minecraft_root : Path
        The minecraft root (from the fixture)

    Returns
    -------
    Path
        The absolute path to the thing you're wanting to check
    """
    if path.expanduser().is_absolute():
        return path.expanduser()
    return (minecraft_root / path).absolute()


def parametrize_over_instances(*instance_names: str):
    """Apply a pytest.mark.parametrize decorator to a test to apply the test
    to each of the specified instances (and apply clear and simple test IDs).

    Parameters
    ----------
    *instance_names : str
        The instances to test. If no instance names are provided, then all
        instances will be included

    Notes
    -----
      - The parametrized tests will be ordered as provided
      - The name of the parametrized argument provided to the test will be "instance"
    """
    instance_lookup = {mc.name: mc for mc in TESTING_INSTANCES}
    if len(instance_names) == 0:
        instance_names = tuple(instance_lookup.keys())

    instances = [instance_lookup[name] for name in instance_names]

    return pytest.mark.parametrize("instance", instances, ids=instance_names)


def scripted_prompt(responses: Iterable[str]) -> Callable[..., str]:
    """Create a replacement for the built-in input() method for use in
    monkeypatching that will process inputs given from a script of responses

    Parameters
    ----------
    responses : list-like of str
        The scripted responses

    Returns
    -------
    function
        A drop-in replacement for the built-in input method
    """
    script = iter(responses)

    def read_from_script(prompt: str | None = None) -> str:
        line = next(script)
        print((prompt or "") + line)
        return line

    return read_from_script


def instance(
    name: str,
    root: Path,
    minecraft_versions: Iterable[str] | None = None,
    modloader: str | None = None,
    groups: Iterable[str] | None = None,
    tags: Iterable[str] | None = None,
) -> InstanceSpec:
    """Shortcut constructor"""
    return InstanceSpec(
        name,
        root,
        tuple(minecraft_versions or ()),
        modloader or "",
        tuple(groups or ()),
        tuple(tags or ()),
    )


def normalize_instance(mc: InstanceSpec) -> InstanceSpec:
    """Normalize the values inside an instance tuple"""
    return mc._replace(
        # this should be fully checked by instance.equals()
        root=mc.root.expanduser().relative_to(mc.root.expanduser().parent.parent),
        modloader=normalize_modloader(mc.modloader)[0],
        minecraft_versions=tuple(sorted(mc.minecraft_versions)),
        groups_=tuple(sorted(group.lower() for group in mc.groups_)),
        tags_=tuple(sorted(tag.lower() for tag in mc.tags_)),
    )
