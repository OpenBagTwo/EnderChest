"""Additional pytest CLI options. h/t https://stackoverflow.com/a/52458082"""


def pytest_addoption(parser):
    parser.addoption(
        "--use-local-ssh",
        action="store_true",
        default=False,
        help=(
            "By default, SFTP tests are run against a mock SSH server."
            " If your system happens to be set up for passwordless sshing"
            " into localhost, you can choose to run your tests against your"
            " actual SSH server by using this flag."
        ),
    )
