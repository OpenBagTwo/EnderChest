"""Tests of the sync-helper utilities"""
import os
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest

from enderchest.sync import file
from enderchest.sync import utils as sync_utils
from enderchest.sync.utils import Operation as Op


class TestPathFromURI:
    def test_roundtrip(self, tmpdir):
        original_path = Path(tmpdir) / "this has a space in it" / "(="
        assert (
            sync_utils.path_from_uri(urlparse(original_path.as_uri())) == original_path
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
        assert address == "nugget@localhost:/home/nugget"


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
        shutil.copy(one, two)
        assert sync_utils.is_identical(one.stat(), two.stat())

    def test_modified_files_are_not_identical(self, tmp_path):
        one = tmp_path / "one"
        one.write_text("I'm the original")
        two = tmp_path / "two"
        shutil.copy(one, two)
        with two.open("a") as f:
            f.write("\n")
        assert not sync_utils.is_identical(one.stat(), two.stat())

    def test_checks_modified_time(self, tmp_path):
        one = tmp_path / "one"
        one.write_text("I'm the original")
        two = tmp_path / "two"
        shutil.copy(one, two)
        time.sleep(0.01)
        two.write_text("I'm the original")

        # meta-test that the file contents are identical
        assert one.read_bytes() == two.read_bytes()

        assert not sync_utils.is_identical(one.stat(), two.stat())

    @pytest.mark.xfail(reason="Method does not compute hashes")
    def test_two_files_of_the_same_size_are_not_identical(self, tmp_path):
        one = tmp_path / "one"
        one.write_text("I'm the original")
        two = tmp_path / "two"
        two.write_text("I'm the octagonl")

        assert not sync_utils.is_identical(one.stat(), two.stat())


class TestDiff:
    @pytest.fixture
    def file_system(self, tmp_path):
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
        (dst_tree / "branch" / "acorn").touch()
        (dst_tree / "beehive").touch()
        (dst_tree / "root").mkdir()
        (dst_tree / "root" / "cicada").touch()

        yield tmp_path

    @pytest.fixture
    def diff(self, file_system):
        yield sync_utils.diff(
            file.get_contents(file_system / "oak"),
            file.get_contents(file_system / "birch"),
        )

    def test_diff_omits_identical_contents(self, diff):
        assert {
            Path("branch") / "acorn",
            Path("branch") / "twig",
            Path("branch"),
        }.intersection((f for f, _ in diff)) == set()

    def test_diff_captures_updates(self, diff):
        assert [Path("branch") / "leaf"] == [f for f, op in diff if op == Op.REPLACE]

    def test_diff_captures_creation_of_files_and_folders(self, diff):
        assert {
            Path("branch2") / "acorn",
            Path("branch2"),
        } == {f for f, op in diff if op == Op.CREATE}

    def test_diff_captures_deletion_of_files_and_folders(self, diff):
        assert {
            Path("beehive"),
            Path("root"),
            Path("root") / "cicada",
        } == {f for f, op in diff if op == Op.DELETE}


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
