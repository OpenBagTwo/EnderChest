"""Tests for setting up folders and files"""
from enderchest import craft, load_shulker_boxes
from enderchest.config import ShulkerBox

from . import utils


def test_config_roundtrip(minecraft_root):
    original_shulker = ShulkerBox(
        3,
        "original",
        minecraft_root / "EnderChest" / "original",
        match_criteria=(
            ("minecraft", (">1.12,<2.0",)),
            ("modloader", ("*",)),
            ("tags", ("aether", "optifine")),
            ("instances", ("aether legacy", "paradise lost")),
        ),
        link_folders=("screenshots", "logs"),
    )

    utils.pre_populate_enderchest(minecraft_root / "EnderChest")

    craft.craft_shulker_box(minecraft_root, original_shulker)

    parsed_shulkers = load_shulker_boxes(minecraft_root)

    assert parsed_shulkers == [original_shulker]
