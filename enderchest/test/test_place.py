"""Tests around instance-linking functionality"""
import itertools
import logging
import os
import re
from collections import defaultdict
from pathlib import Path

import pytest

from enderchest import ShulkerBox
from enderchest import filesystem as fs
from enderchest import gather, place
from enderchest import shulker_box as sb
from enderchest.loggers import IMPORTANT

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

    def test_max_depth_of_two_returns_subdirectories(self, minecraft_root) -> None:
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

    def test_place_exits_when_there_is_no_enderchest(self, minecraft_root, caplog):
        placements = place.place_ender_chest(minecraft_root.parent)
        assert len(caplog.records) == 1
        assert (
            caplog.records[0].levelno,
            caplog.records[0].message.split(" from")[0],  # hacky "startswith"
        ) == (logging.ERROR, "Could not load EnderChest")

        assert placements == {}

    @pytest.mark.parametrize(
        "error_handling",
        ("abort", "ignore", "skip", "skip-instance", "skip-shulker-box"),
    )
    def test_place_handles_error_when_an_instance_is_missing(
        self, minecraft_root, error_handling, caplog
    ):
        instance_folder = minecraft_root / "instances" / "axolotl"
        safe_keeping = minecraft_root / "axolotl.bkp"

        instance_folder.rename(safe_keeping)

        try:
            placements = place.place_ender_chest(
                minecraft_root, error_handling=error_handling
            )
        finally:
            safe_keeping.rename(instance_folder)

        errors = [record for record in caplog.records if record.levelname == "ERROR"]
        assert errors[0].msg.startswith("No minecraft instance exists at")
        assert placements.get("axolotl", {}) == {}

    @pytest.mark.parametrize("relative", (True, False), ids=("relative", "absolute"))
    @utils.parametrize_over_instances("official", "axolotl")
    def test_respects_the_relative_parameter(self, minecraft_root, instance, relative):
        placements = place.place_ender_chest(minecraft_root, relative=relative)
        instance_folder = utils.resolve(instance.root, minecraft_root)

        assert placements[instance.name][Path("logs")] == ["global"]
        assert (instance_folder / "logs").readlink().is_absolute() is (not relative)

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_replaces_empty_folders(self, minecraft_root, instance):
        placements = place.place_ender_chest(minecraft_root)
        instance_folder = utils.resolve(instance.root, minecraft_root)

        assert placements[instance.name][Path("logs")] == ["global"]

        # and to be sure
        assert (instance_folder / "logs").resolve() == (
            minecraft_root / "EnderChest" / "global" / "logs"
        ).resolve()

        # finally, just to be explicit
        assert (instance_folder / "logs" / "bumpona.log").read_text(
            "utf-8"
        ).splitlines()[0] == "Like a bump on a bump on a log, baby."

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_is_able_to_place_files(self, minecraft_root, instance):
        # including in directories that didn't previously exist!
        placements = place.place_ender_chest(minecraft_root)

        instance_folder = utils.resolve(instance.root, minecraft_root)

        assert not (instance_folder / "config").is_symlink()

        resource_path = Path("config") / "iris.properties"
        assert placements[instance.name][resource_path] == ["global"]

        # and to be sure
        assert (instance_folder / resource_path).resolve() == (
            minecraft_root / "EnderChest" / "global" / resource_path
        )

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_doesnt_choke_on_relative_root(
        self, minecraft_root, instance, monkeypatch
    ):
        monkeypatch.chdir(minecraft_root.parent)
        placements = place.place_ender_chest(Path(minecraft_root.name))

        instance_folder = utils.resolve(instance.root, minecraft_root)

        assert not (instance_folder / "config").is_symlink()

        resource_path = Path("config") / "iris.properties"
        assert placements[instance.name][resource_path] == ["global"]

        # and to be sure
        assert (instance_folder / resource_path).resolve() == (
            minecraft_root / "EnderChest" / "global" / resource_path
        )

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_is_able_to_place_root_level_files(self, minecraft_root, instance):
        placements = place.place_ender_chest(minecraft_root)

        instance_folder = utils.resolve(instance.root, minecraft_root)

        assert placements[instance.name][Path("usercache.json")] == ["global"]

        # and to be sure
        assert (instance_folder / "usercache.json").resolve() == (
            minecraft_root / "EnderChest" / "global" / "usercache.json"
        )

        # finally, just to be explicit
        assert (
            instance_folder / "usercache.json"
        ).read_text() == "alexander\nmomoa\nbateman\n"

    @utils.parametrize_over_instances("official", "axolotl")
    def test_does_not_place_shulker_config(self, minecraft_root, instance):
        placements = place.place_ender_chest(minecraft_root)

        instance_folder = utils.resolve(instance.root, minecraft_root)

        assert placements[instance.name].get(Path(fs.SHULKER_BOX_CONFIG_NAME), []) == []

        # and to be sure
        assert not (instance_folder / fs.SHULKER_BOX_CONFIG_NAME).exists()

    @utils.parametrize_over_instances("bee")
    def test_shulker_configs_can_be_placed_if_you_really_want(
        self, minecraft_root, instance
    ):
        # it's explicitly overridden in the forge config
        utils.pre_populate_enderchest(
            minecraft_root / "EnderChest", utils.OPTIFINE_SHULKER
        )
        placements = place.place_ender_chest(minecraft_root)

        instance_folder = utils.resolve(instance.root, minecraft_root)

        assert placements[instance.name][Path(fs.SHULKER_BOX_CONFIG_NAME)] == [
            "optifine"
        ]

        # and to be sure
        assert (
            instance_folder / fs.SHULKER_BOX_CONFIG_NAME
        ).resolve() == fs.shulker_box_config(minecraft_root, "optifine")

    @utils.parametrize_over_instances("official", "axolotl")
    def test_link_folder_can_be_a_symlink(self, minecraft_root, instance):
        placements = place.place_ender_chest(minecraft_root)

        instance_folder = utils.resolve(instance.root, minecraft_root)

        assert placements[instance.name][Path("crash-reports")] == ["global"]
        assert Path("crash-reports") / "20230524.log" not in placements[instance.name]

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

    @pytest.mark.parametrize("link_type", ("absolute", "relative"))
    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_places_symlinks(self, minecraft_root, instance, link_type):
        placements = place.place_ender_chest(
            minecraft_root, relative=link_type == "relative"
        )

        instance_folder = utils.resolve(instance.root, minecraft_root)
        save_path = Path("saves") / "test"

        assert placements[instance.name][save_path] == ["global"]
        assert save_path / "level.dat" not in placements[instance.name]

        # the counterpoint to the whole "one assertion per test" rule--this
        # is a cascading case of figuring way of figuring out just how badly
        # the impl is borked

        assert (instance_folder / save_path).exists()
        assert (instance_folder / save_path / "level.dat").exists()
        assert (
            instance_folder / save_path / "level.dat"
        ).read_text() == "hello world\n"

        assert (instance_folder / save_path).is_symlink()
        assert not (instance_folder / save_path / "level.dat").is_symlink()

        assert (instance_folder / save_path / "level.dat").resolve() == (
            minecraft_root / "worlds" / "testbench" / "level.dat"
        )

    @utils.parametrize_over_instances("official", "axolotl")
    def test_absolute_symlinks_fully_resolve_target(self, minecraft_root, instance):
        placements = place.place_ender_chest(minecraft_root, relative=False)

        instance_folder = utils.resolve(instance.root, minecraft_root)
        save_path = Path("saves") / "test"

        link_target = os.path.abspath(os.readlink(instance_folder / save_path))

        assert placements[instance.name][save_path] == ["global"]
        assert save_path / "level.dat" not in placements[instance.name]

        # Windows shenanigans: https://bugs.python.org/issue42957
        if link_target.startswith(("\\\\?\\", "\\??\\")):  # pragma: no cover
            link_target = link_target[4:]

        assert link_target == str(minecraft_root / "worlds" / "testbench")

    @utils.parametrize_over_instances("axolotl", "bee")
    def test_place_cleans_up_broken_symlinks_by_default(self, minecraft_root, instance):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        broken_link = instance_folder / "shaderpacks" / "Seuss CitH.zip.txt"
        broken_link.symlink_to(minecraft_root / "i-do-not-exist.txt")
        assert broken_link in broken_link.parent.iterdir()

        _ = place.place_ender_chest(minecraft_root)

        assert broken_link not in broken_link.parent.iterdir()

    @utils.parametrize_over_instances("axolotl")
    def test_place_can_be_told_to_leave_broken_links_alone(
        self, minecraft_root, instance
    ):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        broken_link = instance_folder / "shaderpacks" / "Seuss CitH.zip.txt"
        broken_link.symlink_to(minecraft_root / "i-do-not-exist.txt")
        assert broken_link in broken_link.parent.iterdir()

        _ = place.place_ender_chest(minecraft_root, keep_broken_links=True)

        assert broken_link in broken_link.parent.iterdir()

    @pytest.mark.parametrize("link_type", ("absolute", "relative"))
    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_cleans_up_stale_symlinks_by_default(
        self, minecraft_root, instance, link_type
    ):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        old_box = fs.shulker_box_root(minecraft_root, "Old Man Shulker")
        old_box.mkdir()
        old_file = old_box / "i-do-exist.txt"
        old_file.write_text("Hello there\n")
        # no config file means it's not actually / no longer a shulker box

        stale_link = instance_folder / "old-file.txt"
        if link_type == "absolute":
            stale_link.symlink_to(old_file)
        else:
            stale_link.symlink_to(os.path.relpath(old_file, stale_link.parent))

        _ = place.place_ender_chest(minecraft_root)

        assert stale_link not in stale_link.parent.iterdir()

        # but make sure the original file is okay
        assert old_file.read_text() == "Hello there\n"

    @pytest.mark.parametrize("link_type", ("absolute", "relative"))
    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_will_not_remove_links_pointing_outside_of_enderchest(
        self,
        minecraft_root,
        instance,
        link_type,
    ):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        old_file = minecraft_root / "workspace" / "i-do-exist.txt"
        old_file.write_text("Hello there\n")

        stale_link = instance_folder / "old_file.txt"
        if link_type == "absolute":
            stale_link.symlink_to(old_file)
        else:
            stale_link.symlink_to(os.path.relpath(old_file, stale_link.parent))

        _ = place.place_ender_chest(minecraft_root)

        assert stale_link in stale_link.parent.iterdir()

    @pytest.mark.parametrize("link_type", ("absolute", "relative"))
    @utils.parametrize_over_instances("official", "axolotl")
    def test_stale_link_cleaning_is_based_on_direct_target(
        self,
        minecraft_root,
        instance,
        link_type,
    ):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        working_file = minecraft_root / "workspace" / "i-do-exist.txt"
        working_file.write_text("Hello there\n")

        box_link = fs.shulker_box_root(minecraft_root, "some_box") / "valid.txt"
        box_link.parent.mkdir()
        box_link.symlink_to(working_file)

        link_link = instance_folder / "valid.txt"
        if link_type == "absolute":
            link_link.symlink_to(box_link)
        else:
            link_link.symlink_to(os.path.relpath(box_link, link_link.parent))

        _ = place.place_ender_chest(minecraft_root)

        assert link_link not in link_link.parent.iterdir()

        # and then just make sure that the originals are okay
        assert working_file.read_text() == "Hello there\n"
        assert box_link.resolve() == working_file

    @pytest.mark.parametrize("link_type", ("absolute", "relative"))
    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_can_be_told_to_leave_stale_links_alone(
        self,
        minecraft_root,
        instance,
        link_type,
    ):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        old_box = fs.shulker_box_root(minecraft_root, "Old Man Shulker")
        old_box.mkdir()
        old_file = old_box / "i-do-exist.txt"
        old_file.write_text("Hello there")

        stale_link = instance_folder / "old-file.txt"
        if link_type == "absolute":
            stale_link.symlink_to(old_file)
        else:
            stale_link.symlink_to(os.path.relpath(old_file, stale_link.parent))

        _ = place.place_ender_chest(minecraft_root, keep_stale_links=True)

        assert stale_link in stale_link.parent.iterdir()

    @utils.parametrize_over_instances("official", "axolotl")
    @pytest.mark.parametrize(
        "error_handling",
        ("abort", "ignore", "skip", "skip-instance", "skip-shulker-box"),
    )
    def test_place_will_not_overwrite_a_non_empty_folder(
        self,
        minecraft_root,
        instance,
        caplog,
        error_handling,
    ):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        resource_path = Path("screenshots") / "thumbs.db"
        existing_file = instance_folder / resource_path
        existing_file.write_text("opposable")

        placements = place.place_ender_chest(
            minecraft_root, error_handling=error_handling
        )
        assert placements[instance.name].get(resource_path, []) == []

        error_log = "\n".join(
            record.msg for record in caplog.records if record.levelno == logging.ERROR
        )
        assert re.search(
            rf"{instance.name}((.|\n)*)screenshots((.|\n)*)empty", error_log
        )

        # make sure the file is still there afterward
        assert existing_file.exists()
        assert existing_file.resolve() == existing_file
        assert existing_file.read_text() == "opposable"

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_will_not_overwrite_a_file(self, minecraft_root, instance, caplog):
        instance_folder = utils.resolve(instance.root, minecraft_root)
        resource_path = Path("usercache.json")
        existing_file = instance_folder / resource_path
        existing_file.write_text("isaacs\n")

        placements = place.place_ender_chest(minecraft_root)
        assert placements[instance.name].get(resource_path, []) == []

        error_log = "\n".join(
            record.msg for record in caplog.records if record.levelname == "ERROR"
        )
        assert re.search(
            rf"{instance.name}((.|\n)*)usercache.json((.|\n)*)exists", error_log
        )

        # make sure the file is still there afterward
        assert existing_file.exists()
        assert existing_file.resolve() == existing_file
        assert existing_file.read_text() == "isaacs\n"

    @utils.parametrize_over_instances("official", "axolotl")
    def test_place_will_overwrite_an_existing_symlink(self, minecraft_root, instance):
        # this also tests that place will place files inside of a symlinked folder
        instance_folder = utils.resolve(instance.root, minecraft_root)
        original_target = minecraft_root / "workspace" / "teavsrp_lite.zip"
        original_target.write_text("I will trade you these\nfor less of these\n")
        resource_path = Path("resourcepacks") / "TEAVSRP.zip"
        existing_symlink = instance_folder / resource_path
        existing_symlink.symlink_to(original_target)

        placements = place.place_ender_chest(minecraft_root)
        assert placements[instance.name][resource_path] == ["global"]

        assert existing_symlink.read_text() == "Breaking News!\n"
        assert (
            existing_symlink.resolve()
            == (minecraft_root / "EnderChest" / "global" / resource_path).resolve()
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

    @pytest.mark.parametrize(
        "star_instances, star_tags",
        itertools.product(*((False, True),) * 2),
        ids=("", "tags=*", "instances=*", "instances=*,tags=*"),
    )
    def test_shulker_box_with_no_match_conditions_matches_everything(
        self, star_instances, star_tags
    ):
        match_criteria = []
        if star_instances:
            match_criteria.append(("instances", ("*",)))
        if star_tags:
            match_criteria.append(("tags", ("*",)))

        global_shulker = ShulkerBox(
            0, "global", Path("ignoreme"), tuple(match_criteria), ()
        )

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
        # though in this case the values would have been normalized
        loader_matching_shulker = ShulkerBox(
            0,
            "forge instances",
            Path("ignoreme"),
            (("modloader", ("forge",)),),
            (),
        )

        assert self.matchall(loader_matching_shulker) == ["bee"]

    def test_loader_matching_treats_empty_string_as_vanilla(self):
        loader_matching_shulker = ShulkerBox(
            0,
            "Vanilla Only",
            Path("ignoreme"),
            (("modloader", ("",)),),
            (),
        )

        assert self.matchall(loader_matching_shulker) == ["official", "axolotl"]

    def test_loader_matching_accepts_wildcards(self):
        loader_matching_shulker = ShulkerBox(
            0,
            "Everybody",
            Path("ignoreme"),
            (("modloader", ("*",)),),
            (),
        )

        assert self.matchall(loader_matching_shulker) == [
            "official",
            "axolotl",
            "bee",
            "Chest Boat",
            "Drowned",
        ]

    def test_loader_matching_knows_how_to_interpret_fabric_like(self, tmp_path):
        (tmp_path / "shulker.cfg").write_text("[modloader]\nFabric-Like\n")

        loader_matching_shulker = ShulkerBox.from_cfg(tmp_path / "shulker.cfg")

        instances = [
            utils.instance("match_me", Path("foo"), modloader="Fabric Loader"),
            utils.instance("dont-match-me", Path("blah"), modloader="Fabulous Loader"),
            utils.instance("match me too", Path("bruh"), modloader="Quilt Loader"),
        ]

        assert [
            instance.name
            for instance in instances
            if loader_matching_shulker.matches(instance)
        ] == ["match_me", "match me too"]

    def test_loader_checks_multi_argument(self):
        loader_matching_shulker = ShulkerBox(
            0,
            "Fabric Instances",
            Path("ignoreme"),
            (
                (
                    "modloader",
                    (
                        "",
                        "*bric*",
                    ),
                ),
            ),
            (),
        )

        assert self.matchall(loader_matching_shulker) == [
            "official",
            "axolotl",
            "Chest Boat",
        ]

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
                ("modloader", ("Forge", "Fabric Loader")),
                ("tags", ("vanilla*",)),
                ("instances", ("official", "axolotl", "bee", "Chest Boat")),
            ),
            (),
        )
        assert self.matchall(multi_condition_shulker) == ["Chest Boat"]


@pytest.mark.usefixtures("multi_box_setup_teardown")
class TestMultiShulkerPlacing:
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
        _ = place.place_ender_chest(minecraft_root, error_handling=error_handling)
        # TODO: test placements dict

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
        resource_path = Path("resourcepacks") / "stuff.zip"
        placements = place.place_ender_chest(
            minecraft_root, error_handling=error_handling
        )

        assert placements["bee"][resource_path] == ["global", "optifine"]

        assert (
            minecraft_root / "instances" / "bee" / ".minecraft" / resource_path
        ).read_text() == "optifine-optimized!"

    def test_default_behavior_is_to_stop_at_first_error(self, minecraft_root, caplog):
        _ = place.place_ender_chest(minecraft_root)

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

    @pytest.mark.parametrize("prompt", (False, True), ids=["", "prompted"])
    def test_ignore_failures(
        self, home, minecraft_root, prompt, monkeypatch, caplog, capsys
    ):
        if prompt:
            monkeypatch.setattr("builtins.input", utils.scripted_prompt(("c",)))

        placements = place.place_ender_chest(
            minecraft_root,
            error_handling="prompt" if prompt else "ignore",
            relative=False,
        )
        _ = capsys.readouterr()  # suppress outputs

        assert placements["official"].get(Path("options.txt"), []) == []
        assert placements["official"][Path("mods") / "FoxNap.jar"] == ["1.19"]

        errors = [
            i for i, record in enumerate(caplog.records) if record.levelname == "ERROR"
        ]

        assert len(errors) == 1
        error_idx = errors[0]
        assert "options.txt already exists" in caplog.records[error_idx].msg

        # note: there's actually no guarantee that this link didn't generate
        #       before the failure...
        assert (home / ".minecraft" / "mods" / "FoxNap.jar").is_symlink()  # and exists

    @pytest.mark.parametrize("prompt", (False, True), ids=["", "prompted"])
    def test_skip_match(
        self, home, minecraft_root, prompt, monkeypatch, caplog, capsys
    ):
        if prompt:
            monkeypatch.setattr("builtins.input", utils.scripted_prompt(("m",)))

        placements = place.place_ender_chest(
            minecraft_root, error_handling="prompt" if prompt else "skip"
        )
        _ = capsys.readouterr()  # suppress outputs

        assert placements["official"].get(Path("options.txt"), []) == []
        assert placements["official"][Path("data") / "achievements.txt"] == ["vanilla"]

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

    @pytest.mark.parametrize("prompt", (False, True), ids=["", "prompted"])
    def test_skip_instance(self, home, minecraft_root, prompt, monkeypatch, capsys):
        if prompt:
            monkeypatch.setattr("builtins.input", utils.scripted_prompt(("i",)))

        placements = place.place_ender_chest(
            minecraft_root, error_handling="prompt" if prompt else "skip-instance"
        )
        _ = capsys.readouterr()  # suppress outputs

        assert placements["official"].get(Path("options.txt"), []) == []
        assert placements["Chest Boat"][Path("options.txt")] == ["1.19"]

        assert (
            minecraft_root / "instances" / "chest-boat" / ".minecraft" / "options.txt"
        ).read_text() == "autoJump:true"
        assert not (home / ".minecraft" / "data" / "achievements.txt").exists()

    @pytest.mark.parametrize("prompt", (False, True), ids=["", "prompted"])
    def test_skip_shulker_box(self, home, minecraft_root, prompt, monkeypatch, capsys):
        if prompt:
            monkeypatch.setattr("builtins.input", utils.scripted_prompt(("s",)))

        placements = place.place_ender_chest(
            minecraft_root, error_handling="prompt" if prompt else "skip-shulker"
        )
        _ = capsys.readouterr()  # suppress outputs

        assert placements["official"].get(Path("options.txt"), []) == []
        assert placements["Chest Boat"].get(Path("options.txt"), []) == []

        assert (
            home / ".minecraft" / "data" / "achievements.txt"
        ).read_text() == "Spelled acheivements correctly!"

        assert not (
            minecraft_root / "instances" / "chest-boat" / ".minecraft" / "options.txt"
        ).exists()

    def test_raise_on_invalid_error_handling_arg(self, home, minecraft_root, caplog):
        with pytest.raises(ValueError, match="Unrecognized error-handling method"):
            _ = place.place_ender_chest(minecraft_root, error_handling="not a thing")

    def test_prompt_and_quit(self, home, minecraft_root, caplog, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", utils.scripted_prompt(("q",)))

        place.place_ender_chest(minecraft_root, error_handling="prompt")
        _ = capsys.readouterr()  # suppress outputs

        errors = [
            i for i, record in enumerate(caplog.records) if record.levelname == "ERROR"
        ]
        assert len(errors) == 2
        error_idx = errors[0]
        assert "options.txt already exists" in caplog.records[error_idx].msg

        # and then make sure that it actually did abort

        assert not (home / ".minecraft" / "data" / "achievements.txt").exists()

    def test_prompt_and_retry(self, home, minecraft_root, caplog, monkeypatch) -> None:
        conflict_file_path = home / ".minecraft" / "options.txt"
        safe_keeping = minecraft_root / "options.txt.bkp"

        calls: list[str | None] = []

        def ope_lemme_delete_that(prompt: str | None = None) -> str:
            if calls:
                raise AssertionError("Should have only been called once")
            calls.append(prompt)
            conflict_file_path.rename(safe_keeping)
            return ""

        monkeypatch.setattr("builtins.input", ope_lemme_delete_that)

        try:
            placements = place.place_ender_chest(
                minecraft_root, error_handling="prompt", relative=False
            )
            assert placements["official"].get(Path("options.txt"), []) == ["1.19"]

            errors = [
                i
                for i, record in enumerate(caplog.records)
                if record.levelname == "ERROR"
            ]
            # meta-tests that I found the right line
            assert len(errors) == 1
            error_idx = errors[0]
            assert "options.txt already exists" in caplog.records[error_idx].msg

            assert conflict_file_path.is_symlink()
        finally:
            if safe_keeping.exists():
                conflict_file_path.unlink(missing_ok=True)
                safe_keeping.rename(conflict_file_path)

    def test_invalid_prompt_response_will_just_keep_asking(
        self, home, minecraft_root, caplog, monkeypatch, capsys
    ):
        monkeypatch.setattr(
            "builtins.input",
            utils.scripted_prompt(("blargh", "grahr", "rrgh", "i dunno man", "q")),
        )

        _ = place.place_ender_chest(minecraft_root, error_handling="prompt")
        _ = capsys.readouterr()  # suppress outputs

        errors = [record for record in caplog.records if record.levelname == "ERROR"]
        assert len(errors) == 6

    def test_skip_shulker_box_that_doesnt_match_host(self, home, minecraft_root):
        with fs.shulker_box_config(minecraft_root, "1.19").open("a") as config_file:
            config_file.write(
                """
[hosts]
not-this-chest
"""
            )

        placements = place.place_ender_chest(minecraft_root)
        assert "1.19" not in set(sum(placements["Chest Boat"].values(), []))

        assert not (
            minecraft_root / "instances" / "chest-boat" / ".minecraft" / "options.txt"
        ).exists()

        assert (
            home / ".minecraft" / "data" / "achievements.txt"
        ).read_text() == "Spelled acheivements correctly!"


@pytest.mark.usefixtures("multi_box_setup_teardown")
class TestPlacementCaching:
    def test_place_cache_roundtrip(self, home, minecraft_root, caplog):
        placements = place.place_ender_chest(minecraft_root, error_handling="ignore")
        place.cache_placements(minecraft_root, placements)
        assert placements == place.load_placement_cache(minecraft_root)


@pytest.fixture
def placement_cache(home, minecraft_root, caplog, multi_box_setup_teardown):
    placements = place.place_ender_chest(
        minecraft_root, error_handling="ignore", relative=False
    )
    place.cache_placements(minecraft_root, placements)
    yield place.load_placement_cache(minecraft_root)
    fs.place_cache(minecraft_root).unlink()


class TestResourceTracing:
    @pytest.mark.parametrize(
        "pattern_type",
        ("filename", "resource_path", "glob", "relative_path", "absolute_path"),
    )
    def test_track_down_a_simple_single_file(
        self, placement_cache, minecraft_root, pattern_type
    ):
        instance_folder = Path("instances") / "bee" / ".minecraft"
        resource_path = Path("mods") / "optifine.jar"

        pattern = str(
            {
                "filename": resource_path.name,
                "resource_path": resource_path,
                "glob": "opti*.jar",
                "relative_path": instance_folder / resource_path,
                "absolute_path": (
                    minecraft_root / instance_folder / resource_path
                ).absolute(),
            }[pattern_type]
        )
        assert place.trace_resource(
            minecraft_root,
            pattern,
            instance_name="bee",
            placements=placement_cache,
        ) == [(instance_folder, resource_path, ["optifine"])]

    @pytest.mark.parametrize(
        "pattern_type",
        ("filename", "resource_path", "glob", "relative_path", "absolute_path"),
    )
    def test_track_down_a_single_multi_linked_file(
        self, placement_cache, minecraft_root, pattern_type
    ):
        instance_folder = Path("instances") / "bee" / ".minecraft"
        resource_path = Path("resourcepacks") / "stuff.zip"

        pattern = str(
            {
                "filename": resource_path.name,
                "resource_path": resource_path,
                "glob": "stuff*",
                "relative_path": instance_folder / resource_path,
                "absolute_path": (
                    minecraft_root / instance_folder / resource_path
                ).absolute(),
            }[pattern_type]
        )
        assert place.trace_resource(
            minecraft_root,
            pattern,
            instance_name="bee",
            placements=placement_cache,
        ) == [(instance_folder, resource_path, ["global", "optifine"])]

    def test_track_down_multiple_files(self, placement_cache, minecraft_root):
        instance_folder = Path("instances") / "bee" / ".minecraft"

        assert sorted(
            place.trace_resource(
                minecraft_root,
                "*.zip",
                instance_name="bee",
                placements=placement_cache,
            ),
            key=lambda x: str(x[0] / x[1]).lower(),
        ) == [
            (
                instance_folder,
                Path("resourcepacks") / "stuff.zip",
                ["global", "optifine"],
            ),
            (instance_folder, Path("resourcepacks") / "TEAVSRP.zip", ["global"]),
            (instance_folder, Path("shaderpacks") / "Seuss CitH.zip", ["optifine"]),
        ]

    def test_search_all_instances(self, placement_cache, minecraft_root):
        instance_folders = {
            instance.name: instance.root
            for instance in gather.load_ender_chest_instances(
                minecraft_root, log_level=logging.DEBUG
            )
        }

        mods_folder = Path("mods")

        assert sorted(
            place.trace_resource(
                minecraft_root,
                "*.jar",
                placements=placement_cache,
            ),
            key=lambda x: str(x[0] / x[1]).lower(),
        ) == [
            (instance_folders["bee"], mods_folder / "BME.jar", ["optifine"]),
            (instance_folders["bee"], mods_folder / "optifine.jar", ["optifine"]),
            (instance_folders["Chest Boat"], mods_folder / "FoxNap.jar", ["1.19"]),
            (instance_folders["official"], mods_folder / "FoxNap.jar", ["1.19"]),
        ]


@pytest.mark.usefixtures("multi_box_setup_teardown")
class TestListPlacements:
    @pytest.mark.parametrize("fail_type", ("no_cache", "bad_cache"))
    def test_if_no_cache_then_suggest_running_place(
        self, minecraft_root, fail_type, caplog
    ):
        if fail_type == "bad_cache":
            fs.place_cache(minecraft_root).write_text("This is not a json")

        place.list_placements(minecraft_root, pattern="*")

        errors = [record for record in caplog.records if record.levelname == "ERROR"]

        assert len(errors) == 1
        assert "enderchest place" in errors[0].message

    @pytest.mark.usefixtures("placement_cache")
    def test_errors_out_if_no_such_instance(self, minecraft_root, caplog):
        place.list_placements(minecraft_root, pattern="*", instance_name="utopia")

        errors = [record for record in caplog.records if record.levelname == "ERROR"]

        assert len(errors) == 1
        assert "No instance named" in errors[0].message

    @pytest.mark.usefixtures("placement_cache")
    def test_warns_if_no_matches(self, minecraft_root, caplog):
        place.list_placements(minecraft_root, pattern="nemo")

        problems = [
            record
            for record in caplog.records
            if record.levelname in ("WARNING", "ERROR")
        ]

        assert len(problems) == 1
        assert problems[0].levelname == "WARNING"
        assert (
            "Note: this command does not check inside linked folders."
            in problems[0].message
        )

    @pytest.mark.usefixtures("placement_cache")
    def test_only_top_priority_box_is_important(self, minecraft_root, caplog):
        place.list_placements(minecraft_root, pattern="stuff.zip", instance_name="bee")

        logs = defaultdict(list)
        for record in caplog.records:
            logs[record.levelno].append(record)

        assert len(logs[logging.ERROR]) == len(logs[logging.WARNING]) == 0

        assert len(logs[IMPORTANT]) == 2 and len(logs[logging.INFO]) == 1
        assert all(
            (
                "resolves to" in logs[IMPORTANT][0].message,
                "optifine" in logs[IMPORTANT][1].args,
                "global" in logs[logging.INFO][0].args,
            )
        )

    def test_warns_if_a_symlink_no_longer_exists(
        self, minecraft_root, caplog, placement_cache
    ):
        placement_cache["Chest Boat"][Path("config") / "BME" / "options.txt"] = [
            "optifine"
        ]
        place.cache_placements(minecraft_root, placement_cache)

        place.list_placements(
            minecraft_root, pattern="options.txt", instance_name="Chest Boat"
        )

        logs = defaultdict(list)
        for record in caplog.records:
            logs[record.levelno].append(record)

        assert len(logs[logging.ERROR]) == 0 and len(logs[logging.INFO]) == 0

        assert len(logs[logging.WARNING]) == 1 and len(logs[IMPORTANT]) == 3

        assert all(
            (
                "no longer exists" in logs[logging.WARNING][0].message,
                "optifine" in logs[IMPORTANT][0].args,
                "resolves to" in logs[IMPORTANT][1].message,
                "1.19" in logs[IMPORTANT][2].args,
            )
        ) or all(  # doesn't matter which comes first
            (
                "resolves to" in logs[IMPORTANT][0].message,
                "1.19" in logs[IMPORTANT][1].args,
                "no longer exists" in logs[logging.WARNING][0].message,
                "optifine" in logs[IMPORTANT][2].args,
            )
        )
