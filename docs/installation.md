# Installation

[![PyPI version](https://badge.fury.io/py/enderchest.svg)](https://badge.fury.io/py/enderchest)
![PyPI downloads](https://img.shields.io/pypi/dm/enderchest.svg)

EnderChest has minimal package dependencies and should run on pretty much
any computer or operating system. It does require **Python 3.10 or greater,**
portable distributions (read: no need for admin privileges)  of which are
available through miniconda and
[mambaforge](https://github.com/conda-forge/miniforge#mambaforge).

!!! warning
    Because of EnderChest's
    [heavy reliance on symlinks](../about#symlinks-to-the-rescue), Windows users
    are required to **turn on Developer Mode**.
    [Read more here.](https://blogs.windows.com/windowsdeveloper/2016/12/02/symlinks-windows-10/)

Once you have Python installed,

1. Open a terminal and create a new virtual environment via:
   ```bash
   mamba create -n enderchest "python>=3.10" "pip>22"
   ```
   (substitute `conda` for `mamba` as needed, and skip this step and the next if
    you're using the system Python)

1. Activate your new environment:
    ```bash
    conda activate enderchest
    ```

1. Install `enderchest` from PyPI using pip:
    ```bash
    python -m pip install --user enderchest[test]
    ```

1. Ensure that EnderChest is compatible with your system by running:
    ```bash
    python -m pytest --pyargs enderchest.test
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

## Bleeding Edge

If you'd like to test out upcoming features or help with beta testing, you
can install from the current development branch via:

```bash
$ python -m pip install --user git+https://github.com/OpenBagTwo/EnderChest.git@dev#egg=enderchest[test]
```

**Be warned** that any code on this branch is considered highly experimental.
As always, make sure to regularly back up any important data you're managing
with this tool.
