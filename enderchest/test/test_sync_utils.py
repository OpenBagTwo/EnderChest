"""Tests of the sync-helper utilities"""
import importlib
import logging
import os
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest

from enderchest import sync
from enderchest.sync import file
from enderchest.sync import utils as sync_utils
from enderchest.sync.utils import Operation as Op


class TestDetermineAvailableProtocols:
    def test_available_protocols_only_include_resolvable_modules(self, monkeypatch):
        monkeypatch.setattr(sync, "PROTOCOLS", ("file", "subspace"))
        assert sync._determine_available_protocols() == ("file",)


class TestPathFromURI:
    def test_roundtrip(self, tmpdir):
        original_path = Path(tmpdir) / "this has a space in it" / "(="
        assert (
            sync_utils.abspath_from_uri(urlparse(original_path.as_uri()))
            == original_path
        )


class TestURIToSSH:
    def test_simple_parse(self):
        address = sync_utils.uri_to_ssh(
            urlparse("rsync://openbagtwo@couchgaming:22/home/openbagtwo/minecraft")
        )
        assert address == "openbagtwo@couchgaming:22:/home/openbagtwo/minecraft"

    def test_no_username_parse(self):
        address = sync_utils.uri_to_ssh(
            urlparse("rsync://steamdeck/home/openbagtwo/minecraft")
        )
        assert address == "steamdeck:/home/openbagtwo/minecraft"

    def test_no_netloc_parse(self):
        address = sync_utils.uri_to_ssh(urlparse("rsync:///mnt/external/minecraft-bkp"))
        assert address == "localhost:/mnt/external/minecraft-bkp"

    def test_no_hostname_parse(self):
        """Can't believe this is a valid URI"""
        address = sync_utils.uri_to_ssh(urlparse("rsync://nugget@/home/nugget/"))
        assert address == "nugget@localhost:/home/nugget/"


class TestRenderRemote:
    @pytest.mark.parametrize("alias", ("matching", "not-matching"))
    def test_render_omits_alias_only_if_it_matches_hostname(self, alias):
        uri = "prtcl://youser@matching:101/some/directory"
        rendered = sync_utils.render_remote(alias, urlparse(uri))
        if alias == "matching":
            assert rendered == uri
        else:
            assert rendered == uri + " (not-matching)"


class TestIsIdentical:
    def test_copied_files_are_identical(self, tmp_path):
        one = tmp_path / "one"
        one.write_text("I'm the original\n")
        two = tmp_path / "two"
        shutil.copy2(one, two)
        assert sync_utils.is_identical(one.stat(), two.stat())

    def test_modified_files_are_not_identical(self, tmp_path):
        one = tmp_path / "one"
        one.write_text("I'm the original")
        two = tmp_path / "two"
        shutil.copy2(one, two)
        with two.open("a") as f:
            f.write("\n")
        assert not sync_utils.is_identical(one.stat(), two.stat())

    @pytest.mark.parametrize("target_type", ("file", "folder"))
    def test_symlink_is_not_identical_to_its_target(self, tmp_path, target_type):
        target = tmp_path / "bulleye"
        if target_type == "file":
            target.touch()
        else:
            target.mkdir()

        linky = tmp_path / "linky"
        linky.symlink_to(target, target_is_directory=target_type == "folder")

        assert not sync_utils.is_identical(target.lstat(), linky.lstat())

    def test_checks_modified_time(self, tmp_path):
        one = tmp_path / "one"
        one.write_text("I'm the original")
        two = tmp_path / "two"
        shutil.copy(one, two)
        time.sleep(1)  # ugh
        two.write_text("I'm the original")

        # meta-test that the file contents are identical
        assert one.read_bytes() == two.read_bytes()

        assert not sync_utils.is_identical(one.stat(), two.stat())

    def test_does_not_check_modified_time_of_directories(self, tmp_path):
        one = tmp_path / "one"
        one.mkdir(parents=True)
        two = tmp_path / "two"
        time.sleep(1)  # ugh
        two.mkdir()
        assert sync_utils.is_identical(one.stat(), two.stat())

    @pytest.mark.xfail(reason="Method does not compute hashes")
    def test_two_files_of_the_same_size_are_not_identical(self, tmp_path):
        one = tmp_path / "one"
        one.write_text("I'm the original")
        two = tmp_path / "two"
        two.write_text("I'm the octagonl")

        assert not sync_utils.is_identical(one.stat(), two.stat())


@pytest.fixture
def file_system(tmp_path):
    source_tree = tmp_path / "oak"
    (source_tree / "branch").mkdir(parents=True)
    (source_tree / "branch" / "twig").mkdir()
    (source_tree / "branch" / "leaf").write_text("green")
    (source_tree / "branch" / "acorn").touch()
    (source_tree / "branch2").mkdir()
    (source_tree / "branch2" / "acorn").touch()

    dst_tree = tmp_path / "birch"
    (dst_tree / "branch").mkdir(parents=True)
    (dst_tree / "branch" / "twig").mkdir()
    (dst_tree / "branch" / "leaf").write_text("yellow")
    shutil.copy2((source_tree / "branch" / "acorn"), (dst_tree / "branch" / "acorn"))
    (dst_tree / "beehive").touch()
    (dst_tree / "root").mkdir()
    (dst_tree / "root" / "cicada").touch()

    yield tmp_path


@pytest.fixture
def diff(file_system):
    yield sync_utils.diff(
        file.get_contents(file_system / "oak"),
        file.get_contents(file_system / "birch"),
    )


class TestDiff:
    def test_diff_omits_identical_contents(self, diff):
        assert {
            Path("branch") / "acorn",
            Path("branch") / "twig",
            Path("branch"),
        }.intersection((f for f, *_ in diff)) == set()

    def test_diff_captures_updates(self, diff):
        assert [Path("branch") / "leaf"] == [f for f, _, op in diff if op == Op.REPLACE]

    def test_diff_captures_creation_of_files_and_folders(self, diff):
        assert [
            Path("branch2"),
            Path("branch2") / "acorn",
        ] == [f for f, _, op in diff if op == Op.CREATE]

    def test_diff_captures_deletion_of_files_and_folders(self, diff):
        assert [
            Path("root") / "cicada",
            Path("beehive"),
            Path("root"),
        ] == [f for f, _, op in diff if op == Op.DELETE]


class TestGenerateSyncReport:
    def test_generate_sync_report(self, diff, caplog):
        expected = [
            "Deleting beehive",
            """Within branch...
  - Creating 0 files
  - Replacing 1 file
  - Deleting 0 files""",
            "Creating branch2",
            "Deleting root",
        ]

        sync_utils.generate_sync_report(diff)

        info_logs = [
            (record.msg % record.args).strip()
            for record in caplog.records
            if record.levelno == logging.INFO
        ]

        assert info_logs == expected


class TestFileIgnorePatternBuilder:
    def test_simple_match(self):
        assert file.ignore_patterns("hello")(
            "greetings", ("bonjour", "hello", "hellooooo")
        ) == {"hello"}

    def test_wildcard(self):
        assert file.ignore_patterns("hel*")(
            "responses", ("como sa va", "hello", "hell no", "help")
        ) == {"hello", "hell no", "help"}

    def test_multi_pattern_match(self):
        assert file.ignore_patterns("hel*", "bye")(
            "responses", ("hello", "goodbye", "hellooo", "bye")
        ) == {"hello", "hellooo", "bye"}

    def test_full_path_check(self):
        ignore = file.ignore_patterns(os.path.join("root", "branch"))
        assert (
            ignore("root", ("branch", "trunk")),
            ignore("trunk", ("branch", "leaf")),
        ) == ({"branch"}, set())

    def test_match_is_performed_on_the_end(self):
        ignore = file.ignore_patterns(os.path.join("root", "branch"), "leaf")
        assert (
            ignore(os.path.join("tree", "root"), ("branch", "trunk")),
            ignore("wind", ("leaf", "blows")),
        ) == ({"branch"}, {"leaf"})


class TestFileClean:
    def test_clean_cleans_recursively_while_respecting_ignore(self, tmp_path):
        root = tmp_path / "root"

        (root / "empty dir").mkdir(parents=True)
        (root / "will be empty").mkdir()
        (root / "will be empty" / "filey").touch()
        (root / "will not be empty").mkdir()
        (root / "will not be empty" / "file-o bread").touch()
        (root / "will not be empty" / "important.txt").write_text("leave me be\n")
        (root / "dont go inside").mkdir()
        (root / "dont go inside" / "keep me safe").touch()
        (root / "tricky linky").symlink_to(root / "will not be empty")
        (root / "trickier linkier").symlink_to(root / "dont go inside")

        file.clean(root, ignore=file.ignore_patterns("*.txt", "dont*"), dry_run=False)

        assert set(root.rglob("**/*")) == {
            root / "will not be empty",
            root / "will not be empty" / "important.txt",
            root / "dont go inside",
            root / "dont go inside" / "keep me safe",
        }
