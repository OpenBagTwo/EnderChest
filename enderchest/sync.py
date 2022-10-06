"""Utilities for synchronizing chests across different computers"""
import os
import shlex
import socket
import stat
import warnings
from dataclasses import dataclass, field
from pathlib import PosixPath
from typing import NamedTuple, Sequence

from . import contexts


class Remote(NamedTuple):
    """Specification of a remote EnderChest installation to sync with using rsync over
    ssh (other protocols are not explicitly supported).

    Attributes
    ----------
    host : str
        The address (_e.g._ 127.0.0.1) or cname/URL (_e.g._ steamdeck.local) of the
        host you're syncing with.
    root : path
        The root directory on the remote machine that contains all your minecraft stuff.
        Explicitly expects that the folder contains: your EnderChest folder;
        your Multi-MC-style instances folder; your servers.
    username : str, optional
        The username for logging onto the remote machine. If None is specified on
        instantiation, it's assumed that you don't need a username to log into the
        server from this local.
    alias : str
        A shorthand way to refer to the remote installation. If None is specified on
        instantiation, this will be the same as the host attribute.
    remote_folder : str
        The full specification of the remote root, _e.g._
        deck@steamdeck.local:~/minecraft

    Notes
    -----
    This class is not designed to be safe against injection attacks and has none of the
    protections you'd get out of using, say, the urllib.parse module.
    """

    host: str | None  # intentionally not in the docstring to use None for local mirror
    root: str | os.PathLike
    username: str | None = None
    alias_: str | None = None

    @property
    def alias(self) -> str:
        return self.alias_ or self.host or PosixPath(self.root).name

    @property
    def _encoded_root(self) -> str:
        """Shell-script safe version of the root folder.

        Notes
        -----
        Can't just use shlex.quote directly because it tries to quote "~"
        """
        root_string = str(self.root)
        if root_string == "~":
            return root_string
        if root_string.startswith("~/"):
            return "~/" + shlex.quote(root_string[2:])
        return shlex.quote(root_string)

    @property
    def remote_folder(self) -> str:
        if not self.host:
            # then the "remote" is actually local
            return self._encoded_root
        if not self.username:
            url = shlex.quote(self.host)
        else:
            url = f"{self.username}@{shlex.quote(self.host)}"
        return f"{url}:{self._encoded_root}"

    @classmethod
    def from_string(cls, oneline_spec: str) -> "Remote":
        match oneline_spec.split(":"):
            case [root]:
                address: str | None = None
            case address, *root:
                root = ":".join(root)
            case _:
                raise ValueError(f"Unable to parse {oneline_spec} into a remote spec")
        if address is None:
            username: str | None = None
            host: str | None = None
        else:
            match address.split("@"):
                case [host]:
                    username = None
                case username, host:
                    pass
                case _:
                    raise ValueError(
                        f"Unable to parse {oneline_spec} into a remote spec"
                    )
        return Remote(host, root, username)


@dataclass
class RemoteSync:
    """
    A specification of a remote and the commands to run pre- and post- syncing
    with the remote"

    Attributes
    ----------
    remote : Remote
        The remote to sync
    pre_open: list of str
        Any commands to run before pulling in EnderChest changes from the remote
    pre_close: list of str
        Any commands to run before pushing EnderChest changes to the remote
    post_open: list of str
        Any commands to run after pulling in EnderChest changes from the remote
    post_close: list of str
        Any commands to run after pushing EnderChest changes to the remote
    """

    remote: Remote
    pre_open: Sequence[str] = field(default_factory=list)
    pre_close: Sequence[str] = field(default_factory=list)
    post_open: Sequence[str] = field(default_factory=list)
    post_close: Sequence[str] = field(default_factory=list)


def link_to_other_chests(
    local_root: str | os.PathLike,
    *remotes: Remote | RemoteSync,
    local_alias: str | None = None,
    overwrite: bool = False,
    omit_scare_message: bool = False,
    pre_open: Sequence[str] | None = None,
    pre_close: Sequence[str] | None = None,
    post_open: Sequence[str] | None = None,
    post_close: Sequence[str] | None = None,
) -> None:
    """Generate bash scripts for syncing to EnderChest installations on other computers.
    These will be saved in your EnderChest/local-only folder under `open.sh`
    (for pulling from remotes) and `close.sh` (for pushing to other remotes)

    Parameters
    ----------
    local_root : path
        The local root directory that contains both the EnderChest directory, instances
        and servers
    *remotes : Remotes / RemoteSyncs
        The remote installations to sync with
    local_alias : str, optional
        A shorthand way to refer to the local installation. This is what determines the
        name of the local settings backup folder inside remote "other-locals" folders.
        If None is specified, this computer's hostname will be used.
    overwrite : bool, optional
        By default, if an open/close script exists, this method will leave it alone.
        To instead overwrite any existing scripts, explicitly pass in the keyword
        argument overwrite=True
    omit_scare_message : bool, optional
        By default, the scripts this method generates are not runnable and tell the user
        to first open them in a text editor and look them over. If you *really really
        trust* this method and the use of it, pass in the keyword argument
        omit_scare_message=True to omit this safeguard and just make them runnable from
        the get-go.
    pre_open: list of str, optional
        Any commands to run before pulling in EnderChest changes from the remotes
    pre_close: list of str, optional
        Any commands to run before pushing EnderChest changes to the remotes
    post_open: list of str, optional
        Any commands to run after pulling in EnderChest changes from the remotes
    post_close: list of str, optional
        Any commands to run after pushing EnderChest changes to the remotes

    Returns
    -------
    None

    Warnings
    --------
    If one of the scripts already exists, this method will emit a warning that
    generation of a new script is being kipped (if overwrite=True is not specified) or
    that the old script is being overwritten (if this method is called with
    overwrite=True).

    Notes
    -----
    - This method is designed for flexibility and transparency over robustness and ease
      of use. That means that **you need to open the scripts this function generates**
      and look them over before ou can actually run them. This also gives you a chance
      add your own tweaks and customizations before embedding the syncing into your
      automations.
    - The remotes are assumed to be specified in **priority order**
      (top priority first), meaning the first remote:
      - will be the first to receive local changes
      - will be the first to try pulling remote changes from
    """
    open_script = HEADER
    close_script = HEADER

    if not omit_scare_message:
        open_script += SCARE_MESSAGE
        close_script += SCARE_MESSAGE

    open_script += "\n"

    if pre_open:
        open_script += "".join([f"{command}\n" for command in pre_open])
    if pre_close:
        close_script += "".join([f"{command}\n" for command in pre_close])

    for remote in remotes:
        yeet, yoink = _build_rsync_scripts(
            local_root, local_alias or socket.gethostname(), remote
        )
        close_script += "\n" + yeet
        open_script += "{\n    " + "\n    ".join(yoink.split("\n")[:-1]) + "\n} || "

    open_script += """{
    echo "Could not pull changes from any remote EnderChests."
    echo "Are you outside your local network?"
    exit 1
}
"""

    if post_open:
        open_script += "".join([f"{command}\n" for command in post_open])
    if post_close:
        close_script += "".join([f"{command}\n" for command in post_close])

    for name, script in (("open", open_script), ("close", close_script)):
        script_path = contexts(local_root).local_only / f"{name}.sh"

        if script_path.exists():
            warning_message = f"{name.title()} script already exists."

            if not overwrite:
                warning_message += " Skipping."
                warnings.warn(warning_message)
                continue
            else:
                warning_message += " Overwriting."
                warnings.warn(warning_message)

        script_path.write_text(script)
        script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)


HEADER = """#!/usr/bin/env bash
set -e
"""

SCARE_MESSAGE = """
########################## DELETE AFTER READING ########################################
echo "These scripts were auto-generated and should be checked before first running!"
echo "Please open" $(realpath "$0")
echo "and read through the entire script to make sure it's doing what you want,"
echo "then delete the section marked "DELETE AFTER READING" near the top of the file."
echo
echo "It's also *strongly recommended* to run the commands first with"
echo "the flags: --dry-run --verbose to make absolutely sure the script is doing"
echo "what you want before you potentially overwrite an entire file system."
exit 1
########################################################################################
"""

SHARED_SYNC = """# sync changes from {source_desc} to {destination_desc}
rsync {options} \\
    {source}/EnderChest/ \\
    {destination}/EnderChest/ \\
    {exclusions} \\
    "$@"
"""

LOCAL_BACKUP = """# backup local settings to {remote_desc}
rsync {options} \\
    {local_root}/EnderChest/local-only/ \\
    {remote_root}/EnderChest/other-locals/{local_desc} \\
    "$@"
"""


def _build_rsync_scripts(
    local_root: str | os.PathLike, local_alias: str, remote: Remote | RemoteSync
) -> tuple[str, str]:
    """Build two rsync scripts: one for pushing local changes to a remote instance and
    another for pulling remote changes to the local

    Parameters
    ----------
    local_root : path
        The local root directory that contains both the EnderChest directory, instances
        and servers
    local_alias : str
        A shorthand way to refer to the local installation. This is what determines the
        name of the local settings backup folder inside the remote installation's
        "other-locals" folder.
    remote : Remote or RemoteSync
        The specification of the installation to sync with

    Returns
    -------
    str
        rsync command to push local changes to the remote instance
    str
        rsync command to pull remote changes to the local instance

    Notes
    -----
    - This method omits the header (shebang and set -e) from the generated scripts, as
      the intent is to allow for combining multiple calls into two large scripts.
    - This method is not designed to be safe against injection attacks--the goal is to
      generate **scripts** that the user can then tweak and modify before calling
      manually.
    - The local backup part of the script will assume that this computer's hostname is
      the best way to reference this EnderChest installation in the remote's
      "other-locals" folder. That's not going to be ideal if you're managing,
      say, multiple installations on the same computer (like, across separate user
      accounts?).
    """
    options = "-az --delete"
    # TODO: make z toggleable (to support local copies)
    # TODO: set timeout and controls around the conditions under you expect the remote
    #  to be accessible, _i,e,_
    #       - internet-accessible (for a server you can access outside the LAN
    #       - always-on (for desktops that don't get turned off when not in use)
    exclusion_folders = (".git", "local-only", "other-locals")
    exclusions = " ".join((f'--exclude="{folder}"' for folder in exclusion_folders))

    if isinstance(remote, Remote):
        remote = RemoteSync(remote)

    yoink = "".join([f"{command}\n" for command in remote.pre_open])
    yeet = "".join([f"{command}\n" for command in remote.pre_close])

    local_root_path = shlex.quote(str(PosixPath(local_root).expanduser().resolve()))

    yeet += SHARED_SYNC.format(
        source_desc="this EnderChest",
        destination_desc=remote.remote.alias,
        options=options,
        source=local_root_path,
        destination=remote.remote.remote_folder,
        exclusions=exclusions,
    )
    yeet += LOCAL_BACKUP.format(
        remote_desc=remote.remote.alias,
        options=options,
        local_root=local_root_path,
        remote_root=remote.remote.remote_folder,
        local_desc=local_alias,
    )

    yoink += SHARED_SYNC.format(
        source_desc=remote.remote.alias,
        destination_desc="this EnderChest",
        options=options,
        source=remote.remote.remote_folder,
        destination=local_root_path,
        exclusions=exclusions,
    )
    yoink += "".join([f"{command}\n" for command in remote.post_open])
    yeet += "".join([f"{command}\n" for command in remote.post_close])

    return yeet, yoink
