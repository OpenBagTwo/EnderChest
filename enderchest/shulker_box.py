"""Specification and configuration of a shulker box"""
import datetime as dt
import fnmatch
from configparser import ConfigParser, ParsingError
from pathlib import Path
from typing import NamedTuple

import semantic_version as semver

from ._version import get_versions
from .instance import InstanceSpec


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
        consistents of:
          - the name of the condition
          - the matching values for that condition

        The logic applied is that an instance must match at least one value
        for each condition (so it's ANDing a collection of ORs)
    link_folders : list-like of str
        The folders that should be linked in their entirety

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
        root = config_file.parent
        name = root.name
        parser = ConfigParser(allow_no_value=True, inline_comment_prefixes=(";",))
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
            if normalized in ("instance", "tag"):
                normalized += "s"  # lazy re-pluralization

            if normalized == "propertie":  # lulz
                # TODO check to make sure properties hasn't been read before
                # most of this section gets ignored
                priority = parser[section].getint("priority", 0)
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

        return cls(priority, name, root, tuple(match_criteria.items()), link_folders)

    def write_to_cfg(self, config_file: Path) -> None:
        """Write this shulker's configuration to file

        Parameters
        ----------
        config_file : Path
            The path to the config file

        Notes
        -----
        The "root" attribute is ignored for this method
        """
        config = ConfigParser(allow_no_value=True)
        config.add_section("properties")
        config.set("properties", "priority", str(self.priority))
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

        with open(config_file, "w") as f:
            f.write(f"; {config_file.relative_to(config_file.parent.parent)}\n")
            config.write(f)

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
                        if fnmatch.fnmatch(instance.name, value):
                            break
                    else:
                        return False
                case "tags":
                    for value in values:
                        if fnmatch.filter(instance.tags, value):
                            break
                    else:
                        return False
                case "modloader":
                    normalized: list[str] = sum(
                        [_normalize_modloader(value) for value in values], []
                    )
                    for value in normalized:
                        if fnmatch.filter(
                            _normalize_modloader(instance.modloader), value
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
                case _:
                    raise NotImplementedError(
                        f"Don't know how to apply match condition {condition}."
                    )

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
        print("FML", version_spec, version_string)
        # fall back to simple fnmatching
        return fnmatch.fnmatch(version_spec, version_string)
