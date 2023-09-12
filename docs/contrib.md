# Contribution Guide

[![coverage](../img/coverage.svg)](../coverage)
[![lint](../img/pylint.svg)](../lint-report.txt)

EnderChest is an open source project, and its source code is
[publicly available on GitHub](https://github.com/OpenBagTwo/EnderChest).

Please open [a new issue](https://github.com/OpenBagTwo/EnderChest/issues/new)
to report a bug or to propose a new feature or enhancement.

If you would like to contribute your own bugfixes or code enhancements, start by
[forking this repo](https://github.com/OpenBagTwo/EnderChest/fork), and cloning
it into your local workspace.

!!! note
    Note that all work should be done off of the `dev` branch

## Setting up a Development Environment

The EnderChest development environment is managed using
[conda](https://docs.conda.io/en/latest/). If you don't have one already,
I highly recommend using a [conda-forge](https://conda-forge.org/)-based
distribution, such as [mambaforge](https://github.com/conda-forge/miniforge#mambaforge).

Once you have conda installed and your fork cloned to your local workspace, navigate
to that workspace and:

1. Create the development environment via
   ```bash
   mamba env create
   ```
   (substitute `conda` if you so choose)
1. Install the package in editable mode:
   ```bash
   python -m pip install --user -e .[test]
   ```
1. Set up [pre-commit](https://pre-commit.com/):
   ```bash
   pre-commit install
   ```

!!! warning "Note"
    The [developemnt environment](https://github.com/OpenBagTwo/EnderChest/blob/dev/environment.yml)
    specifies [`rsync`](https://anaconda.org/conda-forge/rsync) as a dependency,
    and there is currently no build of rsync available for Windows. If you are
    developing from Windows, you will either need to do your development within
    WSL or comment out that line and install rsync yourself.


Once that's done, start developing! Pre-commit is a fantastic tool that will
take care of most style-guide enforcement for you, but details are below.

## Style Guide

EnderChest follows the standard Python style guides, most notably
[PEP8](https://peps.python.org/pep-0008/), targeting the Python 3.10 feature set.
The one exception is that the line length maximum is set to 88, not 79. All
non-trivial and "public" functions must have docstrings in
[the NumPy style](https://numpydoc.readthedocs.io/en/latest/format.html).

All code should be fully type-hinted, leveraging the latest changes
[introduced to the language](https://docs.python.org/3/whatsnew/3.10.html#new-features-related-to-type-hints).
Favor use of `| None` ✅ instead of `Optional` ❌ and built-in types (`list`, `tuple` ✅)
[over their capitalized types](https://docs.python.org/3/whatsnew/3.9.html#type-hinting-generics-in-standard-collections)
(`from typing import List, Tuple` ❌).

??? example "Type Hinting Pro Tip"
    A good practice to follow when using type hints is to make your return hints
    as specific and explicit as possible while making your parameter hints
    as broad as the function will allow. For example:
    ```python
    from typing import Any, Collection


    def stringify_dedupe_and_sort(sort_me: Collection[Any]) -> list[str]:
        """Take a collection of stuff, turn them all into strings, remove
        any duplicates, and then return the results sorted in alphabetical
        (lexical?) order

        Parameters
        ----------
        sort_me : list-like
            The things you want to sort

        Returns
        -------
        list of str
            The stringified, deduped and sorted items

        Notes
        -----
        @ me if you want to see this implemented via a one-line comprehension!
        """
        return_me: list[str] = []
        for value in sort_me:
            stringified: str = str(value)
            for i, existing_value in enumerate(return_me):
                if existing_value > stringified:
                    return_me.insert(i, stringified)
                    break
                elif existing_value == stringified:
                    break
                else:
                    pass
            else:
                return_me.append(stringified)

        return return_me
    ```
    In the above, `sort_me` could be a list of strings, a set of `Path`s, or
    really any group of objects that you can iteratethrough and
    that has a defined length (and even that isn't even _technically_
    a requirement). Meanwhile on the output side, you're defining right off the
    bat that `return_me` is going to be a list and then enforcing that every
    member will be a string.

There are a variety of other style conventions, especially around non-Python
files, but they will be automatically enforced by
[pre-commit](https://github.com/OpenBagTwo/EnderChest/blob/dev/.pre-commit-config.yaml).

## Unit Testing

While unit tests are not globally required, any PR will require validation that
the changes introduced are performing as intended (see below), and unit tests
are a great way to provide that, especially given that EnderChest is meant to
run across a wide variety of platforms. EnderChest uses
[py.test](https://docs.pytest.org/en/7.3.x/) as its test runner, and a wide
variety of
[testing utilities](https://github.com/OpenBagTwo/EnderChest/blob/dev/enderchest/test/utils.py)
and [fixtures](https://github.com/OpenBagTwo/EnderChest/blob/dev/enderchest/test/conftest.py)
are available for you to leverage for help mocking out file systems.

### Tests Requiring SSH

SFTP syncing was originally tested against an SSH server running locally that
could be authenticated against passwordlessly. To remove the requirement that
developers have their systems set up similarly, these tests now default to
[mocking the calls to paramiko](https://github.com/OpenBagTwo/EnderChest/blob/dev/enderchest/test/mock_paramiko.py)
using
[cached SFTP attributes](https://github.com/OpenBagTwo/EnderChest/blob/dev/enderchest/test/testing_files/lstat_cache.json).

If you make any changes or additions to the "remote" file system used by these
tests, this cache will need to be regenerated, and for that you will need to
set up SSH for local passwordless authentication.

!!! tip
    A good example for configuring key-based passwordless SSH on a POSIX
    system can be found in
    [our GitHub Actions](https://github.com/OpenBagTwo/EnderChest/blob/paramiko/.github/workflows/pull_request.yml#L40-L47).

The current procedure to regenerate that cache is:

1. Un-comment [this unit test](https://github.com/OpenBagTwo/EnderChest/blob/853bdbac76124fb9e6d4a754f4dd73c48e66d829/enderchest/test/test_sync.py#L542-L545)
1. Run
   ```bash
   pytest enderchest/tests/test_sync.py::TestSFTPSync::test_generate_lstat_cache --use-local-ssh
   ```
1. Re-comment-out that test, then make sure the cache is working by running
   ```bash
   pytest -vvx enderchest/tests/test_sync.py::TestSFTPSync
   ```
1. If all tests pass when using the cache, then make sure to `git add` the
   regenerated testing file and include it in your next commit

## Documentation

In addition to internal (docstring) documentation, the EnderChest project includes
HTML documentation hosted on GitHub Pages. This includes the static guides (that
you are literally reading right now) as well as dynamically-generated HTML docs.

The tool that performs this magic is called [MkDocs](https://www.mkdocs.org/) and
is included in the EnderChest development environment. One of MkDocs' killer]
features is its ability to quickly render and serve the documentation locally.
To do this, navigate your terminal to the repo root, activate your EnderChest
environment and run the command:

```bash
mkdocs serve
```

and the terminal will soon contain a link (typically to http://127.0.0.1:8000/)
where you can preview the documentation.

When developing EnderChest, you should _both_ check
the [compiled API docs based on your docstrings](http://127.0.0.1:8000/reference/enderchest/)
([and changes to the CLI](http://127.0.0.1:8000/cli/)) to ensure that everything
is rendering as it should.

## Development Workflow

EnderChest development follows
[Gitflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow),
with all development done on feature-branches created off the `dev` branch.

Once a significant number of changes have been merged into `dev` (usually the
culmination of a
[milestone](https://github.com/OpenBagTwo/EnderChest/milestones)), a staging
branch will be created off of `dev`, and a PR will be opened targeting merging
changes from that branch into `release`. This process is typically accompanied
by the creation of release candidate versions which are built and uploaded to PyPI
for pre-release testing. During this phase, changes will be made directly
to the staging branch to fix any bugs or regressions that come up during testing.

Once it's time to cut a release,

1. The staging PR will be merged into `release`.
2. A [new release](https://github.com/OpenBagTwo/EnderChest/releases/new) will
   be created targeting the `release` branch and with a tag of the form
   [`v0.x.y`](https://semver.org/). The release notes should highlight the
   significant changes in the new version, and the auto-generated release notes
   should be modified to cover the period from the last full release
   (as opposed to just the last release candidate).

    !!! tip
        Create draft release notes when cutting the first release candidate
        so that you can just copy them into the full release

3. Cutting the new release will automatically push a new package build to
   [pypi](https://pypi.org/project/enderchest/) and
   [update the docs](https://openbagtwo.github.io/EnderChest/release/).
4. Once the release is complete, the `dev` branch must be **rebased** on top of
   `release`. This serves two goals:
   - it applies any changes committed directly to the staging branch to `dev`
   - it keeps the commit history linear (and makes it much easier to calculate)
     the number of commits in `dev` since the last release.

## Opening a PR

Once you're ready to contribute your code change back,
[open a PR](https://github.com/OpenBagTwo/EnderChest/compare) (remember to
target the `dev` branch unless this is a hotfix), fill out the PR template, and
then tag **[@OpenBagTwo](https://github.com/OpenBagTwo)** for review.

## License

This project--the executable, source code and all documentation--are published
under the
[GNU Public License v3](https://github.com/OpenBagTwo/EnderChest/blob/dev/LICENSE),
and any contributions to or derivatives of this project _must_ be licensed under
compatible terms.
