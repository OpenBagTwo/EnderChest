"""Higher-level functionality around synchronizing with different EnderCherts"""

import logging
from pathlib import Path
from time import sleep
from typing import Sequence
from urllib.parse import ParseResult, urlparse

from . import filesystem as fs
from . import gather, place
from .enderchest import EnderChest
from .loggers import IMPORTANT, SYNC_LOGGER
from .prompt import confirm
from .sync import abspath_from_uri, pull, push, remote_file, render_remote


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
    remotes: list[tuple[ParseResult, str]] = [
        (urlparse(uri) if isinstance(uri, str) else uri, remote_chest.name)
    ]

    remotes.extend(remote_chest.remotes)
    SYNC_LOGGER.info(
        "Loaded the following remotes:\n %s",
        "\n".join(f"  - {render_remote(alias, uri)}" for uri, alias in remotes),
    )

    if len(set(alias for _, alias in remotes)) != len(remotes):
        raise RuntimeError(
            f"There are duplicates aliases in the list of remotes pulled from {uri}"
        )
    return remotes


def sync_with_remotes(
    minecraft_root: Path,
    pull_or_push: str,
    dry_run: bool = False,
    sync_confirm_wait: bool | int | None = None,
    **sync_kwargs,
) -> None:
    """Pull changes from or push changes to remote EnderChests

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder). This will be used to
        construct relative paths.
    pull_or_push : str
        "pull" or "push"
    dry_run: bool, optional
         Perform a dry run of the sync operation, reporting the operations\
         that will be performed but not actually carrying them out
    sync_confirm_wait : bool or int, optional
        The default behavior when syncing EnderChests is to first perform a dry
        run of every sync operation and then wait 5 seconds before proceeding with the
        real sync. The idea is to give the user time to interrupt the sync if
        the dry run looks wrong. This can be changed by either raising or lowering
        the value of confirm, by disabling the dry-run-first behavior entirely
        (`confirm=False`) or by requiring that the user explicitly confirms
        the sync (`confirm=True`). This default behavior can also be modified
        in the EnderChest config. This parameter will be ignored when performing
        a dry run.
    sync_kwargs
        Any additional arguments that should be passed into the syncing
        operation

    Notes
    -----
    - When pulling changes, this method will try each remote in the order they
      are configured and stop once it has successfully pulled from a remote.

    This method will attempt to push local changes to *every* remote
    """
    if pull_or_push not in ("pull", "push"):
        raise ValueError(
            'Invalid choice for sync operation. Choices are "pull" and "push"'
        )
    try:
        if sync_confirm_wait is None:
            sync_confirm_wait = gather.load_ender_chest(
                minecraft_root
            ).sync_confirm_wait
        this_chest = gather.load_ender_chest(minecraft_root)

        # I know this is redundant, but we want those logs
        remotes = gather.load_ender_chest_remotes(
            minecraft_root, log_level=logging.DEBUG
        )
    except (FileNotFoundError, ValueError) as bad_chest:
        SYNC_LOGGER.error(
            f"Could not load EnderChest from {minecraft_root}:\n  {bad_chest}"
        )
        return
    if not remotes:
        SYNC_LOGGER.error("EnderChest has no remotes. Aborting.")
        return  # kinda unnecessary

    synced_somewhere = False
    exclusions: Sequence[str] = sync_kwargs.pop("exclude", None) or ()
    for remote_uri, alias in remotes:
        if dry_run:
            runs: tuple[bool, ...] = (True,)
        elif sync_confirm_wait is False or sync_confirm_wait <= 0:
            runs = (False,)
        else:
            runs = (True, False)
        for do_dry_run in runs:
            if dry_run:
                prefix = "Simulating an attempt"
            else:
                prefix = "Attempting"
            try:
                if pull_or_push == "pull":
                    SYNC_LOGGER.log(
                        IMPORTANT,
                        f"{prefix} to pull changes from %s",
                        render_remote(alias, remote_uri),
                    )
                    remote_chest = remote_uri._replace(
                        path=urlparse(
                            (
                                fs.ender_chest_folder(
                                    abspath_from_uri(remote_uri),
                                    check_exists=False,
                                )
                            ).as_uri()
                        ).path
                    )
                    pull(
                        remote_chest,
                        minecraft_root,
                        exclude=[
                            *this_chest.do_not_sync,
                            *exclusions,
                        ],
                        dry_run=do_dry_run,
                        **sync_kwargs,
                    )
                else:
                    SYNC_LOGGER.log(
                        IMPORTANT,
                        f"{prefix} to push changes"
                        f" to {render_remote(alias, remote_uri)}",
                    )
                    local_chest = fs.ender_chest_folder(minecraft_root)
                    push(
                        local_chest,
                        remote_uri,
                        exclude=[
                            *this_chest.do_not_sync,
                            *exclusions,
                        ],
                        dry_run=do_dry_run,
                        **sync_kwargs,
                    )
            except (
                FileNotFoundError,
                ValueError,
                NotImplementedError,
                TimeoutError,
                RuntimeError,
            ) as sync_fail:
                SYNC_LOGGER.warning(
                    f"Could not sync changes with {render_remote(alias, remote_uri)}:"
                    f"\n  {sync_fail}"
                )
                break
            if do_dry_run == runs[-1]:
                continue
            if sync_confirm_wait is True:
                if not confirm(default=True):
                    SYNC_LOGGER.error("Aborting")
                    return
            else:
                SYNC_LOGGER.debug(f"Waiting for {sync_confirm_wait} seconds")
                sleep(sync_confirm_wait)
        else:
            synced_somewhere = True
            if pull_or_push == "pull":
                if this_chest.place_after_open and not dry_run:
                    place.place_ender_chest(
                        minecraft_root,
                        keep_broken_links=False,
                        keep_stale_links=False,
                        error_handling="abort",
                        relative=False,
                    )
                break
    if not synced_somewhere:
        SYNC_LOGGER.error("Could not sync with any remote EnderChests")
