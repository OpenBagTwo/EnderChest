"""Specification and configuration of an EnderChest"""
import datetime as dt
from configparser import ConfigParser, ParsingError
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from socket import gethostname
from typing import Iterable, Sequence
from urllib.parse import ParseResult, urlparse

from . import filesystem as fs
from . import instance as i
from . import sync
from ._version import get_versions
from .loggers import CRAFT_LOGGER, GATHER_LOGGER


@dataclass(init=False, repr=False)
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
    sync_confirm_wait: bool or int
        The default behavior when syncing EnderChests is to first perform a dry
        run of every sync operation and then wait 5 seconds before proceeding with the
        real sync. The idea is to give the user time to interrupt the sync if
        the dry run looks wrong. This can be changed by either raising or lowering
        the value of confirm, by disabling the dry-run-first behavior entirely
        (`confirm=False`) or by requiring that the user explicitly confirms
        the sync (`confirm=True`). This default behavior can also be overridden
        when actually calling the sync commands.
    """

    name: str
    _uri: ParseResult
    _instances: list[i.InstanceSpec]
    _remotes: dict[str, ParseResult]
    sync_confirm_wait: bool | int = 5

    def __init__(
        self,
        uri: str | ParseResult | Path,
        name: str | None = None,
        remotes: Iterable[str | ParseResult | tuple[str, str] | tuple[ParseResult, str]]
        | None = None,
        instances: Iterable[i.InstanceSpec] | None = None,
    ):
        try:
            if isinstance(uri, ParseResult):
                self._uri = uri
            elif isinstance(uri, Path):
                self._uri = urlparse(uri.absolute().as_uri())
            else:
                self._uri = urlparse(uri)
        except AttributeError as parse_problem:
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
        return fs.ender_chest_folder(Path(self._uri.path))

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
        self._instances = [
            old_instance
            for old_instance in self._instances
            if not i.equals(Path(self._uri.path), instance, old_instance)
        ]
        name = instance.name
        counter = 0
        taken_names = {old_instance.name for old_instance in self._instances}
        while True:
            if name not in taken_names:
                break
            counter += 1
            name = f"{instance.name}.{counter}"

        GATHER_LOGGER.debug(f"Registering instance {instance.name} at {instance.root}")
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
            if not alias:
                raise AttributeError(f"{remote.geturl()} has no hostname")
            GATHER_LOGGER.debug(f"Registering remote {remote.geturl()} ({alias})")
            self._remotes[alias] = remote
        except AttributeError as parse_problem:
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
        parser = ConfigParser(
            allow_no_value=True,
            delimiters=("=",),
            inline_comment_prefixes=(";",),
            interpolation=None,
        )
        parser.optionxform = str  # type: ignore
        try:
            assert parser.read(config_file)
        except ParsingError as bad_cfg:
            raise ValueError(f"Could not parse {config_file}") from bad_cfg
        except AssertionError:
            raise FileNotFoundError(f"Could not open {config_file}")

        # All I'm gonna say is that Windows pathing is the worst
        path = urlparse(config_file.absolute().parent.parent.as_uri()).path

        instances: list[i.InstanceSpec] = []
        remotes: list[str | tuple[str, str]] = []

        scheme: str | None = None
        netloc: str | None = None
        name: str | None = None
        sync_confirm_wait: str | None = None

        for section in parser.sections():
            if section == "properties":
                scheme = parser[section].get("sync-protocol")
                netloc = parser[section].get("address")
                name = parser[section].get("name")
                sync_confirm_wait = parser[section].get("sync-confirmation-time")
            elif section == "remotes":
                for remote in parser[section].items():
                    if remote[1] is None:
                        raise ValueError("All remotes must have an alias specified")
                    else:
                        remotes.append((remote[1], remote[0]))
            else:
                instances.append(i.InstanceSpec.from_cfg(parser[section]))

        scheme = scheme or sync.DEFAULT_PROTOCOL
        netloc = netloc or sync.get_default_netloc()
        uri = ParseResult(
            scheme=scheme, netloc=netloc, path=path, params="", query="", fragment=""
        )

        ender_chest = EnderChest(uri, name, remotes, instances)
        if sync_confirm_wait is not None:
            match sync_confirm_wait.lower():
                case "true" | "prompt" | "yes":
                    ender_chest.sync_confirm_wait = True
                case "false" | "no" | "skip":
                    ender_chest.sync_confirm_wait = False
                case _:
                    try:
                        ender_chest.sync_confirm_wait = int(sync_confirm_wait)
                    except ValueError:
                        raise ValueError(
                            "Invalid value for sync-confirmation-time:"
                            f" {sync_confirm_wait}"
                        )
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
        config = ConfigParser(allow_no_value=True, interpolation=None)
        config.optionxform = str  # type: ignore
        config.add_section("properties")
        config.set("properties", "name", self.name)
        config.set("properties", "address", self._uri.netloc)
        config.set("properties", "sync-protocol", self._uri.scheme)
        config.set(
            "properties",
            "sync-confirmation-time",
            str(self.sync_confirm_wait)
            if self.sync_confirm_wait is not True
            else "prompt",
        )
        config.set("properties", "last_modified", dt.datetime.now().isoformat(sep=" "))
        config.set(
            "properties", "generated_by_enderchest_version", get_versions()["version"]
        )

        config.add_section("remotes")
        for uri, name in self.remotes:
            config.set("remotes", name, uri.geturl())
        for instance in self.instances:
            config.add_section(instance.name)
            config.set(instance.name, "root", str(instance.root))
            config.set(
                instance.name,
                "minecraft_version",
                _list_to_ini(instance.minecraft_versions),
            )
            config.set(instance.name, "modloader", instance.modloader)
            config.set(
                instance.name,
                "tags",
                _list_to_ini(instance.tags),
            )

        buffer = StringIO()
        buffer.write(f"; {fs.ENDER_CHEST_CONFIG_NAME}\n")
        config.write(buffer)
        buffer.seek(0)  # rewind

        if config_file:
            config_file.write_text(buffer.read())
            buffer.seek(0)
        return buffer.read()


def _list_to_ini(values: Sequence) -> str:
    """Format a list of values into a string suitable for use in an INI entry

    Parameters
    ----------
    values : list-like
        the values in the list

    Returns
    -------
    str
        The formatted INI value
    """
    if len(values) == 0:
        return ""
    if len(values) == 1:
        return values[0]
    return "\n" + "\n".join(values)


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
