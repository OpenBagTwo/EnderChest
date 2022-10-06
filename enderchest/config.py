"""Logic for parsing configuration files"""
import json
import os
import warnings
from configparser import ConfigParser, ParsingError, SectionProxy
from pathlib import Path
from typing import Any, Sequence

from .sync import Remote, RemoteSync


class Config:
    """The configuration spec for the EnderChest package

    Attributes
    ----------
    local_root : Path
        The path on the local installation of the minecraft directory (which
        should / will contain the EnderChest folder, along with the instances
        and servers directories)
    remotes : list-like of RemoteSync
        The specifications of the remote EnderChest installations to sync with,
        complete with any wrapper commands
    craft_options: dict
        Any additional options to pass to the craft command
    """

    @classmethod
    def _default_craft_options(cls) -> dict:
        """The default craft options if None are specified. Note that providing
        *any* value to craft_options will completely replace this dict"""

        # TODO: figure out how to to have
        return {
            "local_alias": None,
            "pre_open": [],
            "pre_close": [],
            "post_open": [],
            "post_close": [],
        }

    def __init__(
        self,
        local_root: str | os.PathLike,
        remotes: Sequence[RemoteSync],
        craft_options: dict[str, Any] | None = None,
    ):
        self.local_root = local_root
        self.remotes = remotes
        self.craft_options = Config._default_craft_options()
        if craft_options:
            self.craft_options.update(craft_options)

    @property
    def _config(self) -> ConfigParser:
        parser = ConfigParser()
        local: dict[str, str] = {"root": str(self.local_root)}
        if alias := self.craft_options["local_alias"]:
            local["name"] = alias
        parser["local"] = local

        options: dict[str, Any] = {}
        for keyword, value in self.craft_options.items():
            if keyword == "local_alias":
                continue
            if keyword in ("pre_open", "pre_close", "post_open", "post_close"):
                options[keyword] = json.dumps(value)
            else:
                options[keyword] = value

        parser["options"] = options

        for remote_sync in self.remotes:
            remote = remote_sync.remote
            remote_spec: dict[str, str] = {
                "host": remote.host if remote.host else "",
                "root": str(remote.root),
            }
            if username := remote.username:
                remote_spec["username"] = username
            for wrapper in ("pre_open", "pre_close", "post_open", "post_close"):
                if commands := getattr(remote_sync, wrapper):
                    remote_spec[wrapper] = json.dumps(commands)
            parser[remote.alias] = remote_spec
        return parser

    @property
    def _asdict(self) -> dict[str, Any]:
        as_dict = {}
        for section in self._config.sections():
            as_dict[section] = {
                keyword: self._config.get(section, keyword)
                for keyword in self._config.options(section)
            }
        return as_dict

    def __repr__(self) -> str:
        return repr(self._asdict)

    def __eq__(self, other) -> bool:
        try:
            return self._asdict == other._asdict
        except AttributeError:
            return self._asdict == other


def parse_config_file(config_path: str | os.PathLike) -> Config:
    """Parse a config file

    Parameters
    ----------
    config_path : path
        The path to the config file

    Returns
    -------
    Config
        The parsed config file contents
    """
    with open(config_path) as config_file:
        return parse_config(config_file.read())


def parse_config(contents: str) -> Config:
    """Parse the contents of a config file

    Parameters
    ----------
    contents : str
        The raw config file contents

    Returns
    -------
    Config
        The parsed config file contents
    """
    parser = ConfigParser()
    parser.read_string(contents)

    if "local" not in parser:
        raise ParsingError("Configuration must contain a [local] section")
    local_root, options = _parse_local_section(parser["local"])
    if "options" in parser:
        more_options = _parse_options_section(parser["options"])
        for option, value in more_options.items():
            if option in ("pre_open", "pre_close", "post_open", "post_close"):
                options[option].extend(value)
            elif option in options and value != options[option]:
                raise ParsingError(f"Found conflicting values for {option}")
            else:
                options[option] = value

    remotes = [
        _parse_remote_section(parser[alias])
        for alias in parser.sections()
        if alias not in ("local", "options")
    ]

    return Config(local_root, remotes, options)


def _parse_local_section(section: SectionProxy) -> tuple[str, dict[str, Any]]:
    """Parse the local section of the config

    Parameters
    ----------
    section : SectionProxy
        The local section of the config

    Returns
    -------
    str
        The local root folder
    dict
        Any keyword options to pass to the craft command

    Raises
    ------
    ParsingError
        If a required parameter isn't present or if a given option cannot be parsed
    """
    try:
        root = Path(section["root"]).as_posix()
    except KeyError:
        raise ParsingError("Config must explicitly specify a local root directory")
    except (TypeError, ValueError):
        raise ParsingError(
            f'Invalid value for root parameter in local config: {section["root"]} '
        )

    alias_option_names = {"name", "alias"}
    if len(alias_option_names.intersection(section.keys())) > 1:
        raise ParsingError(
            "Found conflicting values for local installation's name/alias"
        )

    for option_name in alias_option_names:
        try:
            local_alias = _parse_string(section.get(option_name))
        except (TypeError, ValueError):
            raise ParsingError(
                f"Invalid value for {option_name} option in local config:"
                f" {section[option_name]}"
            )
        if local_alias:
            break
    else:
        local_alias = None

    # options can also be provided in local section
    return root, {"local_alias": local_alias, **_parse_options_section(section)}


def _parse_options_section(section: SectionProxy) -> dict[str, Any]:
    """Parse the local section of the config

    Parameters
    ----------
    section : SectionProxy
        The options section of the config

    Returns
    -------
    dict
        Keyword options to pass to the craft command

    Raises
    ------
    ParsingError
        If a required parameter isn't present or if a given option cannot be parsed
    """
    options: dict[str, Any] = {}

    if "generate_runnable_scripts" in section:
        omit_scare_warnings: bool | str | None = None
        # first try parsing as a boolean
        try:
            omit_scare_warnings = section.getboolean("generate_runnable_scripts")
        except ValueError:
            pass
        if omit_scare_warnings is False:
            pass
        elif (
            _parse_string(section["generate_runnable_scripts"])
            == "I acknowledge that this is dangerous"
        ):
            # you said the magic word!
            omit_scare_warnings = True
        else:
            # you didn't say the magic word
            warnings.warn(
                "Setting provided to generate_runnable_scripts"
                " option does not contain explicit risk acknowledgement."
                "\nTreating as False."
            )
            omit_scare_warnings = False
        options["omit_scare_warnings"] = omit_scare_warnings

    if "overwrite_scripts" in section:
        try:
            options["overwrite"] = section.getboolean("overwrite_scripts") or False
        except ValueError:
            raise ParsingError(
                "Expected boolean value for overwrite_scripts option."
                f' Got {section.get("overwrite_scripts")} instead.'
            )
    options.update(_parse_pre_and_post_commands(section))
    return options


def _parse_remote_section(
    section: SectionProxy,
) -> RemoteSync:
    """Parse a remote section

    Parameters
    ----------
    section : SectionProxy
        A section of the config specifying a remote source

    Returns
    -------
    RemoteSync
        The specification of the remote source, complete with wrapper commands

    Raises
    ------
    ParsingError
        If a required parameter isn't present or if a given option cannot be parsed
    """
    alias = _parse_string(section.name)

    host_option_names = {"host", "hostname", "url", "address"}
    if len(host_option_names.intersection(section.keys())) > 1:
        raise ParsingError(
            f"Found conflicting values for hostname/address in config {alias}"
        )

    for option_name in host_option_names:
        try:
            host = _parse_string(section.get(option_name))
        except (TypeError, ValueError):
            raise ParsingError(
                f"Invalid value for {option_name} parameter in config {alias}:"
                f" {section[option_name]}"
            )
        if host:
            break
    else:
        host = alias

    try:
        root = Path(section["root"]).as_posix()
    except KeyError:
        raise ParsingError(f"{alias} remote config must specify a root directory")
    except (TypeError, ValueError):
        raise ParsingError(
            f'Invalid value for root parameter in config {alias}: {section["root"]}'
        )

    if "user" in section and "username" in section:
        raise ParsingError(
            f"Found conflicting values for user/username in config {alias}"
        )
    try:
        username = _parse_string(section.get("username", section.get("user")))
    except (TypeError, ValueError):
        raise ParsingError(
            f'Invalid value for username parameter in config {alias}: {section["host"]}'
        )

    wrapper_commands = _parse_pre_and_post_commands(section)
    return RemoteSync(Remote(host, root, username, alias), **wrapper_commands)


def _parse_pre_and_post_commands(
    section: SectionProxy,
) -> dict[str, list[str]]:
    """Parse the provided section to rerun the pre- and post-, -open and -close commands

    Parameters
    ----------
    section : SectionProxy
        A section of the config

    Returns
    -------
    dict of str to lists of str
        A mapping that provides the pre- and post-, -open and -close commands
    """
    return {
        f"{timing}_{script}": _parse_pre_or_post_command_entry(
            section.get(f"{timing}_{script}")
        )
        for timing in ("pre", "post")
        for script in ("open", "close")
    }


def _parse_pre_or_post_command_entry(entry: str | None) -> list[str]:
    """Parse a config entry for:
        - pre_open
        - pre_close
        - post_open
        - post_close

    Parameters
    ----------
    entry : str or None
        The raw entry

    Returns
    -------
    list of str
        The parsed commands
    """
    if entry is None:
        return []
    try:
        parsed = json.loads(entry)
    except json.JSONDecodeError:
        parsed = entry
    if isinstance(parsed, str):
        parsed = [_parse_string(parsed)]
    return parsed


def _parse_string(entry: str | None) -> str | None:
    """Strip quotes from strings

    Parameters
    ----------
    entry : str or None
        The raw entry

    Returns
    -------
    str or None
        The de-quoted string, or None if the raw entry was None
    """
    if entry is None:
        return None
    for quote_char in ('"""', "'''", "'", '"'):
        if entry.startswith(quote_char) and entry.endswith(quote_char):
            return entry[len(quote_char) : -len(quote_char)]
    # if not quoted
    return entry
