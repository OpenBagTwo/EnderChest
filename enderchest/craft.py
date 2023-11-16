"""Functionality for setting up the folder structure of both chests and shulker boxes"""
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable, Sequence
from urllib.parse import ParseResult

from pathvalidate import is_valid_filename

from . import filesystem as fs
from . import sync
from .enderchest import EnderChest, create_ender_chest
from .gather import (
    _report_shulker_boxes,
    gather_minecraft_instances,
    load_ender_chest,
    load_ender_chest_instances,
    load_ender_chest_remotes,
    load_shulker_boxes,
)
from .instance import InstanceSpec, normalize_modloader
from .loggers import CRAFT_LOGGER
from .prompt import NO, YES, confirm, prompt
from .remote import fetch_remotes_from_a_remote_ender_chest
from .shulker_box import ShulkerBox, create_shulker_box


def craft_ender_chest(
    minecraft_root: Path,
    copy_from: str | ParseResult | None = None,
    instance_search_paths: Iterable[str | Path] | None = None,
    remotes: Iterable[str | ParseResult | tuple[str, str] | tuple[ParseResult, str]]
    | None = None,
    overwrite: bool = False,
) -> None:
    """Craft an EnderChest, either from the specified keyword arguments, or
    interactively via prompts

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff is in (or, at least, the
        one inside which you want to create your EnderChest)
    copy_from : URI, optional
        Optionally bootstrap your configuration by pulling the list of remotes
        from an existing remote EnderChest
    instance_search_paths : list of Paths, optional
        Any paths to search for Minecraft instances
    remotes : list of URIs or (URI, str) tuples, optional
        Any remotes you wish you manually specify. If used with `copy_from`, these
        will overwrite any remotes pulled from the remote EnderChest. When a
        (URI, str) tuple is provided, the second value will be used as the
        name/alias of the remote.
    overwrite : bool, optional
        This method will not overwrite an EnderChest instance installed within
        the `minecraft_root` unless the user provides `overwrite=True`

    Notes
    -----
    - The guided / interactive specifier will only be used if no other keyword
      arguments are provided (not even `overwrite=True`)
    - The instance searcher will first attempt to parse any instances it finds
      as official-launcher Minecrafts and then, if that doesn't work, will try
      parsing them as MultiMC-style instances.
    - The instance searcher is fully recursive, so keep that in mind before
      passing in, say "/"
    """
    if not minecraft_root.exists():
        CRAFT_LOGGER.error(f"The directory {minecraft_root} does not exist")
        CRAFT_LOGGER.error("Aborting")
        return
    if (
        copy_from is None
        and instance_search_paths is None
        and remotes is None
        and not overwrite
    ):
        # then we go interactive
        try:
            ender_chest = specify_ender_chest_from_prompt(minecraft_root)
        except (FileExistsError, RuntimeError):
            CRAFT_LOGGER.error("Aborting")
            return
    else:
        try:
            fs.ender_chest_config(minecraft_root, check_exists=True)
            exist_message = (
                f"There is already an EnderChest installed to {minecraft_root}"
            )
            if overwrite:
                CRAFT_LOGGER.warning(exist_message)
            else:
                CRAFT_LOGGER.error(exist_message)
                CRAFT_LOGGER.error("Aborting")
                return
        except FileNotFoundError:
            pass  # no existing chest? no problem!

        ender_chest = EnderChest(minecraft_root)

        for search_path in instance_search_paths or ():
            for instance in gather_minecraft_instances(
                minecraft_root, Path(search_path), None
            ):
                ender_chest.register_instance(instance)

        if copy_from:
            try:
                for remote, alias in fetch_remotes_from_a_remote_ender_chest(copy_from):
                    if alias == ender_chest.name:
                        continue  # don't register yourself!
                    ender_chest.register_remote(remote, alias)
            except (RuntimeError, ValueError) as fetch_fail:
                CRAFT_LOGGER.error(
                    f"Could not fetch remotes from {copy_from}:\n  {fetch_fail}"
                )
                CRAFT_LOGGER.error("Aborting.")
                return

        for extra_remote in remotes or ():
            if isinstance(extra_remote, (str, ParseResult)):
                ender_chest.register_remote(extra_remote)
            else:
                ender_chest.register_remote(*extra_remote)

    create_ender_chest(minecraft_root, ender_chest)
    CRAFT_LOGGER.info(
        "\nNow craft some shulker boxes via\n$ enderchest craft shulker_box\n"
    )


def craft_shulker_box(
    minecraft_root: Path,
    name: str,
    priority: int | None = None,
    link_folders: Sequence[str] | None = None,
    instances: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
    hosts: Sequence[str] | None = None,
    overwrite: bool = False,
):
    """Craft a shulker box, either from the specified keyword arguments, or
    interactively via prompts

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    name : str
        A name to give to this shulker box
    priority : int, optional
        The priority for linking assets in the shulker box (higher priority
        shulkers are linked last)
    link_folders : list of str, optional
        The folders that should be linked in their entirety
    instances : list of str, optional
        The names of the instances you'd like to link to this shulker box
    tags : list of str, optional
        You can instead (see notes) provide a list of tags where any instances
        with those tags will be linked to this shulker box
    hosts : list of str, optional
        The EnderChest installations that this shulker box should be applied to
    overwrite : bool, optional
        This method will not overwrite an existing shulker box unless the user
        provides `overwrite=True`

    Notes
    -----
    - The guided / interactive specifier will only be used if no other keyword
      arguments are provided (not even `overwrite=True`)
    - The conditions specified by instances, tags and hosts are ANDed
      together--that is, if an instance is listed explicitly, but it doesn't
      match a provided tag, it will not link to this shulker box
    - Wildcards are supported for instances, tags and hosts (but not link-folders)
    - Not specifying instances, tags or hosts is equivalent to providing `["*"]`
    - When values are provided to the keyword arguments, no validation is performed
      to ensure that they are valid or actively in use
    """
    if not is_valid_filename(name):
        CRAFT_LOGGER.error(f"{name} is not a valid name: must be usable as a filename")
        return

    try:
        folders = load_ender_chest(minecraft_root).shulker_box_folders
        if (
            priority is None
            and link_folders is None
            and instances is None
            and tags is None
            and hosts is None
            and not overwrite
        ):
            try:
                shulker_box = specify_shulker_box_from_prompt(minecraft_root, name)
            except FileExistsError as seat_taken:
                CRAFT_LOGGER.error(seat_taken)
                CRAFT_LOGGER.error("Aborting")
                return
        else:
            config_path = fs.shulker_box_config(minecraft_root, name)
            if config_path.exists():
                exist_message = (
                    f"There is already a shulker box named {name}"
                    f" in {fs.ender_chest_folder(minecraft_root)}"
                )
                if overwrite:
                    CRAFT_LOGGER.warning(exist_message)
                else:
                    CRAFT_LOGGER.error(exist_message)
                    CRAFT_LOGGER.error("Aborting")
                    return
            match_criteria: list[tuple[str, tuple[str, ...]]] = []
            if instances is not None:
                match_criteria.append(("instances", tuple(instances)))
            if tags is not None:
                match_criteria.append(("tags", tuple(tags)))
            if hosts is not None:
                match_criteria.append(("hosts", tuple(hosts)))
            shulker_box = ShulkerBox(
                priority=priority or 0,
                name=name,
                root=minecraft_root,
                match_criteria=tuple(match_criteria),
                link_folders=tuple(link_folders or ()),
            )
    except FileNotFoundError as no_ender_chest:
        CRAFT_LOGGER.error(no_ender_chest)
        return

    create_shulker_box(minecraft_root, shulker_box, folders)


def specify_ender_chest_from_prompt(minecraft_root: Path) -> EnderChest:
    """Parse an EnderChest based on interactive user input

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff is in (or, at least, the
        one inside which you want to create your EnderChest)

    Returns
    -------
    EnderChest
        The resulting EnderChest
    """
    try:
        root = fs.ender_chest_folder(minecraft_root)
        CRAFT_LOGGER.info(
            f"This will overwrite the EnderChest configuration at {root}."
        )
        if not confirm(default=False):
            message = f"Aborting: {fs.ender_chest_config(minecraft_root)} exists."
            raise FileExistsError(message)
    except FileNotFoundError:
        # good! Then we don't already have an EnderChest here
        CRAFT_LOGGER.debug(f"{minecraft_root} does not already contain an EnderChest")

    instances: list[InstanceSpec] = []

    while True:
        search_home = prompt(
            "Would you like to search your home directory for the official launcher?",
            suggestion="Y/n",
        ).lower()
        if search_home == "" or search_home in YES:
            instances.extend(
                gather_minecraft_instances(minecraft_root, Path.home(), official=True)
            )
        elif search_home not in NO:
            continue
        break

    while True:
        search_here = prompt(
            "Would you like to search the current directory for MultiMC-type instances?",
            suggestion="Y/n",
        ).lower()
        if search_here == "" or search_here in YES:
            instances.extend(
                gather_minecraft_instances(minecraft_root, Path(), official=False)
            )
        elif search_here not in NO:
            continue
        break

    if minecraft_root.absolute() != Path().absolute():
        while True:
            search_mc_folder = prompt(
                f"Would you like to search {minecraft_root} for MultiMC-type instances?",
                suggestion="Y/n",
            ).lower()
            if search_mc_folder == "" or search_here in YES:
                instances.extend(
                    gather_minecraft_instances(
                        minecraft_root, minecraft_root, official=False
                    )
                )
            elif search_mc_folder not in NO:
                continue
            break

    CRAFT_LOGGER.info(
        "\nYou can always add more instances later using"
        "\n$ enderchest gather minecraft\n"
    )

    while True:
        remotes: list[tuple[ParseResult, str]] = []
        remote_uri = prompt(
            "Would you like to grab the list of remotes from another EnderChest?"
            "\nIf so, enter the URI of that EnderChest now (leave empty to skip)."
        )
        if remote_uri == "":
            break
        try:
            remotes.extend(fetch_remotes_from_a_remote_ender_chest(remote_uri))
        except Exception as fetch_fail:
            CRAFT_LOGGER.error(
                f"Could not fetch remotes from {remote_uri}\n  {fetch_fail}"
            )
            if not confirm(default=True):
                continue
        break

    CRAFT_LOGGER.info(
        "\nYou can always add more remotes later using"
        "\n$ enderchest gather enderchest\n"
    )

    while True:
        protocol = (
            prompt(
                (
                    "Specify the method for syncing with this EnderChest."
                    "\nSupported protocols are: " + ", ".join(sync.SUPPORTED_PROTOCOLS)
                ),
                suggestion=sync.DEFAULT_PROTOCOL,
            ).lower()
            or sync.DEFAULT_PROTOCOL
        )

        if protocol not in sync.SUPPORTED_PROTOCOLS:
            CRAFT_LOGGER.error("Unsupported protocol\n")
            continue
        break

    while True:
        default_netloc = sync.get_default_netloc()
        netloc = (
            prompt(
                (
                    "What's the address for accessing this machine?"
                    "\n(hostname or IP address, plus often a username)"
                ),
                suggestion=default_netloc,
            )
            or default_netloc
        )

        uri = ParseResult(
            scheme=protocol,
            netloc=netloc,
            path=minecraft_root.as_posix(),
            params="",
            query="",
            fragment="",
        )
        if not uri.hostname:
            CRAFT_LOGGER.error("Invalid hostname")
            continue
        break

    while True:
        name = (
            prompt("Provide a name for this EnderChest", suggestion=uri.hostname)
            or uri.hostname
        )
        if name in (alias for _, alias in remotes):
            CRAFT_LOGGER.error(
                f"The name {name} is already in use. Choose a different name."
            )
            continue
        break

    ender_chest = EnderChest(uri, name, remotes, instances)

    CRAFT_LOGGER.info(
        "\n%s\nPreparing to generate an EnderChest with the above configuration.",
        ender_chest.write_to_cfg(),
    )

    if not confirm(default=True):
        raise RuntimeError("EnderChest creation aborted.")

    return ender_chest


def specify_shulker_box_from_prompt(minecraft_root: Path, name: str) -> ShulkerBox:
    """Parse a shulker box based on interactive user input

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    name : str
        The name to give to the shulker box

    Returns
    -------
    ShulkerBox
        The resulting ShulkerBox
    """
    ender_chest = load_ender_chest(minecraft_root)
    shulker_root = fs.shulker_box_root(minecraft_root, name)
    if shulker_root in shulker_root.parent.iterdir():
        if not shulker_root.is_dir():
            raise FileExistsError(
                f"A file named {name} already exists in your EnderChest folder."
            )
        CRAFT_LOGGER.warning(
            f"There is already a folder named {name} in your EnderChest folder."
        )
        if not confirm(default=False):
            raise FileExistsError(
                f"There is already a folder named {name} in your EnderChest folder."
            )

    shulker_box = ShulkerBox(0, name, shulker_root, (), ())

    def refresh_ender_chest_instance_list() -> Sequence[InstanceSpec]:
        """The primary reason to lambda-fy this is to re-print the instance list."""
        return load_ender_chest_instances(minecraft_root)

    instances = refresh_ender_chest_instance_list()

    explicit_type = "name"
    if len(instances) > 0:
        explicit_type = "number"
    while True:
        selection_type = prompt(
            f"Would you like to specify instances by [F]ilter or by [N]{explicit_type[1:]}?"
        ).lower()
        match selection_type:
            case "f" | "filter":
                shulker_box = _prompt_for_filters(shulker_box, instances)
            case "n":
                if explicit_type == "name":
                    shulker_box = _prompt_for_instance_names(shulker_box)
                else:  # if explicit_type == "number"
                    shulker_box = _prompt_for_instance_numbers(
                        shulker_box, instances, refresh_ender_chest_instance_list
                    )
            case "name":
                # yeah, this is always available
                shulker_box = _prompt_for_instance_names(shulker_box)
            case "number":
                if explicit_type == "name":
                    continue
                shulker_box = _prompt_for_instance_numbers(
                    shulker_box, instances, refresh_ender_chest_instance_list
                )
            case _:
                continue
        break

    while True:
        selection_type = prompt(
            "Folders to Link?"
            "\nThe [G]lobal set is:"
            f' {", ".join(ender_chest.global_link_folders) or "(none)"}'
            "\nThe [S]tandard set is:"
            f' {", ".join(ender_chest.standard_link_folders) or "(none)"}'
            "\nYou can also choose [N]one or to [M]anually specify the folders to link",
            suggestion="S",
        ).lower()
        match selection_type:
            case "n" | "none":
                link_folders: tuple[str, ...] = ()
            case "g" | "global" | "global set":
                link_folders = tuple(ender_chest.global_link_folders)
            case "s" | "standard" | "standard set" | "":
                link_folders = tuple(ender_chest.standard_link_folders)
            case "m" | "manual" | "manually specify":
                folder_choices = prompt(
                    "Specify the folders to link using a comma-separated list"
                    " (wildcards are not allowed)"
                )
                link_folders = tuple(
                    folder.strip() for folder in folder_choices.split(",")
                )
            case _:
                continue
        break

    while True:
        # this is such a kludge
        existing_shulker_boxes = load_shulker_boxes(
            minecraft_root, log_level=logging.DEBUG
        )
        if existing_shulker_boxes:
            _report_shulker_boxes(
                existing_shulker_boxes, logging.INFO, "the current EnderChest"
            )

        value = (
            prompt(
                (
                    "What priority value should be assigned to this shulker box?"
                    "\nhigher number = applied later"
                ),
                suggestion="0",
            )
            or "0"
        )
        try:
            priority = int(value)
        except ValueError:
            continue
        break

    while True:
        _ = load_ender_chest_remotes(minecraft_root)  # to display some log messages
        values = (
            prompt(
                (
                    "What hosts (EnderChest installations) should use this shulker box?"
                    "\nProvide a comma-separated list (wildcards are allowed)"
                    "\nand remember to include the name of this EnderChest"
                    f' ("{ender_chest.name}")'
                ),
                suggestion="*",
            )
            or "*"
        )
        hosts = tuple(host.strip() for host in values.split(","))

        host = ender_chest.name

        if not shulker_box._replace(match_criteria=(("hosts", hosts),)).matches_host(
            host
        ):
            CRAFT_LOGGER.warning(
                "This shulker box will not link to any instances on this machine"
            )
            if not confirm(default=False):
                continue
        break

    shulker_box = shulker_box._replace(
        priority=priority,
        match_criteria=shulker_box.match_criteria + (("hosts", hosts),),
        link_folders=link_folders,
    )

    CRAFT_LOGGER.info(
        "\n%sPreparing to generate a shulker box with the above configuration.",
        shulker_box.write_to_cfg(),
    )

    if not confirm(default=True):
        raise RuntimeError("Shulker box creation aborted.")

    return shulker_box


def _prompt_for_filters(
    shulker_box: ShulkerBox, instances: Sequence[InstanceSpec]
) -> ShulkerBox:
    """Prompt the user for a ShulkerBox spec by filters

    Parameters
    ----------
    shulker_box : ShulkerBox
        The starting ShulkerBox (with no match critera)
    instances : list of InstanceSpec
       The list of instances registered to the EnderChest

    Returns
    -------
    ShulkerBox
        The updated shulker box (with filter-based match criteria)

    Notes
    -----
    When instances is non-empty, the prompt will check in with the user at
    each step to make sure that the specified filters are filtering as intended.
    If that list is empty (or at the point that the user has filtered down to
    an empty list) then the user's gonna be flying blind.
    """

    def check_progress(
        new_condition: str, values: Iterable[str]
    ) -> tuple[ShulkerBox | None, list[str]]:
        """As we add new conditions, report to the user the list of instances
        that this shulker will match and confirm with them that they want
        to continue.

        Parameters
        ----------
        new_condition : str
            The type of condition being added
        values : list-like of str
           The values for the new condition

        Returns
        -------
        ShulkerBox or None
            If the user confirms that things look good, this will return the
            shulker box, updated with the new condition. Otherwise, the first
            returned value will be None
        list of str
            The names of the instances matching the updated set of filters

        Notes
        -----
        If instances is empty, then this method won't check in with the user
        and will just return the updated shulker box.
        """
        tester = shulker_box._replace(
            match_criteria=shulker_box.match_criteria
            + ((new_condition, tuple(values)),)
        )

        if len(instances) == 0:
            return tester, []

        matches = [instance.name for instance in instances if tester.matches(instance)]

        default = True
        if len(matches) == 0:
            CRAFT_LOGGER.warning("Filters do not match any known instance.")
            default = False
        elif len(matches) == 1:
            CRAFT_LOGGER.info(f"Filters match the instance: {matches[0]}")
        else:
            CRAFT_LOGGER.info(
                "Filters match the instances:\n%s",
                "\n".join([f"  - {name}" for name in matches]),
            )
        return tester if confirm(default=default) else None, matches

    while True:
        version_spec = (
            prompt(
                (
                    "Minecraft versions:"
                    ' (e.g: "*", "1.19.1, 1.19.2, 1.19.3", "1.19.*", ">=1.19.0,<1.20")'
                ),
                suggestion="*",
            )
            or "*"
        )

        updated, matches = check_progress(
            "minecraft", (version.strip() for version in version_spec.split(", "))
        )
        if updated:
            shulker_box = updated
            instances = [instance for instance in instances if instance.name in matches]
            break

    while True:
        modloader = (
            prompt(
                (
                    "Modloader?"
                    "\n[N]one, For[G]e, Fa[B]ric, [Q]uilt, [L]iteLoader"
                    ' (or multiple, e.g: "B,Q", or any using "*")'
                ),
                suggestion="*",
            )
            or "*"
        )

        modloaders: set[str] = set()
        for entry in modloader.split(","):
            match entry.strip().lower():
                case "" | "n" | "none" | "vanilla":
                    modloaders.update(normalize_modloader(None))
                case "g" | "forge":
                    modloaders.update(normalize_modloader("Forge"))
                case "b" | "fabric" | "fabric loader":
                    modloaders.update(normalize_modloader("Fabric Loader"))
                case "q" | "quilt":
                    modloaders.update(normalize_modloader("Quilt Loader"))
                case "l" | "liteloader":
                    modloaders.update(normalize_modloader("LiteLoader"))
                case _:
                    modloaders.update(normalize_modloader(entry))

        updated, matches = check_progress("modloader", sorted(modloaders))
        if updated:
            shulker_box = updated
            instances = [instance for instance in instances if instance.name in matches]
            break

    while True:
        tag_count = Counter(sum((instance.tags for instance in instances), ()))
        # TODO: should this be most common among matches?
        example_tags: list[str] = [tag for tag, _ in tag_count.most_common(5)]
        CRAFT_LOGGER.debug(
            "Tag counts:\n%s",
            "\n".join(f"  - {tag}: {count}" for tag, count in tag_count.items()),
        )

        if len(example_tags) == 0:
            # provide examples if the user isn't using tags
            example_tags = [
                "vanilla-plus",
                "multiplayer",
                "modded",
                "dev",
                "april-fools",
            ]

        tags = (
            prompt(
                "Tags?"
                f'\ne.g.{", ".join(example_tags)}'
                "\n(or multiple using comma-separated lists or wildcards)"
                "\nNote: tag-matching is not case-sensitive.",
                suggestion="*",
            )
            or "*"
        )

        updated, matches = check_progress(
            "tags", (tag.strip() for tag in tags.split(","))
        )
        if updated:
            shulker_box = updated
            instances = [instance for instance in instances if instance.name in matches]
            break

    return shulker_box


def _prompt_for_instance_names(shulker_box: ShulkerBox) -> ShulkerBox:
    """Prompt a user for the names of specific instances, then add that list
    to the shulker box spec.

    Parameters
    ----------
    shulker_box : ShulkerBox
        The starting ShulkerBox, presumably with limited or no match criteria

    Returns
    -------
    ShulkerBox
        The updated shulker box (with explicit criteria based on instance names)

    Notes
    -----
    This method does not validate against lists of known instances
    """
    instances = tuple(
        entry.strip()
        for entry in prompt(
            "Specify instances by name, separated by commas."
            "\nYou can also use wildcards (? and *)",
            suggestion="*",
        ).split(",")
    )
    if instances == ("",):
        instances = ("*",)

    if instances == ("*",):
        CRAFT_LOGGER.warning(
            "This shulker box will be applied to all instances,"
            " including ones you create in the future."
        )
        default = False
    else:
        CRAFT_LOGGER.info(
            "You specified the following instances:\n%s",
            "\n".join([f"  - {name}" for name in instances]),
        )
        default = True

    if not confirm(default=default):
        CRAFT_LOGGER.debug("Trying again to prompt for instance names")
        return _prompt_for_instance_names(shulker_box)

    return shulker_box._replace(
        match_criteria=shulker_box.match_criteria + (("instances", instances),)
    )


def _prompt_for_instance_numbers(
    shulker_box: ShulkerBox,
    instances: Sequence[InstanceSpec],
    instance_loader: Callable[[], Sequence[InstanceSpec]],
) -> ShulkerBox:
    """Prompt the user to specify the instances they'd like by number

    Parameters
    ----------
    shulker_box : ShulkerBox
        The starting ShulkerBox, presumably with limited or no match criteria
    instances : list of InstanceSpec
       The list of instances registered to the EnderChest
    instance_loader : method that returns a list of InstanceSpec
        A method that when called, prints and returns a refreshed list of instances
        registered to the EnderChest

    Returns
    -------
    ShulkerBox
        The updated shulker box (with explicit criteria based on instance names)
    """
    selections = prompt(
        (
            "Which instances would you like to include?"
            '\ne.g. "1,2,3", "1-3", "1-6" or "*" to specify all'
        ),
        suggestion="*",
    )
    selections = re.sub("/s", " ", selections)  # normalize whitespace
    if selections == "":
        selections = "*"

    if re.search("[^0-9-,* ]", selections):  # check for invalid characters
        CRAFT_LOGGER.error("Invalid selection\n")
        return _prompt_for_instance_numbers(
            shulker_box, instance_loader(), instance_loader
        )

    selected_instances: set[str] = set()
    for entry in selections.split(","):
        match entry.replace(" ", ""):
            case "*":
                selected_instances.update(instance.name for instance in instances)
                break  # because it's not like there's any that can be added
            case value if value.isdigit():
                # luckily we don't need to worry about negative numbers
                index = int(value) - 1
                if index < 0 or index >= len(instances):
                    CRAFT_LOGGER.error(f"Invalid selection: {entry} is out of range\n")
                    return _prompt_for_instance_numbers(
                        shulker_box, instance_loader(), instance_loader
                    )
                selected_instances.add(instances[index].name)
            case value if match := re.match("([0-9]+)-([0-9]+)$", value):
                bounds = tuple(int(bound) for bound in match.groups())
                if bounds[0] > bounds[1]:
                    CRAFT_LOGGER.error(
                        f"Invalid selection: {entry} is not a valid range\n"
                    )
                    return _prompt_for_instance_numbers(
                        shulker_box, instance_loader(), instance_loader
                    )
                if max(bounds) > len(instances) or min(bounds) < 1:
                    CRAFT_LOGGER.error(f"Invalid selection: {entry} is out of range\n")
                    return _prompt_for_instance_numbers(
                        shulker_box, instance_loader(), instance_loader
                    )
                selected_instances.update(
                    instance.name for instance in instances[bounds[0] - 1 : bounds[1]]
                )

    choices = tuple(
        instance.name for instance in instances if instance.name in selected_instances
    )

    CRAFT_LOGGER.info(
        "You selected the instances:\n%s",
        "\n".join([f"  - {name}" for name in choices]),
    )
    if not confirm(default=True):
        CRAFT_LOGGER.debug("Trying again to prompt for instance numbers")
        CRAFT_LOGGER.info("")  # just making a newline
        return _prompt_for_instance_numbers(
            shulker_box, instance_loader(), instance_loader
        )

    return shulker_box._replace(
        match_criteria=shulker_box.match_criteria + (("instances", choices),)
    )
