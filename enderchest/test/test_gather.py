"""Tests around file discovery and registration"""

import os
from pathlib import Path

import pytest

from enderchest import craft
from enderchest import filesystem as fs
from enderchest import gather
from enderchest import instance as i
from enderchest import inventory

from . import utils


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
            key=lambda instance: (
                instance.name if instance.name != "official" else "aaa"
            ),  # sorting hack
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
        assert inventory.load_ender_chest(minecraft_root).instances == ()
        gather.update_ender_chest(minecraft_root, (home, minecraft_root / "instances"))

        instances = sorted(
            inventory.load_ender_chest_instances(minecraft_root),
            key=lambda instance: (
                instance.name if instance.name != "official" else "aaa"
            ),  # sorting hack
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
        enderchest = inventory.load_ender_chest(minecraft_root)

        expected: dict[str, tuple[str, ...]] = {}
        for idx, instance in enumerate(enderchest._instances):
            tags = tuple((str(num) for num in range(idx + 1)))
            expected[instance.name] = tuple(sorted(tags + instance.groups_))
            enderchest._instances[idx] = instance._replace(
                tags_=tags, groups_=("outdated",)
            )
        enderchest.write_to_cfg(fs.ender_chest_config(minecraft_root))

        gather.update_ender_chest(minecraft_root, (home, minecraft_root / "instances"))

        enderchest = inventory.load_ender_chest(minecraft_root)

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
