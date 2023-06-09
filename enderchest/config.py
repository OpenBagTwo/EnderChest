"""Helpers for parsing and writing INI-format config files"""
from configparser import ConfigParser, ParsingError
from pathlib import Path
from typing import Sequence


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
    except AssertionError:
        raise FileNotFoundError(f"Could not open {config_file}")
    return configurator


def list_to_ini(values: Sequence) -> str:
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
