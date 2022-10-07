"""Test functionality around creating the EnderChest folder"""
from pathlib import Path

from enderchest import contexts, craft


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

    def test_craft_expands_user(self, tmp_path, monkeypatch):
        generated_contexts = []

        def patched_contexts(*args, **kwargs):
            """Don't actually want to create a bunch of folders in my home
            directory, so instead just snag the folders that *would* have been
            generated and return a Context in a tmpdir"""
            generated_contexts.append(contexts(*args, **kwargs))
            return contexts(tmp_path)

        monkeypatch.setattr(craft, "contexts", patched_contexts)
        craft.craft_ender_chest("~/minecraft", craft_folders_only=True)

        assert (
            generated_contexts[0].universal.parent.parent == Path.home() / "minecraft"
        )
