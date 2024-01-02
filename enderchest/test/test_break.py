"""Tests of the EnderChest uninstallation procedure"""
import logging
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

    @pytest.mark.usefixtures("multi_box_setup_teardown")
    def test_break_allows_you_to_proceed_even_when_there_are_conflicts(
        self, minecraft_root, home, monkeypatch, capsys, caplog
    ):
        script_reader = utils.scripted_prompt([""])
        monkeypatch.setattr("builtins.input", script_reader)

        uninstall.break_ender_chest(minecraft_root)

        _ = capsys.readouterr()  # suppress outputs
        errorish_log = [
            record for record in caplog.records if record.levelno >= logging.WARNING
        ]

        assert (
            errorish_log[0].levelno == logging.ERROR
            and errorish_log[0].message.startswith("Error linking")
            and "options.txt" in errorish_log[0].message
        )

        assert errorish_log[-2].message.startswith("Are you sure")

        assert len(errorish_log) == 3


@pytest.mark.usefixtures("multi_box_setup_teardown")
class TestBreaking:
    @pytest.fixture
    def placement_cache(self, minecraft_root, capsys, caplog):
        """Setup/teardwon for this class"""
        utils.pre_populate_enderchest(
            fs.ender_chest_folder(minecraft_root, check_exists=False),
            *utils.TESTING_SHULKER_CONFIGS
        )
        placement_cache = place.place_ender_chest(
            minecraft_root, relative=False, error_handling="ignore"
        )

        errorish_log = [
            record for record in caplog.records if record.levelno >= logging.WARNING
        ]
        assert len(errorish_log) == 1
        assert (
            errorish_log[0].levelno == logging.ERROR
            and errorish_log[0].message.startswith("Error linking")
            and "options.txt" in errorish_log[0].message
        )

        # assert that the placement cache is clean
        assert not placement_cache["official"].get(Path("options.txt"), [])

        yield placement_cache

        _ = capsys.readouterr()  # suppress outputs

    @pytest.fixture
    def instance_lookup(self, minecraft_root):
        yield {
            instance.name: instance
            for instance in gather.load_ender_chest_instances(
                minecraft_root, logging.DEBUG
            )
        }

    def test_clean_uninstall_emits_no_warnings(
        self, minecraft_root, placement_cache, instance_lookup, caplog
    ):
        uninstall._break(minecraft_root, instance_lookup, placement_cache)
        warnings = [
            record for record in caplog.records if record.levelno >= logging.WARNING
        ]
        assert len(warnings) == 0

    @pytest.mark.parametrize(
        "instance", (instance.name for instance in utils.TESTING_INSTANCES)
    )
    def test_uninstall_replaces_links_with_copies(
        self, minecraft_root, placement_cache, instance_lookup, instance
    ):
        resource_path = instance_lookup[instance].root.expanduser() / "usercache.json"

        # meta-test
        assert resource_path.readlink().is_relative_to(
            fs.ender_chest_folder(minecraft_root)
        )
        uninstall._break(minecraft_root, instance_lookup, placement_cache)

        assert resource_path.exists()
        assert not resource_path.is_symlink()
        assert resource_path.read_text() == "alexander\nmomoa\nbateman\n"

    @pytest.mark.parametrize("instance", ("axolotl", "bee"))
    def test_uninstall_copies_based_on_highest_priority(
        self,
        minecraft_root,
        placement_cache,
        instance_lookup,
        instance,
    ):
        resource_path = (
            instance_lookup[instance].root.expanduser() / "resourcepacks" / "stuff.zip"
        )
        uninstall._break(minecraft_root, instance_lookup, placement_cache)

        assert resource_path.exists()
        assert not resource_path.is_symlink()
        assert (
            resource_path.read_text() == "optifine-optimized!"
            if instance == "bee"
            else "dfgwhgsadfhsd"
        )

    @pytest.mark.parametrize(
        "instance", (instance.name for instance in utils.TESTING_INSTANCES)
    )
    def test_uninstall_replaces_links_pointing_outside_the_chest(
        self, minecraft_root, placement_cache, instance_lookup, instance
    ):
        resource_path = (
            instance_lookup[instance].root.expanduser()
            / "resourcepacks"
            / "TEAVSRP.zip"
        )

        # meta-test
        assert not resource_path.readlink().is_relative_to(
            fs.ender_chest_folder(minecraft_root)
        )

        uninstall._break(minecraft_root, instance_lookup, placement_cache)

        assert resource_path.exists()
        assert not resource_path.is_symlink()
        assert resource_path.read_text() == "Breaking News!\n"

    def test_uninstall_proceeds_past_conflicts(
        self, minecraft_root, instance_lookup, placement_cache, caplog
    ) -> None:
        # though these should be caught during the generation of the placement cache

        # Normally the order of placements cannot be guaranteed, so we can't test
        # match-skips vs. ignores
        # (see: `test_place.py::TestMultiShulkerPlacing::test_ignore_failures
        # but also... # TODO sort `place._rglob`?)
        # but because dicts in Python 3.6/7+ are ordered dicts, we can manipulate
        # the placement cache to GUARANTEE that the conflict happens first
        home_placements: dict[Path, list[str]] = {Path("options.txt"): ["1.19"]}
        home_placements.update(placement_cache["official"])
        placement_cache["official"] = home_placements
        # meta-test
        assert list(placement_cache["official"].keys())[0] == Path("options.txt")

        resource_path = (
            instance_lookup["official"].root.expanduser() / "config" / "iris.properties"
        )

        uninstall._break(minecraft_root, instance_lookup, placement_cache)

        errorish_log = [
            record for record in caplog.records if record.levelno >= logging.WARNING
        ]
        assert len(errorish_log) == 1

        assert "options.txt already exists" in errorish_log[0].message
        assert resource_path.exists()
        assert not resource_path.is_symlink()
        assert resource_path.read_text() == "flower or aperture?\n"

    @pytest.mark.parametrize(
        "instance", (instance.name for instance in utils.TESTING_INSTANCES)
    )
    def test_uninstall_proceeds_past_broken_links(
        self, minecraft_root, instance_lookup, placement_cache, instance, caplog
    ):
        (fs.shulker_box_root(minecraft_root, "global") / "backups").rmdir()

        # should be safe, because the link folders *are* linked deterministically,
        # in the order set by the shulker box config
        resource_path = instance_lookup["Chest Boat"].root.expanduser() / "logs"

        uninstall._break(minecraft_root, instance_lookup, placement_cache)

        errorish_log = [
            record for record in caplog.records if record.levelno >= logging.WARNING
        ]
        assert len(errorish_log) == len(instance_lookup)

        assert all(
            ("No such file or directory" in record.message for record in errorish_log)
        )
        assert resource_path.exists()
        assert not resource_path.is_symlink()
        assert (
            (resource_path / "bumpona.log").read_text("utf-8").startswith("Like a bump")
        )


class TestCLI:
    # TODO

    pass
