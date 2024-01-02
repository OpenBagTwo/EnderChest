"""Loggers for the various EnderChest actions"""
import logging

BREAK_LOGGER = logging.getLogger("enderchest.break")
CRAFT_LOGGER = logging.getLogger("enderchest.craft")
GATHER_LOGGER = logging.getLogger("enderchest.gather")
PLACE_LOGGER = logging.getLogger("enderchest.place")
SYNC_LOGGER = logging.getLogger("enderchest.sync")

IMPORTANT = 25  # INFO logs that should still be displayed on "-q"
logging.addLevelName(IMPORTANT, "INFO")


class CLIFormatter(logging.Formatter):
    """Colorful formatter for the CLI

    h/t https://stackoverflow.com/a/56944256"""

    grey = "\x1b[2;20m"
    yellow = "\x1b[33;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: grey + "%(message)s" + reset,
        logging.INFO: "%(message)s",
        IMPORTANT: "%(message)s",
        logging.WARNING: yellow + "%(message)s" + reset,
        logging.ERROR: bold_red + "%(message)s" + reset,
        logging.CRITICAL: bold_red + "%(message)s" + reset,
    }

    def format(self, record: logging.LogRecord) -> str:
        return logging.Formatter(self.FORMATS.get(record.levelno)).format(record)


def verbosity_to_log_level(verbosity: int) -> int:
    """Convert a verbosity level (number of `-v`s minus number of `-q`s) to
    a logging level

    Parameters
    ----------
    verbosity: int
        A verbosity level usually specified by the number of `-v` flags a user
        provides minus the number of `-q` flags. As a baseline, a verbosity of
        0 will set the level to handle all INFO-level messages and above.

    Returns
    -------
    int
        The corresponding log level that should be set

    Notes
    -----
    Technically the default logging level is set just high enough to exclude
    DEBUG by default. This allows us to capture intermediate log levels (read:
    `IMPORTANT`) at the `verbosity = -1` (`-q`) level.
    """
    return logging.DEBUG + 1 - 10 * verbosity
