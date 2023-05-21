"""Functionality for setting up the folder structure of both chests and shulker boxes"""
import re
from collections import Counter
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable, Sequence
from urllib.parse import ParseResult

from pathvalidate import is_valid_filename

from . import enderchest
from . import filesystem as fs
from . import sync
from .enderchest import EnderChest
from .instance import InstanceSpec
from .loggers import CRAFT_LOGGER, SYNC_LOGGER
from .orchestrate import (
    gather_minecraft_instances,
    load_ender_chest,
    load_shulker_boxes,
)
from .prompt import NO, YES, confirm, prompt
from .shulker_box import ShulkerBox

DEFAULT_SHULKER_FOLDERS = (  # TODO: customize in enderchest.cfg
    "config",
    "mods",
    "resourcepacks",
    "saves",
    "shaderpacks",
)

STANDARD_LINK_FOLDERS = (  # TODO: customize in enderchest.cfg
    "backups",
    "cachedImages",
    "crash-reports",
    "logs",
    "replay_recordings",
    "screenshots",
    ".bobby",
)


def craft_ender_chest(minecraft_root: Path, ender_chest: EnderChest) -> None:
    """Create an EnderChest based on the provided configuration

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff is in (or, at least, the
        one inside which you want to create your EnderChest)
    ender_chest : EnderChest
        The spec of the chest to create

    Notes
    -----
    - The "root" attribute of the EnderChest config will be ignored--instead
      the EnderChest will be created at <minecraft_root>/EnderChest
    - This method does not check to see if there is already an EnderChest set
      up at the specified location--if one exists, its config will
      be overwritten
    """
    root = fs.ender_chest_folder(minecraft_root, check_exists=False)
    root.mkdir(exist_ok=True)

    config_path = fs.ender_chest_config(minecraft_root, check_exists=False)
    ender_chest.write_to_cfg(config_path)
    CRAFT_LOGGER.debug(f"EnderChest configuration written to {config_path}")


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
        pass

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

    if minecraft_root != Path():
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
        "You can always add more instances later using\n$ enderchest gather"
    )

    while True:
        remotes: list[tuple[str, str]] = []
        remote_uri = prompt(
            "Would you like to grab the list of remotes from another EnderChest?"
            "\nIf so, enter the URI of that EnderChest now (leave empty to skip)."
        )
        if remote_uri == "":
            break
        try:
            remote_chest = enderchest.load_remote_ender_chest(remote_uri)
            remotes.append((remote_chest.name, remote_chest.uri))
            remotes.extend(
                (alias, uri.geturl()) for alias, uri in remote_chest.remotes.items()
            )
            SYNC_LOGGER.info(
                "Loaded the following remotes:\n"
                + "\n".join("  - {}: {}".format(*remote) for remote in remotes)
            )
        except Exception as grab_fail:
            SYNC_LOGGER.error(
                f"Could not parse or access the remote EnderChest\n{grab_fail}"
            )
            continue
        aliases: set[str] = set(alias for alias, _ in remotes)
        if len(aliases) != len(remotes):
            SYNC_LOGGER.error("There are duplicates aliases in the list of remotes")
            continue
        break

    while True:
        protocol = prompt(
            (
                "Specify the method for syncing with this EnderChest."
                "\nSupported protocols are: " + ", ".join(sync.SUPPORTED_PROTOCOLS)
            ),
            suggestion=sync.DEFAULT_PROTOCOL,
        ).lower()
        if protocol == "":
            protocol = sync.DEFAULT_PROTOCOL
        if protocol not in sync.SUPPORTED_PROTOCOLS:
            SYNC_LOGGER.error("Unsupported protocol\n")
            continue
        break

    while True:
        default_netloc = sync.get_default_netloc()
        netloc = prompt(
            (
                "What's the address for accessing this machine?"
                "\n(hostname or IP address, plus often a username)"
            ),
            suggestion=default_netloc,
        )
        if netloc == "":
            netloc = default_netloc

        uri = ParseResult(
            scheme=protocol,
            netloc=netloc,
            path=str(minecraft_root),
            params="",
            query="",
            fragment="",
        )
        if not uri.hostname:
            CRAFT_LOGGER.error("Invalid hostname")
            continue
        break

    while True:
        name = prompt("Provide a name for this EnderChest", suggestion=uri.hostname)
        if name == "":
            name = uri.hostname
        if name in aliases:
            CRAFT_LOGGER.error(
                f"The name {name} is already in use. Choose a different name."
            )
            continue
        break

    ender_chest = EnderChest(uri, name, remotes, instances)

    with NamedTemporaryFile("w") as test_file:
        ender_chest.write_to_cfg(Path(test_file.name))

        # TODO: capture as logs?
        CRAFT_LOGGER.info("\n\n" + test_file.read())
        CRAFT_LOGGER.info(
            "\nPreparing to generate an EnderChest with the above configuration."
        )

        if not confirm(default=True):
            raise RuntimeError("EnderChest creation aborted.")

    return ender_chest


def craft_shulker_box(minecraft_root: Path, shulker_box: ShulkerBox) -> None:
    """Create a shulker box folder based on the provided configuration

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)
    shulker_box : ShulkerBox
        The spec of the box to create

    Notes
    -----
    - The "root" attribute of the ShulkerBox config will be ignored--instead
      the shulker box will be created at
      <minecraft_root>/EnderChest/<shulker box name>
    - This method will fail if there is no EnderChest set up in the minecraft
      root
    - This method does not check to see if there is already a shulker box
      set up at the specificed location--if one exists, its config will
      be overwritten
    """
    root = fs.shulker_box_root(minecraft_root, shulker_box.name)
    root.mkdir(exist_ok=True)

    for folder in (*DEFAULT_SHULKER_FOLDERS, *shulker_box.link_folders):
        CRAFT_LOGGER.debug(f"Creating {root / folder}")
        (root / folder).mkdir(exist_ok=True, parents=True)

    config_path = fs.shulker_box_config(minecraft_root, shulker_box.name)
    shulker_box.write_to_cfg(config_path)
    CRAFT_LOGGER.debug(f"Shulker box configuration written to {config_path}")


def specify_shulker_box_from_prompt(minecraft_root: Path) -> ShulkerBox:
    """Parse a shulker box based on interactive user input

    Parameters
    ----------
    minecraft_root : Path
        The root directory that your minecraft stuff (or, at least, the one
        that's the parent of your EnderChest folder)

    Returns
    -------
    ShulkerBox
        The resulting ShulkerBox
    """
    while True:
        name = prompt("Provide a name for the shulker box")
        if not is_valid_filename(name):
            CRAFT_LOGGER.error("Name must be useable as a valid filename.")
            continue
        shulker_root = fs.shulker_box_root(minecraft_root, name)
        if shulker_root in shulker_root.parent.glob("*"):
            if not shulker_root.is_dir():
                CRAFT_LOGGER.error(
                    f"A file named {name} already exists in your EnderChest folder."
                )
                continue
            CRAFT_LOGGER.warning(
                f"There is already a folder named {name} in your EnderChest folder."
            )
            if not confirm(default=False):
                continue
        break

    shulker_box = ShulkerBox(0, name, shulker_root, (), ())

    # TODO: hosts

    instances = load_ender_chest(minecraft_root).instances

    explicit_type = "name"
    if len(instances) > 0:
        _print_instance_list(instances)
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
                    shulker_box = _prompt_for_instance_numbers(shulker_box, instances)
            case "name":
                # yeah, this is always available
                shulker_box = _prompt_for_instance_names(shulker_box)
            case "number":
                if explicit_type == "name":
                    continue
                shulker_box = _prompt_for_instance_numbers(shulker_box, instances)
            case _:
                continue
        break

    while True:
        selection_type = prompt(
            "Folders to Link?"
            "\nUse the [S]tandard set, [M]anually specify or do [N]one?"
            "\nThe standard set is: " + ", ".join(STANDARD_LINK_FOLDERS)
        ).lower()
        match selection_type:
            case "n" | "none":
                link_folders: tuple[str, ...] = ()
            case "s" | "standard" | "standard set":
                link_folders = STANDARD_LINK_FOLDERS
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

    shulker_box = shulker_box._replace(link_folders=link_folders)

    while True:
        _ = load_shulker_boxes(minecraft_root)  # to display some log messages
        value = prompt(
            (
                "What priority value should be assigned to this shulker box?"
                "\nhigher number = applied later"
            ),
            suggestion="0",
        )
        if value == "":
            value = "0"
        try:
            priority = int(value)
        except ValueError:
            continue
        break

    shulker_box = shulker_box._replace(priority=priority)

    return shulker_box


def _prompt_for_filters(
    shulker_box: ShulkerBox, instances: Sequence[InstanceSpec]
) -> ShulkerBox:
    """Prompt the user for a ShulkerBox spec by filters

    Parameters
    ----------
    shulker_box : ShulkerBox
        The starting ShulkerBox (with no match critera)
    instances : list-like of InstanceSpec
        The list of known instances

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
            CRAFT_LOGGER.error("Filters do not match any known instance.")
            default = False
        elif len(matches) == 1:
            CRAFT_LOGGER.info(f"Filters matches the instance: {matches[0]}")
        else:
            CRAFT_LOGGER.info(
                "Filters matches the instances:\n"
                + "\n".join([f"  - {name}" for name in matches])
            )
        return tester if confirm(default=default) else None, matches

    while True:
        version_spec = prompt(
            (
                "Minecraft versions:"
                ' (e.g: "*", "1.19.1, 1.19.2, 1.19.3", "1.19.*", ">=1.19.0,<1.20")'
            ),
            suggestion="*",
        )
        if version_spec == "":
            version_spec = "*"

        updated, matches = check_progress(
            "minecraft", (version.strip() for version in version_spec.split(", "))
        )
        if updated:
            shulker_box = updated
            instances = [instance for instance in instances if instance.name in matches]
            break

    while True:
        modloader = prompt(
            (
                "Modloader?"
                "\n[N]one, For[G]e, Fa[B]ric, [Q]uilt, [L]iteLoader"
                ' (or multiple, e.g: "B,Q", or any using "*")'
            ),
            suggestion="*",
        )
        if modloader == "":
            modloader = "*"

        modloaders: list[str] = []
        for entry in modloader.split(","):
            match entry.strip().lower():
                case "" | "n" | "none" | "vanilla":
                    modloaders.append("None")
                case "g" | "forge":
                    modloaders.append("Forge")
                case "b" | "fabric" | "fabric loader":
                    modloaders.append("Fabric Loader")
                case "q" | "quilt":
                    modloaders.append("Quilt Loader")
                case "l" | "liteloader":
                    modloaders.append("LiteLoader")
                case _:
                    modloaders.append(entry)

        updated, matches = check_progress("modloader", modloaders)
        if updated:
            shulker_box = updated
            instances = [instance for instance in instances if instance.name in matches]
            break

    while True:
        tag_count = Counter(sum((instance.tags for instance in instances), ()))
        # TODO: should this be most common among matches?
        example_tags: list[str] = [tag for tag, _ in tag_count.most_common(5)]
        CRAFT_LOGGER.debug(
            "Tag counts:\n"
            + "\n".join(f"  - {tag}: {count}" for tag, count in tag_count.items())
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

        tags = prompt(
            "Tags?"
            f'\ne.g.{", ".join(example_tags)}'
            "\n(or multiple using comma-separated lists or wildcards)",
            suggestion="*",
        )
        if tags == "":
            tags = "*"

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
            "You specified the following instances:\n"
            + "\n".join([f"  - {name}" for name in instances])
        )
        default = True

    if not confirm(default=default):
        CRAFT_LOGGER.debug("Trying again to prompt for instance names")
        return _prompt_for_instance_names(shulker_box)

    return shulker_box._replace(
        match_criteria=shulker_box.match_criteria + (("instances", instances),)
    )


def _prompt_for_instance_numbers(
    shulker_box: ShulkerBox, instances: Sequence[InstanceSpec]
) -> ShulkerBox:
    """Prompt the user to specify the instances they'd like by number

    Parameters
    ----------
    shulker_box : ShulkerBox
        The starting ShulkerBox, presumably with limited or no match criteria
    instances : list-like of InstanceSpec
        The names of the  available instances

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
        CRAFT_LOGGER.error("Invalid selection")
        _print_instance_list(instances)
        return _prompt_for_instance_numbers(shulker_box, instances)

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
                    CRAFT_LOGGER.error(f"Invalid selection: {entry} is out of range")
                    _print_instance_list(instances)
                    return _prompt_for_instance_numbers(shulker_box, instances)
                selected_instances.add(instances[index].name)
            case value if match := re.match("([0-9]+)-([0-9]+)$", value):
                bounds = tuple(int(bound) for bound in match.groups())
                if bounds[0] > bounds[1]:
                    CRAFT_LOGGER.error(
                        f"Invalid selection: {entry} is not a valid range"
                    )
                    _print_instance_list(instances)
                    return _prompt_for_instance_numbers(shulker_box, instances)
                if max(bounds) > len(instances) or min(bounds) < 1:
                    CRAFT_LOGGER.error(f"Invalid selection: {entry} is out of range\n")
                    _print_instance_list(instances)
                    return _prompt_for_instance_numbers(shulker_box, instances)
                selected_instances.update(
                    instance.name for instance in instances[bounds[0] - 1 : bounds[1]]
                )

    choices = tuple(
        instance.name for instance in instances if instance.name in selected_instances
    )

    CRAFT_LOGGER.info(
        "You selected the instances:\n" + "\n".join([f"  - {name}" for name in choices])
    )
    if not confirm(default=True):
        CRAFT_LOGGER.debug("Trying again to prompt for instance numbers")
        _print_instance_list(instances)
        return _prompt_for_instance_numbers(shulker_box, instances)

    return shulker_box._replace(
        match_criteria=shulker_box.match_criteria + (("instances", choices),)
    )


def _print_instance_list(instances: Sequence[InstanceSpec]) -> None:
    """Just centralizing the implementation of how the instance list gets
    displayed

    Parameters
    ----------
    instances : list-like of InstanceSpec
        The available instances
    """
    CRAFT_LOGGER.info(
        "\nThese are the instances that are currently registered:\n"
        + "\n".join(
            [
                f"  {i + 1}. {instance.name} ({instance.root})"
                for i, instance in enumerate(instances)
            ]
        )
    )
