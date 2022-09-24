"""Test functionality around linking instances"""
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
