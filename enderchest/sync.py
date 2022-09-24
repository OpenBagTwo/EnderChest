"""Utilities for synchronizing chests across different computers"""
import os
import socket
import warnings
from pathlib import Path

from . import contexts

HEADER = """#!/usr/bin/env bash
set -e

########################## DELETE AFTER READING ########################################
echo "These scripts were auto-generated and should be checked before first running!"
echo "Please open" $(realpath "$0")
echo "and read through the entire script to make sure it's doing what you want,"
echo "then delete the section marked "DELETE AFTER READING" near the top of the file."
echo
echo "It's also *strongly recommended* to run the commands first with
echo "the flags: --dry-run --verbose to make absolutely sure the script is doing 
echo "what you want before you potentially overwrite an entire file system."
exit 1
#########################################################################################

"""

SHARED_SYNC = """# sync changes from {source_desc} to {destination_desc}
rsync {options} {source}/EnderChest/ {destination}/EnderChest/ {exclusions} "$@"
"""

LOCAL_BACKUP = """# backup local settings to {remote}
rsync {options} {local_root}/EnderChest/local-only/ {remote}:{remote_root}/EnderChest/other-locals/{hostname}/. "$@"
"""


def _build_rsync_scripts(
    local_root: str | os.PathLike, remote: str, remote_root: str | os.PathLike
) -> tuple[str, str]:
    """Build two rsync scripts: one for pushing local changes to a remote instance and another for pulling remote
    changes to the local

    Parameters
    ----------
    local_root : path
        The local root directory that contains both the EnderChest directory, instances and servers
    remote : str
        The username @ hostname / IP of the remote machine, _e.g._ deck@steamdeck.local or openbagtwo@127.0.0.1
    remote_root : path
        The root directory on the remote machine that contains both the EnderChest directory, instances and servers

    Returns
    -------
    str
        rsync command to push local changes to the remote instance
    str
        rsync command to pull remote changes to the local instance

    Notes
    -----
    - This method omits the header (shebang and set -e) from the generated scripts, as the intent is to allow for
      combining multiple calls into two large scripts.
    - This method is not designed to be safe against injection attacks--the goal is to generate **scripts** that the
      user can then tweak and modify before calling manually.
    - The local backup part of the script will assume that this computer's hostname is the best way to reference this
      EnderChest installation in the remote's "other-locals" folder. That's not going to be ideal if you're managing,
      say, multiple installations on the same computer (like, across separate user accounts?).
    """
    options = "-az --delete"  # TODO: make z toggleable (to support local copies); conditionally add "v"
    exclusion_folders = (".git", "local-only", "other-locals")
    exclusions = " ".join((f'--exclude="{folder}"' for folder in exclusion_folders))

    yeet = SHARED_SYNC.format(
        source_desc="this EnderChest",
        destination_desc=remote.split("@")[-1],
        options=options,
        source=Path(local_root).resolve(),
        destination=f"{remote}:{remote_root}",
        exclusions=exclusions,
    ) + LOCAL_BACKUP.format(
        options=options,
        local_root=Path(local_root).resolve(),
        remote=remote,
        remote_root=remote_root,
        hostname=socket.gethostname(),
    )

    yoink = SHARED_SYNC.format(
        source_desc=remote.split("@")[-1],
        destination_desc="this EnderChest",
        options=options,
        source=f"{remote}:{remote_root}",
        destination=Path(local_root).resolve(),
        exclusions=exclusions,
    )

    return yeet, yoink


def link_to_other_chests(
    local_root: str | os.PathLike, *remotes: tuple[str, str | os.PathLike]
) -> None:
    """Generate bash scripts for syncing to EnderChest installations on other computers. These will be saved in
    your EnderChest/local-only folder under `open.sh` (for pulling from remotes) and `close.sh` (for pushing to other
    remotes)

    Parameters
    ----------
    local_root : path
        The local root directory that contains both the EnderChest directory, instances and servers
    *remotes : tuples of (str, path)
        The remote installations to sync with, specified as tuples of:
          - remote_address (including username, so, like, "deck@steamdeck.local" or "openbagtwo@127.0.0.1")
          - remote_root : the path to the remote's root directory (e.g. "~/minecraft")

    Returns
    -------
    None

    Notes
    -----
    - This method is designed for flexibility and transparency over robustness and ease of use. That means that
      **you need to open the scripts this function generates** and look them over before you can actually run them. This
      also gives you a chance add your own tweaks and customizations before first use.
    - The remotes are assumed to be specified in **priority order** (top priority first), meaning the first remote:
      - will be the first to receive local changes
      - will be the first to try pulling remote changes from
    """

    open_script = HEADER
    close_script = HEADER

    for remote, remote_root in remotes:
        yeet, yoink = _build_rsync_scripts(local_root, remote, remote_root)
        close_script += "\n" + yeet
        open_script += "{\n    " + "\n    ".join(yoink.split("\n")[:-1]) + "\n} || "

    open_script += """{
    echo "Could not pull changes from any remote EnderChests. Are you outside your local network?"
    exit 1
}
"""

    for name, script in (("open", open_script), ("close", close_script)):
        script_path = contexts(local_root).local_only / f"{name}.sh"

        if script_path.exists():
            warnings.warn(f"{name.title()} script already exists. Skipping.")
        else:
            with script_path.open("x") as script_file:
                script_file.write(script)
