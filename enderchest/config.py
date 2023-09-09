"""Helpers for parsing and writing INI-format config files"""
import ast
import datetime as dt
from configparser import ConfigParser, ParsingError
from io import StringIO
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ._version import get_versions


def get_configurator() -> ConfigParser:
    """Generate a configuration parser capable of reading or writing INI files

    Returns
    -------
    ConfigParser
        The pre-configured configurator
    """
    configurator = ConfigParser(
        allow_no_value=True, inline_comment_prefixes=(";",), interpolation=None
    )
    configurator.optionxform = str  # type: ignore
    return configurator


def read_cfg(config_file: Path) -> ConfigParser:
    """Read in a configuration file

    Parameters
    ----------
    config_file : Path
        The path to the configuration file

    Returns
    -------
    ConfigParser
        The parsed configuration

    Raises
    ------
    ValueError
        If the config file at that location cannot be parsed
    FileNotFoundError
        If there is no config file at the specified location
    """
    configurator = get_configurator()
    try:
        assert configurator.read(config_file)
    except ParsingError as bad_cfg:
        raise ValueError(f"Could not parse {config_file}") from bad_cfg
    except AssertionError as not_read:
        raise FileNotFoundError(f"Could not open {config_file}") from not_read
    return configurator


def dumps(
    header: str | None,
    properties: dict[str, Any],
    **sections: Mapping[str, Any] | Sequence[str],
) -> str:
    """Serialize a configuration into an INI-formatted string

    Parameters
    ----------
    header: str
        A header to render as a comment at the top of the file
    properties: dict
        The "main" section contents. Note that this method will add some of its own
    **sections : dict or list
        Any additional sections to write. Each section may consist of a set
        of key-value pairs or they might simply be a list of values

    Returns
    -------
    str
        The contents of the configuration, suitable for writing to file
    """
    config = get_configurator()

    config.add_section("properties")
    for key, value in properties.items():
        config.set("properties", to_ini_key(key), to_ini_value(value))

    config.set(
        "properties",
        "last-modified",
        to_ini_value(dt.datetime.now()),
    )
    config.set(
        "properties", "generated-by-enderchest-version", get_versions()["version"]
    )

    for section, values in sections.items():
        section_name = to_ini_key(section)
        config.add_section(section_name)
        if isinstance(values, Mapping):
            for key, value in values.items():
                config.set(section_name, to_ini_key(key), to_ini_value(value))
        else:
            for value in values:
                config.set(section_name, to_ini_value(value))

    buffer = StringIO()
    if header:
        buffer.write(f"; {header}\n")
    config.write(buffer)
    buffer.seek(0)  # rewind
    return buffer.read()


def to_ini_key(key: str) -> str:
    """Style guide enforcement for INI keys

    Parameters
    ----------
    key : str
        The entry key to normalize

    Returns
    -------
    str
        The normalized key
    """
    return key.replace("_", "-")


def to_ini_value(value: Any) -> str:
    """Format a value into a string suitable for use in an INI entry

    Parameters
    ----------
    value
        The value to format

    Returns
    -------
    str
        The formatted INI-appropriate value
    """
    if isinstance(value, str):
        # have to put in this check since strings are iterable
        return value
    if value is None:
        return ""
    if isinstance(value, Iterable):
        return list_to_ini(list(value))
    if isinstance(value, dt.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, dt.date):
        # note that datetimes are considered dates
        return value.isoformat()

    return str(value)


def list_to_ini(values: Sequence) -> str:
    """Format a list of values into a string suitable for use in an INI entry

    Parameters
    ----------
    values : list-like
        the values in the list

    Returns
    -------
    str
        The formatted INI-appropriate value
    """
    if len(values) == 0:
        return ""
    if len(values) == 1:
        return values[0]
    return "\n" + "\n".join(values)


def parse_ini_list(entry: str) -> list[str]:
    """Parse a list from an INI config entry

    Parameters
    ----------
    entry : str
        The raw entry from the INI

    Returns
    -------
    list of str
        The parsed entries

    Notes
    -----
    This method is *only* for parsing specific values of a key-value entry
    *and not* for the whole "section is the key, lines are the values" thing
    I've got going on.
    """
    entry = entry.strip()
    try:
        parsed = ast.literal_eval(entry)
        if isinstance(parsed, str):
            return [parsed]
        return [str(value) for value in parsed]
    except (TypeError, ValueError, SyntaxError):
        # if only it were that easy...
        pass

    values: list[str] = []
    for line in entry.splitlines():
        try:
            values.append(str(ast.literal_eval(line)))
        except (TypeError, ValueError, SyntaxError):
            values.append(line.strip())
    return values
