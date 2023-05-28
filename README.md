# EnderChest

[![PyPI version](https://badge.fury.io/py/enderchest.svg)](https://badge.fury.io/py/enderchest)
![PyPI downloads](https://img.shields.io/pypi/dm/enderchest.svg)

![Linux](https://img.shields.io/badge/GNU/Linux-000000?style=flat-square&logo=linux&logoColor=white&color=eda445)
![SteamOS](https://img.shields.io/badge/SteamOS-3776AB.svg?style=flat-square&logo=steamdeck&logoColor=white&color=7055c3)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows&logoColor=white)
![MacOS](https://img.shields.io/badge/mac%20os-000000?style=flat-square&logo=apple&logoColor=white&color=434334)

[![python](https://img.shields.io/badge/Python-3.10,3.11-3776AB.svg?style=flat&logo=python&logoColor=white&color=ffdc53&labelColor=3d7aaa)](https://www.python.org)
![coverage](https://raw.githubusercontent.com/OpenBagTwo/EnderChest/gh-pages/coverage.svg)
![lint](https://raw.githubusercontent.com/OpenBagTwo/EnderChest/gh-pages/pylint.svg)


A system for managing your minecraft installations across instances and
installations

## In a Nutshell

EnderChest is a command-line utility for selectively sharing Minecraft assets
(configurations, mods, worlds, etc.)...

1. ...across different computers
1. ...across different instances on the same computer
1. ...across server and client installations

## Installation

EnderChest is written for **Python 3.10 or greater,** but should otherwise
run on any architecture or operating system.

The latest release can be installed from PyPI via `pip`:

```bash
$ python -m pip install --user enderchest
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
