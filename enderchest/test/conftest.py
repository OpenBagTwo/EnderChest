"""Useful setup / teardown fixtures"""
import importlib.resources
from pathlib import Path

import pytest

from enderchest.craft import craft_ender_chest


@pytest.fixture
def local_root(tmp_path):
    """A temporary local minecraft root folder (initially instantiated without an
    EnderChest)"""
    local_root = tmp_path / "minecraft"
    (local_root / "instances").mkdir(parents=True)
    (local_root / "servers").mkdir(parents=True)
    (local_root / "worlds").mkdir(
        parents=True
    )  # makes sense to store the actual saves outside the EnderChest folder
    (local_root / "workspace").mkdir(
        parents=True
    )  # generic other stuff that exists in the minecraft root

    do_not_touch: dict[Path, str] = {
        local_root / "README.md": "#Hello\n\nI'm your friendly neighborhood README!\n",
        (
            local_root / "workspace" / "cool_project.py"
        ): 'print("Gosh, I hope no one deletes or overwrites me")\n',
        (
            local_root
            / "instances"
            / "worlds_best_modpack"
            / ".minecraft"
            / "mods"
            / "worldsbestmod.jar"
        ): "beepboop",
        local_root / "worlds" / "olam" / "level.dat": "level dis\n",
        (
            local_root / "workspace" / "neat_resource_pack" / "pack.mcmeta"
        ): '{"so": "meta"}\n',
    }
    mod_builds_folder = local_root / "workspace" / "BestModEver" / "build" / "libs"

    do_not_touch.update(
        {
            mod_builds_folder / "BME_1.19_alpha.jar": "alfalfa",
            mod_builds_folder / "BME_1.19.1_beta.jar": "beater",
            mod_builds_folder / "BME_1.19.2_nightly.jar": "can i get a bat",
        }
    )

    for path, contents in do_not_touch.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)

    yield local_root

    # check on teardown that all those "do_not_touch" files are untouched
    for path, contents in do_not_touch.items():
        assert path.read_text() == contents


@pytest.fixture
def local_enderchest(local_root):
    """An existing EnderChest directory within the local root that's got some stuff
    in it (but critically no sync scripts)
    """
    craft_ender_chest(local_root, craft_folders_only=True)

    chest_folder = local_root / "EnderChest"

    do_not_touch: dict[Path, str] = {
        chest_folder / ".git" / "log": "i committed some stuff\n",
        (
            chest_folder / "client-only" / "resourcepacks" / "stuff.zip@axolotl"
        ): "dfgwhgsadfhsd",
        (
            chest_folder
            / "local-only"
            / "shaderpacks"
            / "Seuss CitH.zip.txt@axolotl@bee@cow"
        ): (
            "with settings at max"
            "\nits important to note"
            "\nthe lag is real bad"
            "\nbut just look at that goat!"
        ),
    }

    (
        chest_folder / "global" / "resourcepacks" / "neat_resource_pack@axolotl@bee"
    ).symlink_to(local_root / "workspace" / "neat_resource_pack")

    symlinks: dict[Path, Path] = {  # map of links to targets
        (chest_folder / "client-only" / "saves" / "olam@axolotl@bee@cow"): (
            local_root / "worlds" / "olam"
        ),
        (chest_folder / "global" / "mods" / "BME.jar@axolotl"): (
            local_root
            / "workspace"
            / "BestModEver"
            / "build"
            / "libs"
            / "BME_1.19_alpha.jar"
        ),
        (chest_folder / "global" / "mods" / "BME.jar@bee"): (
            local_root
            / "workspace"
            / "BestModEver"
            / "build"
            / "libs"
            / "BME_1.19.1_beta.jar"
        ),
        (chest_folder / "global" / "mods" / "BME.jar@cow"): (
            local_root
            / "workspace"
            / "BestModEver"
            / "build"
            / "libs"
            / "BME_1.19.2_nightly.jar"
        ),
    }

    for path, contents in do_not_touch.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)

    for link_path, target in symlinks.items():
        link_path.parent.mkdir(parents=True, exist_ok=True)
        link_path.symlink_to(target)

    yield chest_folder

    for link_path, target in symlinks.items():
        assert link_path.resolve() == target.resolve()

    for path, contents in do_not_touch.items():
        assert path.read_text() == contents


@pytest.fixture
def example_config_path():
    with importlib.resources.path(
        "enderchest.test", "example_configs"
    ) as example_configs:
        yield example_configs / "example.cfg"
