"""Tests around file discovery and registration"""
import pytest

from enderchest import filesystem as fs
from enderchest import orchestrate as o

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
        _ = o.load_shulker_boxes(minecraft_root)
        assert (
            """0. global
  1. 1.19
  2. vanilla
  3. optifine"""
            in caplog.records[-1].msg
        )

    def test_list_shulker_box_warns_if_theres_a_bad_box(self, minecraft_root, caplog):
        _ = o.load_shulker_boxes(minecraft_root)

        warnings = [
            record for record in caplog.records if record.levelname == "WARNING"
        ]
        assert (
            "not_ini/shulkerbox.cfg is not a valid shulker config:" in warnings[-1].msg
        )
