"""Specification of a Minecraft instance"""
from configparser import SectionProxy
from pathlib import Path
from typing import NamedTuple


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
    modloader : str or None
        The (display) name of the modloader, or None if this is a vanilla
        instance
    tags : list-like of str
        The tags assigned to this instance
    """

    name: str
    root: Path
    minecraft_versions: tuple[str, ...]
    modloader: str | None
    tags: tuple[str, ...]

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
            tuple(section["minecraft_version"].strip().split()),
            section.get("modloader", None),
            tuple(section.get("tags", "").strip().split()),
        )
