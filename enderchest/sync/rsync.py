"""rsync sync implementation. Relies on the user having rsync installed on their system"""
import os.path
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Iterable
from urllib.parse import ParseResult, unquote

from . import SYNC_LOGGER, get_default_netloc, uri_to_ssh

RSYNC = shutil.which("rsync")
if RSYNC is None:  # pragma: no cover
    raise RuntimeError(
        "No rsync executable found on your system. Cannot sync using this protocol."
    )


def _get_rsync_version() -> tuple[int, int]:
    """Determine the installed version of Rsync

    Returns
    -------
    int
        The major version of the resolved Rsync executable
    int
        The minor version of the resolved Rsync executable

    Raises
    -----
    RuntimeError
        If Rsync is not installed, if `rsync --version` returns an error or if
        the version information cannot be decoded from the `rsync --version`
        output
    """
    try:
        result = subprocess.run(
            ["rsync", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.stderr:  # TODO: #124 just use check=True
            raise RuntimeError(result.stderr.decode("utf-8"))

        head = result.stdout.decode("utf-8").splitlines()[0]
    except (FileNotFoundError, IndexError):
        raise RuntimeError("Rsync is not installed or could not be executed.")

    try:
        if match := re.match(
            r"^rsync[\s]+version ([0-9]+).([0-9]+).([0-9]+)",
            head,
        ):
            major, minor, *_ = match.groups()
            return int(major), int(minor)
        raise AssertionError
    except (AssertionError, ValueError):
        raise RuntimeError(f"Could not parse version output:\n{head}")


rsync_version = _get_rsync_version()
if rsync_version < (3, 2):
    raise RuntimeError(
        "EnderChest requires Rsync 3.2 or newer."
        " The version detected on your system is {}.{}".format(*rsync_version)
    )


def run_rsync(
    working_directory: Path,
    source: str,
    destination_folder: str,
    delete: bool,
    dry_run: bool,
    exclude: Iterable[str],
    *additional_args: str,
    timeout: int | None = None,
    verbosity: int = 0,
    rsync_flags: str | None = None,
) -> None:
    """Run an operation with rsync

    Parameters
    ----------
    working_directory : Path
        The working directory to run the sync command from
    source : str
        The source file or folder to sync, specified as either a URI string,
        an ssh address or a path relative to the working directory
    destination_folder : str
        The destination folder where the file or folder should be synced to,
        with the same formats available as for source
    delete : bool
        Whether part of the syncing should include deleting files at the destination
        that aren't at the source
    dry_run : bool
        Whether to only simulate this sync (report the operations to be performed
        but not actually perform them)
    exclude : list of str
        Any patterns that should be excluded from the sync (and sync)
    *additional_args : str
        Any additional arguments to pass into the rsync command
    timeout : int, optional
        The number of seconds to wait before timing out the sync operation.
        If None is provided, no explicit timeout value will be set.
    verbosity : int
        A modifier for how much info to output either to stdout or the INFO-level
        logs. At...

          - verbosity = -2 : No information will be printed, even on dry runs
          - verbosity = -1 : The sync itself will be silent. Dry runs will only
                             report the sync statistics.
          - verbosity =  0 : Actual syncs will display a progress bar. Dry run
                             reports will summarize the changes to each shulker
                             box in addition to reporting the sync statistics .
          - verbosity =  1 : Actual syncs will report the progress of each file
                             transfer. Dry runs will report on each file to
                             be created, updated or deleted.
          - verbosity =  2 : Dry runs and syncs will print or log the output
                             of rsync run using the `-vv` modifier

        Verbosity values outside of this range will simply be capped / floored
        to [-2, 2].
    rsync_flags : str, optional
        By default, rsync will be run using the flags "shaz" which means:

          - no space splitting
          - use output (file sizes, mostly) human-readable
          - archive mode (see: https://www.baeldung.com/linux/rsync-archive-mode)
          - compress data during transfer

        Advanced users may choose to override these options, but **you do so
        at your own peril**.

    Raises
    ------
    TimeoutError
        If the rsync operation times out before completion
    RuntimeError
        If the rsync operation fails for any other reason

    Notes
    -----
    This method does not perform any validation or normalization of the source,
    destination, exclude-list, additional arguments or rsync options.
    """
    rsync_flags = rsync_flags or "shaz"

    args: list[str] = [RSYNC, f"-{rsync_flags}"]  # type: ignore[list-item]
    if delete:
        args.append("--delete")
    if dry_run:
        args.extend(("--dry-run", "--stats"))
        if verbosity < 1:
            # at 1+ we don't need it to be machine-parseable
            args.append("--out-format=%i %n")
    else:
        if verbosity >= 0:
            args.append("--stats")
        if verbosity == 0:
            args.append("--info=progress2")
        if verbosity >= 1:
            args.append("--progress")
    if verbosity > 0:
        args.append("-" + "v" * verbosity)

    for pattern in exclude:
        args.extend(("--exclude", pattern))
    args.extend(additional_args)
    args.extend((source, destination_folder))

    SYNC_LOGGER.debug(
        "Executing the following command:\n %s",
        " ".join(args),
    )

    with subprocess.Popen(
        args,
        stdout=subprocess.PIPE if dry_run else None,
        stderr=subprocess.PIPE,
        cwd=working_directory,
    ) as proc:
        if timeout:
            try:
                proc.wait(timeout)
            except subprocess.TimeoutExpired as times_up:
                proc.kill()
                if proc.stdout is not None:
                    if output_log := proc.stdout.read().decode("UTF-8"):
                        SYNC_LOGGER.warning(output_log)
                if proc.stderr is not None:
                    if error_log := proc.stderr.read().decode("UTF-8"):
                        SYNC_LOGGER.error(error_log)
                raise TimeoutError("Timeout reached.") from times_up

        if proc.stdout is not None:
            if output_log := proc.stdout.read().decode("UTF-8"):
                if verbosity > 0:
                    dry_run_output = output_log.splitlines()
                else:
                    dry_run_output = summarize_rsync_report(output_log)
                    SYNC_LOGGER.info("\nSUMMARY\n-------")
                for line in dry_run_output:
                    if _is_important_stats_line(line):
                        SYNC_LOGGER.log(25, line)
                    else:
                        SYNC_LOGGER.debug(line)

        if proc.stderr is not None:
            if error_log := proc.stderr.read().decode("UTF-8"):
                if "No such file or directory" in error_log:
                    raise FileNotFoundError(error_log)
                raise RuntimeError(error_log)  # pragma: no cover


def summarize_rsync_report(raw_output: str, depth: int = 2) -> list[str]:
    """Take the captured output from running
    `rsync -ha --out-format="%i %n"`
    and report a high-level summary to the logging.INFO level

    Parameters
    ----------
    raw_output : str
        The raw output captured from running the rsync command
    depth : int, optional
        How many directories to go down from the root to generate the summary.
        Default is 2 (just report on top-level files and folders within the
        source folder).

    Returns
    -------
    list of str
        Any lines that weren't part of the rsync report (and were probably
        part of `--stats`?)

    Notes
    -----
    The rsync man page (https://linux.die.net/man/1/rsync) describes the output
    format as... "cryptic," which I find rather charitable. The relevant bits
    are that `--out-format="%i %n"` produces:
    - `%i` : a string of 11 characters that gives various metadata about the file
      transfer operation (is it a file, a directory or a link? Is it being
      sent or received? Created, updated or deleted?)
    - `%n`: the path of the file (or whatever), unquoted, un-escaped
    """
    summary: dict[str, dict[str, int] | str] = defaultdict(
        lambda: {"create": 0, "update": 0, "delete": 0}
    )
    stats: list[str] = []
    for line in raw_output.splitlines():
        if line == "":  # skip empty lines
            continue

        info = line.split()[0]
        full_path = os.path.normpath(" ".join(line.split()[1:]))
        path_key = os.sep.join(full_path.split(os.sep)[:depth])

        if info.startswith("*deleting"):
            if full_path == path_key:
                summary[path_key] = "delete"
            else:
                entry = summary[path_key]
                if not isinstance(entry, str):
                    entry["delete"] += 1
                # otherwise the whole thing is being deleted
        elif info[2:5] == "+++":  # this is a creation
            if full_path == path_key:
                summary[path_key] = "create"
            else:
                if info[1] != "d":  # don't count directories
                    entry = summary[path_key]
                    if isinstance(entry, str):
                        # then this is described by the top-level op
                        pass
                    else:
                        entry["create"] += 1
                    # otherwise the whole key is being created
        elif info[:2] in ("<f", ">f"):  # file transfer
            # and remember that creates were caught above, so this must be an update
            if full_path == path_key:
                summary[path_key] = "update"
            else:
                entry = summary[path_key]
                if isinstance(entry, str):  # pragma: no cover
                    # this should never happen, but still
                    pass
                else:
                    entry["update"] += 1
        elif info[:2] == "cL":  # this is replacing a link, as far as I can tell
            if full_path == path_key:
                summary[path_key] = "update"
            else:
                entry = summary[path_key]
                if isinstance(entry, str):  # pragma: no cover
                    # this should never happen, but still
                    pass
                else:
                    entry["update"] += 1
        elif info[:1] == ".":  # pragma: no cover
            # this just means permissions or dates are being updated or something
            pass
        else:  # then hopefully this is part of the stats report
            stats.append(line)
            continue

        SYNC_LOGGER.debug(line)

    for path_key, report in sorted(summary.items()):
        if isinstance(report, str):
            # nice that these verbs follow the same pattern
            SYNC_LOGGER.info(f"{report[:-1].title()}ing {path_key}")
        else:
            SYNC_LOGGER.info(
                f"Within {path_key}...\n%s",
                "\n".join(
                    f"  - {op[:-1].title()}ing {count} file{'' if count == 1 else 's'}"
                    for op, count in report.items()
                ),
            )
    return stats


def _is_important_stats_line(line: str) -> bool:
    """Determine if a stats line is worth logging at the INFO level (or whether
    it should be relegated to the DEBUG log)

    Parameters
    ----------
    line : str
        The log line to evaluate

    Returns
    -------
    bool
        True if and only if the line is identified as important
    """
    return line.startswith(
        (
            "Number of created files:",
            "Number of deleted files:",
            "Number of regular files transferred:",
            "Total transferred file size:",
        )
    )


def pull(
    remote_uri: ParseResult,
    local_path: Path,
    exclude: Iterable[str],
    dry_run: bool,
    use_daemon: bool = False,
    timeout: int | None = None,
    delete: bool = True,
    verbosity: int = 0,
    rsync_args: Iterable[str] | None = None,
) -> None:
    """Sync an upstream file or folder into the specified location using rsync.
    This will overwrite any files and folders already at the destination.

    Parameters
    ----------
    remote_uri : ParseResult
        The URI for the remote resource to copy from
    local_path : Path
        The destination folder
    exclude : list of str
        Any patterns that should be excluded from the sync
    dry_run : bool
        Whether to only simulate this sync (report the operations to be performed
        but not actually perform them)
    use_daemon : bool, optional
        By default, the rsync is performed over ssh. If you happen to have an
        rsync daemon running on your system, however, you're welcome to leverage
        it instead by passing in `use_daemon=True`
    timeout : int, optional
        The number of seconds to wait before timing out the sync operation.
        If None is provided, no explicit timeout value will be set.
    delete : bool, optional
        Whether part of the syncing should include deleting files at the destination
        that aren't at the source. Default is True.
    verbosity : int
        A modifier for how much info to output either to stdout or the INFO-level
        logs. Defaults to 0.
    rsync_args: list of str, optional
        Any additional arguments to pass into rsync. Note that rsync is run by
        default with the flags: `-shaz`

    Raises
    ------
    FileNotFoundError
        If the destination folder does not exist

    Notes
    -----
    - This method does not provide for interactive authentication. If using
      rsync over SSH, you'll need to be set up for password-less (key-based)
      access.
    - If the destination folder does not already exist, this method will not
      create it or its parent directories.
    """
    if not local_path.exists():
        raise FileNotFoundError(f"{local_path} does not exist")

    if remote_uri.netloc == get_default_netloc():
        SYNC_LOGGER.debug("Performing sync as a local transfer")
        remote_path: str = unquote(remote_uri.path)
    elif use_daemon:
        remote_path = remote_uri.geturl()
    else:
        remote_path = uri_to_ssh(remote_uri)

    if rsync_args:  # pragma: no cover
        raise NotImplementedError

    run_rsync(
        local_path.parent,
        remote_path,
        local_path.name,
        delete,
        dry_run,
        exclude,
        *(rsync_args or ()),
        timeout=timeout,
        verbosity=verbosity,
    )


def push(
    local_path: Path,
    remote_uri: ParseResult,
    exclude: Iterable[str],
    dry_run: bool,
    use_daemon: bool = False,
    timeout: int | None = None,
    delete: bool = True,
    verbosity: int = 0,
    rsync_args: Iterable[str] | None = None,
) -> None:
    """Sync a local file or folder into the specified location using rsync.
    This will overwrite any files and folders already at the destination.

    Parameters
    ----------
    local_path : Path
        The file or folder to copy
    remote_uri : ParseResult
        The URI for the remote location to copy into
    exclude : list of str
        Any patterns that should be excluded from the sync
    dry_run : bool
        Whether to only simulate this sync (report the operations to be performed
        but not actually perform them)
    use_daemon : bool, optional
        By default, the rsync is performed over ssh. If you happen to have an
        rsync daemon running on your system, however, you're welcome to leverage
        it instead by passing in `use_daemon=True`
    timeout : int, optional
        The number of seconds to wait before timing out the sync operation.
        If None is provided, no explicit timeout value will be set.
    delete : bool, optional
        Whether part of the syncing should include deleting files at the destination
        that aren't at the source. Default is True.
    verbosity : int
        A modifier for how much info to output either to stdout or the INFO-level
        logs. Defaults to 0.
    rsync_args: list of str, optional
        Any additional arguments to pass into rsync. Note that rsync is run by
        default with the flags: `-shaz`

    Notes
    -----
    - This method does not provide for interactive authentication. If using
      rsync over SSH, you'll need to be set up for password-less (key-based)
      access.
    - If the destination folder does not already exist, this method will very
      likely fail.
    """
    if remote_uri.netloc == get_default_netloc():
        SYNC_LOGGER.debug("Performing sync as a local transfer")
        remote_path: str = unquote(remote_uri.path)
    elif use_daemon:
        remote_path = remote_uri.geturl()
    else:
        remote_path = uri_to_ssh(remote_uri)

    if rsync_args:  # pragma: no cover
        raise NotImplementedError

    run_rsync(
        local_path.parent,
        local_path.name,
        remote_path,
        delete,
        dry_run,
        exclude,
        *(rsync_args or ()),
        timeout=timeout,
        verbosity=verbosity,
    )
