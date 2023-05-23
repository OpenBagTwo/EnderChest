"""Loggers for the various EnderChest actions"""
import logging

CRAFT_LOGGER = logging.getLogger("enderchest.craft")
GATHER_LOGGER = logging.getLogger("enderchest.gather")
PLACE_LOGGER = logging.getLogger("enderchest.place")
SYNC_LOGGER = logging.getLogger("enderchest.sync")


class CLIFormatter(logging.Formatter):
    """Colorful formatter for the CLI

    h/t https://stackoverflow.com/a/56944256"""

    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: grey + "%(message)s" + reset,
        logging.INFO: "%(message)s",
        logging.WARNING: yellow + "%(message)s" + reset,
        logging.ERROR: bold_red + "%(message)s" + reset,
        logging.CRITICAL: bold_red + "%(message)s" + reset,
    }

    def format(self, record: logging.LogRecord) -> str:
        return logging.Formatter(self.FORMATS.get(record.levelno)).format(record)
