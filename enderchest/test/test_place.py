"""Tests around instance-linking functionality"""
from pathlib import Path

import pytest

from enderchest import ShulkerBox, place

from . import utils


class TestSingleShulkerPlace:
    """Test the simplest case of linking--where the files in the shulker should
    go into every instance"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, minecraft_root, home):
        """Setup / teardown for this test class"""
        chest_folder = minecraft_root / "EnderChest"
        utils.pre_populate_enderchest(chest_folder, utils.GLOBAL_SHULKER)

        do_not_touch = {
            (chest_folder / "global" / "resourcepacks" / "stuff.zip"): "dfgwhgsadfhsd",
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
    def test_place_is_willing_to_replace_empty_folders_by_default(
        self, minecraft_root, instance
    ):
        place.place_enderchest(minecraft_root)
        instance_folder = utils.resolve(instance.root, minecraft_root)

        assert (instance_folder / "logs").resolve() == (
            minecraft_root / "EnderChest" / "global" / "logs"
        ).resolve()

        # also, just to be explicit
        assert (instance_folder / "logs" / "bumpona.log").exists()

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_is_able_to_place_individual_files(self, minecraft_root, instance):
        place.place_enderchest(minecraft_root)

        instance_folder = utils.resolve(instance.root, minecraft_root)

        assert not (instance_folder / "resourcepacks").is_symlink()

        assert (instance_folder / "resourcepacks" / "stuff.zip").resolve() == (
            minecraft_root / "EnderChest" / "global" / "resourcepacks" / "stuff.zip"
        )

    @utils.parametrize_over_instances("axolotl", "bee")
    def test_place_cleans_up_broken_symlinks_by_default(self, minecraft_root, instance):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        broken_link = instance_folder / "shaderpacks" / "Seuss CitH.zip.txt"
        broken_link.symlink_to(minecraft_root / "i-do-not-exist.txt")
        assert broken_link in broken_link.parent.glob("*")

        place.place_enderchest(minecraft_root)

        assert broken_link not in broken_link.parent.glob("*")

    @utils.parametrize_over_instances("axolotl")
    def test_place_can_be_told_to_leave_broken_links_alone(
        self, minecraft_root, instance
    ):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        broken_link = instance_folder / "shaderpacks" / "Seuss CitH.zip.txt"
        broken_link.symlink_to(minecraft_root / "i-do-not-exist.txt")
        assert broken_link in broken_link.parent.glob("*")

        place.place_enderchest(minecraft_root, cleanup=False)

        assert broken_link in broken_link.parent.glob("*")

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_will_not_overwrite_a_non_empty_folder(
        self, minecraft_root, instance
    ):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        existing_file = instance_folder / "screenshots" / "thumbs.db"
        existing_file.write_text("opposable")

        with pytest.raises(
            RuntimeError, match=rf"{instance.name}((.|\n)*)screenshots((.|\n)*)empty"
        ):
            place.place_enderchest(minecraft_root)

        # make sure the file is still there afterwards
        assert existing_file.exists()
        assert existing_file.resolve() == existing_file
        assert existing_file.read_text() == "opposable"

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_will_not_overwrite_a_file(self, minecraft_root, instance):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        existing_file = instance_folder / "resourcepacks" / "stuff.zip"
        existing_file.write_text("other_stuff")

        with pytest.raises(
            RuntimeError, match=rf"{instance.name}((.|\n)*)stuff.zip((.|\n)*)exists"
        ):
            place.place_enderchest(minecraft_root)

        # make sure the file is still there afterwards
        assert existing_file.exists()
        assert existing_file.resolve() == existing_file
        assert existing_file.read_text() == "other_stuff"

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_will_overwrite_an_existing_symlink(self, minecraft_root, instance):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        (minecraft_root / "workspace" / "other_stuff.zip").write_text("working stuff")
        existing_symlink = instance_folder / "resourcepacks" / "stuff.zip"
        existing_symlink.symlink_to(minecraft_root / "workspace" / "other_stuff.zip")

        place.place_enderchest(minecraft_root)

        assert (
            existing_symlink.resolve()
            == minecraft_root / "EnderChest" / "global" / "resourcepacks" / "stuff.zip"
        )
        assert existing_symlink.read_text() == "dfgwhgsadfhsd"


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

    def test_tag_matching_is_exact(self):
        tag_matching_shulker = ShulkerBox(
            0,
            "vanilla",
            Path("ignoreme"),
            (("tags", ("vanilla", "Vanilla Plus")),),
            (),
        )

        assert self.matchall(tag_matching_shulker) == ["official", "axolotl"]

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
            (">=1.19,<1.20",),
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
