"""Test functionality around creating the EnderChest folder"""
from enderchest import craft


class TestCraftEnderChest:
    def test_new_ender_chest_has_correct_top_level_structure(self, local_root):
        assert not (local_root / "EnderCheest").exists()

        craft.craft_ender_chest(local_root)

        assert sorted(
            (path.name for path in (local_root / "EnderChest").glob("*"))
        ) == [
            "client-only",
            "global",
            "local-only",
            "other-locals",
            "server-only",
        ]

    def test_crafting_a_chest_where_theres_already_a_chest_is_fine(
        self, local_enderchest
    ):
        craft.craft_ender_chest(local_enderchest / "..")

        assert {
            "client-only",
            "global",
            "local-only",
            "other-locals",
            "server-only",
        }.issubset((path.name for path in local_enderchest.glob("*")))
