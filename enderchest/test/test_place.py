"""Test functionality around linking instances"""
import os
from pathlib import Path

import pytest

from enderchest import place


class TestLink:
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

    @pytest.mark.parametrize("linker", ("link_instance", "link_server"))
    def test_linker_skips_nonexistent_folder_by_default(
        self, tmp_path, aether_dot_zip, linker
    ):
        getattr(place, linker)(
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

    def test_link_server_will_create_folders_inside_of_existing_server_folders(
        self, tmp_path, aether_dot_zip
    ):
        (tmp_path / "i_sort_of_exist" / "backups").mkdir(parents=True)
        place.link_server(
            Path("backups") / "aether.zip",
            tmp_path / "i_sort_of_exist",
            aether_dot_zip,
        )

        assert (tmp_path / "i_sort_of_exist" / "backups" / "aether.zip").exists()

    @pytest.mark.parametrize("linker", ("link_instance", "link_server"))
    def test_link_instance_can_be_made_to_create_folders(
        self, tmp_path, aether_dot_zip, linker
    ):
        getattr(place, linker)(
            Path("backups") / "aether.zip",
            tmp_path / "makeme",
            aether_dot_zip,
            check_exists=False,
        )
        minecraft_root = tmp_path / "makeme"
        if linker == "link_instance":
            minecraft_root /= ".minecraft"
        assert (minecraft_root / "backups" / "aether.zip").exists()

    @pytest.mark.parametrize("linker", ("link_instance", "link_server"))
    @pytest.mark.parametrize("check_exists", (True, False))
    def test_linker_will_overwrite_existing_links(
        self, check_exists, tmp_path, aether_dot_zip, beether_dot_zip, linker
    ):
        beether_contents = beether_dot_zip.read_bytes()

        minecraft_root = tmp_path / "i_exist"
        if linker == "link_instance":
            minecraft_root /= ".minecraft"

        (minecraft_root / "backups").mkdir(parents=True)
        (minecraft_root / "backups" / "aether.zip").symlink_to(beether_dot_zip)

        getattr(place, linker)(
            Path("backups") / "aether.zip",
            tmp_path / "i_exist",
            aether_dot_zip,
            check_exists=check_exists,
        )

        assert (
            minecraft_root / "backups" / "aether.zip"
        ).read_bytes() == aether_dot_zip.read_bytes()

        # assert that the original is unchanged
        assert beether_dot_zip.read_bytes() == beether_contents

    @pytest.mark.parametrize("linker", ("link_instance", "link_server"))
    @pytest.mark.parametrize("check_exists", (True, False))
    def test_linker_will_not_overwrite_an_actual_file(
        self, check_exists, tmp_path, aether_dot_zip, beether_dot_zip, linker
    ):
        beether_contents = beether_dot_zip.read_bytes()

        minecraft_root = tmp_path / "i_exist"
        if linker == "link_instance":
            minecraft_root /= ".minecraft"

        (minecraft_root / "backups").mkdir(parents=True)
        beether_dot_zip.rename(minecraft_root / "backups" / "aether.zip")
        with pytest.raises(FileExistsError):
            getattr(place, linker)(
                Path("backups") / "aether.zip",
                tmp_path / "i_exist",
                aether_dot_zip,
                check_exists=check_exists,
            )

        assert (
            minecraft_root / "backups" / "aether.zip"
        ).read_bytes() == beether_contents

        assert not (minecraft_root / "backups" / "aether.zip").is_symlink()


@pytest.mark.usefixtures("local_enderchest")
class TestPlaceEnderChest:
    @pytest.fixture(autouse=True)
    def create_some_instances(self, local_root):
        (local_root / "instances" / "axolotl" / ".minecraft").mkdir(parents=True)
        (local_root / "instances" / "bee" / ".minecraft").mkdir(parents=True)
        (local_root / "servers" / "axolotl").mkdir(parents=True)
        (local_root / "servers" / "chest.boat").mkdir(parents=True)

    @pytest.mark.parametrize("cleanup", (True, False))
    @pytest.mark.parametrize(
        "instances, servers, resource_path",
        (
            (("axolotl",), (), ("resourcepacks", "stuff.zip")),
            (("axolotl", "bee"), (), ("shaderpacks", "Seuss CitH.zip.txt")),
            (
                ("axolotl", "bee"),
                ("axolotl",),
                ("resourcepacks", "neat_resource_pack"),
            ),
            (("axolotl", "bee"), (), ("saves", "olam")),
            (("axolotl",), ("axolotl",), ("mods", "BME.jar")),
            (("bee",), (), ("mods", "BME.jar")),  # not the same mod
            ((), ("chest.boat",), ("mods", "BME.jar")),  # also not the same mod
        ),
    )
    def test_placing_create_links_to_shared_resources(
        self, cleanup, instances, servers, resource_path, local_root
    ):
        place.place_enderchest(local_root, cleanup=cleanup)

        minecraft_folders: list[Path] = []
        for instance in instances:
            minecraft_folders.append(local_root / "instances" / instance / ".minecraft")
        for server in servers:
            minecraft_folders.append(local_root / "servers" / server)

        destinations: set[Path] = set()

        for link_path in minecraft_folders:
            for path_part in resource_path:
                link_path = link_path / path_part
            destinations.add(os.path.realpath(link_path, strict=True))
        assert len(destinations) == 1

    @pytest.mark.parametrize("cleanup", (True, False))
    def test_placing_doesnt_create_folders_for_missing_instances(
        self, cleanup, local_root
    ):
        place.place_enderchest(local_root, cleanup=cleanup)
        assert not (local_root / "instances" / "Chest Boat").exists()

    @pytest.mark.parametrize("cleanup", (True, False))
    def test_placing_doesnt_create_folders_for_missing_servers(
        self, cleanup, local_root
    ):
        place.place_enderchest(local_root, cleanup=cleanup)
        assert not (local_root / "servers" / "bee").exists()

    @pytest.mark.parametrize("cleanup", (True, False))
    @pytest.mark.parametrize("minecraft_type", ("instance", "server"))
    def test_placing_doesnt_make_broken_links(
        self, cleanup, minecraft_type, local_root
    ):
        global_config = local_root / "EnderChest" / "global" / "config"
        global_config.mkdir(parents=True, exist_ok=True)
        (global_config / "BME.txt@axolotl").symlink_to(
            local_root / "workspace" / "BestModEver" / "there_is_no_config_here.txt"
        )

        place.place_enderchest(local_root, cleanup=cleanup)

        if minecraft_type == "instance":
            minecraft_folder = local_root / "instances" / "axolotl" / ".minecraft"
        else:
            minecraft_folder = local_root / "servers" / "axolotl"

        assert "BME.txt" not in [
            path.name for path in (minecraft_folder / "config").glob("*")
        ]

    @pytest.mark.parametrize("minecraft_type", ("instance", "server"))
    def test_existing_broken_links_are_cleaned_up_by_default(
        self, minecraft_type, local_root
    ):
        if minecraft_type == "instance":
            minecraft_folder = local_root / "instances" / "axolotl" / ".minecraft"
        else:
            minecraft_folder = local_root / "servers" / "axolotl"

        config_folder = minecraft_folder / "config"
        config_folder.mkdir(parents=True, exist_ok=True)
        (config_folder / "BME.txt").symlink_to(
            local_root / "workspace" / "BestModEver" / "there_is_no_config_here.txt"
        )

        place.place_enderchest(local_root)

        assert "BME.txt" not in [path.name for path in config_folder.glob("*")]

    @pytest.mark.parametrize("minecraft_type", ("instance", "server"))
    def test_cleanup_of_existing_broken_links_can_be_disabled(
        self, minecraft_type, local_root
    ):
        if minecraft_type == "instance":
            minecraft_folder = local_root / "instances" / "axolotl" / ".minecraft"
        else:
            minecraft_folder = local_root / "servers" / "axolotl"

        config_folder = minecraft_folder / "config"
        config_folder.mkdir(parents=True, exist_ok=True)
        (config_folder / "BME.txt").symlink_to(
            local_root / "workspace" / "BestModEver" / "there_is_no_config_here.txt"
        )

        place.place_enderchest(local_root, cleanup=False)

        assert "BME.txt" in [path.name for path in config_folder.glob("*")]

    @pytest.mark.parametrize("cleanup", (True, False))
    def test_server_only_assets_dont_go_in_instances(self, cleanup, local_root):
        (local_root / "EnderChest" / "server-only" / "banlist.txt@axolotl").write_text(
            "openbagtwo\n"
        )

        place.place_enderchest(local_root, cleanup=cleanup)

        assert list((local_root / "instances").rglob("banlist.txt")) == []

    @pytest.mark.parametrize("cleanup", (True, False))
    def test_client_only_assets_dont_go_in_servers(self, cleanup, local_root):
        (local_root / "EnderChest" / "client-only" / "options.txt@axolotl").write_text(
            "render_distance=ALL THE CHUNKS\n"
        )

        place.place_enderchest(local_root, cleanup=cleanup)

        assert list((local_root / "servers").rglob("options.txt")) == []
