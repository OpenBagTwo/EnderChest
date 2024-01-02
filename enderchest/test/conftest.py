"""Useful setup / teardown fixtures"""
from importlib.resources import as_file
from pathlib import Path
from typing import Generator

import pytest

from .testing_files import CLIENT_OPTIONS
from .utils import (
    TESTING_SHULKER_CONFIGS,
    populate_instances_folder,
    populate_official_minecraft_folder,
    pre_populate_enderchest,
)


@pytest.fixture
def use_local_ssh(request):
    """h/t https://stackoverflow.com/a/55003726
    (though it's also in the pytest docs lol)
    """
    return request.config.getoption("--use-local-ssh", False)


@pytest.fixture
def file_system(tmp_path) -> Generator[tuple[Path, Path], None, None]:
    """Create a testing file system and throw a bunch of random files across
    it.

    This method serves as both a setup and a teardown, as nothing
    in EnderChest's operations should be messing with these files, and
    this fixture asserts as such"""

    minecraft_root = tmp_path / "minecraft"
    minecraft_root.mkdir(parents=True)

    populate_instances_folder(minecraft_root / "instances")

    home = tmp_path / "home"
    home.mkdir(parents=True)

    populate_official_minecraft_folder(home / ".minecraft")

    (minecraft_root / "worlds").mkdir(
        parents=True
    )  # makes sense to store the actual saves outside the EnderChest folder
    (minecraft_root / "workspace").mkdir(
        parents=True
    )  # generic other stuff that exists in the minecraft root

    # files that EnderChest should not touch
    # (map) of file paths to their contents
    do_not_touch: dict[Path, str] = {
        minecraft_root
        / "README.md": "#Hello\n\nI'm your friendly neighborhood README!\n",
        (
            minecraft_root / "workspace" / "cool_project.py"
        ): 'print("Gosh, I hope no one deletes or overwrites me")\n',
        minecraft_root / "worlds" / "olam" / "level.dat": "level dis\n",
        minecraft_root / "worlds" / "testbench" / "level.dat": "hello world\n",
        (
            minecraft_root / "workspace" / "neat_resource_pack" / "pack.mcmeta"
        ): '{"so": "meta"}\n',
        (minecraft_root / "resourcepacks" / "TEAVSRP.zip"): "Breaking News!\n",
        (
            minecraft_root / "crash-reports" / "20230524.log"
        ): "ERROR: Everything is broken\nWARNING: And somehow also on fire\n",
        (
            minecraft_root / "instances" / "axolotl" / ".minecraft" / "options.txt"
        ): "renderDistance:1\n",
        home / "Pictures" / "Screenshots" / "sunrise.png": "PRETTY!!!\n",
    }

    with as_file(CLIENT_OPTIONS) as options_txt:
        do_not_touch[home / ".minecraft" / "options.txt"] = options_txt.read_text()

    mod_builds_folder = minecraft_root / "workspace" / "BestModEver" / "build" / "libs"

    do_not_touch.update(
        {
            mod_builds_folder / "BME_1.19_alpha.jar": "alfalfa",
            mod_builds_folder / "BME_1.19.1_beta.jar": "beater",
            mod_builds_folder / "BME_1.19.2_nightly.jar": "can i get a bat",
        }
    )

    chest_folder = minecraft_root / "EnderChest"

    do_not_touch.update(
        {
            chest_folder / ".git" / "log": "i committed some stuff\n",
            chest_folder / "global" / "usercache.json": "alexander\nmomoa\nbateman\n",
            (
                chest_folder / "global" / "config" / "iris.properties"
            ): "flower or aperture?\n",
        }
    )

    symlinks: dict[Path, Path] = {  # map of links to targets
        minecraft_root / "official_launcher" / ".minecraft": home / ".minecraft",
        (
            minecraft_root
            / "instances"
            / "chest-boat"
            / ".minecraft"
            / "mods"
            / "BME.jar"
        ): (mod_builds_folder / "BME_1.19_alpha.jar"),
        (chest_folder / "global" / "crash-reports"): (minecraft_root / "crash-reports"),
        (chest_folder / "global" / "resourcepacks"): (minecraft_root / "resourcepacks"),
        (chest_folder / "global" / "screenshots"): (home / "Pictures" / "Screenshots"),
        (chest_folder / "global" / "saves" / "test"): (
            minecraft_root / "worlds" / "testbench"
        ),
        (chest_folder / "1.19" / "saves" / "olam"): (
            minecraft_root / "worlds" / "olam"
        ),
        (chest_folder / "optifine" / "mods" / "BME.jar"): (
            mod_builds_folder / "BME_1.19.2_nightly.jar"
        ),
    }

    for path, contents in do_not_touch.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)

    for link_path, target in symlinks.items():
        link_path.parent.mkdir(parents=True, exist_ok=True)
        link_path.symlink_to(target, target_is_directory=target.is_dir())

    yield home, minecraft_root

    # check on teardown that all the symlinks still point to the right places
    for link_path, target in symlinks.items():
        assert link_path.resolve() == target.resolve()

    # check on teardown that all those "do_not_touch" files are untouched
    for path, contents in do_not_touch.items():
        assert not path.is_symlink()
        assert path.read_text() == contents


@pytest.fixture
def minecraft_root(file_system, monkeypatch):
    """Direct fixture pointing to the parent of the EnderChest folder and make
    sure all of our tests are running out of the minecraft root"""
    monkeypatch.chdir(file_system[1])
    yield file_system[1]


@pytest.fixture
def home(file_system, monkeypatch):
    """Direct fixture pointing to the user's "home" folder (with monkeypatching
    used to make the OS treat it as home)
    """
    home = file_system[0]

    # make sure SSH keys are still accessible post-fixting
    (home / ".ssh").symlink_to(Path.home() / ".ssh", target_is_directory=True)

    monkeypatch.setenv("HOME", str(home))  # posix
    monkeypatch.setenv("USERPROFILE", str(home))  # windows

    # check this right away so we can abort testing if it's not working
    assert Path.home() == home

    yield home


@pytest.fixture
def multi_box_setup_teardown(minecraft_root, home):
    """Setup / teardown for complex tests involving multiple boxes
    and overlapping resources"""
    chest_folder = minecraft_root / "EnderChest"
    pre_populate_enderchest(chest_folder, *TESTING_SHULKER_CONFIGS)

    do_not_touch = {
        (chest_folder / "global" / "resourcepacks" / "stuff.zip"): "dfgwhgsadfhsd",
        (chest_folder / "global" / "logs" / "bumpona.log"): (
            "Like a bump on a bump on a log, baby.\n"
            "Like I'm in a fist fight with a fog, baby.\n"
            "Step-ball-change and a pirouette.\n"
            "And I regret, I regret.\n"
        ),
        (chest_folder / "1.19" / "mods" / "FoxNap.jar"): "hello-maestro",
        (chest_folder / "1.19" / "options.txt"): "autoJump:true",
        (
            chest_folder / "vanilla" / "data" / "achievements.txt"
        ): "Spelled acheivements correctly!",
        (chest_folder / "optifine" / "mods" / "optifine.jar"): "sodium4life",
        (chest_folder / "optifine" / "shaderpacks" / "Seuss CitH.zip"): (
            "But those trees! Oh those trees! But those truffula trees!"
            "\nAll resplendent and gorgeous in ray-traced 3Ds"
        ),
        (
            chest_folder / "optifine" / "resourcepacks" / "stuff.zip"
        ): "optifine-optimized!",
        (
            minecraft_root
            / "instances"
            / "bee"
            / ".minecraft"
            / "shaderpacks"
            / "Seuss CitH.zip.txt"
        ): (
            "with settings at max"
            "\nits important to note"
            "\nthe lag is real bad"
            "\nbut just look at that goat!"
        ),
    }

    for path, contents in do_not_touch.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)

    yield

    # check on teardown that all those "do_not_touch" files are untouched
    for path, contents in do_not_touch.items():
        assert path.read_text("utf-8") == contents


@pytest.fixture(autouse=True)
def set_log_levels(caplog):
    with caplog.at_level(20):
        yield
