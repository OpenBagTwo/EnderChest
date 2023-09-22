# Installation

[![PyPI version](https://badge.fury.io/py/enderchest.svg)](https://badge.fury.io/py/enderchest)
![PyPI downloads](https://img.shields.io/pypi/dm/enderchest.svg)

EnderChest has minimal package dependencies and should run on pretty much
any computer or operating system. It does require **Python 3.10 or greater,**
portable distributions (read: no need for admin privileges) of which are
available through miniconda and
[mambaforge](https://github.com/conda-forge/miniforge#mambaforge).

You can check your Python version by opening a terminal and running:
```bash
python3 -V
```

!!! warning
    Because of EnderChest's
    [heavy reliance on symlinks](../about#symlinks-to-the-rescue), Windows users
    are required to **turn on Developer Mode**.
    [Read more here.](https://blogs.windows.com/windowsdeveloper/2016/12/02/symlinks-windows-10/)

## Installing EnderChest

The recommended way to install EnderChest is via [`pipx`](https://pypa.github.io/pipx/):
```bash
pipx install enderchest
```

If you can't install `pipx` on your system or if your system Python is too old,
you can use a conda environment instead following the instructions in the next
section. If you prefer to use `pip` directly with the system Python, skip to
[this section](#installation-via-pip).

### Creating a conda environment

These instructions assume that you've already downloaded and installed
[mambaforge](https://github.com/conda-forge/miniforge#mambaforge)
or another conda distribution and that mamba/conda is already registered
to your system path.

1. Open a terminal (miniforge prompt on Windows) and create a new virtual environment via:
   ```bash
   mamba create -n enderchest "python>=3.10" "pip>22"
   ```
   (substitute `conda` for `mamba` as needed)

1. Activate your new environment:
    ```bash
    conda activate enderchest
    ```

Then continue onto the next section.

### Installation via pip

3. Install `enderchest` from PyPI using pip:
    ```bash
    python3 -m pip install --user enderchest[test]
    ```

    !!! info "Optional"
        If you plan on connecting to any remote servers via
        [SFTP](../suggestions#sftp-protocol) instead of `rsync`, include the
        `sftp` extra:
         ```bash
         python3 -m pip install --user enderchest[sftp,test]
         ```

4. Ensure that EnderChest is compatible with your system by running:
    ```bash
    python3 -m pytest --pyargs enderchest.test
    ```
    If all tests pass, then you're good to go!

!!! tip
    If you'd like `enderchest` to be available outside of your virtual environment,
    you can copy the executable to somewhere within your system path, _e.g._ for
    Linux, starting with the virtual environment deactivated:
    ```bash
    $ echo $PATH
    /home/openbagtwo/.mambaforge/condabin:/home/openbagtwo/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin
    $ conda activate enderchest
    $ which enderchest
    /home/openbagtwo/.mambaforge/envs/enderchest/bin/enderchest
    $ cp /home/openbagtwo/.mambaforge/envs/enderchest/bin/enderchest ~/.local/bin/
    ```

## Installing `rsync`

EnderChest's preferred syncing protocol is
[`rsync`](https://www.digitalocean.com/community/tutorials/how-to-use-rsync-to-sync-local-and-remote-directories),
and to use EnderChest with `rsync` you'll need **version 3.2 or newer**.

You can check if a sufficiently recent version of `rsync` is installed
on your system by running the command:

```bash
rsync -V
```

If you get a message back stating: `rsync: -V: unknown option`, then your `rsync`
is too old (you can confirm this by running `rsync --version`), and you'll need
to follow the instructions below to get a more modern version installed:

### Conda (macOS and Linux)

If you've already installed EnderChest in a conda-managed virtual environment,
following the instructions above,
[conda builds of `rsync` are available](https://anaconda.org/conda-forge/rsync)
for Mac and Linux and can be installed within your virtual environment via:

```bash
conda activate enderchest
mamba install rsync
```
(substituting `conda` for `mamba` if needed).

### Other options for macOS

You can (and, honestly, should) upgrade your
system's rsync installation via
[homebrew](https://formulae.brew.sh/formula/rsync) or
[MacPorts](https://ports.macports.org/port/rsync/)

### Windows
Use of `rsync` on Windows [is not currently supported](https://github.com/OpenBagTwo/EnderChest/issues/67),
though it may be possible using [Cygwin](https://github.com/cygwin/cygwin-install-action)
or [WSL](https://learn.microsoft.com/en-us/windows/wsl/install).

Luckily, [other protocols are available](../suggestions#other-syncing-protocols),
though they may require re-installing EnderChest with additional extras, _i.e._

```bash
pipx install enderchest[sftp]
```

## Bleeding Edge

If you'd like to test out upcoming features or help with beta testing, you
can install from the current development branch via:

```bash
python3 -m pip install --user git+https://github.com/OpenBagTwo/EnderChest.git@dev#egg=enderchest[test,sftp]
```

**Be warned** that any code on this branch is considered highly experimental.
As always, make sure to regularly back up any important data you're managing
with this tool.
