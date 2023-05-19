"""Specification and configuration of an EnderChest"""
import datetime as dt
from configparser import ConfigParser
from dataclasses import dataclass, field
from getpass import getuser
from pathlib import Path
from socket import gethostname
from typing import Iterable, Sequence
from urllib.parse import ParseResult, urlparse

from ._version import get_versions
from .filesystem import ender_chest_folder
from .instance import InstanceSpec
from .sync import DEFAULT_SYNC_PROTOCOL


@dataclass(init=False, repr=False)
class EnderChest:
    """Configuration of an EnderChest

    Parameters
    ----------
    uri : URI
        The "address" of this EnderChest as it can be accessed from other
        EnderChest installations. This should include both the path to where
        the EnderChest folder can be found (that is, the parent of the
        EnderChest folder itself, aka the "minecraft_root"), its net location
        including credentials, and the protocol that should be used to perform
        the syncing.
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
    instances : list of InstanceSpec
        The instances registered with this EnderChest
    remotes : dict of str to tuple
        The other EnderChest installations this EnderChest is aware of
    """

    name: str
    _uri: ParseResult
    instances: list[InstanceSpec]

    remotes: dict[str, ParseResult]

    def __init__(
        self,
        uri: str | ParseResult,
        name: str | None = None,
        remotes: Iterable[str | ParseResult | tuple[str, str] | tuple[ParseResult, str]]
        | None = None,
        instances: Iterable[InstanceSpec] | None = None,
    ):
        try:
            self._uri = uri if isinstance(uri, ParseResult) else urlparse(uri)
        except AttributeError as parse_problem:
            raise ValueError(f"{uri} is not a valid URI") from parse_problem

        self.name = name or self._uri.hostname or gethostname()

        self.instances = [instance for instance in instances or ()]
        self.remotes = {}

        for remote in remotes or ():
            try:
                if isinstance(remote, str):
                    remote = urlparse(remote)
                if isinstance(remote, ParseResult):
                    if not remote.hostname:
                        raise AttributeError(f"{remote.geturl()} has no hostname")
                    self.remotes[remote.hostname] = remote
                else:
                    remote_uri, alias = remote
                    if isinstance(remote_uri, str):
                        remote_uri = urlparse(remote_uri)
                    self.remotes[alias] = remote_uri
            except AttributeError as parse_problem:
                raise ValueError(
                    f"{remote} is not a valid remote spec"
                ) from parse_problem

    @property
    def uri(self) -> str:
        return self._uri.geturl()

    def __repr__(self) -> str:
        return f"EnderChest({self.uri, self.name})"

    @property
    def root(self) -> Path:
        return ender_chest_folder(Path(self._uri.path))

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
        """
        parser = ConfigParser(
            allow_no_value=True, delimiters=("=",), inline_comment_prefixes=(";",)
        )
        parser.read(config_file)

        path = str(config_file.absolute().parent.parent)

        instances: list[InstanceSpec] = []
        remotes: list[str | tuple[str, str]] = []

        scheme: str | None = None
        netloc: str | None = None
        name: str | None = None

        for section in parser.sections():
            if section == "properties":
                scheme = parser[section].get("sync-protocol")
                netloc = parser[section].get("address")
                name = parser[section].get("name")
            elif section == "remotes":
                for remote in parser[section].items():
                    if remote[1] is None:
                        remotes.append(remote[0])
                    else:
                        remotes.append((remote[1], remote[0]))
            else:
                instances.append(InstanceSpec.from_cfg(parser[section]))

        scheme = scheme or DEFAULT_SYNC_PROTOCOL
        netloc = netloc or f"{getuser()}@{gethostname()}"
        uri = ParseResult(
            scheme=scheme, netloc=netloc, path=path, params="", query="", fragment=""
        )

        return EnderChest(uri, name, remotes, instances)

    def write_to_cfg(self, config_file) -> None:
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
        config.set("properties", "name", self.name)
        config.set("properties", "address", self._uri.netloc)
        config.set("properties", "sync-protocol", self._uri.scheme)
        config.set("properties", "last_modified", dt.datetime.now().isoformat(sep=" "))
        config.set(
            "properties", "generated_by_enderchest_version", get_versions()["version"]
        )

        config.add_section("remotes")
        for name, uri in self.remotes.items():
            if name != uri.hostname:
                config.set("remotes", name, uri.geturl())
            else:
                config.set("remotes", uri.geturl())
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
        with config_file.open("w") as f:
            config.write(f)


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
