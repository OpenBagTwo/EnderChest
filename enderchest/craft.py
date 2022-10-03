"""Utilities for setting up the folder structure"""
import os
from collections import defaultdict

from . import contexts
from .config import Config, parse_config_file
from .sync import Remote, RemoteSync, link_to_other_chests


def craft_ender_chest_from_config(config: Config | str | os.PathLike) -> None:
    """Craft the EnderChest folder structure and set up the sync scripts based on the
    contents of a config file

    Parameters
    ----------
    config : Config or path
        The path to a config file, or the parsed config itself

    Returns
    -------
    None
    """
    if not isinstance(config, Config):
        config = parse_config_file(config)
    craft_ender_chest(config.local_root, *config.remotes, **config.craft_options)


def craft_ender_chest(
    root: str | os.PathLike,
    *remotes: Remote | RemoteSync,
    craft_folders_only: bool = False,
    **sync_options
) -> None:
    """Create the EnderChest folder structure in the specified root directory as well
    as the sync scripts

    Parameters
    ----------
    root : path
        The root directory to put the EnderChest folder structure into
    *remotes : Remotes / RemoteSyncs
        The remote installations to sync with
    craft_folders_only : bool, optional
        If set to True, this method will only set up the EnderChest folders and will
        not create any sync scripts.
    **sync_options
        Any additional arguments to pass to the sync.link_to_other_chests()

    Returns
    -------
    None
    """
    folders_for_contexts = _parse_folder_context_combos()
    for context_type, context_root in contexts(root)._asdict().items():
        context_root.mkdir(parents=True, exist_ok=True)
        for folder in folders_for_contexts[context_type]:
            (context_root / folder).mkdir(parents=True, exist_ok=True)

    if not craft_folders_only:
        link_to_other_chests(root, *remotes, **sync_options)


# sometimes you just need a CSV
_FOLDER_CONTEXT_COMBOS = """
folder/context, universal, client_only, server_only, local_only
config,         yes,       yes,         yes,         yes
mods,           yes,       yes,         yes,         yes
resourcepacks,  yes,       yes,         no,          yes
saves,          no,        yes,         yes,         yes
shaderpacks,    no,        yes,         no,          yes
"""  # mote: omission of other_locals is intentional as remote names are top-level there


def _parse_folder_context_combos() -> dict[str, set[str]]:
    """But we definitely need to be able to turn that into something
    useful, in this case

    Returns
    -------
    dict of str to list-like of str
        A map of contexts to the folders that should be initialized in that context
    """
    header, *content = _FOLDER_CONTEXT_COMBOS.strip().split("\n")
    contexts = [cell.strip() for cell in header.split(",")[1:]]
    folders_for_contexts: dict[str, set[str]] = defaultdict(set)
    for row in content:
        folder, *values = (cell.strip() for cell in row.split(","))
        for i, value in enumerate(values):
            if value == "yes":
                folders_for_contexts[contexts[i]].add(folder)
    return folders_for_contexts
