"""Specification of a Minecraft instance"""
import re
from configparser import SectionProxy
from pathlib import Path
from typing import NamedTuple

from . import config as cfg


class InstanceSpec(NamedTuple):
    """Specification of a Minecraft instance

    Parameters
    ----------
    name : str
        The "display name" for the instance
    root : Path
        The path to its ".minecraft" folder
    minecraft_versions : list-like of str
        The minecraft versions of this instance. This is typically a 1-tuple,
        but some loaders (such as the official one) will just comingle all
        your assets together across all profiles
    modloader : str
        The (display) name of the modloader (vanilla corresponds to "")
    tags : list-like of str
        The tags assigned to this instance, including both the ones assigned
        in the launcher (groups) and the ones assigned by hand.
    """

    name: str
    root: Path
    minecraft_versions: tuple[str, ...]
    modloader: str
    groups_: tuple[str, ...]
    tags_: tuple[str, ...]

    @classmethod
    def from_cfg(cls, section: SectionProxy) -> "InstanceSpec":
        """Parse an instance spec as read in from the enderchest config file

        Parameters
        ----------
        section : dict-like of str to str
            The section in the enderchest config as parsed by a ConfigParser

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
            section.name,
            Path(section["root"]),
            tuple(
                parse_version(version.strip())
                for version in cfg.parse_ini_list(
                    section.get("minecraft-version", section.get("minecraft_version"))
                )
            ),
            normalize_modloader(section.get("modloader", None))[0],
            tuple(cfg.parse_ini_list(section.get("groups", ""))),
            tuple(cfg.parse_ini_list(section.get("tags", ""))),
        )

    @property
    def tags(self):
        return tuple(sorted({*self.groups_, *self.tags_}))


def normalize_modloader(loader: str | None) -> list[str]:
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


def equals(
    minecraft_root: Path, instance: InstanceSpec, other_instance: InstanceSpec
) -> bool:
    """Determine whether two instances point to the same location

    Parameters
    ----------
    minecraft_root : Path
        The starting location (the parent of where your EnderChest folder lives)
    instance : InstanceSpec
        the first instance
    other_instance : InstanceSpec
        the instance to compare it against

    Returns
    -------
    bool
        True if and only if the two instances have the same root, with regards
        to the provided `minecraft_root`
    """
    path = minecraft_root / instance.root.expanduser()
    other_path = minecraft_root / other_instance.root.expanduser()
    return path.expanduser().resolve() == other_path.expanduser().resolve()


def parse_version(version_string: str) -> str:
    """The first release of each major Minecraft version doesn't follow strict
    major.minor.patch semver. This method appends the ".0" so that our version
    matcher doesn't mess up

    Parameters
    ----------
    version_string : str
        The version read in from the Minecraft instance's config

    Returns
    -------
    str
        Either the original version string or the original version string with
        ".0" tacked onto the end of it

    Notes
    -----
    Regex adapted straight from https://semver.org
    """
    if re.match(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)$", version_string):
        return version_string + ".0"
    return version_string


def merge(*instances: InstanceSpec) -> InstanceSpec:
    """Merge multiple instances, layering information from the ones provided later
    on top of the ones provided earlier

    Parameters
    ----------
    *instances : InstanceSpec
        The instances to combine

    Returns
    -------
    InstanceSpec
        The merged instance

    Notes
    -----
    The resulting merged instance will use:
      - the first instance's name
      - the union of all non-group tags
      - all other data from the last instance
    """
    try:
        combined_instance = instances[-1]
    except IndexError as nothing_to_merge:
        raise ValueError(
            "Must provide at least one instance to merge"
        ) from nothing_to_merge
    tags = tuple(sorted(set(sum((instance.tags_ for instance in instances), ()))))
    return combined_instance._replace(name=instances[0].name, tags_=tags)
