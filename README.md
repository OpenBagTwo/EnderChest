# EnderChest

A system for managing your minecraft installations across instances and installations

## Motivation

With the arrival of my Steam Deck, I find myself with the very First World problem of having too
many Minecraft installations across a too many computers, and I really want to
keep everything synced and backed up.
This isn't as simple of a problem as just having a central repository on a NAS,
as the machines I've got running Minecraft range from an Raspberry Pi, to an M1 Macbook to the
controller-operated Steam Deck to an absolute beast of a desktop battlestation. Each machine
needs its own settings, client mods and tweaks for optimal gameplay.

Furthermore, since I do mod development and have content creation aspirations, several of my machines
have multiple instance variants that are, for example, streamlined for development and testing
or optimized for ReplayMod rendering, but for which I still want to share some mods,
resourcepacks and worlds with other instances.

And finally, there are some instances that I want to run on a server--either local or hosted--and keeping
resource packs, mods and other assets synced between servers and clients is a giant pain.

In short, there are three different levels of coordination that need to take place:
1. Selective sharing across different computers
1. Selective sharing across different instances on the same computer
1. Selective sharing across server and client installations

## Directory Tree
To that end, the basic folder layout is split out by the context of which instances / installations
will need to sync these files.

```
<minecraft root>: a single folder where all your minecraft data will live
├── EnderChest: the root directory for all resources managed by this package
│   ├── global: put anything here that should go in every minecraft installation, client or server
│   ├── client-only: put anything here that should only go in a client-side installation and not a server
│   ├── local-only: anything that's only for THIS PARTICULAR INSTALLATION and not for sharing across different computers
│   └── server-only: anything that's only needed on a server (properties file, banlist, etc.)
│
├── instances: this is where EnderChest will assume your curseforge / Multi-MC-fork instances live
├── servers: this is where EnderChest will assume all your server installations live
```

Having a centrally-managed "instances" folder that contains all your Minecraft (client) instances is something
that's natively supported by MultiMC variants as well as the command-line clients
[`portablemc`](https://github.com/mindstorm38/portablemc) and [`ferium`](https://github.com/gorilla-devs/ferium), but
other launchers like GDLauncher, CurseForge and the official launcher might require you to use symlinks to store
your instances in a convenient place.

## Linking to instances by tagging through file names

Within the four EnderChest folders, you'll specify which files and folders need to go into which instances or servers by suffixing
files and folders with `@instancename`.

For example, let's say you have an `options.txt` file you want to use across all your client-side instances named "current". You'll
want to save that `options.txt` to inside the `client-only` folder and name it `options.txt@current`.

If you were to also want to use this in your instances named "legacy" you'd just append the tag, so the file would be named
`options.txt@current@legacy`. Creating a single tag that applies to multiple instances, or is automatically applied to, say,
all Fabric 1.19 instances, is not currently implemented, but it is planned.

This applies to folders as well. If you want to install the 1.19 version of [Lithium](https://github.com/CaffeineMC/lithium-fabric)
on your "nirvana" server, you would save the mod inside the `server-only` folder as `mods/lithium-fabric-mc1.19-0.8.0.jar@nirvana`.


### Linking entire folders

For mods, it makes sense to tag each file on a case-by-case basis, but for, say, screenshots and logs, you're going to want
to treat the _folder itself_ as a file in terms of tagging (so maybe you'll create a folder in `EnderChest/global/` called
`backups@nirvana@current@legacy`). It might turn out to make sense for the _default behavior_ to be to automatically link
these folders across all instances, but for now, you'll need to explicitly tag each instance you want centrally managed.


### The default behavior is that instance files are not linked

This is most applicable to world saves--if you create a new world, you will need to:

1. **manually move** the world folder into the EnderChest` folder, putting it under the appropriate context subfolder (and the "saves"
   folder underneath that)
1. Append the tags for the original instance and any instances that should share access to the world **to the world's folder name**
1. Run the command to regenerate all the links.

### Name Collisions and Conflicts

Let's say you have four files:

1. `EnderChest/global/config/foxnap.yaml@current`
2. `EnderChest/client-only/config/foxnap.yaml@current`
3. `EnderChest/client-only/config/foxnap.yaml@current@legacy`
4. `EnderChest/client-only/config/foxnap.yaml@legacy@current`

Which configuration will be used inside your "current" instance?

The answer is (4), as linking is done global -> client-only -> local-only -> server-only,
then in alphabetical order, but I can't think of a valid use-case for this, so
collision detection is something that will probably get added at a later date.

Similarly, if your setup were the following:

1. `EnderChest/config@current/foxnap.yaml`
2. `EnderChest/config/foxnap.yaml@current`

I'm not exactly sure what it should do, but I can pretty much guarantee that it's not doing what you wanted.

### Y Tho?

If you're a Windows or MacOS user, you may be wondering _why the heck_ I thought it was a **good idea**
to create a system that relied on _giving files weird and unreadable extensions_. And, friend, you're not
wrong, but here's the advantages of this system:

- inside your _actual_ Minecraft folders, the symbolic links generated _will_ have the expected extensions
  and will function normally
- centralizing assets makes it easy to share and update assets across multiple instances
- centrally managing assets enforces that the instance folders and _the launchers themselves_ contain
  very little actual and important content, thus making it easy to switch to new launcher--instead of
  having to "import" an instance from the old launcher, you can just create a new instance in the new
  launcher, symlink the `.minecraft` folder they create to your centralized minecraft root, then run
  `enderchest place` to put everything into the new instances.
- tagging the filenames of each and every asset guarantees that you don't have a bunch of unused
  and unneeded assets sitting around--it's encoded _right in the filename and folder structure_
  which instances need that asset and for what.
- Doing everything through filenames ensures that **you don't need a special app or UI** to manage
  your assets--any file browser (that will let you see and edit extensions) will do.
- This design makes EnderChest **stateless**--there are no configuration files and no setup process
  beyond running `enderchest craft` to create the EnderChest folder


### All that being said...

I am planning on exploring an alternative implementation--call it "ChestMonster"--where all your
assets would be stored in a centralized and easy to sync place, but where the linking is managed
via a simple text file.


## Installation

EnderChest has no package dependencies but does require **python 3.10 or greater.** So unless your system
Python is already 3.10+, you'll need to first create a virtual environment (releasing as a stand-alone binary
is planned). Assuming that you're starting from zero, the recommended installation steps are:

1. Download and install a [`conda`](https://docs.conda.io/en/latest/) distribution
   ([`mambaforge`](https://github.com/conda-forge/miniforge#mambaforge) highly recommended)
2. Open a terminal and create a new virtual enviroment via:
   ```bash
   $ mamba create -n enderchest "python>=3.10" "pip>22"
   ```
   (substitute `conda` for `mamba` as needed)
3. Activate your new environment:
   ```bash
   $ conda activate enderchest
   ```
4. Install `enderchest` from github via pip:
   ```bash
   $ python -m pip install --user git://github.com/OpenBagTwo/EnderChest.git@release
   ```

(`poetry` support is planned)

## Usage

EnderChest is a command-line utility. With your `enderchest` virtual environment activated, run the command

```bash
$ enderchest --help
```

for full documentation on how to run this package. Full examples and tutorials will be available with
the docs.

## Contributing

Please open [a new issue](https://github.com/OpenBagTwo/EnderChest/issues/new) to report a bug or to propose a new
feature or enhancement.

If you would like to contribute your own bugfixes or code enhancements, start by
[forking this repo](https://github.com/OpenBagTwo/EnderChest/fork), and cloning it into your local workspace.

Once you've done that, navigate to the repo root and:

1. Create the development environment via
   ```bash
   $ mamba env create
   ```
   (substitute `conda` if you so choose)
2. Install the package in editable mode:
   ```bash
   python -m pip install --user -e .
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
