# EnderChest

[![PyPI version](https://badge.fury.io/py/enderchest.svg)](https://badge.fury.io/py/enderchest)
![PyPI downloads](https://img.shields.io/pypi/dm/enderchest.svg)

![Linux](https://img.shields.io/badge/GNU/Linux-000000?style=flat-square&logo=linux&logoColor=white&color=eda445)
![SteamOS](https://img.shields.io/badge/SteamOS-3776AB.svg?style=flat-square&logo=steamdeck&logoColor=white&color=7055c3)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows&logoColor=white)
![MacOS](https://img.shields.io/badge/mac%20os-000000?style=flat-square&logo=apple&logoColor=white&color=434334)
![RaspberryPi](https://img.shields.io/badge/Raspberry%20Pi-000000?style=flat-square&logo=raspberrypi&logoColor=white&color=c51a4a)

[![Python](https://img.shields.io/badge/Python-3.10,3.11,3.12-3776AB.svg?style=flat&logo=python&logoColor=white&color=ffdc53&labelColor=3d7aaa)](https://www.python.org)
[![coverage](https://openbagtwo.github.io/EnderChest/dev/img/coverage.svg)](https://openbagtwo.github.io/EnderChest/dev/coverage)
[![lint](https://openbagtwo.github.io/EnderChest/dev/img/pylint.svg)](https://openbagtwo.github.io/EnderChest/dev/lint-report.txt)


A system for managing your minecraft installations across instances and
installations

## In a Nutshell

EnderChest is a command-line utility for selectively sharing Minecraft assets
(configurations, mods, worlds, etc.)...

1. ...across different computers
1. ...across different instances on the same computer
1. ...across server and client installations

### A Note On Linking

Starting with Minecraft 1.20, Mojang by default
[no longer allows worlds to load if they are or if they contain symbolic links](https://help.minecraft.net/hc/en-us/articles/16165590199181).
While it is true that an improper symlink could cause Minecraft to write data
to a place it shouldn't, nothing in EnderChest will ever generate a symlink whose
target is outside of your EnderChest folder _unless you place_ a symbolic link in
your EnderChest pointing to somewhere else (which you may want to do so that your
screenshots, for example, point to your "My Pictures" folder).

If you still have concerns about symlinks or questions about how they work,
read through
[this guide](https://www.makeuseof.com/tag/what-is-a-symbolic-link-what-are-its-uses-makeuseof-explains/)
or [watch this explainer](https://www.youtube.com/watch?v=mA08E59-zo8), and if
you still have questions, feel free to
[open an issue](https://github.com/OpenBagTwo/EnderChest/issues/new?assignees=OpenBagTwo&labels=question&title=symlink%20question).

## Installation

EnderChest is written for **Python 3.10 or greater,** but should otherwise
run on any architecture or operating system.

Note that the recommended sync protocol is
[`rsync`](https://www.digitalocean.com/community/tutorials/how-to-use-rsync-to-sync-local-and-remote-directories), and EnderChest requires
[version 3.2 or newer](https://dev.to/al5ina5/updating-rsync-on-macos-so-you-re-not-stuck-with-14-year-old-software-1b5i).
However, other protocols are available if a modern `rsync` is not an option for you.

The latest release can be installed from PyPI via [`pipx`](https://pypa.github.io/pipx/):

```bash
pipx install enderchest
```

Full installation instructions can be found on
[GitHub Pages](https://openbagtwo.github.io/EnderChest/dev/installation).

## Usage

EnderChest is a command-line utility. With your `enderchest` virtual
environment activated, run the following command to get an overview of the
available actions:

```bash
$ enderchest --help
```

and use:

```bash
$ enderchest <verb> --help
```
(_e.g._ `enderchest place --help`)

for further details on running each of those commands.

Full documentation, including tutorials, examples and full CLI docs, can be
found on [GitHub Pages](https://openbagtwo.github.io/EnderChest/).

### Quick-Start Guide

To get started, navigate your terminal to the directory where you'd like to
store your EnderChest. Then run:

```bash
$ enderchest craft
```

which will take you through a guided setup.

Once your EnderChest is set up (and you've hopefully registered a few instances),
run

```bash
$ enderchest craft shulker_box <name>
```

for a guided setup of your first shulker box.
Run this command again (with  a different name) to create a new shulker box.

Now move whatever Minecraft assets (mods, configs, worlds) you want into that
shulker box and run:

```bash
$ enderchest place
```

to create symlinks from your registered instance.

If you've set up your EnderChest to sync with other remote installations, you
can push your local changes by running:

```bash
$ enderchest close
```

To pull in any changes from other installations, run:
```bash
$ enderchest open
```

and then

```bash
$ enderchest place
```

to update your symlinks.

More detailed usage instructions can be found on
[GitHub Pages](https://openbagtwo.github.io/EnderChest/dev/usage).

## Uninstalling

If you decide that EnderChest isn't for you, running

```bash
$ enderchest break
```

will replace all symlinks into your EnderChest folder with hard copies of
the linked resources. After that completes, you can safely delete your
EnderChest folder and remove the package via your Python package manager, _e.g._
```bash
pipx uninstall enderchest
```

## Contributing

If you're interested in helping develop this project, have a look at the
[repo backlog](https://github.com/OpenBagTwo/EnderChest/issues) and then read
through the
[contributor's guide](https://openbagtwo.github.io/EnderChest/dev/contrib).

## License

This project--the executable, source code and all documentation--are published
under the
[GNU Public License v3](https://github.com/OpenBagTwo/EnderChest/blob/dev/LICENSE),
and any contributions to or derivatives of this project _must_ be licensed under
compatible terms.
