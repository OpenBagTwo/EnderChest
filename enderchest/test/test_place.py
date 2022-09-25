"""Test functionality around linking instances"""
import os
from pathlib import Path

import pytest

from enderchest import place


class TestLinkInstance:
    @pytest.fixture
    def aether_dot_zip(self, tmp_path):
        a_backup = tmp_path / "aether.zip"
        a_backup.write_bytes(b"beepboop")
        yield a_backup

    @pytest.fixture
    def beether_dot_zip(self, tmp_path):
        another_backup = tmp_path / "beether.zip"
        another_backup.write_bytes(b"buzzbuzz")
        yield another_backup

    def test_link_instance_skips_nonexistent_instances_by_default(
        self, tmp_path, aether_dot_zip
    ):
        place.link_instance(
            Path("backups") / "aether.zip", tmp_path / "idonotexist", aether_dot_zip
        )

        assert not (tmp_path / "idonotexist").exists()

    def test_link_instance_will_create_folders_inside_of_existing_instances(
        self, tmp_path, aether_dot_zip
    ):
        (tmp_path / "i_sort_of_exist" / ".minecraft" / "backups").mkdir(parents=True)
        place.link_instance(
            Path("backups") / "aether.zip",
            tmp_path / "i_sort_of_exist",
            aether_dot_zip,
        )

        assert (
            tmp_path / "i_sort_of_exist" / ".minecraft" / "backups" / "aether.zip"
        ).exists()

    def test_link_instance_can_be_made_to_create_instance_folders(
        self, tmp_path, aether_dot_zip
    ):

        place.link_instance(
            Path("backups") / "aether.zip",
            tmp_path / "makeme",
            aether_dot_zip,
            check_exists=False,
        )

        assert (tmp_path / "makeme" / ".minecraft" / "backups" / "aether.zip").exists()

    @pytest.mark.parametrize("check_exists", (True, False))
    def test_link_instance_will_overwrite_existing_links(
        self, check_exists, tmp_path, aether_dot_zip, beether_dot_zip
    ):
        beether_contents = beether_dot_zip.read_bytes()

        (tmp_path / "i_exist" / ".minecraft" / "backups").mkdir(parents=True)
        (tmp_path / "i_exist" / ".minecraft" / "backups" / "aether.zip").symlink_to(
            beether_dot_zip
        )

        place.link_instance(
            Path("backups") / "aether.zip",
            tmp_path / "i_exist",
            aether_dot_zip,
            check_exists=check_exists,
        )

        assert (
            tmp_path / "i_exist" / ".minecraft" / "backups" / "aether.zip"
        ).read_bytes() == aether_dot_zip.read_bytes()

        # assert that the original is unchanged
        assert beether_dot_zip.read_bytes() == beether_contents

    @pytest.mark.parametrize("check_exists", (True, False))
    def test_link_instance_will_not_overwrite_an_actual_file(
        self, check_exists, tmp_path, aether_dot_zip, beether_dot_zip
    ):
        beether_contents = beether_dot_zip.read_bytes()

        (tmp_path / "i_exist" / ".minecraft" / "backups").mkdir(parents=True)
        beether_dot_zip.rename(
            tmp_path / "i_exist" / ".minecraft" / "backups" / "aether.zip"
        )
        with pytest.raises(FileExistsError):
            place.link_instance(
                Path("backups") / "aether.zip",
                tmp_path / "i_exist",
                aether_dot_zip,
                check_exists=check_exists,
            )

        assert (
            tmp_path / "i_exist" / ".minecraft" / "backups" / "aether.zip"
        ).read_bytes() == beether_contents

        assert not (
            tmp_path / "i_exist" / ".minecraft" / "backups" / "aether.zip"
        ).is_symlink()


@pytest.mark.usefixtures("local_enderchest")
class TestPlaceEnderChest:
    @pytest.fixture(autouse=True)
    def create_some_instances(self, local_root):
        (local_root / "instances" / "axolotl" / ".minecraft").mkdir(parents=True)
        (local_root / "instances" / "bee" / ".minecraft").mkdir(parents=True)

    @pytest.mark.parametrize("cleanup", (True, False))
    @pytest.mark.parametrize(
        "resource",
        (
            (("axolotl",), "resourcepacks", "stuff.zip"),
            (("axolotl", "bee"), "shaderpacks", "Seuss CitH.zip.txt"),
            (("axolotl", "bee"), "resourcepacks", "neat_resource_pack"),
            (("axolotl", "bee"), "saves", "olam"),
            (("axolotl",), "mods", "BME.jar"),
            (("bee",), "mods", "BME.jar"),  # not the same mod
        ),
    )
    def test_placing_create_links_inside_instances(self, cleanup, resource, local_root):
        place.place_enderchest(local_root, cleanup=cleanup)
        instances, *path = resource
        destinations: set[Path] = set()
        for instance in instances:
            link_path = local_root / "instances" / instance / ".minecraft"
            for path_part in path:
                link_path = link_path / path_part
            destinations.add(os.path.realpath(link_path, strict=True))
        assert len(destinations) == 1

    @pytest.mark.parametrize("cleanup", (True, False))
    def test_placing_doesnt_create_folders_for_missing_instances(
        self, cleanup, local_root
    ):
        place.place_enderchest(local_root, cleanup=cleanup)
        assert not (local_root / "instances" / "cow").exists()

    @pytest.mark.parametrize("cleanup", (True, False))
    def test_placing_doesnt_make_broken_links(self, cleanup, local_root):

        global_config = local_root / "EnderChest" / "global" / "config"
        global_config.mkdir(parents=True, exist_ok=True)
        (global_config / "BME.txt@axolotl").symlink_to(
            local_root / "workspace" / "BestModEver" / "there_is_no_config_here.txt"
        )

        place.place_enderchest(local_root, cleanup=cleanup)

        assert "BME.txt" not in [
            path.name
            for path in (
                local_root / "instances" / "axolotl" / ".minecraft" / "config"
            ).glob("*")
        ]
