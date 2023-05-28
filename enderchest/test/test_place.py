"""Tests around instance-linking functionality"""
import os
import re
from pathlib import Path

import pytest

from enderchest import ShulkerBox
from enderchest import filesystem as fs
from enderchest import place
from enderchest import shulker_box as sb

from . import utils


class TestRglob:
    def test_max_depth_of_one_is_equivalent_to_a_plain_glob(self, minecraft_root):
        glob = sorted(minecraft_root.iterdir())
        assert len(glob) > 0  # meta-test

        assert glob == sorted(place._rglob(minecraft_root, 1))

    def test_max_depth_of_zero_finds_all_files_in_path(self, minecraft_root):
        search_dir = minecraft_root / "workspace"  # choose someplace with no links
        rglob = sorted([path for path in search_dir.rglob("*") if not path.is_dir()])
        assert len(rglob) > 0  # meta-test

        assert rglob == sorted(place._rglob(minecraft_root / "workspace", 0))

    def test_max_depth_of_two_returns_subdirectories(self, minecraft_root):
        instances_folder = minecraft_root / "instances"
        expected: list[Path] = [instances_folder / "instgroups.json"]
        for instance in utils.TESTING_INSTANCES[1:]:
            expected.extend(
                (
                    instances_folder / instance.root.parent.name / ".minecraft",
                    instances_folder / instance.root.parent.name / "instance.cfg",
                    instances_folder / instance.root.parent.name / "mmc-pack.json",
                )
            )
        expected.sort()

        assert expected == sorted(place._rglob(instances_folder, 2))


class TestSingleShulkerPlace:
    """Test the simplest case of linking--where the files in the shulker should
    go into every instance"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, minecraft_root, home):
        """Setup / teardown for this test class"""
        chest_folder = minecraft_root / "EnderChest"
        utils.pre_populate_enderchest(chest_folder, utils.GLOBAL_SHULKER)

        do_not_touch = {
            (chest_folder / "global" / "logs" / "bumpona.log"): (
                "Like a bump on a bump on a log, baby.\n"
                "Like I'm in a fist fight with a fog, baby.\n"
                "Step-ball-change and a pirouette.\n"
                "And I regret, I regret.\n"
            ),
        }

        for path, contents in do_not_touch.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)

        yield

        # check on teardown that all those "do_not_touch" files are untouched
        for path, contents in do_not_touch.items():
            assert path.read_text() == contents

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_replaces_empty_folders(self, minecraft_root, instance):
        place.place_ender_chest(minecraft_root)
        instance_folder = utils.resolve(instance.root, minecraft_root)

        assert (instance_folder / "logs").resolve() == (
            minecraft_root / "EnderChest" / "global" / "logs"
        ).resolve()

        # also, just to be explicit
        assert (instance_folder / "logs" / "bumpona.log").exists()

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_is_able_to_place_files(self, minecraft_root, instance):
        # including in directories that didn't previously exist!
        place.place_ender_chest(minecraft_root)

        instance_folder = utils.resolve(instance.root, minecraft_root)

        assert not (instance_folder / "config").is_symlink()

        assert (instance_folder / "config" / "iris.properties").resolve() == (
            minecraft_root / "EnderChest" / "global" / "config" / "iris.properties"
        )

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_is_able_to_place_root_level_files(self, minecraft_root, instance):
        place.place_ender_chest(minecraft_root)

        instance_folder = utils.resolve(instance.root, minecraft_root)

        assert (
            instance_folder / "usercache.json"
        ).read_text() == "alexander\nmomoa\nbateman\n"

        assert (instance_folder / "usercache.json").resolve() == (
            minecraft_root / "EnderChest" / "global" / "usercache.json"
        )

    @utils.parametrize_over_instances("official", "axolotl")
    def test_does_not_place_shulker_config(self, minecraft_root, instance):
        place.place_ender_chest(minecraft_root)

        instance_folder = utils.resolve(instance.root, minecraft_root)

        assert not (instance_folder / fs.SHULKER_BOX_CONFIG_NAME).exists()

    @utils.parametrize_over_instances("official", "axolotl")
    def test_link_folder_can_be_a_symlink(self, minecraft_root, instance):
        place.place_ender_chest(minecraft_root)

        instance_folder = utils.resolve(instance.root, minecraft_root)

        # the counterpoint to the whole "one assertion per test" rule--this
        # is a cascading case of figuring way of figuring out just how badly
        # the impl is borked

        assert (instance_folder / "crash-reports").exists()
        assert (instance_folder / "crash-reports" / "20230524.log").read_text() == (
            "ERROR: Everything is broken\n" "WARNING: And somehow also on fire\n"
        )

        assert (instance_folder / "crash-reports").is_symlink()

        assert (instance_folder / "crash-reports" / "20230524.log").resolve() == (
            minecraft_root / "crash-reports" / "20230524.log"
        )

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_places_symlinks(self, minecraft_root, instance):
        place.place_ender_chest(minecraft_root)

        instance_folder = utils.resolve(instance.root, minecraft_root)

        # the counterpoint to the whole "one assertion per test" rule--this
        # is a cascading case of figuring way of figuring out just how badly
        # the impl is borked

        assert (instance_folder / "saves" / "test").exists()
        assert (instance_folder / "saves" / "test" / "level.dat").exists()
        assert (
            instance_folder / "saves" / "test" / "level.dat"
        ).read_text() == "hello world\n"

        assert not (instance_folder / "saves" / "test" / "level.dat").is_symlink()

        assert (instance_folder / "saves" / "test" / "level.dat").resolve() == (
            minecraft_root / "worlds" / "testbench" / "level.dat"
        )

    @utils.parametrize_over_instances("axolotl", "bee")
    def test_place_cleans_up_broken_symlinks_by_default(self, minecraft_root, instance):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        broken_link = instance_folder / "shaderpacks" / "Seuss CitH.zip.txt"
        broken_link.symlink_to(minecraft_root / "i-do-not-exist.txt")
        assert broken_link in broken_link.parent.iterdir()

        place.place_ender_chest(minecraft_root)

        assert broken_link not in broken_link.parent.iterdir()

    @utils.parametrize_over_instances("axolotl")
    def test_place_can_be_told_to_leave_broken_links_alone(
        self, minecraft_root, instance
    ):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        broken_link = instance_folder / "shaderpacks" / "Seuss CitH.zip.txt"
        broken_link.symlink_to(minecraft_root / "i-do-not-exist.txt")
        assert broken_link in broken_link.parent.iterdir()

        place.place_ender_chest(minecraft_root, cleanup=False)

        assert broken_link in broken_link.parent.iterdir()

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_will_not_overwrite_a_non_empty_folder(
        self, minecraft_root, instance, caplog
    ):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        existing_file = instance_folder / "screenshots" / "thumbs.db"
        existing_file.write_text("opposable")

        place.place_ender_chest(minecraft_root)

        error_log = "\n".join(
            record.msg for record in caplog.records if record.levelname == "ERROR"
        )
        assert re.search(
            rf"{instance.name}((.|\n)*)screenshots((.|\n)*)empty", error_log
        )

        # make sure the file is still there afterwards
        assert existing_file.exists()
        assert existing_file.resolve() == existing_file
        assert existing_file.read_text() == "opposable"

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_will_not_overwrite_a_file(self, minecraft_root, instance, caplog):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        existing_file = instance_folder / "usercache.json"
        existing_file.write_text("isaacs\n")

        place.place_ender_chest(minecraft_root)

        error_log = "\n".join(
            record.msg for record in caplog.records if record.levelname == "ERROR"
        )
        assert re.search(
            rf"{instance.name}((.|\n)*)usercache.json((.|\n)*)exists", error_log
        )

        # make sure the file is still there afterwards
        assert existing_file.exists()
        assert existing_file.resolve() == existing_file
        assert existing_file.read_text() == "isaacs\n"

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_will_overwrite_an_existing_symlink(self, minecraft_root, instance):
        # this also tests that place will place files inside of a symlinked folder
        instance_folder = utils.resolve(instance.root, minecraft_root)
        original_target = minecraft_root / "workspace" / "teavsrp_lite.zip"
        original_target.write_text("I will trade you these\nfor less of these\n")
        existing_symlink = instance_folder / "resourcepacks" / "TEAVSRP.zip"
        existing_symlink.symlink_to(original_target)

        place.place_ender_chest(minecraft_root)

        assert existing_symlink.read_text() == "Breaking News!\n"
        assert (
            existing_symlink.resolve()
            == (
                minecraft_root
                / "EnderChest"
                / "global"
                / "resourcepacks"
                / "TEAVSRP.zip"
            ).resolve()
        )

        # also make sure the original file is okay
        assert (
            original_target.read_text() == "I will trade you these\nfor less of these\n"
        )


class TestMatchesVersion:
    @pytest.mark.parametrize(
        "version", ("1.19.4", "1.20-pre6", "23w13a_or_b", "not even trying")
    )
    def test_simple_equality_checks(self, version):
        assert sb._matches_version(version, version)

    @pytest.mark.parametrize(
        "version_spec",
        ("1.19", "1.19.*", ">=1.19.0,<1.20"),
        ids=("minor-version", "wildcard", "bounding"),
    )
    def test_version_bounding(self, version_spec):
        assert sb._matches_version(version_spec, "1.19.4")

    @pytest.mark.parametrize(
        "version", ("1.19.4", "1.20-pre6", "23w13a_or_b", "not even trying")
    )
    def test_star_matches_anything(self, version):
        assert sb._matches_version("*", version)

    @pytest.mark.parametrize(
        "version", ("1.20-pre1", "1.20-rc1", "1.20.3-pre16", "1.20-forge")
    )
    def test_prereleases_etc_align_with_their_wildcarded_versions(self, version):
        assert sb._matches_version("1.20*", version)


class TestShulkerInstanceMatching:
    @staticmethod
    def matchall(shulker: ShulkerBox) -> list[str]:
        """Return the names of the testing instances that match the
        provided shulker

        Parameters
        ----------
        shulker : ShulkerBox
            The shulker to test

        Returns
        -------
        list of str
            The names of any testing instances that match the provided shulker
            (ordered in the order they're provided in utils.TESTING_INSTANCES)
        """
        return [
            instance.name
            for instance in utils.TESTING_INSTANCES
            if shulker.matches(instance)
        ]

    def test_shulker_box_with_no_match_conditions_matches_everything(self):
        global_shulker = ShulkerBox(0, "global", Path("ignoreme"), (), ())

        assert self.matchall(global_shulker) == [
            instance.name for instance in utils.TESTING_INSTANCES
        ]

    def test_matching_shulkers_by_instance_name(self):
        name_matching_shulker = ShulkerBox(
            0,
            "name_matching",
            Path("ignoreme"),
            (("instances", ("axolotl", "Chest Boat")),),
            (),
        )

        assert self.matchall(name_matching_shulker) == ["axolotl", "Chest Boat"]

    def test_instance_name_matching_is_exact(self):
        name_matching_shulker = ShulkerBox(
            0,
            "name_matching",
            Path("ignoreme"),
            (("instances", ("Bee", "Chest_Boat")),),
            (),
        )

        assert self.matchall(name_matching_shulker) == []

    def test_matching_shulkers_by_tag(self):
        tag_matching_shulker = ShulkerBox(
            0,
            "modz",
            Path("ignoreme"),
            (("tags", ("modded",)),),
            (),
        )

        assert self.matchall(tag_matching_shulker) == ["bee"]

    def test_tag_matching_ignores_case(self):
        tag_matching_shulker = ShulkerBox(
            0,
            "vanilla",
            Path("ignoreme"),
            (("tags", ("vanilla", "Vanilla Plus")),),
            (),
        )

        assert self.matchall(tag_matching_shulker) == [
            "official",
            "axolotl",
            "Chest Boat",
        ]

    def test_tag_matching_supports_wildcards(self):
        tag_matching_shulker = ShulkerBox(
            0,
            "vanilla-ish",
            Path("ignoreme"),
            (("tags", ("vanilla*",)),),
            (),
        )

        assert self.matchall(tag_matching_shulker) == [
            "official",
            "axolotl",
            "Chest Boat",
        ]

    def test_loader_matching_is_case_insensitive(self):
        loader_matching_shulker = ShulkerBox(
            0,
            "forge instances",
            Path("ignoreme"),
            (("modloader", ("forge",)),),
            (),
        )

        assert self.matchall(loader_matching_shulker) == ["bee"]

    @pytest.mark.parametrize("loader_spec", ("fabric", "quilt/fabric"))
    def test_loader_matching_maps_common_aliases(self, loader_spec):
        loader_matching_shulker = ShulkerBox(
            0,
            "fabric instances",
            Path("ignoreme"),
            (("modloader", (loader_spec,)),),
            (),
        )

        assert self.matchall(loader_matching_shulker) == ["Chest Boat"]

    def test_explicit_version_matching(self):
        minecraft_specific_shulker = ShulkerBox(
            0,
            "votey",
            Path("ignoreme"),
            (("minecraft", ("23w13a_or_b",)),),
            (),
        )

        assert self.matchall(minecraft_specific_shulker) == ["official"]

    @pytest.mark.parametrize(
        "version_spec",
        (
            ("1.19.0", "1.19.1", "1.19.2", "1.19.3", "1.19.4"),
            ("1.19",),
            ("1.19.*",),
            (">=1.19.0,<1.20",),
        ),
        ids=("explicit", "minor-version", "wildcard", "bounding"),
    )
    def test_version_bounding(self, version_spec):
        minecraft_specific_shulker = ShulkerBox(
            0,
            "votey",
            Path("ignoreme"),
            (("minecraft", version_spec),),
            (),
        )

        assert self.matchall(minecraft_specific_shulker) == ["official", "Chest Boat"]

    def test_instance_must_match_all_conditions(self):
        multi_condition_shulker = ShulkerBox(
            0,
            "finnicky",
            Path("ignoreme"),
            (
                ("modloader", ("forge", "fabric")),
                ("tags", ("vanilla*",)),
                ("instances", ("official", "axolotl", "bee", "Chest Boat")),
            ),
            (),
        )
        assert self.matchall(multi_condition_shulker) == ["Chest Boat"]


class TestMultiShulkerPlacing:
    @pytest.fixture(autouse=True)
    def setup_teardown(self, minecraft_root, home):
        """Setup / teardown for this test class"""
        chest_folder = minecraft_root / "EnderChest"
        utils.pre_populate_enderchest(chest_folder, *utils.TESTING_SHULKER_CONFIGS)

        do_not_touch = {
            (chest_folder / "global" / "resourcepacks" / "stuff.zip"): "dfgwhgsadfhsd",
            (chest_folder / "global" / "logs" / "bumpona.log"): (
                "Like a bump on a bump on a log, baby.\n"
                "Like I'm in a fist fight with a fog, baby.\n"
                "Step-ball-change and a pirouette.\n"
                "And I regret, I regret.\n"
            ),
            (chest_folder / "1.19" / "mods" / "FoxNap.jar"): "hello-maestro",
            (chest_folder / "1.19" / "options.txt"): "autoJump:true",
            (
                chest_folder / "vanilla" / "data" / "achievements.txt"
            ): "Spelled acheivements correctly!",
            (chest_folder / "optifine" / "mods" / "optifine"): "sodium4life",
            (chest_folder / "optifine" / "shaderpacks" / "Seuss CitH.zip"): (
                "But those trees! Oh those trees! But those truffula trees!"
                "\nAll resplendent and gorgeous in ray-traced 3Ds"
            ),
            (
                chest_folder / "optifine" / "resourcepacks" / "stuff.zip"
            ): "optifine-optimized!",
            (
                minecraft_root
                / "instances"
                / "bee"
                / ".minecraft"
                / "shaderpacks"
                / "Seuss CitH.zip.txt"
            ): (
                "with settings at max"
                "\nits important to note"
                "\nthe lag is real bad"
                "\nbut just look at that goat!"
            ),
        }

        for path, contents in do_not_touch.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)

        yield

        # check on teardown that all those "do_not_touch" files are untouched
        for path, contents in do_not_touch.items():
            assert path.read_text() == contents

    @pytest.mark.parametrize("error_handling", ("ignore", "skip"))
    @pytest.mark.parametrize(
        "shulker_box, instance, should_match", utils.TESTING_SHULKER_INSTANCE_MATCHES
    )
    def test_multi_shulker_place_correctly_identifies_matches(
        self,
        minecraft_root,
        caplog,
        shulker_box,
        instance,
        should_match,
        error_handling,
    ):
        place.place_ender_chest(minecraft_root, error_handling=error_handling)

        link_log = "\n".join(
            record.msg for record in caplog.records if record.levelname == "INFO"
        )

        assert (
            f'{os.path.join(instance, ".minecraft")} to {shulker_box}' in link_log
        ) is should_match

    @pytest.mark.parametrize("error_handling", ("ignore", "skip"))
    def test_multi_shulker_place_overwrites_overlapping_symlinks(
        self, minecraft_root, error_handling
    ):
        place.place_ender_chest(minecraft_root, error_handling=error_handling)

        assert (
            minecraft_root
            / "instances"
            / "bee"
            / ".minecraft"
            / "resourcepacks"
            / "stuff.zip"
        ).read_text() == "optifine-optimized!"

    def test_default_behavior_is_to_stop_at_first_error(self, minecraft_root, caplog):
        place.place_ender_chest(minecraft_root)

        assert not (
            minecraft_root
            / "instances"
            / "chest_boat"
            / ".minecraft"
            / "mods"
            / "FoxNap.jar"
        ).exists()

        error_log = "\n".join(
            record.msg for record in caplog.records if record.levelname == "ERROR"
        )

        assert error_log.endswith(
            f'{os.path.join("~", ".minecraft", "options.txt")}'  # fricking escape chars
            + " already exists\nAborting"
        )

    def test_skip_match(self, home, minecraft_root, caplog):
        place.place_ender_chest(minecraft_root, error_handling="skip")

        errors = [
            i for i, record in enumerate(caplog.records) if record.levelname == "ERROR"
        ]
        # meta-tests that I found the right line
        assert len(errors) == 1
        error_idx = errors[0]
        assert "options.txt already exists" in caplog.records[error_idx].msg

        assert (
            caplog.records[error_idx + 1].levelname,
            caplog.records[error_idx + 1].msg,
        ) == ("WARNING", "Skipping the rest of this match")

        # and then make sure that it actually did move on

        assert caplog.records[error_idx + 2].levelname == "INFO"
        assert caplog.records[error_idx + 2].msg.startswith("Linking")

        # and now check for a subsequent place

        assert (
            home / ".minecraft" / "data" / "achievements.txt"
        ).read_text() == "Spelled acheivements correctly!"

    def test_skip_instance(self, home, minecraft_root):
        place.place_ender_chest(minecraft_root, error_handling="skip-instance")

        assert (
            minecraft_root / "instances" / "chest-boat" / ".minecraft" / "options.txt"
        ).read_text() == "autoJump:true"
        assert not (home / ".minecraft" / "data" / "achievements.txt").exists()

    def test_skip_shulker_box(self, home, minecraft_root):
        place.place_ender_chest(minecraft_root, error_handling="skip-shulker")

        assert (
            home / ".minecraft" / "data" / "achievements.txt"
        ).read_text() == "Spelled acheivements correctly!"

        assert not (
            minecraft_root / "instances" / "chest-boat" / ".minecraft" / "options.txt"
        ).exists()

    def test_skip_shulker_box_that_doesnt_match_host(self, home, minecraft_root):
        with fs.shulker_box_config(minecraft_root, "1.19").open("a") as config_file:
            config_file.write(
                """
[hosts]
not-this-chest
"""
            )

        place.place_ender_chest(minecraft_root)

        assert not (
            minecraft_root / "instances" / "chest-boat" / ".minecraft" / "options.txt"
        ).exists()

        assert (
            home / ".minecraft" / "data" / "achievements.txt"
        ).read_text() == "Spelled acheivements correctly!"
