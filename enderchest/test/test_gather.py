"""Tests around file discovery and registration"""
import re

import pytest

from enderchest import craft
from enderchest import filesystem as fs
from enderchest import gather
from enderchest import instance as i

from . import utils


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

    def test_list_shulker_box_reports_the_boxes_in_order(self, minecraft_root, caplog):
        _ = gather.load_shulker_boxes(minecraft_root)
        assert (
            """0. global
  1. 1.19
  2. vanilla
  3. optifine"""
            in caplog.records[-1].msg
        )

    def test_list_shulker_box_warns_if_theres_a_bad_box(self, minecraft_root, caplog):
        _ = gather.load_shulker_boxes(minecraft_root)

        warnings = [
            record for record in caplog.records if record.levelname == "WARNING"
        ]

        assert re.search(
            rf"Could not parse(.*)not_ini(.*){fs.SHULKER_BOX_CONFIG_NAME}",
            warnings[-1].msg,
        )


class TestGatherInstances:
    def test_official_instance_parsing(self, home):
        assert utils.normalize_instance(
            gather.gather_metadata_for_official_instance(home / ".minecraft")
        ) == utils.normalize_instance(utils.TESTING_INSTANCES[0])

    def test_instance_search_finds_official_instance(self, minecraft_root, home):
        assert i.equals(
            minecraft_root,
            gather.gather_minecraft_instances(minecraft_root, home, official=True)[0],
            utils.TESTING_INSTANCES[0],
        )

    @pytest.mark.parametrize(
        "instance, idx",
        (
            ("axolotl", 1),
            ("bee", 2),
            ("chest-boat", 3),
        ),
    )
    def test_mmc_instance_parsing(self, minecraft_root, instance, idx):
        print(list((minecraft_root / "instances" / instance).rglob("*")))
        assert utils.normalize_instance(
            gather.gather_metadata_for_mmc_instance(
                minecraft_root / "instances" / instance / ".minecraft"
            )
        ) == utils.normalize_instance(
            # we're not testing aliasing right now
            utils.TESTING_INSTANCES[idx]._replace(name=instance)
        )

    def test_instance_search_finds_mmc_instances(self, minecraft_root):
        instances = sorted(
            gather.gather_minecraft_instances(
                minecraft_root, minecraft_root, official=False
            ),
            key=lambda instance: instance.name,
        )

        assert len(instances) == 3

        assert all(
            [
                i.equals(
                    minecraft_root, instances[idx - 1], utils.TESTING_INSTANCES[idx]
                )
                for idx in range(1, 4)
            ]
        )

    def test_instance_search_can_find_all_instances(self, minecraft_root, home):
        instances = sorted(
            gather.gather_minecraft_instances(
                minecraft_root, minecraft_root, official=None
            ),
            key=lambda instance: instance.name
            if instance.name != "official"
            else "aaa",  # sorting hack
        )

        assert len(instances) == 4

        assert all(
            [
                i.equals(minecraft_root, instances[idx], utils.TESTING_INSTANCES[idx])
                for idx in range(4)
            ]
        )

    def test_instance_search_warns_if_no_instances_can_be_found(
        self, minecraft_root, caplog
    ):
        empty_folder = minecraft_root / "nothing in there"
        empty_folder.mkdir()
        instances = gather.gather_minecraft_instances(
            minecraft_root, empty_folder, official=None
        )

        assert len(instances) == 0

        warn_log = "\n".join(
            record.msg for record in caplog.records if record.levelname == "WARNING"
        )

        assert "Could not find any Minecraft instances" in warn_log

    def test_onboarding_new_instances(self, minecraft_root, home):
        # start with a blank chest
        craft.craft_ender_chest(minecraft_root, remotes=())
        gather.update_ender_chest(minecraft_root, ("~", minecraft_root))

        instances = sorted(
            gather.load_ender_chest_instances(minecraft_root),
            key=lambda instance: instance.name
            if instance.name != "official"
            else "aaa",  # sorting hack
        )

        assert len(instances) == 4

        assert all(
            [
                i.equals(minecraft_root, instances[idx], utils.TESTING_INSTANCES[idx])
                for idx in range(4)
            ]
        )
