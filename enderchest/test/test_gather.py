"""Tests around file discovery and registration"""
import logging
import os
import re
from pathlib import Path

import pytest

from enderchest import craft
from enderchest import filesystem as fs
from enderchest import gather
from enderchest import instance as i

from . import utils


class TestLoadEnderChestInstances:
    def test_bad_folder_just_returns_empty(self, tmp_path, caplog):
        assert gather.load_ender_chest_instances(tmp_path) == []


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
        assert gather.load_shulker_boxes(tmp_path) == []

    def test_warn_for_a_chest_without_boxes(self, tmp_path, caplog):
        root = tmp_path / "nowhere"
        root.mkdir()
        craft.craft_ender_chest(root, remotes=(), overwrite=True)
        _ = gather.load_shulker_boxes(root)

        assert "There are no shulker boxes" in "\n".join(
            (
                record.msg
                for record in caplog.records
                if record.levelno == logging.WARNING
            )
        )

    def test_list_shulker_box_reports_the_boxes_in_order(self, minecraft_root, caplog):
        _ = gather.load_shulker_boxes(minecraft_root)
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
        _ = gather.load_shulker_boxes(Path(minecraft_root.name))
        assert (
            """0. global
  1. 1.19
  2. vanilla
  3. optifine"""
            in caplog.records[-1].msg % caplog.records[-1].args
        )

    def test_list_shulker_box_warns_if_theres_a_bad_box(self, minecraft_root, caplog):
        _ = gather.load_shulker_boxes(minecraft_root)

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
        assert gather.get_shulker_boxes_matching_instance(tmp_path, "outstance") == []

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
            for box in gather.load_shulker_boxes(
                minecraft_root, log_level=logging.DEBUG
            )
        }

        expected = []
        for box_name, mc_name, should_match in utils.TESTING_SHULKER_INSTANCE_MATCHES:
            if mc_name == instance_name_lookup.get(instance_name, instance_name):
                if should_match:
                    expected.append(box_lookup[box_name])

        assert (
            gather.get_shulker_boxes_matching_instance(minecraft_root, instance_name)
            == expected
        )

    @pytest.mark.parametrize(
        "shulker_box_name",
        list({box for _, box, _ in utils.TESTING_SHULKER_INSTANCE_MATCHES}) + ["unown"],
    )
    def test_loading_instances_that_match_boxes(self, minecraft_root, shulker_box_name):
        instance_lookup = {
            mc.name: mc
            for mc in gather.load_ender_chest_instances(
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
            gather.get_instances_matching_shulker_box(minecraft_root, shulker_box_name)
            == expected
        )


class TestGatherInstances:
    @pytest.fixture(autouse=True)
    def setup_teardown(self, minecraft_root, home):
        utils.pre_populate_enderchest(
            fs.ender_chest_folder(minecraft_root, check_exists=False)
        )

        yield

        # tests that with offer-to-update set to False, EnderChest doesn't go rogue
        assert not (home / ".minecraft" / "allowed_symlinks.txt").exists()

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

        assert len(instances) == 4

        assert all(
            [
                i.equals(
                    minecraft_root, instances[idx - 1], utils.TESTING_INSTANCES[idx]
                )
                for idx in range(1, 5)
            ]
        )

    def test_instance_search_doesnt_choke_on_relative_root(
        self, minecraft_root, monkeypatch
    ):
        monkeypatch.chdir(minecraft_root.parent)
        instances = sorted(
            gather.gather_minecraft_instances(
                Path(minecraft_root.name), Path(minecraft_root.name), official=False
            ),
            key=lambda instance: instance.name,
        )

        assert len(instances) == 4

        assert all(
            [
                i.equals(
                    minecraft_root, instances[idx - 1], utils.TESTING_INSTANCES[idx]
                )
                for idx in range(1, 5)
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

        assert len(instances) == 5

        assert all(
            [
                i.equals(minecraft_root, instances[idx], utils.TESTING_INSTANCES[idx])
                for idx in range(5)
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
        craft.craft_ender_chest(minecraft_root, remotes=(), overwrite=True)
        ec_config = (
            fs.ender_chest_config(minecraft_root).read_text("utf-8").splitlines()
        )
        # this is a horrible way tp do this
        ec_config[6] = "offer-to-update-symlink-allowlist = False"
        fs.ender_chest_config(minecraft_root).write_text("\n".join(ec_config))
        assert gather.load_ender_chest(minecraft_root).instances == ()
        gather.update_ender_chest(minecraft_root, (home, minecraft_root / "instances"))

        instances = sorted(
            gather.load_ender_chest_instances(minecraft_root),
            key=lambda instance: instance.name
            if instance.name != "official"
            else "aaa",  # sorting hack
        )

        assert len(instances) == 5

        assert all(
            [
                i.equals(minecraft_root, instances[idx], utils.TESTING_INSTANCES[idx])
                for idx in range(5)
            ]
        )

    def test_updating_an_instance_does_not_overwrite_tags(
        self, minecraft_root, home
    ) -> None:
        enderchest = gather.load_ender_chest(minecraft_root)

        expected: dict[str, tuple[str, ...]] = {}
        for idx, instance in enumerate(enderchest._instances):
            tags = tuple((str(num) for num in range(idx + 1)))
            expected[instance.name] = tuple(sorted(tags + instance.groups_))
            enderchest._instances[idx] = instance._replace(
                tags_=tags, groups_=("outdated",)
            )
        enderchest.write_to_cfg(fs.ender_chest_config(minecraft_root))

        gather.update_ender_chest(minecraft_root, (home, minecraft_root / "instances"))

        enderchest = gather.load_ender_chest(minecraft_root)

        assert expected == {
            instance.name: instance.tags for instance in enderchest.instances
        }


class TestSymlinkAllowlistVersionChecker:
    """aka check my regex"""

    @pytest.mark.parametrize(
        "version_string, expected",
        (
            ("1.19.4", False),
            ("1.20", True),
            ("1.20.1-pre1", True),
            ("1.21-pre1", True),
            ("1.19-rc2", False),
            ("1.2.1", False),
            ("22w43a", False),
            ("23w9a", False),
            ("23w09a", False),
            ("23w51a", True),
            ("24w6a", True),
            ("24w06a", True),
        ),
    )
    def test_check_if_version_needs_allow_list(self, version_string, expected):
        assert gather._needs_symlink_allowlist(version_string) == expected


class TestSymlinkAllowlistHandling:
    @pytest.fixture(autouse=True)
    def setup_teardown(self, minecraft_root):
        utils.pre_populate_enderchest(
            fs.ender_chest_folder(minecraft_root, check_exists=False)
        )
        with fs.ender_chest_config(minecraft_root).open("w") as ec_config:
            ec_config.write(
                """
[properties]
"""
            )

        utils.populate_mmc_instance_folder(
            minecraft_root / "instances" / "talespin", "1.20", "Quilt", "talespin"
        )

        (
            minecraft_root
            / "instances"
            / "talespin"
            / ".minecraft"
            / "allowed_symlinks.txt"
        ).write_text(
            "my_development_folder\n"
        )  # read: not EnderChest

        yield

        assert (
            (
                minecraft_root
                / "instances"
                / "talespin"
                / ".minecraft"
                / "allowed_symlinks.txt"
            )
            .read_text()
            .startswith("my_development_folder\n")
        )

    @pytest.mark.parametrize("instance", ("official", "talespin"))
    def test_ender_chest_does_not_write_allowlist_without_consent(
        self, minecraft_root, home, monkeypatch, capsys, instance
    ):
        if instance == "official":
            search_path = home
        else:
            search_path = minecraft_root / "instances" / "talespin"
        i_forbid_it = utils.scripted_prompt(["no"])
        monkeypatch.setattr("builtins.input", i_forbid_it)

        gather.gather_minecraft_instances(minecraft_root, search_path, None)

        _ = capsys.readouterr()  # suppress outputs

        # easier to check both
        assert not (home / ".minecraft" / "allowed_symlinks.txt").exists()
        assert (
            minecraft_root
            / "instances"
            / "talespin"
            / ".minecraft"
            / "allowed_symlinks.txt"
        ).read_text() == "my_development_folder\n"

        # make sure all responses were used
        with pytest.raises(StopIteration):
            i_forbid_it()

    @pytest.mark.parametrize(
        "symlinked_root", (False, True), ids=("direct_root", "symlinked_root")
    )
    def test_ender_chest_will_write_allowlists_with_consent(
        self, symlinked_root, minecraft_root, home, monkeypatch, capsys, tmp_path
    ):
        mkay = utils.scripted_prompt(["y"] * 3)
        monkeypatch.setattr("builtins.input", mkay)

        if symlinked_root:
            (tmp_path / "mc").symlink_to(minecraft_root)
            provided_root = tmp_path / "mc"
        else:
            provided_root = minecraft_root

        gather.gather_minecraft_instances(provided_root, home, True)

        # this is also testing that you're not getting prompted
        # for pre-1.20 instances
        gather.gather_minecraft_instances(
            provided_root, minecraft_root / "instances", False
        )

        _ = capsys.readouterr()  # suppress outputs

        ender_chest_path = os.path.realpath(fs.ender_chest_folder(minecraft_root))

        assert (
            home / ".minecraft" / "allowed_symlinks.txt"
        ).read_text() == ender_chest_path + "\n"
        assert (
            minecraft_root
            / "instances"
            / "talespin"
            / ".minecraft"
            / "allowed_symlinks.txt"
        ).read_text() == f"my_development_folder\n{ender_chest_path}\n"

        # make sure all responses were used
        with pytest.raises(StopIteration):
            mkay()
