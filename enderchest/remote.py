"""Higher-level functionality around synchronizing with different EnderCherts"""
import logging
import os
from pathlib import Path
from urllib.parse import ParseResult, urlparse

from . import filesystem as fs
from . import gather
from .enderchest import EnderChest
from .loggers import SYNC_LOGGER
from .sync import path_from_uri, pull, push, remote_file, render_remote


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


def pull_upstream_changes(minecraft_root: Path, **sync_kwargs) -> None:
    """Pull in changes from a remote EnderChest

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder). This will be used to
        construct relative paths.
    sync_kwargs
        Any additional arguments that should be passed into the syncing
        operation

    Notes
    -----
    This method will try each remote in the order they are configured and stop
    once it has successfully pulled from a remote.
    """
    try:
        remotes = gather.load_ender_chest_remotes(
            minecraft_root, log_level=logging.DEBUG
        )
    except (FileNotFoundError, ValueError) as bad_chest:
        SYNC_LOGGER.error(
            f"Could not load EnderChest from {minecraft_root}:\n  {bad_chest}"
        )
        return
    if not remotes:
        SYNC_LOGGER.error("Enderchest has no remotes. Aborting")
        return  # kinda unnecessary

    for uri, alias in remotes:
        SYNC_LOGGER.info(
            "Attempting to pull changes from" f" {render_remote(alias, uri)}"
        )
        try:
            remote_chest = uri._replace(
                path=urlparse(
                    (
                        fs.ender_chest_folder(
                            path_from_uri(uri),
                            check_exists=False,
                        )
                    ).as_uri()
                ).path
            )

            pull(
                remote_chest,
                minecraft_root,
                exclude=[
                    os.path.join(
                        fs.ENDER_CHEST_FOLDER_NAME, fs.ENDER_CHEST_CONFIG_NAME
                    ),
                    os.path.join(fs.ENDER_CHEST_FOLDER_NAME, ".*"),
                    *sync_kwargs.pop("exclude", ()),
                ],
                **sync_kwargs,
            )
        except Exception as exc:
            SYNC_LOGGER.warning(
                f"Could not pull changes from {render_remote(alias, uri)}:" f"\n  {exc}"
            )
            continue
        break
    else:
        SYNC_LOGGER.error("Could not sync with any remote EnderChests")


def push_changes_upstream(minecraft_root: Path, **sync_kwargs) -> None:
    """Push changes to all a remote EnderChests

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder). This will be used to
        construct relative paths.
    sync_kwargs
        Any additional arguments that should be passed into the syncing
        operation

    Notes
    -----
    This method will attempt to push local changes to *every* remote
    """
    try:
        remotes = gather.load_ender_chest_remotes(
            minecraft_root, log_level=logging.DEBUG
        )
    except (FileNotFoundError, ValueError) as bad_chest:
        SYNC_LOGGER.error(
            f"Could not load EnderChest from {minecraft_root}:\n  {bad_chest}"
        )
        return
    if not remotes:
        SYNC_LOGGER.error("Enderchest has no remotes. Aborting")
        return  # kinda unnecessary

    pushed_somewhere = False
    for remote_uri, alias in remotes:
        SYNC_LOGGER.info(
            f"Attempting to push changes to {render_remote(alias, remote_uri)}"
        )
        try:
            local_chest = fs.ender_chest_folder(minecraft_root)
            push(
                local_chest,
                remote_uri,
                exclude=[
                    os.path.join(
                        fs.ENDER_CHEST_FOLDER_NAME, fs.ENDER_CHEST_CONFIG_NAME
                    ),
                    os.path.join(fs.ENDER_CHEST_FOLDER_NAME, ".*"),
                    *sync_kwargs.pop("exclude", ()),
                ],
                **sync_kwargs,
            )
            pushed_somewhere = True
        except Exception as exc:
            SYNC_LOGGER.warning(
                f"Could not push changes to {render_remote(alias, remote_uri)}:"
                f"\n  {exc}"
            )
    if not pushed_somewhere:
        SYNC_LOGGER.error("Could not sync with any remote EnderChests")
