from pathlib import Path
from typing import Iterable

from enderchest import instance as i

from .utils import instance


class TestInstanceEquality:
    def test_two_instances_with_different_paths_are_not_equal(self):
        assert not i.equals(
            Path(), instance("foo", Path("a")), instance("foo", Path("b"))
        )

    def test_two_instances_with_the_same_path_are_equal(self):
        assert i.equals(Path(), instance("foo", Path("a")), instance("fufu", Path("a")))

    def test_two_instances_with_the_same_abspath_are_equal(self, minecraft_root):
        assert i.equals(
            minecraft_root,
            instance("foo", minecraft_root / "instances" / "axolotl"),
            instance("fufu", Path("instances/axolotl")),
        )

    def test_equality_check_works_with_expanduser(self, minecraft_root, home):
        assert i.equals(
            minecraft_root,
            instance("foo", home / "Library" / "SomeKindOfMC" / "Instances" / "foo"),
            instance("fufu", Path("~/Library/SomeKindOfMC/Instances/foo")),
        )

    def test_equality_check_works_with_minecraft_root_in_home(self, home):
        assert i.equals(
            Path("~/Library/SomeKindOfMC"),
            instance("foo", Path("Instances") / "foo"),
            instance("fufu", Path("~/Library/SomeKindOfMC/Instances/foo")),
        )

    def test_equality_resolves_symlinks(self, home, minecraft_root):
        assert i.equals(
            minecraft_root,
            instance("foo", Path("official_launcher") / ".minecraft"),
            instance("fufu", Path("~/.minecraft")),
        )
