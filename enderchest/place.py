"""Symlinking functionality"""
import fnmatch
import itertools
import json
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Sequence

from . import filesystem as fs
from .gather import load_ender_chest, load_ender_chest_instances, load_shulker_boxes
from .loggers import GATHER_LOGGER, IMPORTANT, PLACE_LOGGER
from .prompt import prompt
from .shulker_box import ShulkerBox


def place_ender_chest(
    minecraft_root: Path,
    keep_broken_links: bool = False,
    keep_stale_links: bool = False,
    error_handling: str = "abort",
    relative: bool = True,
    rollback: bool = False,
) -> dict[str, dict[Path, list[str]]]:
    """Link all instance files and folders to all shulker boxes

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    keep_broken_links : bool, optional
        By default, this method will remove any broken links in your instances
        and servers folders. To disable this behavior, pass in
        `keep_broken_links=True`.
    keep_stale_links : bool, optional
        By default, this method will remove any links into your EnderChest folder
        that are no longer specified by any shulker box (such as because the
        instance spec or shulker box configuration changed). To disable this
        behavior, pass in `keep_stale_links=True`.
    error_handling : str, optional
        By default, if a linking failure occurs, this method will terminate
        immediately (`error_handling=abort`). Alternatively,
          - pass in `error_handling="ignore"` to continue as if the link failure
            hadn't occurred
          - pass in `error_handling="skip"` to abort linking the current instance
            to the current shulker box but otherwise continue on
          - pass in `error_handling="skip-instance"` to abort linking the current
            instance altogether but to otherwise continue on with other instances
          - pass in `error_handling="skip-shulker-box"` to abort linking to the current
            shulker box altogether but to otherwise continue on with other boxes
          - pass in `error_handling="prompt"` to ask what to do on each failure
    relative : bool, optional
        By default, links will use relative paths when possible. To use absolute
        paths instead (see: https://bugs.mojang.com/projects/MC/issues/MC-263046),
        pass in `relative=False`. See note below.
    rollback: bool, optional
        In the future in the event of linking errors passing in `rollback=True`
        can be used to roll back any changes that have already been applied
        based on the error-handling method specified.

    Returns
    -------
    dict
        A record of the placed symlinks, structured as a nested dict:

        - the top-level keys are the instance names, with the values being a map
          of the links placed within those instances:
            - the keys of those mappings are the relative paths of the placed
              symlinks inside the instance folder
            - the values are the list of shulker boxes, sorted in ascending
              priority, into which that symlink was linked (explicitly, the
              _last_ entry in each list corresponds to the shulker box inside
              which that link currently points)

    Notes
    -----
    - If one of the files or folders being placed is itself a symlink, relative
      links will be created as *nested* links (a link pointing to the link),
      whereas in "absolute" mode (`relative=False`), the link that will be
      placed will point **directly** to the final target
    - This can lead to the stale-link cleanup behavior not correctly removing
      an outdated symlink if the fully resolved target of a link falls outside
      the EnderChest folder
    - The generated placement record reflects only the placements performed by
      _this_ placement operation ("stale" links will never be included)
    - The generated placements record will include broken links irrespective of
      the `keep_broken_links` argument
    - If the placement is aborted (`error_handling="abort"` or "Abort" selected
      from prompt) then the returned placements will be empty
    """
    placements: dict[str, dict[Path, list[str]]] = {}

    if rollback is not False:  # pragma: no cover
        raise NotImplementedError("Rollbacks are not currently supported")

    try:
        host = load_ender_chest(minecraft_root).name
    except (FileNotFoundError, ValueError) as bad_chest:
        PLACE_LOGGER.error(
            f"Could not load EnderChest from {minecraft_root}:\n  {bad_chest}"
        )
        return {}

    instances = load_ender_chest_instances(minecraft_root, log_level=logging.DEBUG)

    shulker_boxes: list[ShulkerBox] = []

    for shulker_box in load_shulker_boxes(minecraft_root, log_level=logging.DEBUG):
        if not shulker_box.matches_host(host):
            PLACE_LOGGER.debug(
                f"{shulker_box.name} is not intended for linking to this host ({host})"
            )
            continue
        shulker_boxes.append(shulker_box)

    skip_boxes: list[ShulkerBox] = []

    def handle_error(shulker_box: ShulkerBox | None) -> str:
        """Centralized error-handling

        Parameters
        ----------
        shulker_box:
            The current shulker box (in case it needs to be added to the skip list)

        Returns
        -------
        str
            Instructions on what to do next. Options are:
              - retry
              - return
              - break
              - continue
              - pass
        """
        if error_handling == "prompt":
            proceed_how = (
                prompt(
                    "How would you like to proceed?"
                    "\n[Q]uit; [R]etry; [C]ontinue; skip linking the rest of this:"
                    "\n[I]nstance, [S]hulker box, shulker/instance [M]atch?",
                    suggestion="R",
                )
                .lower()
                .replace(" ", "")
                .replace("-", "")
                .replace("_", "")
            )
            match proceed_how:
                case "" | "r":
                    proceed_how = "retry"
                case "" | "i" | "instance" | "skipinstance":
                    proceed_how = "skip-instance"
                case "q" | "quit" | "abort" | "exit" | "stop":
                    proceed_how = "abort"
                case "c" | "continue" | "ignore":
                    proceed_how = "ignore"
                case "m" | "match" | "skip":
                    proceed_how = "skip"
                case "s" | "shulker" | "shulkerbox" | "skipshulker":
                    proceed_how = "skip-shulker"
                case _:
                    PLACE_LOGGER.error("Invalid selection.")
                    return handle_error(shulker_box)
        else:
            proceed_how = error_handling

        match proceed_how:
            case "retry":
                return "retry"
            case "abort" | "stop" | "quit" | "exit":
                PLACE_LOGGER.error("Aborting")
                return "return"
            case "ignore":
                PLACE_LOGGER.debug("Ignoring")
                return "pass"
            case "skip":
                PLACE_LOGGER.warning("Skipping the rest of this match")
                return "continue"
            case "skip-instance":
                PLACE_LOGGER.warning("Skipping any more linking from this instance")

                return "break"
            case "skip-shulker-box" | "skip-shulkerbox" | "skip-shulker":
                PLACE_LOGGER.warning("Skipping any more linking into this shulker box")
                if shulker_box:
                    skip_boxes.append(shulker_box)
                return "continue"
            case _:
                raise ValueError(
                    f"Unrecognized error-handling method: {error_handling}"
                )

    for instance in instances:
        instance_root = (minecraft_root / instance.root.expanduser()).expanduser()
        placements[instance.name] = defaultdict(list)

        handling: str | None = "retry"
        while handling == "retry":
            if instance_root.exists():
                handling = None
                break

            PLACE_LOGGER.error(
                "No minecraft instance exists at"
                f" {instance_root.expanduser().absolute()}"
            )
            handling = handle_error(None)
        if handling is not None:
            match handling:
                case "return":
                    return {}  # intentionally wipe the cache
                case "break":
                    break
                case _:  # nothing to link, so might as well skip the rest
                    continue

        # start by removing all existing symlinks into the EnderChest
        if not keep_stale_links:
            for file in instance_root.rglob("*"):
                if file.is_symlink():
                    if fs.links_into_enderchest(minecraft_root, file):
                        PLACE_LOGGER.debug(
                            f"Removing old link: {file} -> {os.readlink(file)}"
                        )
                        file.unlink()

        for shulker_box in shulker_boxes:
            if not shulker_box.matches(instance):
                continue
            if shulker_box in skip_boxes:
                continue

            box_root = shulker_box.root.expanduser().absolute()

            PLACE_LOGGER.info(f"Linking {instance.root} to {shulker_box.name}")

            resources = set(_rglob(box_root, shulker_box.max_link_depth))

            match_exit = "pass"
            for link_folder in shulker_box.link_folders:
                resources -= {box_root / link_folder}
                resources -= set((box_root / link_folder).rglob("*"))

                handling = "retry"
                while handling == "retry":
                    try:
                        link_resource(link_folder, box_root, instance_root, relative)
                        placements[instance.name][Path(link_folder)].append(
                            shulker_box.name
                        )
                        handling = None
                    except OSError:
                        PLACE_LOGGER.error(
                            f"Error linking shulker box {shulker_box.name}"
                            f" to instance {instance.name}:"
                            f"\n  {(instance.root / link_folder)} is a"
                            " non-empty directory"
                        )
                        handling = handle_error(shulker_box)
                if handling is not None:
                    match handling:
                        case "return":
                            return placements
                        case "break":
                            match_exit = "break"
                            break
                        case "continue":
                            match_exit = "continue"
                            break
                        case "pass":
                            continue  # or pass--it's the end of the loop

            if match_exit not in ("break", "continue"):
                for resource in resources:
                    resource_path = resource.relative_to(box_root)
                    for pattern in shulker_box.do_not_link:
                        if fnmatch.fnmatchcase(
                            str(resource_path), pattern
                        ) or fnmatch.fnmatchcase(
                            str(resource_path), os.path.join("*", pattern)
                        ):
                            PLACE_LOGGER.debug(
                                "Skipping %s (matches pattern %s)",
                                resource_path,
                                pattern,
                            )
                            break
                    else:
                        handling = "retry"
                        while handling == "retry":
                            try:
                                link_resource(
                                    resource_path,
                                    box_root,
                                    instance_root,
                                    relative,
                                )
                                placements[instance.name][resource_path].append(
                                    shulker_box.name
                                )
                                handling = None
                            except OSError:
                                PLACE_LOGGER.error(
                                    f"Error linking shulker box {shulker_box.name}"
                                    f" to instance {instance.name}:"
                                    f"\n  {(instance.root / resource_path)}"
                                    " already exists"
                                )
                                handling = handle_error(shulker_box)
                        if handling is not None:
                            match handling:
                                case "return":
                                    return placements
                                case "break":
                                    match_exit = "break"
                                    break
                                case "continue":
                                    match_exit = "continue"  # technically does nothing
                                    break
                                case "pass":
                                    continue  # or pass--it's the end of the loop

            # consider this a "finally"
            if not keep_broken_links:
                # we clean up as we go, just in case of a failure
                for file in instance_root.rglob("*"):
                    if not file.exists():
                        PLACE_LOGGER.debug(f"Removing broken link: {file}")
                        file.unlink()

            if match_exit == "break":
                break
    return placements


def link_resource(
    resource_path: str | Path,
    shulker_root: Path,
    instance_root: Path,
    relative: bool,
) -> None:
    """Create a symlink for the specified resource from an instance's space
    pointing to the tagged file / folder living inside a shulker box.

    Parameters
    ----------
    resource_path : str or Path
        Location of the resource relative to the instance's ".minecraft" folder
    shulker_root : Path
        The path to the shulker box
    instance_root : Path
        The path to the instance's ".minecraft" folder
    relative : bool
        If True, the link will be use a relative path if possible. Otherwise,
        an absolute path will be used, regardless of whether a relative or
        absolute path was provided.

    Raises
    ------
    OSError
        If a file or non-empty directory already exists where you're attempting
        to place the symlink

    Notes
    -----
    - This method will create any folders that do not exist within an instance
    - This method will overwrite existing symlinks and empty folders
      but will not overwrite or delete any actual files.
    """
    instance_path = (instance_root / resource_path).expanduser().absolute()
    instance_path.parent.mkdir(parents=True, exist_ok=True)

    target: str | Path = (shulker_root / resource_path).expanduser().absolute()
    if relative:
        target = os.path.relpath(target, instance_path.parent)
    else:
        target = target.resolve()  # type: ignore

    if instance_path.is_symlink():
        # remove previous symlink in this spot
        instance_path.unlink()
        PLACE_LOGGER.debug("Removed previous link at %s", instance_path)
    else:
        try:
            os.rmdir(instance_path)
            PLACE_LOGGER.debug("Removed empty directory at %s", instance_path)
        except FileNotFoundError:
            pass  # A-OK

    PLACE_LOGGER.debug("Linking %s to %s", instance_path, target)
    os.symlink(
        target,
        instance_path,
        target_is_directory=(shulker_root / resource_path).is_dir(),
    )


def _rglob(root: Path, max_depth: int) -> Iterable[Path]:
    """Find all files (and directories* and symlinks) in the path up to the
    specified depth

    Parameters
    ----------
    root : Path
        The path to search
    max_depth : int
        The maximum number of levels to go

    Returns
    -------
    list-like of paths
        The files (and directories and symlinks) in the path up to that depth

    Notes
    -----
    - Unlike an actual rglob, this method does not return any directories that
      are not at the maximum depth
    - Setting max_depth to 0 (or below) will return all files in the root, but
      ***be warned*** that because this method follows symlinks, you can very
      easily find yourself in an infinite loop
    """
    top_level = root.iterdir()
    if max_depth == 1:
        return top_level
    return itertools.chain(
        *(
            _rglob(path, max_depth - 1) if path.is_dir() else (path,)
            for path in top_level
        )
    )


def cache_placements(
    minecraft_root: Path, placements: dict[str, dict[Path, list[str]]]
) -> None:
    """Write placement record to file

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    placements : dict
        A record of placed links, as generated by `place_ender_chest`
    """
    cache_file = fs.place_cache(minecraft_root)
    cache_file.write_text(
        json.dumps(
            {
                instance_name: {
                    str(resource_path): shulker_boxes
                    for resource_path, shulker_boxes in instance_placements.items()
                }
                for instance_name, instance_placements in placements.items()
            },
            indent=4,
            sort_keys=False,
        )
    )
    PLACE_LOGGER.debug("Placement cache written to %s", cache_file)


def load_placement_cache(minecraft_root: Path) -> dict[str, dict[Path, list[str]]]:
    """Load the placement cache from file

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)

    Returns
    -------
    dict
        A record of the placed symlinks, structured as a nested dict, matching
        the schema of one generated by `place_ender_chest`

        Raises
    ------
    OSError
        If the placement cache could not be found, read or parsed
    """
    try:
        cache_file = fs.place_cache(minecraft_root)
        GATHER_LOGGER.debug(
            "Loading placement cache from %s", fs.place_cache(minecraft_root)
        )
        raw_dict: dict[str, dict[str, list[str]]] = json.loads(
            cache_file.read_text("UTF-8")
        )
    except json.JSONDecodeError as decode_error:
        raise OSError(
            f"{fs.place_cache(minecraft_root)} is corrupted and could not be parsed:"
        ) from decode_error
    return {
        instance_name: {
            Path(resource_path): shulker_boxes
            for resource_path, shulker_boxes in instance_placements.items()
        }
        for instance_name, instance_placements in raw_dict.items()
    }


def trace_resource(
    minecraft_root: Path,
    pattern: str,
    placements: dict[str, dict[Path, list[str]]],
    instance_name: str | None = None,
) -> list[tuple[Path, Path, list[str]]]:
    """Given a filename or glob pattern, return a list of all matching
    EnderChest-placed symlinks, together with a trace-back of the shulker boxes
    each link targets

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    pattern : filename, path or glob pattern
        The resource to trace
    placements : dict
        A record of placed symlinks, such as the one generated by `place_ender_chest`.
    instance_name : str, optional
        The name of the instance to search. This variable is case-sensitive.
        If None is given, all instances will be searched.

    Returns
    -------
    list of (Path, Path, list) tuples
        - The first item in each list is the path of the instance root
        - The second item in each list is the path to a linked resource
          matching the provided pattern (and instance), relative to the instance
          root
        - The third item is the list of shulker boxes, sorted in ascending
          priority, into which that symlink was linked (explicitly, the
          _last_ entry in each list corresponds to the shulker box inside
          which that link currently points)

    Raises
    ------
    OSError
        If no placement cache was provided and the placement cache file could
        not be found, read or parsed
    KeyError
        If there is no instance registered to this EnderChest with the specified
        name
    """
    instances = {
        instance.name: instance
        for instance in load_ender_chest_instances(
            minecraft_root, log_level=logging.DEBUG
        )
    }
    if instance_name is None:
        return sum(
            (
                trace_resource(minecraft_root, pattern, placements, name)
                for name in instances
            ),
            [],
        )
    instance_root = instances[instance_name].root
    matches: list[tuple[Path, Path, list[str]]] = []
    for resource_path, target_boxes in placements[instance_name].items():
        if (
            fnmatch.fnmatchcase(str(resource_path), pattern)
            or fnmatch.fnmatchcase(str(resource_path), os.path.join("*", pattern))
            or fnmatch.fnmatchcase(
                os.path.abspath(minecraft_root / instance_root / resource_path),
                os.path.join("*", pattern),
            )
        ):
            matches.append((instance_root, resource_path, target_boxes))
    return matches


def report_resource_trace(
    minecraft_root: Path, instance_root: Path, resource_path: Path, boxes: Sequence[str]
) -> None:
    """Print (log) the shulker boxes an instance resource is linked to

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    instance_root : Path
        The path of the EnderChest-placed symlink
    resource_path : Path
        The path to the symlink, relative to the instance root
    boxes : list of str
        The names of the shulker boxes, sorted by ascending priority, that are
        targeted by this symlink (technically only the last entry in this list
        is the actual target)
    """
    symlink_location = instance_root / resource_path
    if len(boxes) == 0:  # pragma: no cover
        # Since defaultdicts are involved, this could happen accidentally at
        # some point and should just be ignored
        return
    *other_box_names, primary_box_name = boxes
    try:
        GATHER_LOGGER.log(
            IMPORTANT,
            "%s currently resolves to %s",
            symlink_location,
            os.path.abspath(
                (
                    symlink_location / (minecraft_root / symlink_location).readlink()
                ).expanduser()
            ),
        )
    except OSError:
        GATHER_LOGGER.warning(
            "%s no longer exists or is not a symlink", symlink_location
        )

    GATHER_LOGGER.log(
        IMPORTANT,
        "    based on being linked into shulker box: %s",
        primary_box_name,
    )
    GATHER_LOGGER.debug(
        "        - > %s",
        fs.shulker_box_root(minecraft_root, primary_box_name) / resource_path,
    )

    for box_name in reversed(other_box_names):
        GATHER_LOGGER.info(
            "    which overwrote the link into shulker box: %s", box_name
        )
        GATHER_LOGGER.debug(
            "        - > %s",
            fs.shulker_box_root(minecraft_root, box_name) / resource_path,
        )


def list_placements(
    minecraft_root: Path, pattern: str, instance_name: str | None = None
) -> None:
    """Report all shulker boxes that provide files matching the given pattern

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    pattern : filename, path or glob pattern
        The pattern of the resource to trace
    instance_name : str, optional
        The name of the instance to search. This variable is case-sensitive.
        If None is given, all instances will be searched.
    """
    try:
        placements = load_placement_cache(minecraft_root)
    except OSError as no_cache:
        GATHER_LOGGER.error(
            "The placement cache could not be loaded:"
            "\n  %s"
            "\nPlease run enderchest place again to regenerate the cache.",
            no_cache,
        )
        return
    try:
        matches = trace_resource(
            minecraft_root, pattern, placements, instance_name=instance_name
        )
    except KeyError:
        GATHER_LOGGER.error(
            "No instance named %s is registered to this EnderChest", instance_name
        )
        return
    if len(matches) == 0:
        GATHER_LOGGER.warning(
            "Could not find any placed resources matching the pattern %s%s."
            "\n\nNote: this command does not check inside linked folders.",
            pattern,
            f"\nin the instance {instance_name}" if instance_name else "",
        )
        return
    for match in matches:
        report_resource_trace(minecraft_root, *match)
