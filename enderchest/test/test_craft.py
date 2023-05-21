"""Tests for setting up folders and files"""
import logging
from pathlib import Path

import pytest

from enderchest import EnderChest, ShulkerBox, craft
from enderchest.gather import load_shulker_boxes

from . import utils


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
                ("instances", ("aether legacy", "paradise lost")),
            ),
            link_folders=("screenshots", "logs"),
        )

        utils.pre_populate_enderchest(minecraft_root / "EnderChest")

        craft.craft_shulker_box(minecraft_root, original_shulker)

        parsed_shulkers = load_shulker_boxes(minecraft_root)

        assert parsed_shulkers == [original_shulker]

    def test_ender_chest_config_roundtrip(self, tmpdir):
        (tmpdir / "EnderChest").mkdir()

        original_ender_chest = EnderChest(
            f"IPoAC://openbagtwo@localhost{tmpdir}",
            name="tester",
            remotes=[
                "irc://you@irl/home/upstairs",
                ("file:///lockbox", "undisclosed location"),
            ],
            instances=utils.TESTING_INSTANCES,
        )

        original_ender_chest.write_to_cfg(
            Path(tmpdir) / "EnderChest" / "enderchest.cfg"
        )

        parsed_ender_chest = EnderChest.from_cfg(
            Path(tmpdir) / "EnderChest" / "enderchest.cfg"
        )

        assert parsed_ender_chest == original_ender_chest


class TestPromptByFilter:
    def test_using_default_responses_results_in_the_expected_shulker_box(
        self, monkeypatch, capsys
    ):
        script_reader = utils.scripted_prompt([""] * 6)
        monkeypatch.setattr("builtins.input", script_reader)

        shulker_box = craft._prompt_for_filters(
            ShulkerBox(0, "tester", Path("ignored"), (), ()), utils.TESTING_INSTANCES
        )

        _ = capsys.readouterr()  # suppress outputs

        assert shulker_box.match_criteria == (
            ("minecraft", ("*",)),
            ("modloader", ("*",)),
            ("tags", ("*",)),
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()

    def test_filter_prompt_doesnt_confirm_when_there_are_no_instances(
        self, monkeypatch, capsys
    ):
        script_reader = utils.scripted_prompt(
            (
                "22w14infinite",
                "N",
                "",
            )
        )
        monkeypatch.setattr("builtins.input", script_reader)

        shulker_box = craft._prompt_for_filters(
            ShulkerBox(0, "tester", Path("ignored"), (), ()), []
        )

        _ = capsys.readouterr()

        assert shulker_box.match_criteria == (
            ("minecraft", ("22w14infinite",)),
            ("modloader", ("None",)),
            ("tags", ("*",)),
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()

    def test_filter_prompt_stops_confirming_once_youre_out_of_instances(
        self, monkeypatch, capsys
    ):
        script_reader = utils.scripted_prompt(
            (
                "22w14infinite",
                "y",
                "b",
                "april-fools*",
            )
        )
        monkeypatch.setattr("builtins.input", script_reader)

        shulker_box = craft._prompt_for_filters(
            ShulkerBox(0, "tester", Path("ignored"), (), ()), utils.TESTING_INSTANCES
        )

        _ = capsys.readouterr()

        assert shulker_box.match_criteria == (
            ("minecraft", ("22w14infinite",)),
            ("modloader", ("Fabric Loader",)),
            ("tags", ("april-fools*",)),
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()

    def test_filter_prompt_lets_you_back_out_of_a_mistake(
        self, monkeypatch, capsys, caplog
    ):
        script_reader = utils.scripted_prompt(
            (
                "1.19.5",
                "",  # default is no
                "1.19",
                "",  # default is yes
                "N,B,Q",
                "",
                "vanilla*",
                "",
            )
        )

        monkeypatch.setattr("builtins.input", script_reader)

        shulker_box = craft._prompt_for_filters(
            ShulkerBox(0, "tester", Path("ignored"), (), ()), utils.TESTING_INSTANCES
        )

        _ = capsys.readouterr()

        assert shulker_box.match_criteria == (
            ("minecraft", ("1.19",)),
            ("modloader", ("None", "Fabric Loader", "Quilt Loader")),
            ("tags", ("vanilla*",)),
        )

        # check that it was showing the right instances right up until the end
        assert caplog.records[-1].msg == (
            """Filters matches the instances:
  - official
  - Chest Boat"""
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()


class TestPromptByName:
    def test_confirms_selections(self, monkeypatch, capsys, caplog):
        script_reader = utils.scripted_prompt(
            (
                "abra, kadabra, alakazam",
                "",  # default should be yes here
            )
        )
        monkeypatch.setattr("builtins.input", script_reader)

        shulker_box = craft._prompt_for_instance_names(
            ShulkerBox(0, "tester", Path("ignored"), (), ())
        )

        _ = capsys.readouterr()

        assert shulker_box.match_criteria == (
            ("instances", ("abra", "kadabra", "alakazam")),
        )

        assert caplog.records[-1].msg == (
            """You specified the following instances:
  - abra
  - kadabra
  - alakazam"""
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()

    def test_default_for_confirmation_is_no_if_empty_response(
        self,
        monkeypatch,
        capsys,
        caplog,
    ):
        script_reader = utils.scripted_prompt(
            (
                "",
                "",
                "",
                "yes",
            )
        )
        monkeypatch.setattr("builtins.input", script_reader)

        shulker_box = craft._prompt_for_instance_names(
            ShulkerBox(0, "tester", Path("ignored"), (), ())
        )

        _ = capsys.readouterr()

        assert shulker_box.match_criteria == (("instances", ("*",)),)

        assert (
            "This shulker box will be applied to all instances"
            in caplog.records[-1].msg
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()


class TestPromptByNumber:
    def test_defaults_results_in_explicit_enumeration(self, monkeypatch, capsys):
        script_reader = utils.scripted_prompt(
            (
                "",
                "",
            )
        )
        monkeypatch.setattr("builtins.input", script_reader)

        def get_instances():
            return utils.TESTING_INSTANCES

        shulker_box = craft._prompt_for_instance_numbers(
            ShulkerBox(0, "tester", Path("ignored"), (), ()),
            get_instances(),
            get_instances,
        )

        _ = capsys.readouterr()

        assert shulker_box.match_criteria == (
            ("instances", tuple(instance.name for instance in utils.TESTING_INSTANCES)),
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()

    def test_number_selection_supports_explicit_numbers_and_ranges(
        self, monkeypatch, capsys
    ):
        script_reader = utils.scripted_prompt(
            (
                "4, 2 - 3",
                "",
            )
        )
        monkeypatch.setattr("builtins.input", script_reader)

        def get_instances():
            return utils.TESTING_INSTANCES

        shulker_box = craft._prompt_for_instance_numbers(
            ShulkerBox(0, "tester", Path("ignored"), (), ()),
            get_instances(),
            get_instances,
        )

        _ = capsys.readouterr()

        assert shulker_box.match_criteria == (
            (
                "instances",
                tuple(instance.name for instance in utils.TESTING_INSTANCES[1:4]),
            ),
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()

    def test_invalid_selection_reminds_you_of_the_instance_list(
        self, monkeypatch, capsys, caplog
    ):
        script_reader = utils.scripted_prompt(
            (
                "7",
                "1, 3",
                "",
            )
        )
        monkeypatch.setattr("builtins.input", script_reader)

        def get_instances():
            logging.info(
                """These are the instances that are currently registered:
  1. official (~/.minecraft)
  2. axolotl (instances/axolotl/.minecraft)
  3. bee (instances/bee/.minecraft)
  4. Chest Boat (instances/chest-boat/.minecraft)"""
            )
            return utils.TESTING_INSTANCES

        shulker_box = craft._prompt_for_instance_numbers(
            ShulkerBox(0, "tester", Path("ignored"), (), ()),
            get_instances(),
            get_instances,
        )

        _ = capsys.readouterr()

        assert """Invalid selection: 7 is out of range

These are the instances that are currently registered:
  1. official (~/.minecraft)
  2. axolotl (instances/axolotl/.minecraft)
  3. bee (instances/bee/.minecraft)
  4. Chest Boat (instances/chest-boat/.minecraft)""" in "\n".join(
            record.msg for record in caplog.records
        )

        assert shulker_box.match_criteria == (
            (
                "instances",
                ("official", "bee"),
            ),
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()
