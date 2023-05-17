"""Functionality around EnderChest and Shulker Box configuration / specification"""
from configparser import ConfigParser, SectionProxy
from pathlib import Path
from typing import NamedTuple


# TODO: the next few methods / classes are almost certainly going in enderchest proper
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
            section.name,
            Path(section["root"]),
            tuple(section["minecraft_version"].strip().split()),
            section.get("modloader", None),
            tuple(section.get("tags", "").strip().split()),
        )


def parse_instance_metadata(enderchest_cfg: Path) -> list[InstanceSpec]:
    """Parse an enderchest.cfg file to get the relevant instance metadata.

    Parameters
    ----------
    enderchest_cfg : Path
        The enderchest config file to read

    Returns
    -------
    list of InstanceSpec
        The instances parsed from the metadata file, in the order listed in
        the metadata file
    """
    instances = ConfigParser()
    instances.read(enderchest_cfg)
    return [
        InstanceSpec.from_cfg(instances[instance_name])
        for instance_name in instances.sections()
    ]


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
        """
        priority = 0  # TODO: figure out how priority is stored in the config
        root = config_file.parent
        name = root.name
        parser = ConfigParser(allow_no_value=True)
        parser.read(config_file)

        link_folders: tuple[str, ...] = ()
        match_criteria: dict[str, tuple[str, ...]] = {}

        for section in parser.sections():
            if section == "link-folders":
                link_folders = tuple(parser[section].keys())
            else:
                match_criteria[section] = tuple(parser[section].keys())

        return cls(0, name, root, tuple(match_criteria.items()), link_folders)

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
            if "*" in values:  # trivially met
                continue
            match condition:
                case _:
                    raise NotImplementedError(
                        f"Don't know how to apply match condition {condition}."
                    )

        return True
