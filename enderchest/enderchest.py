"""Specification and configuration of an EnderChest"""
from dataclasses import dataclass
from pathlib import Path
from socket import gethostname
from typing import Any, Iterable
from urllib.parse import ParseResult, urlparse

from . import config as cfg
from . import filesystem as fs
from . import instance as i
from . import sync
from .loggers import CRAFT_LOGGER, GATHER_LOGGER
from .sync import abspath_from_uri

_DEFAULTS = (
    ("offer_to_update_symlink_allowlist", True),
    ("sync_confirm_wait", 5),
    ("place_after_open", True),
    ("do_not_sync", ("EnderChest/enderchest.cfg", "EnderChest/.*", ".DS_Store")),
    (
        "shulker_box_folders",
        (
            "config",
            "mods",
            "resourcepacks",
            "saves",
            "shaderpacks",
        ),
    ),
    ("standard_link_folders", ()),
    (
        "global_link_folders",
        (
            "backups",
            "cachedImages",
            "crash-reports",
            "logs",
            "replay_recordings",
            "screenshots",
            "schematics",
            "config/litematica",  # still worth having in case max_depth>2
            ".bobby",
        ),
    ),
)


@dataclass(init=False, repr=False, eq=False)
class EnderChest:
    """Configuration of an EnderChest

    Parameters
    ----------
    uri : URI or Path
        The "address" of this EnderChest, ideally as it can be accessed from other
        EnderChest installations, including both the path to where
        the EnderChest folder can be found (that is, the parent of the
        EnderChest folder itself, aka the "minecraft_root"), its net location
        including credentials, and the protocol that should be used to perform
        the syncing. All that being said, if just a path is provided, the
        constructor will try to figure out the rest.
    name : str, optional
        A unique name to give to this EnderChest installation. If None is
        provided, this will be taken from the hostname of the supplied URI.
    instances : list-like of InstanceSpec, optional
        The list of instances to register with this EnderChest installation
    remotes : list-like of URI, or (URI, str) tuples
        A list of other installations that this EnderChest should be aware of
        (for syncing purposes). When a (URI, str) tuple is provided, the
        second value will be used as the name/alias of the remote.

    Attributes
    ----------
    name : str
        The unique name of this EnderChest installation. This is most commonly
        the computer's hostname, but one can configure multiple EnderChests
        to coexist on the same system (either for the sake of having a "cold"
        backup or for multi-user systems).
    uri : str
        The complete URI of this instance
    root : Path
        The path to this EnderChest folder
    instances : list-like of InstanceSpec
        The instances registered with this EnderChest
    remotes : list-like of (ParseResult, str) pairs
        The other EnderChest installations this EnderChest is aware of, paired
        with their aliases
    offer_to_update_symlink_allowlist : bool
        By default, EnderChest will offer to create or update `allowed_symlinks.txt`
        on any 1.20+ instances that do not already blanket allow links into
        EnderChest. **EnderChest will never modify that or any other Minecraft
        file without your express consent.** If you would prefer to edit these
        files yourself (or simply not symlink your world saves), change this
        parameter to False.
    sync_confirm_wait : bool or int
        The default behavior when syncing EnderChests is to first perform a dry
        run of every sync operation and then wait 5 seconds before proceeding with the
        real sync. The idea is to give the user time to interrupt the sync if
        the dry run looks wrong. This can be changed by either raising or lowering
        the value of confirm, by disabling the dry-run-first behavior entirely
        (`confirm=False`) or by requiring that the user explicitly confirms
        the sync (`confirm=True`). This default behavior can also be overridden
        when actually calling the sync commands.
    place_after_open: bool
        By default, EnderChest will follow up any `enderchest open` operation
        with an `enderchest place` to refresh any changed symlinks. This
        functionality can be disabled by setting this parameter to False.
    do_not_sync : list of str
        Glob patterns of files that should not be synced between EnderChest
        installations. By default, this list comprises `EnderChest/enderchest.cfg`,
        any top-level folders starting with a "." (like .git) and
        `.DS_Store` (for all you mac gamers).
    shulker_box_folders : list of str
        The folders that will be created inside each new shulker box
    standard_link_folders : list of str
        The default set of "link folders" when crafting a new shulker box
    global_link_folders : list of str
        The "global" set of "link folders," offered as a suggestion when
        crafting a new shulker box
    """

    name: str
    _uri: ParseResult
    _instances: list[i.InstanceSpec]
    _remotes: dict[str, ParseResult]
    offer_to_update_symlink_allowlist: bool
    sync_confirm_wait: bool | int
    place_after_open: bool
    do_not_sync: list[str]
    shulker_box_folders: list[str]
    standard_link_folders: list[str]
    global_link_folders: list[str]

    def __init__(
        self,
        uri: str | ParseResult | Path,
        name: str | None = None,
        remotes: Iterable[str | ParseResult | tuple[str, str] | tuple[ParseResult, str]]
        | None = None,
        instances: Iterable[i.InstanceSpec] | None = None,
    ):
        for setting, value in _DEFAULTS:
            setattr(self, setting, list(value) if isinstance(value, tuple) else value)

        try:
            if isinstance(uri, ParseResult):
                self._uri = uri
            elif isinstance(uri, Path):
                self._uri = urlparse(uri.absolute().as_uri())
            else:
                self._uri = urlparse(uri)
        except AttributeError as parse_problem:  # pragma: no cover
            raise ValueError(f"{uri} is not a valid URI") from parse_problem

        if not self._uri.netloc:
            self._uri = self._uri._replace(netloc=sync.get_default_netloc())
        if not self._uri.scheme:
            self._uri = self._uri._replace(scheme=sync.DEFAULT_PROTOCOL)

        self.name = name or self._uri.hostname or gethostname()

        self._instances = []
        self._remotes = {}

        for instance in instances or ():
            self.register_instance(instance)

        for remote in remotes or ():
            if isinstance(remote, (str, ParseResult)):
                self.register_remote(remote)
            else:
                self.register_remote(*remote)

    @property
    def uri(self) -> str:
        return self._uri.geturl()

    def __repr__(self) -> str:
        return f"EnderChest({self.uri, self.name})"

    @property
    def root(self) -> Path:
        return fs.ender_chest_folder(abspath_from_uri(self._uri), check_exists=False)

    @property
    def instances(self) -> tuple[i.InstanceSpec, ...]:
        return tuple(self._instances)

    def register_instance(self, instance: i.InstanceSpec) -> i.InstanceSpec:
        """Register a new Minecraft installation

        Parameters
        ----------
        instance : InstanceSpec
            The instance to register

        Returns
        -------
        InstanceSpec
            The spec of the instance as it was actually registered (in case the
            name changed or somesuch)

        Notes
        -----
        - If the instance's name is already assigned to a registered instance,
          this method will choose a new one
        - If this instance shares a path with an existing instance, it will
          replace that instance
        """
        matching_instances: list[i.InstanceSpec] = []
        for old_instance in self._instances:
            if i.equals(abspath_from_uri(self._uri), instance, old_instance):
                matching_instances.append(old_instance)
                self._instances.remove(old_instance)

        instance = i.merge(*matching_instances, instance)

        name = instance.name
        counter = 0
        taken_names = {old_instance.name for old_instance in self._instances}
        while True:
            if name not in taken_names:
                break
            counter += 1
            name = f"{instance.name}.{counter}"

        GATHER_LOGGER.debug(f"Registering instance {name} at {instance.root}")
        self._instances.append(instance._replace(name=name))
        return self._instances[-1]

    @property
    def remotes(self) -> tuple[tuple[ParseResult, str], ...]:
        return tuple((remote, alias) for alias, remote in self._remotes.items())

    def register_remote(
        self, remote: str | ParseResult, alias: str | None = None
    ) -> None:
        """Register a new remote EnderChest installation (or update an existing
        registry)

        Parameters
        ----------
        remote : URI
            The URI of the remote
        alias : str, optional
            an alias to give to this remote. If None is provided, the URI's hostname
            will be used.

        Raises
        ------
        ValueError
            If the provided remote is invalid
        """
        try:
            remote = remote if isinstance(remote, ParseResult) else urlparse(remote)
            alias = alias or remote.hostname
            if not alias:  # pragma: no cover
                raise AttributeError(f"{remote.geturl()} has no hostname")
            GATHER_LOGGER.debug("Registering remote %s (%s)", remote.geturl(), alias)
            self._remotes[alias] = remote
        except AttributeError as parse_problem:  # pragma: no cover
            raise ValueError(f"{remote} is not a valid URI") from parse_problem

    @classmethod
    def from_cfg(cls, config_file: Path) -> "EnderChest":
        """Parse an EnderChest from its config file

        Parameters
        ----------
        config_file : Path
            The path to the config file

        Returns
        -------
        EnderChest
            The resulting EnderChest

        Raises
        ------
        ValueError
            If the config file at that location cannot be parsed
        FileNotFoundError
            If there is no config file at the specified location
        """
        GATHER_LOGGER.debug("Reading config file from %s", config_file)
        config = cfg.read_cfg(config_file)

        # All I'm gonna say is that Windows pathing is the worst
        path = urlparse(config_file.absolute().parent.parent.as_uri()).path

        instances: list[i.InstanceSpec] = []
        remotes: list[str | tuple[str, str]] = []

        requires_rewrite = False

        scheme: str | None = None
        netloc: str | None = None
        name: str | None = None
        sync_confirm_wait: str | None = None
        place_after_open: bool | None = None
        offer_to_update_symlink_allowlist: bool = True
        do_not_sync: list[str] | None = None
        folder_defaults: dict[str, list[str] | None] = {
            "shulker_box_folders": None,
            "standard_link_folders": None,
            "global_link_folders": None,
        }

        for section in config.sections():
            if section == "properties":
                scheme = config[section].get("sync-protocol")
                netloc = config[section].get("address")
                name = config[section].get("name")
                sync_confirm_wait = config[section].get("sync-confirmation-time")
                place_after_open = config[section].getboolean("place-after-open")
                offer_to_update_symlink_allowlist = config[section].getboolean(
                    "offer-to-update-symlink-allowlist", True
                )
                if "do-not-sync" in config[section].keys():
                    do_not_sync = cfg.parse_ini_list(
                        config[section]["do-not-sync"] or ""
                    )
                for setting in folder_defaults.keys():
                    setting_key = setting.replace("_", "-")
                    if setting_key in config[section].keys():
                        folder_defaults[setting] = cfg.parse_ini_list(
                            config[section][setting_key] or ""
                        )
            elif section == "remotes":
                for remote in config[section].items():
                    if remote[1] is None:
                        raise ValueError("All remotes must have an alias specified")
                    remotes.append((remote[1], remote[0]))
            else:
                # TODO: flag requires_rewrite if instance was normalized
                instances.append(i.InstanceSpec.from_cfg(config[section]))

        scheme = scheme or sync.DEFAULT_PROTOCOL
        netloc = netloc or sync.get_default_netloc()
        uri = ParseResult(
            scheme=scheme, netloc=netloc, path=path, params="", query="", fragment=""
        )

        ender_chest = EnderChest(uri, name, remotes, instances)
        if sync_confirm_wait is not None:
            match sync_confirm_wait.lower():
                case "true" | "prompt" | "yes" | "confirm":
                    ender_chest.sync_confirm_wait = True
                case "false" | "no" | "skip":
                    ender_chest.sync_confirm_wait = False
                case _:
                    try:
                        ender_chest.sync_confirm_wait = int(sync_confirm_wait)
                    except ValueError as bad_input:
                        raise ValueError(
                            "Invalid value for sync-confirmation-time:"
                            f" {sync_confirm_wait}"
                        ) from bad_input
        if place_after_open is None:
            GATHER_LOGGER.warning(
                "This EnderChest does not have a value set for place-after-open."
                "\nIt is being set to False for now. To enable this functionality,"
                "\nedit the value in %s",
                config_file,
            )
            ender_chest.place_after_open = False
            requires_rewrite = True
        else:
            ender_chest.place_after_open = place_after_open

        ender_chest.offer_to_update_symlink_allowlist = (
            offer_to_update_symlink_allowlist
        )

        if do_not_sync is not None:
            ender_chest.do_not_sync = do_not_sync
            chest_cfg_exclusion = "/".join(
                (fs.ENDER_CHEST_FOLDER_NAME, fs.ENDER_CHEST_CONFIG_NAME)
            )
            if chest_cfg_exclusion not in do_not_sync:
                GATHER_LOGGER.warning(
                    "This EnderChest was not configured to exclude the EnderChest"
                    " config file from sync operations."
                    "\nThat is being fixed now."
                )
                ender_chest.do_not_sync.insert(0, chest_cfg_exclusion)
                requires_rewrite = True
        for setting in folder_defaults:
            if folder_defaults[setting] is None:
                folder_defaults[setting] = dict(_DEFAULTS)[setting]  # type: ignore
                # requires_rewrite = True  # though I'm considering it
            setattr(ender_chest, setting, folder_defaults[setting])

        if requires_rewrite:
            ender_chest.write_to_cfg(config_file)
            return cls.from_cfg(config_file)
        return ender_chest

    def write_to_cfg(self, config_file: Path | None = None) -> str:
        """Write this EnderChest's configuration to INI

        Parameters
        ----------
        config_file : Path, optional
            The path to the config file, assuming you'd like to write the
            contents to file

        Returns
        -------
        str
            An INI-syntax rendering of this EnderChest's config

        Notes
        -----
        The "root" attribute is ignored for this method
        """
        properties: dict[str, Any] = {
            "name": self.name,
            "address": self._uri.netloc,
            "sync-protocol": self._uri.scheme,
        }
        if self.sync_confirm_wait is True:
            properties["sync-confirmation-time"] = "prompt"
        else:
            properties["sync-confirmation-time"] = self.sync_confirm_wait

        for setting, _ in _DEFAULTS:
            if setting == "sync_confirm_wait":
                continue  # already did this one
            setting_key = setting.replace("_", "-")
            properties[setting_key] = getattr(self, setting)

        remotes: dict[str, str] = {name: uri.geturl() for uri, name in self.remotes}

        instances: dict[str, dict[str, Any]] = {}

        for instance in self.instances:
            instances[instance.name] = {
                "root": instance.root,
                "minecraft-version": instance.minecraft_versions,
                "modloader": instance.modloader,
                "groups": instance.groups_,
                "tags": instance.tags_,
            }

        config = cfg.dumps(
            fs.ENDER_CHEST_CONFIG_NAME, properties, remotes=remotes, **instances
        )

        if config_file:
            CRAFT_LOGGER.debug("Writing configuration file to %s", config_file)
            config_file.write_text(config)
        return config


def create_ender_chest(minecraft_root: Path, ender_chest: EnderChest) -> None:
    """Create an EnderChest based on the provided configuration

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff is in (or, at least, the
        one inside which you want to create your EnderChest)
    ender_chest : EnderChest
        The spec of the chest to create

    Notes
    -----
    - The "root" attribute of the EnderChest config will be ignored--instead
      the EnderChest will be created at <minecraft_root>/EnderChest
    - This method does not check to see if there is already an EnderChest set
      up at the specified location--if one exists, its config will
      be overwritten
    """
    root = fs.ender_chest_folder(minecraft_root, check_exists=False)
    root.mkdir(exist_ok=True)

    config_path = fs.ender_chest_config(minecraft_root, check_exists=False)
    ender_chest.write_to_cfg(config_path)
    CRAFT_LOGGER.info(f"EnderChest configuration written to {config_path}")
