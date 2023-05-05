"""Test the config parser"""
import itertools
import warnings
from configparser import ConfigParser, ParsingError

import pytest

from enderchest import config
from enderchest.sync import Remote, RemoteSync


@pytest.fixture
def example_config_parser(example_config_path):
    parser = ConfigParser()
    with example_config_path.open() as config_file:
        parser.read_file(config_file)
    yield parser


class TestParseString:
    @pytest.mark.parametrize("entry", ("'hello'", '"hello"'))
    def test_strip_simple_quotes(self, entry):
        assert config._parse_string(entry) == "hello"

    @pytest.mark.parametrize("quote_char", ("'''", '"""'))
    def test_strip_multiline_quotes(self, quote_char):
        entry = f"{quote_char}\nhello\n{quote_char}"
        assert config._parse_string(entry) == "\nhello\n"  # read: doesn't strip

    def test_unquoted_string_is_left_alone(self):
        entry = 'echo "hello"'
        assert config._parse_string(entry) == entry

    def test_string_with_mismatching_quotes_is_left_alone(self):
        entry = "'what I'm trying to say is\""
        assert config._parse_string(entry) == entry


class TestParsePreOrPostCommandEntry:
    def test_parsing_a_simple_string(self):
        assert config._parse_pre_or_post_command_entry("echo hello") == ["echo hello"]

    def test_parsing_a_single_line_list_of_commands(self):
        assert config._parse_pre_or_post_command_entry(
            '["echo hello", "echo what a lovely day"]'
        ) == [
            "echo hello",
            "echo what a lovely day",
        ]

    def test_parsing_a_multiline_line_list_of_commands(self):
        # TODO: put a note in a doc somewhere about Windows and backslashes
        assert (
            config._parse_pre_or_post_command_entry(
                r"""[
    "C:\\DOS",
    "C:\\DOS\\run",
    "run DOS\\run"
]
"""
            )
            == [
                r"C:\DOS",
                r"C:\DOS\run",
                r"run DOS\run",
            ]
        )


class TestParsePreAndPostCommands:
    def test_section_with_no_wrapper_commands_still_gives_full_dict(
        self, example_config_parser
    ):
        assert config._parse_pre_and_post_commands(
            example_config_parser["nuggets_laptop"]
        ) == {"pre_open": [], "pre_close": [], "post_open": [], "post_close": []}

    def test_parsing_section_with_unquoted_command(self, example_config_parser):
        assert config._parse_pre_and_post_commands(example_config_parser["options"])[
            "post_open"
        ] == [
            "cd /main/minecraft/EnderChest"
            " && git add ."
            ' && git commit -m "Pulled changes from remotes"'
        ]

    def test_parsing_section_with_quoted_command(self, example_config_parser):
        assert config._parse_pre_and_post_commands(example_config_parser["options"])[
            "post_close"
        ] == [
            "cd /main/minecraft/EnderChest"
            " && git add ."
            ' && git commit -m "Pushing out local changes"'
        ]

    def test_parsing_section_with_multiline_commands(self, example_config_parser):
        assert config._parse_pre_and_post_commands(
            example_config_parser["couch-potato"]
        ) == {
            "pre_open": [],
            "pre_close": ["lectern return $active_world"],
            "post_open": ["lectern checkout $active_world"],
            "post_close": [],
        }


class TestParseRemoteSection:
    @pytest.mark.parametrize(
        "alias", ("couch-potato", "steam-deck.local", "nuggets_laptop")
    )
    def test_alias_comes_from_the_section_header(self, example_config_parser, alias):
        remote = config._parse_remote_section(example_config_parser[alias]).remote
        assert remote.alias == alias

    def test_root_is_required(self):
        parser = ConfigParser()
        parser.read_string(
            """
[floating]
blah=blah
"""
        )
        with pytest.raises(ParsingError, match=r"(floating(.*)root|root(.*)floating)"):
            config._parse_remote_section(parser["floating"])

    def test_parsing_root(self, example_config_parser):
        remote = config._parse_remote_section(
            example_config_parser["couch-potato"]
        ).remote

        assert str(remote.root) == "~/Games/minecraft"

    def test_host_is_alias_by_default(self, example_config_parser):
        remote = config._parse_remote_section(
            example_config_parser["steam-deck.local"]
        ).remote
        assert remote.host == "steam-deck.local"

    def test_setting_host_explicitly(self, example_config_parser):
        remote = config._parse_remote_section(
            example_config_parser["couch-potato"]
        ).remote
        assert remote.host == "192.168.0.101"

    def test_conflicting_hosts_raises_error(self):
        parser = ConfigParser()
        parser.read_string(
            """
[banjo_man]  # you can't tie down a banjo man
hostname=Ms. Bliss
address=on the road
root=/cul/de/sac
"""
        )

        # I don't care about the order, and I'm too lazy and typo-prone to
        # enumerate all 3! permutations by hand
        patterns: list[str] = []
        for permutation in itertools.permutations(("banjo_man", "conflicting", "host")):
            patterns.append(r"(.*)".join(permutation))
        with pytest.raises(ParsingError, match=rf'({"|".join(patterns)})'):
            config._parse_remote_section(parser["banjo_man"])

    def test_no_username_by_default(self, example_config_parser):
        remote = config._parse_remote_section(
            example_config_parser["couch-potato"]
        ).remote
        assert remote.remote_folder == "192.168.0.101:~/Games/minecraft"

    @pytest.mark.parametrize(
        "keyword, alias, expected",
        (
            ("username", "steam-deck.local", "deck"),
            ("user", "nuggets_laptop", "nugget"),
        ),
    )
    def test_setting_username(self, example_config_parser, keyword, alias, expected):
        remote = config._parse_remote_section(example_config_parser[alias]).remote
        assert remote.remote_folder.startswith(f"{expected}@")

    def test_conflicting_username_raises_error(self):
        parser = ConfigParser()
        parser.read_string(
            """
[steve miller band]
root=les/paul
user=space cowboy
username=Maurice (wah wah)
"""
        )

        # I don't care about the order, and I'm too lazy and typo-prone to
        # enumerate all 3! permutations by hand
        patterns: list[str] = []
        for permutation in itertools.permutations(
            ("steve miller band", "conflicting", "user")
        ):
            patterns.append(r"(.*)".join(permutation))
        with pytest.raises(ParsingError, match=rf'({"|".join(patterns)})'):
            config._parse_remote_section(parser["steve miller band"])

    def test_remote_parsing_grabs_wrapper_commands(self, example_config_parser):
        remote_sync = config._parse_remote_section(
            example_config_parser["couch-potato"]
        )

        assert (
            remote_sync.pre_open,
            remote_sync.pre_close,
            remote_sync.post_open,
            remote_sync.post_close,
        ) == (
            [],
            ["lectern return $active_world"],
            ["lectern checkout $active_world"],
            [],
        )


class TestParseOptions:
    @pytest.fixture(autouse=True)
    def raise_uncaught_warnings_as_errors(self):
        with warnings.catch_warnings(record=True) as warnings_log:
            warnings.simplefilter("always")
            yield
        assert [warning.message for warning in warnings_log] == []

    @pytest.mark.parametrize("false", ("False", "false", "no", "0"))
    def test_explicitly_enabling_scare_warnings(self, false):
        parser = ConfigParser()
        parser.read_string(
            f"""
[options]
generate_runnable_scripts={false}
"""
        )
        assert (
            config._parse_options_section(parser["options"])["omit_scare_warnings"]
            is False
        )

    @pytest.mark.parametrize("true", ("True", "1", "yes", "i am sure"))
    def test_disabling_scare_warnings_without_saying_the_magic_words_is_ignored(
        self, true
    ):
        parser = ConfigParser()
        parser.read_string(
            f"""
[options]
generate_runnable_scripts={true}
"""
        )
        with pytest.warns(UserWarning, match="risk acknowledgement"):
            options = config._parse_options_section(parser["options"])
        assert options["omit_scare_warnings"] is False

    @pytest.mark.parametrize("with_quotes", (True, False))
    def test_disabling_scare_warnings_with_the_magic_words(self, with_quotes):
        magic_words = "I acknowledge that this is dangerous"
        if with_quotes:
            magic_words = f'"{magic_words}"'
        parser = ConfigParser()
        parser.read_string(
            f"""
[options]
generate_runnable_scripts={magic_words}
"""
        )
        assert (
            config._parse_options_section(parser["options"])["omit_scare_warnings"]
            is True
        )

    def test_no_scripts_overwrite_by_default(self):
        parser = ConfigParser()
        parser.read_string(
            """
[options]
dephlogisticate=True
"""
        )
        options = config._parse_options_section(parser["options"])
        assert "overwrite" not in options

    @pytest.mark.parametrize(
        "entry, expected",
        (
            *((true, True) for true in ("True", "true", "1", "yes")),
            *((false, False) for false in ("False", "false", "no", "0")),
        ),
    )
    def test_explicitly_setting_scripts_overwrite_option(self, entry, expected):
        parser = ConfigParser()
        parser.read_string(
            f"""
[options]
overwrite_scripts={entry}
"""
        )
        assert config._parse_options_section(parser["options"])["overwrite"] is expected

    def test_non_boolean_overwrite_value_raises_parsing_error(self):
        parser = ConfigParser()
        parser.read_string(
            """
[options]
overwrite_scripts="okay"
"""
        )
        with pytest.raises(
            ParsingError,
            match=r'(overwrite_scripts(.*)"okay"|"okay"(.*)overwrite_scripts)',
        ):
            config._parse_options_section(parser["options"])


class TestParseLocalSection:
    def test_root_is_required(self):
        parser = ConfigParser()
        parser.read_string(
            """
[local]
blah=blah
"""
        )
        with pytest.raises(ParsingError, match=r"(local(.*)root|root(.*)local)"):
            config._parse_local_section(parser["local"])

    def test_parsing_root(self, example_config_parser):
        local_root, _ = config._parse_local_section(example_config_parser["local"])

        assert local_root == "/main/minecraft"

    def test_name_is_not_required(self):
        parser = ConfigParser()
        parser.read_string(
            """
[local]
root=.
"""
        )
        _, options = config._parse_local_section(parser["local"])
        assert options["local_alias"] is None

    @pytest.mark.parametrize("keyword", ("name", "alias"))
    def test_explicitly_setting_name(self, keyword):
        parser = ConfigParser()
        parser.read_string(
            f"""
[local]
{keyword}=me
root=.
"""
        )
        _, options = config._parse_local_section(parser["local"])
        assert options["local_alias"] == "me"

    def test_conflicting_names_gives_error(self):
        parser = ConfigParser()
        parser.read_string(
            """
[local]
name=Antar
alias=OpenBagTwo
root=.
"""
        )
        # I don't care about the order, and I'm too lazy and typo-prone to
        # enumerate all 3! permutations by hand
        patterns: list[str] = []
        for permutation in itertools.permutations(("local", "conflicting", "alias")):
            patterns.append(r"(.*)".join(permutation))
        with pytest.raises(ParsingError, match=rf'({"|".join(patterns)})'):
            config._parse_local_section(parser["local"])

    def test_options_can_also_be_provided_in_local_section(self):
        parser = ConfigParser()
        parser.read_string(
            """
[local]
name=OpenBagTwo
root=.
overwrite_scripts=True
generate_runnable_scripts=no
pre_open=playsound minecraft:door_open
post_close=[
    "stuff in_drawer",
    "goto bed"
    ]
"""
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            _, options = config._parse_local_section(parser["local"])

        assert options == {
            "local_alias": "OpenBagTwo",
            "overwrite": True,
            "omit_scare_warnings": False,
            "pre_open": ["playsound minecraft:door_open"],
            "pre_close": [],
            "post_open": [],
            "post_close": ["stuff in_drawer", "goto bed"],
        }


class TestParseConfig:
    def test_parse_config_from_string(self):
        simple_config = """
[local]
root=~/minecraft

[options]
overwrite_scripts=yes

[mirror]
root=~/minecraft
"""
        expected = config.Config(
            "~/minecraft",
            [RemoteSync(Remote("mirror", "~/minecraft"))],
            craft_options={"overwrite": True},
        )
        parsed_config = config.parse_config(simple_config)

        assert parsed_config == expected

    def test_options_is_optional(self):
        simpler_config = """
[local]
root=~/minecraft
overwrite_scripts=yes

[mirror]
root=~/minecraft
"""
        expected = config.Config(
            "~/minecraft",
            [RemoteSync(Remote("mirror", "~/minecraft"))],
            craft_options={"overwrite": True},
        )
        parsed_config = config.parse_config(simpler_config)

        assert parsed_config == expected

    def test_you_dont_technically_need_any_remotes(self):
        local_only_config = """
[local]
root=~/minecraft
"""
        expected = config.Config(
            "~/minecraft",
            [],
        )
        parsed_config = config.parse_config(local_only_config)

        assert parsed_config == expected

    def test_leaving_off_a_local_section_raises_an_error(self):
        nonlocal_config = """
[options]
blah=True

[mirror]
root=~/minecraft
"""
        with pytest.raises(ParsingError, match="local"):
            config.parse_config(nonlocal_config)

    def test_duplicated_section_raises_an_error(self):
        dupe_config = """
[local]
root=~/minecraft

[options]
blah=True

[mirror]
root=~/minecraft

[mirror]
host=mirror
root=/on/the/wall
"""
        with pytest.raises(Exception, match="mirror"):
            config.parse_config(dupe_config)

    def test_wreappers_stack(self):
        split_wrapper_config = """
[local]
root=~/minecraft
pre_open = echo 1
pre_close = echo 2

[options]
pre_close = [
    "echo 3",
    "echo 4"
    ]
post_open = "echo 5"

"""
        parsed_config = config.parse_config(split_wrapper_config)
        assert (
            parsed_config.craft_options["pre_open"],
            parsed_config.craft_options["pre_close"],
            parsed_config.craft_options["post_open"],
            parsed_config.craft_options["post_close"],
        ) == (["echo 1"], ["echo 2", "echo 3", "echo 4"], ["echo 5"], [])

    def test_other_options_raise_error_on_conflict(self):
        make_up_your_mind_config = """
[local]
root=~/minecraft
overwrite_scripts=True

[options]
overwrite_scripts=no

"""
        with pytest.raises(ParsingError, match="conflicting"):
            config.parse_config(make_up_your_mind_config)

    def test_parse_config_from_file(self, example_config_path):
        expected = config.Config(
            "/main/minecraft",
            (
                RemoteSync(
                    Remote("192.168.0.101", "~/Games/minecraft", alias_="couch-potato"),
                    pre_open=[],
                    post_open=["lectern checkout $active_world"],
                    pre_close=["lectern return $active_world"],
                    post_close=[],
                ),
                RemoteSync(Remote("steam-deck.local", "~/minecraft", "deck")),
                RemoteSync(Remote("nuggets_laptop", "~/Games/minecraft", "nugget")),
            ),
            craft_options={
                "local_alias": "battlestar",
                "post_open": [
                    "cd /main/minecraft/EnderChest"
                    " && git add ."
                    ' && git commit -m "Pulled changes from remotes"'
                ],
                "post_close": [
                    "cd /main/minecraft/EnderChest"
                    " && git add ."
                    ' && git commit -m "Pushing out local changes"'
                ],
                "pre_open": [],
                "pre_close": [],
            },
        )
        assert config.parse_config_file(example_config_path) == expected

    def test_that_configs_are_serializable(self, tmp_path, example_config_path):
        original_config = config.parse_config_file(example_config_path)

        write_path = tmp_path / "config.cfg"
        with write_path.open("w") as f:
            original_config._config.write(f)

        deserialized_config = config.parse_config_file(write_path)
        assert original_config._asdict == deserialized_config._asdict
