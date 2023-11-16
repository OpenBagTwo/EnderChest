"""Specification and configuration of a shulker box"""
import fnmatch
import os
from pathlib import Path
from typing import Any, Iterable, NamedTuple

import semantic_version as semver

from . import config as cfg
from . import filesystem as fs
from .instance import InstanceSpec, normalize_modloader
from .loggers import CRAFT_LOGGER

_DEFAULT_PRIORITY = 0
_DEFAULT_LINK_DEPTH = 2
_DEFAULT_DO_NOT_LINK = ("shulkerbox.cfg", ".DS_Store")


class ShulkerBox(NamedTuple):
    """Specification of a shulker box

    Parameters
    ----------
    priority : int
        The priority for linking assets in the shulker box (higher priority
        boxes are linked last)
    name : str
        The name of the shulker box (which is incidentally used to break
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
    do_not_link : list-like of str, optional
        Glob patterns of files that should not be linked. By default, this list
        comprises `shulkerbox.cfg` and `.DS_Store` (for all you mac gamers).

    Notes
    -----
    A shulker box specification is immutable, so making changes (such as
    updating the match criteria) can only be done on copies created via the
    `_replace` method, inherited from the NamedTuple parent class.
    """

    priority: int
    name: str
    root: Path
    match_criteria: tuple[tuple[str, tuple[str, ...]], ...]
    link_folders: tuple[str, ...]
    max_link_depth: int = _DEFAULT_LINK_DEPTH
    do_not_link: tuple[str, ...] = _DEFAULT_DO_NOT_LINK

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
        config = cfg.read_cfg(config_file)

        match_criteria: dict[str, tuple[str, ...]] = {}

        for section in config.sections():
            normalized = (
                section.lower().replace(" ", "").replace("-", "").replace("_", "")
            )
            if normalized.endswith("s"):
                normalized = normalized[:-1]  # lazy de-pluralization
            if normalized in ("linkfolder", "folder"):
                normalized = "link-folders"
            if normalized in ("donotlink",):
                normalized = "do-not-link"
            if normalized in ("minecraft", "version", "minecraftversion"):
                normalized = "minecraft"
            if normalized in ("modloader", "loader"):
                normalized = "modloader"
            if normalized in ("instance", "tag", "host"):
                normalized += "s"  # lazy re-pluralization

            if normalized == "propertie":  # lulz
                # TODO check to make sure properties hasn't been read before
                # most of this section gets ignored
                priority = config[section].getint("priority", _DEFAULT_PRIORITY)
                max_link_depth = config[section].getint(
                    "max-link-depth", _DEFAULT_LINK_DEPTH
                )
                # TODO: support specifying filters (and link-folders) in the properties section
                continue
            if normalized in match_criteria:
                raise ValueError(f"{config_file} specifies {normalized} more than once")

            if normalized == "minecraft":
                minecraft_versions = []
                for key, value in config[section].items():
                    if value is None:
                        minecraft_versions.append(key)
                    elif key.lower().strip().startswith("version"):
                        minecraft_versions.append(value)
                    else:  # what happens if you specify ">=1.19" or "=1.12"
                        minecraft_versions.append("=".join((key, value)))
                match_criteria[normalized] = tuple(minecraft_versions)
            elif normalized == "modloader":
                modloaders: set[str] = set()
                for loader in config[section].keys():
                    modloaders.update(normalize_modloader(loader))
                match_criteria[normalized] = tuple(sorted(modloaders))
            else:
                # really hoping delimiter shenanigans doesn't show up anywhere else
                match_criteria[normalized] = tuple(config[section].keys())

        link_folders = match_criteria.pop("link-folders", ())
        do_not_link = match_criteria.pop("do-not-link", _DEFAULT_DO_NOT_LINK)

        return cls(
            priority,
            name,
            root,
            tuple(match_criteria.items()),
            link_folders,
            max_link_depth=max_link_depth,
            do_not_link=do_not_link,
        )

    def write_to_cfg(self, config_file: Path | None = None) -> str:
        """Write this box's configuration to INI

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
        properties: dict[str, Any] = {"priority": self.priority}
        if self.max_link_depth != _DEFAULT_LINK_DEPTH:
            properties["max-link-depth"] = self.max_link_depth

        config = cfg.dumps(
            os.path.join(self.name, fs.SHULKER_BOX_CONFIG_NAME),
            properties,
            **dict(self.match_criteria),
            link_folders=self.link_folders,
            do_not_link=self.do_not_link,
        )

        if config_file:
            config_file.write_text(config)
        return config

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
                        if value == "*":  # in case instance.tags is empty
                            break
                        if fnmatch.filter(
                            [tag.lower() for tag in instance.tags], value.lower()
                        ):
                            break
                    else:
                        return False
                case "modloader":
                    for value in values:
                        if fnmatch.fnmatchcase(
                            instance.modloader.lower(),
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


def create_shulker_box(
    minecraft_root: Path, shulker_box: ShulkerBox, folders: Iterable[str]
) -> None:
    """Create a shulker box folder based on the provided configuration

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    shulker_box : ShulkerBox
        The spec of the box to create
    folders : list-like of str
        The folders to create inside the shulker box (not including link folders)

    Notes
    -----
    - The "root" attribute of the ShulkerBox config will be ignored--instead
      the shulker box will be created at
      <minecraft_root>/EnderChest/<shulker box name>
    - This method will fail if there is no EnderChest set up in the minecraft
      root
    - This method does not check to see if there is already a shulker box
      set up at the specified location--if one exists, its config will
      be overwritten
    """
    root = fs.shulker_box_root(minecraft_root, shulker_box.name)
    root.mkdir(exist_ok=True)

    for folder in (*folders, *shulker_box.link_folders):
        CRAFT_LOGGER.debug(f"Creating {root / folder}")
        (root / folder).mkdir(exist_ok=True, parents=True)

    config_path = fs.shulker_box_config(minecraft_root, shulker_box.name)
    shulker_box.write_to_cfg(config_path)
    CRAFT_LOGGER.info(f"Shulker box configuration written to {config_path}")
