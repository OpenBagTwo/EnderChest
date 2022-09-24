"""Utilities for setting up the folder structure"""
import os
from collections import defaultdict

from . import contexts


def craft_ender_chest(root: str | os.PathLike) -> None:
    """Create the EnderChest folder structure in the specified root directory

    Parameters
    ----------
    root : path
        The root directory to put the EnderChest folder structure into
    """
    folders_for_contexts = _parse_folder_context_combos()
    for context_type, context_root in contexts(root)._asdict().items():
        context_root.mkdir(parents=True, exist_ok=True)
        for folder in folders_for_contexts[context_type]:
            (context_root / folder).mkdir(parents=True, exist_ok=True)


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
