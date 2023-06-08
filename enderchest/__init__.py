"""Top-level imports"""
from . import _version
from .enderchest import EnderChest
from .instance import InstanceSpec
from .shulker_box import ShulkerBox

__version__ = _version.get_versions()["version"]


__all__ = [
    "EnderChest",
    "InstanceSpec",
    "ShulkerBox",
]
