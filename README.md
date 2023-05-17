# EnderChest

A system for managing your minecraft installations across instances and
installations

## Motivation

With the arrival of my Steam Deck in 2022, I found myself with the very
First World problem of having too many Minecraft installations across too many
computers, and I really want to keep everything synced and backed up.
This isn't as simple of a problem as just having a central repository on a NAS,
as the machines I've got running Minecraft range from an Raspberry Pi,
to an M1 Macbook to the controller-operated Steam Deck to an absolute beast of
a desktop battlestation. Each machine needs its own settings, client mods and
tweaks for optimal gameplay.

Furthermore, since I make mods and datapacks and have content creation aspirations,
several of my machines have multiple instance variants that are, for example,
streamlined for development and testing or optimized for ReplayMod rendering,
but for which I still want to share some mods, resourcepacks and worlds with
other instances.

And finally, there are some instances that I want to run on a server--either
local or hosted--and keeping resource packs, mods and other assets synced
between servers and clients is a giant pain.

In short, there are three different levels of coordination that need to take place:
1. Selective sharing across different computers
1. Selective sharing across different instances on the same computer
1. Selective sharing across server and client installations

### Symliks to the Rescue!
To that end, the ideal solution is to centralize all my Minecraft files in one
convenient folder that I could easily sync between machines, and then put links
to those files within each Minecraft installation.

To make it easier to separately manage modpacks, GPU-intensive shaders
and in-development resource packs, the ideal structure of this centralized
repo broke down even further into purpose-focused "shulker boxes," where each
box mimics the layout of a minecraft folder.

Storing all of these shulker boxes inside a single "Ender Chest" then enabled
me to sync assets across multiple shulkers to multiple instances, all with
a few commands.

### The EnderChest folder structure

_TODO_

## Installation

EnderChest has minimal package dependencies and should run on pretty much
any computer or operating system. It does require **Python 3.11 or greater,**
portable (read: no need for admin privileges) distributions of which are
available through miniconda and
[mambaforge](https://github.com/conda-forge/miniforge#mambaforge).

Once you have python installed,

1. Open a terminal and create a new virtual enviroment via:
   ```bash
   $ mamba create -n enderchest "python>=3.11" "pip>22"
   ```
   (substitute `conda` for `mamba` as needed)
1. Activate your new environment:
   ```bash
   $ conda activate enderchest
   ```
1. Install `enderchest` from github via pip:
   ```bash
   $ python -m pip install --user git+https://github.com/OpenBagTwo/EnderChest.git@release#egg=enderchest[test]
   ```
   (`poetry` support is planned)
1. Ensure that your installation was successful by running:
   ```bash
   $ pytest --pyargs enderchest
   ```
   If all tests pass, then you're good to go!


## Usage

EnderChest is a command-line utility. With your `enderchest` virtual
environment activated, run the command

```bash
$ enderchest --help
```

for an overview of the available actions you can take, and use:

```bash
$ enderchest <verb> --help
```
(_e.g._ `enderchest place --help`)

for further details on running each of those commands.


Full documentation, including tutorials, examples and API docs, can be found on
[GitHub Pages](https://openbagtwo.github.io/EnderChest/).

### Quick-Start Guide

_TODO_

## Contributing

Please open [a new issue](https://github.com/OpenBagTwo/EnderChest/issues/new) to report a bug or to propose a new
feature or enhancement.

If you would like to contribute your own bugfixes or code enhancements, start by
[forking this repo](https://github.com/OpenBagTwo/EnderChest/fork), and cloning it into your local workspace.

Note that all work should be done off of the `dev` branch.

Once you've done that, navigate to the repo root and:

1. Create the development environment via
   ```bash
   $ mamba env create
   ```
   (substitute `conda` if you so choose)
2. Install the package in editable mode:
   ```bash
   python -m pip install --user -e .[test]
   ```
3. Set up pre-commit:
   ```bash
   pre-commit install
   ```

and then start developing.

Once you're ready to contribute your code change back, open a PR into this repo, and tag
[@OpenBagTwo](https://github.com/OpenBagTwo) for review.

## License

This package is licensed under GPLv3. If you have a use case for adapting this code that requires a more
permissive license, please post an issue, and I'd be more than willing to consider a dual license.
