"""Tests of the EnderChest uninstallation procedure"""
import logging
import os
from pathlib import Path

import pytest

from enderchest import craft
from enderchest import filesystem as fs
from enderchest import gather, place, uninstall

from . import utils


class TestBreakEnderChest:
    def test_cant_break_what_doesnt_exist(self, tmp_path, caplog):
        uninstall.break_ender_chest(tmp_path)
        error_log = [
            record for record in caplog.records if record.levelno == logging.ERROR
        ]
        assert error_log[-1].message == "Aborting."
        assert len(error_log) == 2
        assert error_log[0].message.startswith("Could not load EnderChest")

    def test_break_aborts_for_a_chest_with_no_instances(self, tmp_path, caplog):
        craft.craft_ender_chest(
            tmp_path,
            instance_search_paths=[],  # gotta give a kwarg so it doesn't go interactive
        )
        uninstall.break_ender_chest(tmp_path)
        errorish_log = [
            record for record in caplog.records if record.levelno >= logging.WARNING
        ]
        assert errorish_log[-1].message == "Aborting."
        assert len(errorish_log) == 2
        assert errorish_log[0].levelno == logging.WARNING
        assert "no instances" in errorish_log[0].message.lower()

    def test_break_asks_you_if_youre_really_sure(
        self, minecraft_root, home, monkeypatch, capsys, caplog
    ):
        script_reader = utils.scripted_prompt([""])
        monkeypatch.setattr("builtins.input", script_reader)

        utils.pre_populate_enderchest(
            fs.ender_chest_folder(minecraft_root, check_exists=False),
            *utils.TESTING_SHULKER_CONFIGS
        )

        uninstall.break_ender_chest(minecraft_root)

        _ = capsys.readouterr()  # suppress outputs
        errorish_log = [
            record for record in caplog.records if record.levelno >= logging.WARNING
        ]
        assert errorish_log[-1].message == "Aborting."
        assert errorish_log[-2].levelno == logging.WARNING
        assert errorish_log[-2].message.startswith("Are you sure")

        assert len(errorish_log) == 2


class TestBreaking:
    @pytest.fixture(autouse=True)
    def setup_teardown(self, minecraft_root, multi_box_setup_teardown, capsys, caplog):
        utils.pre_populate_enderchest(
            fs.ender_chest_folder(minecraft_root, check_exists=False),
            *utils.TESTING_SHULKER_CONFIGS
        )
        place.place_ender_chest(minecraft_root, relative=True, error_handling="ignore")

        errorish_log = [
            record for record in caplog.records if record.levelno >= logging.WARNING
        ]
        assert len(errorish_log) == 1
        assert (
            errorish_log[0].levelno == logging.ERROR
            and errorish_log[0].message.startswith("Error linking")
            and "options.txt" in errorish_log[0].message
        )

        yield

        _ = capsys.readouterr()  # suppress outputs

    def test_clean_uninstall_emits_no_warnings(self, minecraft_root, caplog):
        uninstall._break(fs.ender_chest_folder(minecraft_root), utils.TESTING_INSTANCES)
        warnings = [
            record for record in caplog.records if record.levelno >= logging.WARNING
        ]
        assert len(warnings) == 0

    @pytest.mark.parametrize(
        "instance", (instance.name for instance in utils.TESTING_INSTANCES)
    )
    def test_uninstall_replaces_links_with_copies(self, minecraft_root, instance):
        resource_path = {
            instance.name: instance for instance in utils.TESTING_INSTANCES
        }[instance].root.expanduser() / "usercache.json"

        # meta-test
        assert resource_path.resolve().is_relative_to(
            fs.ender_chest_folder(minecraft_root.resolve())
        )
        uninstall._break(fs.ender_chest_folder(minecraft_root), utils.TESTING_INSTANCES)

        assert resource_path.exists()
        assert not resource_path.is_symlink()
        assert resource_path.read_text() == "alexander\nmomoa\nbateman\n"

    @pytest.mark.parametrize(
        "instance", (instance.name for instance in utils.TESTING_INSTANCES)
    )
    def test_uninstall_replaces_links_pointing_outside_the_chest_with_links(
        self, minecraft_root, instance
    ):
        resource_path = {
            instance.name: instance for instance in utils.TESTING_INSTANCES
        }[instance].root.expanduser() / "crash-reports"

        # fix for pytest utilizing symlinks for differently-scoped fixtures
        resource_path.unlink()
        resource_path.symlink_to(
            fs.ender_chest_folder(minecraft_root.resolve())
            / "global"
            / resource_path.name
        )

        # meta-test
        assert not resource_path.resolve().is_relative_to(
            fs.ender_chest_folder(minecraft_root.resolve())
        )

        uninstall._break(fs.ender_chest_folder(minecraft_root), utils.TESTING_INSTANCES)

        assert resource_path.exists()
        assert resource_path.is_symlink()
        assert (
            (resource_path / "20230524.log")
            .read_text()
            .endswith("And somehow also on fire\n")
        )

    @pytest.mark.parametrize("instance", ("axolotl", "bee"))
    def test_uninstall_copies_based_on_highest_priority(
        self,
        minecraft_root,
        instance,
    ):
        resource_path = (
            {instance.name: instance for instance in utils.TESTING_INSTANCES}[
                instance
            ].root.expanduser()
            / "resourcepacks"
            / "stuff.zip"
        )
        uninstall._break(fs.ender_chest_folder(minecraft_root), utils.TESTING_INSTANCES)

        assert resource_path.exists()
        assert resource_path.is_symlink() is (instance != "bee")
        assert (
            resource_path.read_text() == "optifine-optimized!"
            if instance == "bee"
            else "dfgwhgsadfhsd"
        )

    @pytest.mark.parametrize(
        "instance", (instance.name for instance in utils.TESTING_INSTANCES)
    )
    def test_uninstall_proceeds_past_broken_links(
        self, minecraft_root, instance, caplog
    ):
        (fs.shulker_box_root(minecraft_root, "global") / "backups").rmdir()

        resource_path = {
            instance.name: instance for instance in utils.TESTING_INSTANCES
        }["Chest Boat"].root.expanduser() / "logs"

        uninstall._break(fs.ender_chest_folder(minecraft_root), utils.TESTING_INSTANCES)

        errorish_log = [
            record for record in caplog.records if record.levelno >= logging.WARNING
        ]
        assert len(errorish_log) == len(utils.TESTING_INSTANCES)

        assert all(
            (
                (
                    "No such file or directory" in record.message
                    or "system cannot find the file" in record.message
                )
                for record in errorish_log
            )
        )
        assert resource_path.exists()
        assert not resource_path.is_symlink()
        assert (
            (resource_path / "bumpona.log").read_text("utf-8").startswith("Like a bump")
        )

    def test_break_doesnt_touch_links_pointing_directly_outside_of_enderchest(
        self, minecraft_root, caplog
    ):
        # even broken ones
        resource_path = (
            {instance.name: instance for instance in utils.TESTING_INSTANCES}[
                "bee"
            ].root.expanduser()
            / "config"
            / "some_mod.json"
        )

        os.symlink(
            minecraft_root / "null" / "null", resource_path, target_is_directory=False
        )
        uninstall._break(fs.ender_chest_folder(minecraft_root), utils.TESTING_INSTANCES)
        warnings = [
            record for record in caplog.records if record.levelno >= logging.WARNING
        ]
        assert len(warnings) == 0

        assert resource_path.readlink().name == "null"
