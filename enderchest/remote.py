"""Higher-level functionality around synchronizing with different EnderCherts"""


from pathlib import Path
from urllib.parse import ParseResult, urlparse

from . import filesystem as fs
from .enderchest import EnderChest
from .loggers import SYNC_LOGGER
from .sync import remote_file, render_remote


def load_remote_ender_chest(uri: str | ParseResult) -> EnderChest:
    """Load an EnderChest configuration from another machine

    Parameters
    ----------
    uri : URI
        The URI to the remote Minecraft root

    Returns
    -------
    EnderChest
        The remote EnderChest configuration

    Raises
    ------
    ValueError
        If the provided URI is invalid
    RuntimeError
        If the config from the remote EnderChest could not be parsed
    """
    try:
        uri = uri if isinstance(uri, ParseResult) else urlparse(uri)
    except AttributeError as bad_uri:
        raise ValueError(f"{uri} is not a valid URI") from bad_uri

    remote_root = Path(uri.path)
    remote_config_path = fs.ender_chest_config(remote_root, check_exists=False)
    uri = uri._replace(path=remote_config_path.as_posix())

    with remote_file(uri) as remote_config:
        try:
            return EnderChest.from_cfg(remote_config)
        except ValueError as bad_chest:
            raise RuntimeError(
                "The remote EnderChest config downloaded"
                f"from {uri.geturl()} could not be parsed."
            ) from bad_chest


def fetch_remotes_from_a_remote_ender_chest(
    uri: str | ParseResult,
) -> list[tuple[ParseResult, str]]:
    """Grab the list of EnderChests registered with the specified remote EnderChest

    Parameters
    ----------
    uri : URI
        The URI to the remote Minecraft root

    Returns
    -------
    list of (URI, str) tuples
        The URIs of the remote EnderChests, paired with their aliases

    Raises
    ------
    RuntimeError
        If the remote list could not be pulled
    """
    remote_chest = load_remote_ender_chest(uri)
    remotes: list[tuple[ParseResult, str]] = [(remote_chest._uri, remote_chest.name)]

    remotes.extend(remote_chest.remotes)
    SYNC_LOGGER.info(
        "Loaded the following remotes:\n"
        + "\n".join(f"  - {render_remote(alias, uri)}" for uri, alias in remotes)
    )

    if len(set(alias for _, alias in remotes)) != len(remotes):
        raise RuntimeError(
            f"There are duplicates aliases in the list of remotes pulled from {uri}"
        )
    return remotes
