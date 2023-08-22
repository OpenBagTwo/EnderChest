"""Tests of the sync-helper utilities"""
import os
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest

from enderchest.sync import file
from enderchest.sync import utils as sync_utils


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
