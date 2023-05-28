"""Specification and configuration of a shulker box"""
import datetime as dt
import fnmatch
import os
from configparser import ConfigParser, ParsingError
from io import StringIO
from pathlib import Path
from typing import NamedTuple

import semantic_version as semver

from . import filesystem as fs
from ._version import get_versions
from .instance import InstanceSpec
from .loggers import CRAFT_LOGGER


class ShulkerBox(NamedTuple):
    """Specification of a ShulkerBox

    Parameters
    ----------
    priority : int
        The priority for linking assets in the shulker box (higher priority
        shulkers are linked last)
    name : str
        The name of the shulker box (which is incidetentally used to break
        priority ties)
    root : Path
        The path to the root of the shulker box
    match_criteria : list-like of tuples
        The parameters for matching instances to this shulker box. Each element
        consists of:

          - the name of the condition
          - the matching values for that condition

        The logic applied is that an instance must match at least one value
        for each condition (so it's ANDing a collection of ORs)
    link_folders : list-like of str
        The folders that should be linked in their entirety
    max_link_depth : int, optional
        By default, non-root-level folders (that is, folders inside of folders)
        will be treated as files for the purpose of linking. Put another way,
        only files with a depth of 2 or less from the shulker root will be
        linked. This behavior can be overridden by explicitly setting
        the `max_link_depth` value, but **this feature is highly experimental**,
        so use it at your own risk.

    Notes
    -----
    A shulker box specification is immutable, so making changes (such as
    updating the match critera) can only be done on copies created via the
    `_replace` method, inherited from the NamedTuple parent class.
    """

    priority: int
    name: str
    root: Path
    match_criteria: tuple[tuple[str, tuple[str, ...]], ...]
    link_folders: tuple[str, ...]
    max_link_depth: int = 2

    @classmethod
    def from_cfg(cls, config_file: Path) -> "ShulkerBox":
        """Parse a shulker box from its config file

        Parameters
        ----------
        config_file : Path
            The path to the config file

        Returns
        -------
        ShulkerBox
            The resulting ShulkerBox

        Raises
        ------
        ValueError
            If the config file at that location cannot be parsed
        FileNotFoundError
            If there is no config file at the specified location
        """
        priority = 0
        max_link_depth = 2
        root = config_file.parent
        name = root.name
        parser = ConfigParser(
            allow_no_value=True, inline_comment_prefixes=(";",), interpolation=None
        )
        parser.optionxform = str  # type: ignore
        try:
            assert parser.read(config_file)
        except ParsingError as bad_cfg:
            raise ValueError(f"Could not parse {config_file}") from bad_cfg
        except AssertionError:
            raise FileNotFoundError(f"Could not open {config_file}")

        match_criteria: dict[str, tuple[str, ...]] = {}

        for section in parser.sections():
            normalized = (
                section.lower().replace(" ", "").replace("-", "").replace("_", "")
            )
            if normalized.endswith("s"):
                normalized = normalized[:-1]  # lazy de-pluralization
            if normalized in ("linkfolder", "folder"):
                normalized = "link-folders"
            if normalized in ("minecraft", "version", "minecraftversion"):
                normalized = "minecraft"
            if normalized in ("modloader", "loader"):
                normalized = "modloader"
            if normalized in ("instance", "tag", "host"):
                normalized += "s"  # lazy re-pluralization

            if normalized == "propertie":  # lulz
                # TODO check to make sure properties hasn't been read before
                # most of this section gets ignored
                priority = parser[section].getint("priority", 0)
                max_link_depth = parser[section].getint("max-link-depth", 2)
                # TODO: support specifying filters (and link-folders) in the properties section
                continue
            if normalized in match_criteria.keys():
                raise ValueError(f"{config_file} specifies {normalized} more than once")

            if normalized == "minecraft":
                minecraft_versions = []
                for key, value in parser[section].items():
                    if value is None:
                        minecraft_versions.append(key)
                    elif key.lower().strip().startswith("version"):
                        minecraft_versions.append(value)
                    else:  # what happens if you specify ">=1.19" or "=1.12"
                        minecraft_versions.append("=".join((key, value)))
                match_criteria["minecraft"] = tuple(minecraft_versions)
            else:
                # really hoping delimiter shenanigans doesn't show up anywhere else
                match_criteria[normalized] = tuple(parser[section].keys())

        link_folders = match_criteria.pop("link-folders", ())

        return cls(
            priority,
            name,
            root,
            tuple(match_criteria.items()),
            link_folders,
            max_link_depth=max_link_depth,
        )

    def write_to_cfg(self, config_file: Path | None = None) -> str:
        """Write this shulker's configuration to INI

        Parameters
        ----------
        config_file : Path, optional
            The path to the config file, assuming you'd like to write the
            contents to file

        Returns
        -------
        str
            An INI-syntax rendering of this shulker box's config

        Notes
        -----
        The "root" attribute is ignored for this method
        """
        config = ConfigParser(allow_no_value=True, interpolation=None)
        config.optionxform = str  # type: ignore
        config.add_section("properties")
        config.set("properties", "priority", str(self.priority))
        if self.max_link_depth != 2:
            config.set("properties", "max-link-depth", str(self.max_link_depth))
        config.set("properties", "last_modified", dt.datetime.now().isoformat(sep=" "))
        config.set(
            "properties", "generated_by_enderchest_version", get_versions()["version"]
        )

        for condition, values in self.match_criteria:
            config.add_section(condition)
            for value in values:
                config.set(condition, value)

        config.add_section("link-folders")
        for folder in self.link_folders:
            config.set("link-folders", folder)

        buffer = StringIO()
        buffer.write(f"; {os.path.join(self.name, fs.SHULKER_BOX_CONFIG_NAME)}\n")
        config.write(buffer)
        buffer.seek(0)  # rewind

        if config_file:
            config_file.write_text(buffer.read())
            buffer.seek(0)
        return buffer.read()

    def matches(self, instance: InstanceSpec) -> bool:
        """Determine whether the shulker box matches the given instance

        Parameters
        ----------
        instance : InstanceSpec
            The instance's specification

        Returns
        -------
        bool
            True if the instance matches the shulker box's conditions, False
            otherwise.
        """
        for condition, values in self.match_criteria:
            match condition:  # these should have been normalized on read-in
                case "instances":
                    for value in values:
                        if fnmatch.fnmatchcase(instance.name, value):
                            break
                    else:
                        return False
                case "tags":
                    for value in values:
                        if fnmatch.filter(
                            [tag.lower() for tag in instance.tags], value.lower()
                        ):
                            break
                    else:
                        return False
                case "modloader":
                    normalized: list[str] = sum(
                        [_normalize_modloader(value) for value in values], []
                    )
                    for value in normalized:
                        if fnmatch.filter(
                            [
                                loader.lower()
                                for loader in _normalize_modloader(instance.modloader)
                            ],
                            value.lower(),
                        ):
                            break
                    else:
                        return False
                case "minecraft":
                    for value in values:
                        if any(
                            (
                                _matches_version(value, version)
                                for version in instance.minecraft_versions
                            )
                        ):
                            break
                    else:
                        return False
                case "hosts":
                    # this is handled at a higher level
                    pass
                case _:
                    raise NotImplementedError(
                        f"Don't know how to apply match condition {condition}."
                    )
        return True

    def matches_host(self, hostname: str):
        """Determine whether the shulker box should be linked to from the
        current host machine

        Returns
        -------
        bool
            True if the shulker box's hosts spec matches the host, False otherwise.
        """
        for condition, values in self.match_criteria:
            if condition == "hosts":
                if not any(
                    fnmatch.fnmatchcase(hostname.lower(), host_spec.lower())
                    for host_spec in values
                ):
                    return False
        return True


def _normalize_modloader(loader: str | None) -> list[str]:
    """Implement common modloader aliases

    Parameters
    ----------
    loader : str
        User-provided modloader name

    Returns
    -------
    list of str
        The modloader values that should be checked against to match the user's
        intent
    """
    if loader is None:  # this would be from the instance spec
        return [""]
    match loader.lower().replace(" ", "").replace("-", "").replace("_", "").replace(
        "/", ""
    ):
        case "none" | "vanilla":
            return [""]
        case "fabric" | "fabricloader":
            return ["Fabric Loader"]
        case "quilt" | "quiltloader":
            return ["Quilt Loader"]
        case "fabricquilt" | "quiltfabric" | "fabriclike" | "fabriccompatible":
            return ["Fabric Loader", "Quilt Loader"]
        case "forge" | "forgeloader" | "minecraftforge":
            return ["Forge"]
        case _:
            return [loader]


def _matches_version(version_spec: str, version_string: str) -> bool:
    """Determine whether a version spec matches a version string, taking into
    account that neither users nor Mojang rigidly follow semver (or at least
    PEP440)

    Parameters
    ----------
    version_spec : str
        A version specification provided by a user
    version_string : str
        A version string, likely parsed from an instance's configuration

    Returns
    -------
    bool
        True if the spec matches the version, False otherwise

    Notes
    -----
    This method *does not* match snapshots to their corresponding version
    range--for that you're just going to have to be explicit.
    """
    try:
        return semver.SimpleSpec(version_spec).match(semver.Version(version_string))
    except ValueError:
        # fall back to simple fnmatching
        return fnmatch.fnmatchcase(version_string.lower(), version_spec.lower())


DEFAULT_SHULKER_FOLDERS = (  # TODO: customize in enderchest.cfg
    "config",
    "mods",
    "resourcepacks",
    "saves",
    "shaderpacks",
)

STANDARD_LINK_FOLDERS = (  # TODO: customize in enderchest.cfg
    "backups",
    "cachedImages",
    "crash-reports",
    "logs",
    "replay_recordings",
    "screenshots",
    ".bobby",
)


def create_shulker_box(minecraft_root: Path, shulker_box: ShulkerBox) -> None:
    """Create a shulker box folder based on the provided configuration

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    shulker_box : ShulkerBox
        The spec of the box to create

    Notes
    -----
    - The "root" attribute of the ShulkerBox config will be ignored--instead
      the shulker box will be created at
      <minecraft_root>/EnderChest/<shulker box name>
    - This method will fail if there is no EnderChest set up in the minecraft
      root
    - This method does not check to see if there is already a shulker box
      set up at the specificed location--if one exists, its config will
      be overwritten
    """
    root = fs.shulker_box_root(minecraft_root, shulker_box.name)
    root.mkdir(exist_ok=True)

    for folder in (*DEFAULT_SHULKER_FOLDERS, *shulker_box.link_folders):
        CRAFT_LOGGER.debug(f"Creating {root / folder}")
        (root / folder).mkdir(exist_ok=True, parents=True)

    config_path = fs.shulker_box_config(minecraft_root, shulker_box.name)
    shulker_box.write_to_cfg(config_path)
    CRAFT_LOGGER.info(f"Shulker box configuration written to {config_path}")
