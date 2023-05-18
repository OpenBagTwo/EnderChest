"""Functionality for setting up the folder structure of both chests and shulker boxes"""
from collections import Counter
from pathlib import Path
from typing import Iterable, Sequence

from pathvalidate import is_valid_filename

from . import load_instance_metadata
from .config import InstanceSpec, ShulkerBox
from .prompt import confirm, prompt

DEFAULT_SHULKER_FOLDERS = (
    "config",
    "mods",
    "resourcepacks",
    "saves",
    "shaderpacks",
)


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
    The "root" attribute of the ShulkerBox config will be ignored--instead the
    Shulker Box will be created at <minecraft_root>/EnderChest/<shulker box name>
    """
    shulker_root = minecraft_root / "EnderChest" / shulker_box.name

    (minecraft_root / "EnderChest" / shulker_box.name).mkdir(
        parents=True, exist_ok=True
    )
    for folder in (*DEFAULT_SHULKER_FOLDERS, *shulker_box.link_folders):
        (shulker_root / folder).mkdir(exist_ok=True)

    shulker_box.write_to_cfg(shulker_root / "shulkerbox.cfg")


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
            print("Name must be useable as a valid filename.")
            continue
        shulker_root = minecraft_root / "EnderChest" / name
        if shulker_root in shulker_root.parent.glob("*"):
            if not shulker_root.is_dir():
                print(f"A file named {name} already exists in your EnderChest folder.")
                continue
            print(f"There is already a folder named {name} in your EnderChest folder.")
            if not confirm(default=False):
                continue
        break

    shulker_box = ShulkerBox(0, name, shulker_root, (), ())

    instances = load_instance_metadata(minecraft_root)

    explicit_type = "name"
    if len(instances) > 0:
        print(
            "These are the instances that are currently registered:\n"
            + "\n".join(
                [
                    f"  {i + 1}. {instance.name} ({instance.root})"
                    for i, instance in enumerate(instances)
                ]
            )
        )
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

    # TODO: prompt for linked folders

    # TODO: prompt for priority

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
            print("Filters do not match any known instance.")
            default = False
        elif len(matches) == 1:
            print(f"Filters matches the instance: {matches[0]}")
        else:
            print(
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
    raise NotImplementedError


def _prompt_for_instance_numbers(
    shulker_box: ShulkerBox, instances: Sequence[InstanceSpec]
) -> ShulkerBox:
    raise NotImplementedError
