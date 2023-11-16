"""Tests for setting up EnderChests and shulker boxes"""
import logging
import os
from pathlib import Path
from typing import Any

import pytest

from enderchest import EnderChest, ShulkerBox, craft
from enderchest import filesystem as fs
from enderchest.enderchest import create_ender_chest
from enderchest.gather import load_ender_chest
from enderchest.place import place_ender_chest

from . import utils


class TestEnderChestCrafting:
    def test_ender_chest_aborts_right_away_if_minecraft_root_doesnt_exist(
        self, monkeypatch, minecraft_root
    ):
        def mock_prompt(root) -> Any:
            raise AssertionError("I was not to be called.")

        def mock_create(root, chest) -> None:
            raise AssertionError("I was not to be called.")

        def mock_gather(*args, **kwargs) -> list[Any]:
            raise AssertionError("I was not to be called.")

        monkeypatch.setattr(craft, "specify_ender_chest_from_prompt", mock_prompt)
        monkeypatch.setattr(craft, "create_ender_chest", mock_create)
        monkeypatch.setattr(craft, "gather_minecraft_instances", mock_gather)
        monkeypatch.setattr(
            craft, "fetch_remotes_from_a_remote_ender_chest", mock_gather
        )

        craft.craft_ender_chest(minecraft_root / "trunk")

    def test_no_kwargs_routes_to_the_interactive_prompter(
        self, monkeypatch, tmpdir
    ) -> None:
        prompt_log: list[Path] = []

        def mock_prompt(root) -> Any:
            prompt_log.append(root)
            return "MockEnderChest"

        create_log: list[tuple[Path, Any]] = []

        def mock_create(root, chest) -> None:
            create_log.append((root, chest))

        monkeypatch.setattr(craft, "specify_ender_chest_from_prompt", mock_prompt)
        monkeypatch.setattr(craft, "create_ender_chest", mock_create)

        craft.craft_ender_chest(tmpdir)

        assert prompt_log == [tmpdir]
        assert create_log == [(tmpdir, "MockEnderChest")]

    @pytest.mark.parametrize(
        "argument, value",
        (
            ("instance_search_paths", ("~",)),
            ("overwrite", True),
            ("remotes", ("earworm://somewhere/beyond/the-sea",)),
        ),
        ids=("instances", "overwrite", "remotes"),
    )
    def test_any_kwarg_avoids_the_interactive_prompter(
        self,
        monkeypatch,
        argument,
        value,
        minecraft_root,
    ) -> None:
        def mock_prompt(root) -> Any:
            raise AssertionError("I was not to be called.")

        create_log: list[tuple[Path, Any]] = []

        def mock_create(root, chest) -> None:
            create_log.append((root, chest))

        def mock_gather(*args, **kwargs) -> list:
            return []

        def mock_fetch_remotes(*args, **kwargs) -> list:
            raise AssertionError("I was not to be called.")

        monkeypatch.setattr(craft, "specify_ender_chest_from_prompt", mock_prompt)
        monkeypatch.setattr(craft, "create_ender_chest", mock_create)
        monkeypatch.setattr(craft, "gather_minecraft_instances", mock_gather)
        monkeypatch.setattr(
            craft, "fetch_remotes_from_a_remote_ender_chest", mock_fetch_remotes
        )

        craft.craft_ender_chest(minecraft_root, **{argument: value})
        assert len(create_log) == 1

    def test_failed_fetch_aborts_the_create(self, monkeypatch, minecraft_root):
        def mock_prompt(root) -> Any:
            raise AssertionError("I was not to be called.")

        def mock_create(root, chest) -> None:
            raise AssertionError("I was not to be called.")

        def mock_gather(*args, **kwargs) -> list:
            return []

        def mock_fetch_remotes(*args, **kwargs) -> list:
            raise RuntimeError("Don't feel like it.")

        monkeypatch.setattr(craft, "specify_ender_chest_from_prompt", mock_prompt)
        monkeypatch.setattr(craft, "create_ender_chest", mock_create)
        monkeypatch.setattr(craft, "gather_minecraft_instances", mock_gather)
        monkeypatch.setattr(
            craft, "fetch_remotes_from_a_remote_ender_chest", mock_fetch_remotes
        )

        craft.craft_ender_chest(minecraft_root, copy_from="prayer://unreachable")

    def test_default_behavior_is_to_prevent_overwrite(self, minecraft_root, caplog):
        create_ender_chest(
            minecraft_root,
            EnderChest(
                "openbagtwo@battlestation" + minecraft_root.absolute().as_posix()
            ),
        )

        original_config = fs.ender_chest_config(minecraft_root).read_text()

        craft.craft_ender_chest(
            minecraft_root, instance_search_paths=(minecraft_root / "instances",)
        )
        error_log = "\n".join(
            record.msg for record in caplog.records if record.levelname == "ERROR"
        )
        assert "There is already an EnderChest installed" in error_log

        assert fs.ender_chest_config(minecraft_root).read_text() == original_config

    @pytest.mark.parametrize("root_type", ("absolute", "relative"))
    def test_craft_chest_from_config(
        self,
        minecraft_root,
        home,
        caplog,
        monkeypatch,
        capsys,
        root_type,
    ):
        if root_type == "absolute":
            root = minecraft_root
        else:
            root = Path(minecraft_root.name)
            monkeypatch.chdir(minecraft_root.parent)

        # we'll be testing overwriting
        create_ender_chest(
            root,
            EnderChest(
                "sftp://openbagtwo@battlestation" + minecraft_root.absolute().as_posix()
            ),
        )

        never = utils.scripted_prompt(["no"] * 2)
        monkeypatch.setattr("builtins.input", never)

        craft.craft_ender_chest(
            minecraft_root,
            instance_search_paths=(minecraft_root / "instances", home),
            remotes=("rsync://deck@steamdeck/home/deck/minecraft",),
            overwrite=True,
        )

        _ = capsys.readouterr()  # suppress outputs

        assert not [record for record in caplog.records if record.levelname == "ERROR"]

        chest = load_ender_chest(minecraft_root)
        assert len(chest.instances) == 5
        assert len(chest.remotes) == 1

    @pytest.mark.parametrize("root_type", ("absolute", "relative"))
    def test_giving_default_responses_results_in_the_expected_chest(
        self,
        monkeypatch,
        minecraft_root,
        home,
        capsys,
        caplog,
        root_type,
    ):
        if root_type == "absolute":
            root = minecraft_root
            n_responses = 9
        else:
            root = Path(minecraft_root.name)
            monkeypatch.chdir(minecraft_root.parent)
            n_responses = 10  # because now cwd != minecraft root

        script_reader = utils.scripted_prompt([""] * n_responses)
        monkeypatch.setattr("builtins.input", script_reader)

        chest = craft.specify_ender_chest_from_prompt(root)

        _ = capsys.readouterr()  # suppress outputs

        assert not [record for record in caplog.records if record.levelname == "ERROR"]

        assert len(chest.instances) == 5
        assert len(chest.remotes) == 0

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()

    def test_prompter_gives_you_the_chance_to_back_out(
        self, monkeypatch, tmpdir, capsys
    ):
        script_reader = utils.scripted_prompt(
            ["n", "n", "", "", "me@here", "default", "n"]
        )
        monkeypatch.setattr("builtins.input", script_reader)
        os.chdir(tmpdir)

        with pytest.raises(RuntimeError):
            craft.specify_ender_chest_from_prompt(Path(tmpdir))

        _ = capsys.readouterr()  # suppress outputs

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()


class TestShulkerBoxCrafting:
    def test_no_kwargs_routes_to_the_interactive_prompter(self, monkeypatch) -> None:
        prompt_log: list[tuple[Path, str]] = []

        def mock_prompt(root: Path, name: str) -> str:
            prompt_log.append((root, name))
            return "MockShulkerBox"

        create_log: list[tuple[Path, str, list[str]]] = []

        def mock_create(root: Path, box: str, folders: list[str]) -> None:
            create_log.append((root, box, folders))

        class MockEnderChest:
            shulker_box_folders = ["stuff", "junk"]

        def mock_load_ender_chest(root: Path) -> MockEnderChest:
            return MockEnderChest()

        monkeypatch.setattr(craft, "specify_shulker_box_from_prompt", mock_prompt)
        monkeypatch.setattr(craft, "create_shulker_box", mock_create)
        monkeypatch.setattr(craft, "load_ender_chest", mock_load_ender_chest)

        craft.craft_shulker_box(Path("/"), "spitty")

        assert prompt_log == [(Path("/"), "spitty")]
        assert create_log == [(Path("/"), "MockShulkerBox", ["stuff", "junk"])]

    @pytest.mark.parametrize(
        "argument, value",
        (
            ("instances", ("official",)),
            ("overwrite", True),
            ("tags", ("youre", "it")),
            ("hosts", ("elsewhere", "here")),
            ("priority", -12),
        ),
        ids=("instances", "overwrite", "tags", "hosts", "priority"),
    )
    def test_any_kwarg_avoids_the_interactive_prompter(
        self, monkeypatch, argument, value
    ) -> None:
        def mock_prompt(root) -> Any:
            raise AssertionError("I was not to be called.")

        create_log: list[tuple[Path, str, list[str]]] = []

        def mock_create(root, box, folders) -> None:
            create_log.append((root, box, folders))

        class FakePath:
            def exists(self) -> bool:
                return False

        def mock_fs(*args, **kwargs) -> Any:
            return FakePath()

        class MockEnderChest:
            shulker_box_folders = ["tchotchkes"]

        def mock_load_ender_chest(root) -> MockEnderChest:
            return MockEnderChest()

        monkeypatch.setattr(craft, "specify_shulker_box_from_prompt", mock_prompt)
        monkeypatch.setattr(craft, "create_shulker_box", mock_create)
        monkeypatch.setattr(fs, "shulker_box_config", mock_fs)
        monkeypatch.setattr(craft, "load_ender_chest", mock_load_ender_chest)

        craft.craft_shulker_box(Path("minceraft"), "bacon", **{argument: value})
        assert len(create_log) == 1

    def test_warns_if_you_forgot_to_add_yourself_as_the_host(
        self, monkeypatch, minecraft_root, capsys, caplog
    ):
        utils.pre_populate_enderchest(minecraft_root / "EnderChest")
        script_reader = utils.scripted_prompt(
            [
                "F",
                "",
                "",
                "",
                "",
                "",
                "",
                "m",
                # while we're here we might as well check setting
                # the other box properties
                "cachedImages, logs",
                "-12",
                "somewhere_out_there",
                "",  # default false
                "somewhere_out_there,*",
                "",  # this is the final writeme confirmation
            ]
        )
        monkeypatch.setattr("builtins.input", script_reader)

        shulker_box = craft.specify_shulker_box_from_prompt(minecraft_root, "q and a")

        _ = capsys.readouterr()  # suppress outputs

        assert shulker_box == ShulkerBox(
            -12,
            "q and a",
            minecraft_root / "EnderChest" / "q and a",
            match_criteria=(
                ("minecraft", ("*",)),
                ("modloader", ("*",)),
                ("tags", ("*",)),
                ("hosts", ("somewhere_out_there", "*")),
            ),
            link_folders=("cachedImages", "logs"),
        )

        warn_log = "\n".join(
            record.msg for record in caplog.records if record.levelname == "WARNING"
        )

        assert (
            "This shulker box will not link to any instances on this machine"
            in warn_log
        )

    def test_global_box_links_nested_litematica_folder(
        self, monkeypatch, minecraft_root, home, capsys, caplog
    ):
        utils.pre_populate_enderchest(minecraft_root / "EnderChest")

        script_reader = utils.scripted_prompt(
            [
                "F",
                "",
                "",
                "",
                "",
                "",
                "",
                "G",
                "-100",
                "",
                "",  # this is the final writeme confirmation
            ]
        )
        monkeypatch.setattr("builtins.input", script_reader)

        craft.create_shulker_box(
            minecraft_root,
            craft.specify_shulker_box_from_prompt(minecraft_root, "olam"),
            (),  # sneakily testing that it'll create parent dirs
        )

        resource_path = (
            Path("config") / "litematica" / "material_list_2023-11-16_15.43.17.txt"
        )

        (fs.shulker_box_root(minecraft_root, "olam") / resource_path).write_text(
            "lots of TNT\n"
        )

        placements = place_ender_chest(minecraft_root)

        assert (
            placements["axolotl"].get(resource_path, []),
            placements["axolotl"][resource_path.parent],
        ) == ([], ["olam"])


class TestPromptByFilter:
    def test_giving_default_responses_results_in_the_expected_shulker_box(
        self, monkeypatch, capsys
    ):
        script_reader = utils.scripted_prompt([""] * 6)
        monkeypatch.setattr("builtins.input", script_reader)

        shulker_box = craft._prompt_for_filters(
            ShulkerBox(0, "tester", Path("ignored"), (), ()), utils.TESTING_INSTANCES
        )

        _ = capsys.readouterr()  # suppress outputs

        assert shulker_box.match_criteria == (
            ("minecraft", ("*",)),
            ("modloader", ("*",)),
            ("tags", ("*",)),
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()

    def test_filter_prompt_doesnt_confirm_when_there_are_no_instances(
        self, monkeypatch, capsys
    ):
        script_reader = utils.scripted_prompt(
            (
                "22w14infinite",
                "N",
                "",
            )
        )
        monkeypatch.setattr("builtins.input", script_reader)

        shulker_box = craft._prompt_for_filters(
            ShulkerBox(0, "tester", Path("ignored"), (), ()), []
        )

        _ = capsys.readouterr()

        assert shulker_box.match_criteria == (
            ("minecraft", ("22w14infinite",)),
            ("modloader", ("",)),
            ("tags", ("*",)),
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()

    def test_filter_prompt_stops_confirming_once_youre_out_of_instances(
        self, monkeypatch, capsys
    ):
        script_reader = utils.scripted_prompt(
            (
                "22w14infinite",
                "y",
                "b",
                "april-fools*",
            )
        )
        monkeypatch.setattr("builtins.input", script_reader)

        shulker_box = craft._prompt_for_filters(
            ShulkerBox(0, "tester", Path("ignored"), (), ()), utils.TESTING_INSTANCES
        )

        _ = capsys.readouterr()

        assert shulker_box.match_criteria == (
            ("minecraft", ("22w14infinite",)),
            ("modloader", ("Fabric Loader",)),
            ("tags", ("april-fools*",)),
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()

    def test_filter_prompt_lets_you_back_out_of_a_mistake(
        self, monkeypatch, capsys, caplog
    ):
        script_reader = utils.scripted_prompt(
            (
                "1.19.5",
                "",  # default is no
                "1.19",
                "",  # default is yes
                "N,B,Q",
                "",
                "vanilla*",
                "",
            )
        )

        monkeypatch.setattr("builtins.input", script_reader)

        shulker_box = craft._prompt_for_filters(
            ShulkerBox(0, "tester", Path("ignored"), (), ()), utils.TESTING_INSTANCES
        )

        _ = capsys.readouterr()

        assert shulker_box.match_criteria == (
            ("minecraft", ("1.19",)),
            ("modloader", ("", "Fabric Loader", "Quilt Loader")),
            ("tags", ("vanilla*",)),
        )

        # check that it was showing the right instances right up until the end
        assert caplog.records[-1].msg % caplog.records[-1].args == (
            """Filters match the instances:
  - official
  - Chest Boat"""
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()


class TestPromptByName:
    def test_confirms_selections(self, monkeypatch, capsys, caplog):
        script_reader = utils.scripted_prompt(
            (
                "abra, kadabra, alakazam",
                "",  # default should be yes here
            )
        )
        monkeypatch.setattr("builtins.input", script_reader)

        shulker_box = craft._prompt_for_instance_names(
            ShulkerBox(0, "tester", Path("ignored"), (), ())
        )

        _ = capsys.readouterr()

        assert shulker_box.match_criteria == (
            ("instances", ("abra", "kadabra", "alakazam")),
        )

        assert caplog.records[-1].msg % caplog.records[-1].args == (
            """You specified the following instances:
  - abra
  - kadabra
  - alakazam"""
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()

    def test_default_for_confirmation_is_no_if_empty_response(
        self,
        monkeypatch,
        capsys,
        caplog,
    ):
        script_reader = utils.scripted_prompt(
            (
                "",
                "",
                "",
                "yes",
            )
        )
        monkeypatch.setattr("builtins.input", script_reader)

        shulker_box = craft._prompt_for_instance_names(
            ShulkerBox(0, "tester", Path("ignored"), (), ())
        )

        _ = capsys.readouterr()

        assert shulker_box.match_criteria == (("instances", ("*",)),)

        assert (
            "This shulker box will be applied to all instances"
            in caplog.records[-1].msg
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()


class TestPromptByNumber:
    def test_defaults_results_in_explicit_enumeration(self, monkeypatch, capsys):
        script_reader = utils.scripted_prompt(
            (
                "",
                "",
            )
        )
        monkeypatch.setattr("builtins.input", script_reader)

        def get_instances():
            return utils.TESTING_INSTANCES

        shulker_box = craft._prompt_for_instance_numbers(
            ShulkerBox(0, "tester", Path("ignored"), (), ()),
            get_instances(),
            get_instances,
        )

        _ = capsys.readouterr()

        assert shulker_box.match_criteria == (
            ("instances", tuple(instance.name for instance in utils.TESTING_INSTANCES)),
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()

    def test_number_selection_supports_explicit_numbers_and_ranges(
        self, monkeypatch, capsys
    ):
        script_reader = utils.scripted_prompt(
            (
                "4, 2 - 3",
                "",
            )
        )
        monkeypatch.setattr("builtins.input", script_reader)

        def get_instances():
            return utils.TESTING_INSTANCES

        shulker_box = craft._prompt_for_instance_numbers(
            ShulkerBox(0, "tester", Path("ignored"), (), ()),
            get_instances(),
            get_instances,
        )

        _ = capsys.readouterr()

        assert shulker_box.match_criteria == (
            (
                "instances",
                tuple(instance.name for instance in utils.TESTING_INSTANCES[1:4]),
            ),
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()

    def test_invalid_selection_reminds_you_of_the_instance_list(
        self, monkeypatch, capsys, caplog
    ):
        script_reader = utils.scripted_prompt(
            (
                "7",
                "1, 3",
                "",
            )
        )
        monkeypatch.setattr("builtins.input", script_reader)

        def get_instances():
            logging.info(
                """These are the instances that are currently registered:
  1. official (~/.minecraft)
  2. axolotl (instances/axolotl/.minecraft)
  3. bee (instances/bee/.minecraft)
  4. Chest Boat (instances/chest-boat/.minecraft)"""
            )
            return utils.TESTING_INSTANCES

        shulker_box = craft._prompt_for_instance_numbers(
            ShulkerBox(0, "tester", Path("ignored"), (), ()),
            get_instances(),
            get_instances,
        )

        _ = capsys.readouterr()

        assert """Invalid selection: 7 is out of range

These are the instances that are currently registered:
  1. official (~/.minecraft)
  2. axolotl (instances/axolotl/.minecraft)
  3. bee (instances/bee/.minecraft)
  4. Chest Boat (instances/chest-boat/.minecraft)""" in "\n".join(
            record.msg for record in caplog.records
        )

        assert shulker_box.match_criteria == (
            (
                "instances",
                ("official", "bee"),
            ),
        )

        # make sure all responses were used
        with pytest.raises(StopIteration):
            script_reader()
