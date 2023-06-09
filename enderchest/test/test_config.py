"""Tests for reading and writing config files"""
from pathlib import Path
from urllib.parse import urlparse

import pytest

from enderchest import EnderChest, InstanceSpec, ShulkerBox
from enderchest import config as cfg
from enderchest.gather import load_shulker_boxes
from enderchest.shulker_box import create_shulker_box
from enderchest.test import utils


class TestParseIniList:
    @pytest.mark.parametrize(
        "entry, expected",
        (
            ("hello", ["hello"]),
            ('"hello"', ["hello"]),
            ("'hello'", ["hello"]),
            ("  hello  ", ["hello"]),
            ("\nhello\n", ["hello"]),
            ("7", ["7"]),
            ("1,2,3", ["1", "2", "3"]),
            ("1, 2, 3,    ", ["1", "2", "3"]),
            ('"!", "\\"", ","', ["!", '"', ","]),
            ("yo\nmama\nis\n cool", ["yo", "mama", "is", "cool"]),
            ('yo\nmama\n  "  is cool  "', ["yo", "mama", "  is cool  "]),
            ("yo\nmama,papa\nis\ncool", ["yo", "mama,papa", "is", "cool"]),
        ),
        ids=(
            "single_str_uq",
            "single_str_dq",
            "single_str_sq",
            "padded_single_str",
            "newline_padded_single_str",
            "single_val",
            "one_line_list",
            "one_line_list_w_extras",
            "punctuation_list",
            "newlines",
            "newlines_with_quotes",
            "newlines_with_commas",
        ),
    )
    def test_parse_list_from_ini(self, entry, expected):
        assert cfg.parse_ini_list(entry) == expected


class TestConfigWriting:
    def test_shulker_box_config_roundtrip(self, minecraft_root):
        original_shulker = ShulkerBox(
            3,
            "original",
            minecraft_root / "EnderChest" / "original",
            match_criteria=(
                ("minecraft", (">=1.12,<2.0",)),
                ("modloader", ("*",)),
                ("tags", ("aether", "optifine")),
                ("instances", ("aether legacy", "Paradise Lost")),
            ),
            link_folders=("screenshots", "logs"),
            do_not_link=(),  # YEAH BABY! LINK THAT shulkerbox.cfg!!
        )

        utils.pre_populate_enderchest(minecraft_root / "EnderChest")

        create_shulker_box(minecraft_root, original_shulker)

        parsed_boxes = load_shulker_boxes(minecraft_root)

        assert parsed_boxes == [original_shulker]
        assert parsed_boxes[0].do_not_link == ()

    def test_ender_chest_config_roundtrip(self, tmpdir):
        (tmpdir / "EnderChest").mkdir()

        original_ender_chest = EnderChest(
            urlparse(Path(tmpdir).absolute().as_uri()),
            name="tester",
            remotes=[
                "irc://you@irl/home/upstairs",
                ("file:///lockbox", "undisclosed location"),
            ],
            instances=utils.TESTING_INSTANCES,
        )

        original_ender_chest.sync_confirm_wait = 27
        original_ender_chest.offer_to_update_symlink_allowlist = False
        original_ender_chest.do_not_sync = ["EnderChest/enderchest.cfg", "*.local"]

        original_ender_chest.write_to_cfg(
            Path(tmpdir) / "EnderChest" / "enderchest.cfg"
        )

        parsed_ender_chest = EnderChest.from_cfg(
            Path(tmpdir) / "EnderChest" / "enderchest.cfg"
        )
        assert parsed_ender_chest.__dict__ == original_ender_chest.__dict__

    def test_ender_chest_self_corrects_its_config(self, tmpdir):
        (tmpdir / "EnderChest").mkdir()

        original_ender_chest = EnderChest(
            urlparse(Path(tmpdir).absolute().as_uri()),
            name="tester",
            instances=(
                InstanceSpec(
                    "puppet",
                    Path("..") / "instances" / "puppet" / ".minecraft",
                    ("1.20.1-pre1",),
                    "vanilla",
                    ("your", "it"),
                ),
            ),
        )
        original_ender_chest.do_not_sync = ["*.local"]

        original_ender_chest.write_to_cfg(
            Path(tmpdir) / "EnderChest" / "enderchest.cfg"
        )

        parsed_ender_chest = EnderChest.from_cfg(
            Path(tmpdir) / "EnderChest" / "enderchest.cfg"
        )
        assert {
            "do-not-sync": parsed_ender_chest.do_not_sync,
            "modloader": parsed_ender_chest.instances[0].modloader,
        } == {
            "do-not-sync": ["EnderChest/enderchest.cfg", "*.local"],
            "modloader": "",
        }
