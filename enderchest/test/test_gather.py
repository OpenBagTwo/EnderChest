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


class TestGatherServer:
    @pytest.fixture()
    def server_jars(self, minecraft_root: Path) -> dict[Path, i.InstanceSpec]:
        expected_metadata = {}
        server_folder = minecraft_root / "servers"
        server_folder.mkdir(exist_ok=True)

        # this might actually be Aether 1?
        (server_folder / "aether.2").mkdir()
        (
            server_folder
            / "aether.2"
            / "forge-1.7.10-10.13.4.1614-1.7.10-installer.jar"
        ).write_text("Wrong jar\n")
        (server_folder / "aether.2" / ".minecraft").mkdir()
        server_jar = (
            server_folder
            / "aether.2"
            / ".minecraft"
            / "forge-1.7.10-10.13.4.1614-1.7.10-universal.jar"
        )
        server_jar.write_text("Correct jar\n")
        expected_metadata[server_jar] = i.InstanceSpec(
            server_jar.parent.parent.name,
            server_jar.parent.parent,
            ("1.7.10",),
            "Forge",
            ("server",),
            (),
        )

        (
            server_folder / "aether.2" / ".minecraft" / "minecraft_server.1.7.10.jar"
        ).write_text("Wrong jar\n")
        (server_folder / "aether.2" / "mods").mkdir()
        (server_folder / "aether.2" / "mods" / "aether-1.7.10-1.6.jar").write_text(
            "Wrong jar\n"
        )

        (server_folder / "aether.legacy").mkdir()
        (
            server_folder / "aether.legacy" / "forge-1.12.2-14.23.5.2860-installer.jar"
        ).write_text("Wrong jar\n")
        (server_folder / "aether.legacy" / ".minecraft").mkdir()
        server_jar = (
            server_folder
            / "aether.legacy"
            / ".minecraft"
            / "forge-1.12.2-14.23.5.2860.jar"
        )
        server_jar.write_text("Correct jar\n")
        expected_metadata[server_jar] = i.InstanceSpec(
            server_jar.parent.parent.name,
            server_jar.parent.parent,
            ("1.12.2",),
            "Forge",
            ("server",),
            (),
        )
        (
            server_folder
            / "aether.legacy"
            / ".minecraft"
            / "minecraft_server.1.12.2.jar"
        ).write_text("Wrong jar\n")
        (server_folder / "aether.legacy" / "mods").mkdir()
        (
            server_folder / "aether.legacy" / "mods" / "aether-1.12.2-v1.5.2.jar"
        ).write_text("Wrong jar\n")

        (server_folder / "chunk.in.a.globe").mkdir()
        server_jar = (
            server_folder
            / "chunk.in.a.globe"
            / "fabric-server-mc.1.18.1-loader.0.14.4-launcher.0.10.2.jar"
        )
        server_jar.write_text("Correct jar\n")
        expected_metadata[server_jar] = i.InstanceSpec(
            server_jar.parent.name,
            server_jar.parent,
            ("1.18.1",),
            "Fabric Loader",
            ("server",),
            (),
        )
        (server_folder / "chunk.in.a.globe" / ".fabric" / "server").mkdir(parents=True)
        for jar_name in (
            "1.18.1-server.jar",
            "fabric-loader-server-0.13.3-minecraft-1.18.1.jar",
            "fabric-loader-server-0.14.4-minecraft-1.18.1.jar",
        ):
            (
                server_folder / "chunk.in.a.globe" / ".fabric" / "server" / jar_name
            ).write_text("Wrong jar\n")

        centralized_jar_folder = (
            minecraft_root / "EnderChest" / "Chest Monster" / "server_jars"
        )
        centralized_jar_folder.mkdir(parents=True, exist_ok=True)
        for jar_name, launcher in (
            ("minecraft_server-1.20.4.jar", ""),
            (
                "fabric-server-mc.1.20.4-loader.0.15.7-launcher.1.0.0.jar",
                "Fabric Loader",
            ),
            ("forge-1.20.4-49.0.30-shim.jar", "Forge"),
            ("paper-1.20.4-424.jar", "Paper"),
            ("purpur-1.20.4-2142.jar", "Purpur"),
            ("spigot-1.20.4.jar", "Spigot"),
        ):
            (centralized_jar_folder / jar_name).write_text("Correct jar\n")
            expected_metadata[centralized_jar_folder / jar_name] = i.InstanceSpec(
                "ignoreme", Path("ignoreme"), ("1.20.4",), launcher, ("server",), ()
            )
        return expected_metadata

    def test_parsing_metadata_from_jar(self, server_jars):
        expected: list[tuple[Path, tuple[str], str]] = [
            (jar, instance.minecraft_versions, instance.modloader)
            for jar, instance in server_jars.items()
        ]
        results: list[tuple[Path, tuple[str], str]] = []
        for jar in server_jars:
            meta = gather._gather_metadata_from_jar_filename(jar.name)
            results.append((jar, meta["minecraft_versions"], meta["modloader"]))

        assert expected == results

    @pytest.mark.parametrize(
        "server", ("aether.2", "aether.legacy", "chunk.in.a.globe")
    )
    def test_gather_server_instance_parses_metadata_from_the_correct_jar(
        self, server, server_jars, minecraft_root, monkeypatch, capsys
    ):
        script_reader = utils.scripted_prompt(["", ""])
        monkeypatch.setattr("builtins.input", script_reader)

        server_home = minecraft_root / "servers" / server
        instance_meta = gather.gather_metadata_for_minecraft_server(server_home)

        _ = capsys.readouterr()

        for jar, meta in server_jars.items():
            if jar.is_relative_to(server_home):
                expected_meta = meta
                break
        else:
            raise RuntimeError(
                "Whoops! Test class fixture doesn't contain meta for this server home."
            )

        assert expected_meta == instance_meta

    @pytest.mark.parametrize(
        "with_explicit_path", (False, True), ids=("", "with_explicit_path")
    )
    def test_mystery_jar_will_prompt_for_info(
        self, minecraft_root, with_explicit_path, monkeypatch, capsys
    ):
        script_reader = utils.scripted_prompt(["vanilla", "1.0", "OG", "old,vanilla"])
        monkeypatch.setattr("builtins.input", script_reader)
        server_jar = minecraft_root / "servers" / "mystery" / "server.jar"
        server_jar.parent.mkdir(parents=True)
        server_jar.write_text("Correct jar\n")

        instance_meta = gather.gather_metadata_for_minecraft_server(
            server_jar.parent, server_jar=server_jar if with_explicit_path else None
        )

        _ = capsys.readouterr()

        assert instance_meta == i.InstanceSpec(
            "OG",
            server_jar.parent,
            ("1.0",),
            "",
            ("server",),
            ("old", "vanilla"),
        )


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
