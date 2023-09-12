"""Subpackage containing all files and templates used for testing"""
from importlib.resources import files

__all__ = [
    "CLIENT_OPTIONS",
    "ENDERCHEST_CONFIG",
    "LSTAT_CACHE",
    "INSTGROUPS",
    "LAUNCHER_PROFILES",
    "VERSION_MANIFEST",
]

_here = files(__package__)

CLIENT_OPTIONS = _here / "options.txt"

ENDERCHEST_CONFIG = _here / "enderchest.cfg"

LSTAT_CACHE = _here / "lstat_cache.json"

INSTGROUPS = _here / "instgroups.json"

LAUNCHER_PROFILES = _here / "launcher_profiles.json"

VERSION_MANIFEST = _here / "version_manifest_v2.json"
