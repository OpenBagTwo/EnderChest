"""Tests for EnderChest / Shulker Box state resolving functionality"""

import logging
import re
from pathlib import Path

import pytest

from enderchest import craft
from enderchest import filesystem as fs
from enderchest import inventory
from enderchest.test import utils


class TestLoadEnderChestInstances:
    def test_bad_folder_just_returns_empty(self, tmp_path, caplog):
        assert inventory.load_ender_chest_instances(tmp_path) == []


class TestListShulkerBoxes:
    @pytest.fixture(autouse=True)
    def populate_shulker_boxes(self, minecraft_root):
        utils.pre_populate_enderchest(
            minecraft_root / "EnderChest", *utils.TESTING_SHULKER_CONFIGS
        )

        # also write a bad shulker box
        bad_ini = minecraft_root / "EnderChest" / "not_ini" / fs.SHULKER_BOX_CONFIG_NAME
        bad_ini.parent.mkdir()
        bad_ini.write_text("is_this_valid_ini=no")

    def test_bad_folder_just_returns_empty(self, tmp_path, caplog):
        assert inventory.load_shulker_boxes(tmp_path) == []

    def test_warn_for_a_chest_without_boxes(self, tmp_path, caplog):
        root = tmp_path / "nowhere"
        root.mkdir()
        craft.craft_ender_chest(root, remotes=(), overwrite=True)
        _ = inventory.load_shulker_boxes(root)

        assert "There are no shulker boxes" in "\n".join(
            (
                record.msg
                for record in caplog.records
                if record.levelno == logging.WARNING
            )
        )

    def test_list_shulker_box_reports_the_boxes_in_order(self, minecraft_root, caplog):
        _ = inventory.load_shulker_boxes(minecraft_root)
        assert (
            """0. global
  1. 1.19
  2. vanilla
  3. optifine"""
            in caplog.records[-1].msg % caplog.records[-1].args
        )

    def test_list_shulker_box_doesnt_choke_on_relative_root(
        self, minecraft_root, caplog, monkeypatch
    ):
        monkeypatch.chdir(minecraft_root.parent)
        _ = inventory.load_shulker_boxes(Path(minecraft_root.name))
        assert (
            """0. global
  1. 1.19
  2. vanilla
  3. optifine"""
            in caplog.records[-1].msg % caplog.records[-1].args
        )

    def test_list_shulker_box_warns_if_theres_a_bad_box(self, minecraft_root, caplog):
        _ = inventory.load_shulker_boxes(minecraft_root)

        warnings = [
            record for record in caplog.records if record.levelname == "WARNING"
        ]

        assert re.search(
            rf"Could not parse(.*)not_ini(.*){fs.SHULKER_BOX_CONFIG_NAME}",
            warnings[-1].msg % warnings[-1].args,
        )


class TestLoadBoxInstanceMatches:
    @pytest.fixture(autouse=True)
    def populate_shulker_boxes(self, minecraft_root, home):
        utils.pre_populate_enderchest(
            minecraft_root / "EnderChest", *utils.TESTING_SHULKER_CONFIGS
        )

    def test_bad_folder_just_returns_empty(self, tmp_path, caplog):
        assert (
            inventory.get_shulker_boxes_matching_instance(tmp_path, "outstance") == []
        )

    @pytest.mark.parametrize(
        "instance_name",
        [mc.name for mc in utils.TESTING_INSTANCES] + ["unown"],
    )
    def test_loading_boxes_that_match_instance(self, minecraft_root, instance_name):
        # because TESTING_SHULKER_INSTANCE_MATCHES uses the path
        instance_name_lookup = {
            "official": "~",
            "Chest Boat": "chest-boat",
            "Drowned": "drowned",
        }
        box_lookup = {
            box.name: box
            for box in inventory.load_shulker_boxes(
                minecraft_root, log_level=logging.DEBUG
            )
        }

        expected = []
        for box_name, mc_name, should_match in utils.TESTING_SHULKER_INSTANCE_MATCHES:
            if mc_name == instance_name_lookup.get(instance_name, instance_name):
                if should_match:
                    expected.append(box_lookup[box_name])

        assert (
            inventory.get_shulker_boxes_matching_instance(minecraft_root, instance_name)
            == expected
        )

    @pytest.mark.parametrize(
        "shulker_box_name",
        list({box for _, box, _ in utils.TESTING_SHULKER_INSTANCE_MATCHES}) + ["unown"],
    )
    def test_loading_instances_that_match_boxes(self, minecraft_root, shulker_box_name):
        instance_lookup = {
            mc.name: mc
            for mc in inventory.load_ender_chest_instances(
                minecraft_root, log_level=logging.DEBUG
            )
        }
        # because TESTING_SHULKER_INSTANCE_MATCHES uses the path
        instance_lookup["~"] = instance_lookup["official"]
        instance_lookup["chest-boat"] = instance_lookup["Chest Boat"]

        expected = []
        for (
            box_name,
            instance_name,
            should_match,
        ) in utils.TESTING_SHULKER_INSTANCE_MATCHES:
            if box_name == shulker_box_name:
                if should_match:
                    expected.append(instance_lookup[instance_name])

        assert (
            inventory.get_instances_matching_shulker_box(
                minecraft_root, shulker_box_name
            )
            == expected
        )
