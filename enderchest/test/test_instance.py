from pathlib import Path

import pytest

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


class TestInstanceMerging:
    def test_supplying_no_instances_raises_a_sensible_error(self):
        with pytest.raises(ValueError, match="at least one instance"):
            i.merge()

    def test_merging_a_single_instance_results_in_a_copy(self):
        original = instance(
            name="an instance",
            root=Path("."),
            minecraft_versions=("1.21.0",),
            modloader="linen",
            groups=("experimental",),
            tags=("a", "b"),
        )

        merged = i.merge(original)

        assert original is not merged
        assert original == merged

    @pytest.mark.parametrize(
        "field",
        (field for field in i.InstanceSpec._fields if field not in ("name", "tags_")),
    )
    def test_merged_fields_mostly_match_the_last_instance(self, field):
        instances = [
            instance("one", Path("path"), minecraft_versions=("1.20.2",)),
            instance(
                "two",
                Path("path"),
                modloader="blacksmith",
                groups=("forgery",),
                tags=("you're it",),
            ),
            instance(
                "three",
                Path("path"),
                minecraft_versions=("1.21-pre1",),
                groups=("next_gen",),
            ),
        ]

        merged = i.merge(*instances)

        assert getattr(merged, field) == getattr(instances[-1], field)

    def test_merged_name_matches_the_first_instance(self):
        instances = [
            instance("one", Path("path"), tags=("you're it",)),
            instance("two", Path("path"), tags=("hello", "friend")),
            instance("three", Path("path"), tags=("hello", "world")),
            instance("four", Path("path"), tags=("best", "friend")),
            instance("five", Path("path")),
        ]

        merged = i.merge(*instances)

        assert merged.name == "one"

    def test_merged_tags_are_the_union_of_all_instance_tags(self):
        instances = [
            instance("one", Path("path"), tags=("you're it",)),
            instance("two", Path("path"), tags=("hello", "friend")),
            instance("three", Path("path"), tags=("hello", "world")),
            instance("four", Path("path"), tags=("best", "friend")),
            instance("five", Path("path")),
        ]

        merged = i.merge(*instances)

        assert merged.tags_ == ("best", "friend", "hello", "world", "you're it")
