"""Logic for parsing configuration files"""
import json
import os
import warnings
from configparser import ConfigParser, ParsingError, SectionProxy
from pathlib import Path
from typing import Any, NamedTuple, Sequence

from .sync import Remote


class Config(NamedTuple):
    local_root: Path
    open_ops: Sequence[Remote | str]
    close_ops: Sequence[Remote | str]
    craft_options: dict[str, Any] = {}

    # TODO: add serializer


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

    local_root, options = _parse_local_section(parser["local"])
    more_options = _parse_options_section(parser["options"])
    for option, value in more_options.items():
        if option in ("pre_open", "pre_close", "post_open", "post_close"):
            options[option].extend(value)
        elif option in options and value != options[option]:
            raise ParsingError(f"Found conflicting values for {option}")
        options[option] = value

    open_ops: list[Remote | str] = list(options.pop("pre_open"))
    close_ops: list[Remote | str] = list(options.pop("pre_close"))

    for alias in parser.sections():
        if alias in ("local", "options"):
            continue
        (pre_open, pre_close), remote, (post_open, post_close) = _parse_remote_section(
            parser[alias]
        )
        open_ops.extend([*pre_open, remote, *post_open])
        close_ops.extend([*pre_close, remote, *post_close])
    open_ops.extend(options.pop("post_open"))
    close_ops.extend(options.pop("post_close"))

    return Config(local_root, open_ops, close_ops, options)


def _parse_local_section(section: SectionProxy) -> tuple[Path, dict[str, Any]]:
    """Parse the local section of the config

    Parameters
    ----------
    section : SectionProxy
        The local section of the config

    Returns
    -------
    Path
        The local root folder
    dict
        Any keyword options to pass to the craft command

    Raises
    ------
    ParsingError
        If a required parameter isn't present or if a given option cannot be parsed
    """
    try:
        root = Path(section["root"])
    except KeyError:
        raise ParsingError("Config must explicitly specify a local root directory")
    except (TypeError, ValueError):
        raise ParsingError(
            f'Invalid value for root parameter in local config: {section["root"]} '
        )

    alias_option_names = {"name", "alias"}
    if len(alias_option_names.intersection(section.keys())) > 1:
        raise ParsingError(
            f"Found conflicting values for local installation's name/alias"
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
) -> tuple[tuple[list[str], list[str]], Remote, tuple[list[str], list[str]]]:
    """Parse a remote section

    Parameters
    ----------
    section : SectionProxy
        A section of the config specifying a remote source

    Returns
    -------
    tuple of two lists of str
        The list of commands to execute immediately before running the "open" and
        "close" rsync scripts, respectively, for this particular remote
    Remote
        The specification of this remote
    tuple of two lists of str
        The list of commands to execute immediately after running the "open" and
        "close" rsync scripts, respectively, for this particular remote

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
        root = Path(section["root"])
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
    return (
        (wrapper_commands["pre_open"], wrapper_commands["pre_close"]),
        Remote(host, root, username, alias),
        (wrapper_commands["post_open"], wrapper_commands["post_close"]),
    )


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
