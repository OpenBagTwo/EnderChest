# Contribution Guide

![coverage](https://raw.githubusercontent.com/OpenBagTwo/EnderChest/gh-pages/coverage.svg)
![lint](https://raw.githubusercontent.com/OpenBagTwo/EnderChest/gh-pages/pylint.svg)

EnderChest is an open source project, and its source code is
[publicly available on GitHub](https://github.com/OpenBagTwo/EnderChest).

Please open [a new issue](https://github.com/OpenBagTwo/EnderChest/issues/new)
to report a bug or to propose a new feature or enhancement.

If you would like to contribute your own bugfixes or code enhancements, start by
[forking this repo](https://github.com/OpenBagTwo/EnderChest/fork), and cloning
it into your local workspace.

(Note that all work should be done off of the `dev` branch.)

I highly recommend using a [conda-forge](https://conda-forge.org/)-based
Python distribution for development and virtual environment management.

With your
[distribution of choice](https://github.com/conda-forge/miniforge#mambaforge)
installed and configured, navigate to the root of the EnderChest project and
then:

1. Create the development environment via
   ```bash
   mamba env create
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

Once that's done, start developing! Pre-commit is a fanstastic tool that will
take care of most style-guide enforcement for you.

Note that EnderChest strongly leverages type-hinting.

## Opening a PR

Once you're ready to contribute your code change back,
[open a PR](https://github.com/OpenBagTwo/EnderChest/compare) (remember to
target the `dev` branch) and tag **[@OpenBagTwo](https://github.com/OpenBagTwo)**
for review.

## License

This project--the executable, source code and all documentation are published
under the
[GNU Public License v3](https://github.com/OpenBagTwo/EnderChest/blob/dev/LICENSE),
and any contributions to or derivatives of this project _must_ be licensed under
compatible terms.
