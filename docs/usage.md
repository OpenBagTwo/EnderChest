# Quick-Start Guide

This is a brief guide to getting an EnderChest set up and linking. It covers the
most important command-line operations and how to make best use of shulker boxes.

## Locating Your Minecraft Instances

Before setting up an EnderChest, it's a good idea to take a minute and figure
out where all of your Minecraft data is actually stored. This will vary based
on your operating system and the launchers you use.
[This document](https://help.minecraft.net/hc/en-us/articles/4409225939853-Minecraft-Java-Edition-Installation-Issues-FAQ#h_01FFJMSEED8RNP3YA5NYGEK14R),
for example, tells you how to find the official launcher data. MultiMC-derived
programs like PrismLauncher will often have a
["Folder" button](https://prismlauncher.org/wiki/getting-started/migrating-multimc/)
that will take you to the location of each instance, which is especially helpful
for the flatpak distribution.

## Selecting a "Minecraft Root"

Once you have the lay of the land, the next thing you'll want to do is decide
where you want your EnderChest folder to live. This could be your home folder
(`~` or `C:\Users\yourusername\`, in the folder containing your MultiMC
`instances` directory, or anywhere that's convenient for you.
Go to that directory in your terminal.

!!! tip
    You can run any EnderChest command from any location by explicitly specifying
    the Minecraft root, _e.g._
    ```bash
    enderchest craft --root /path/to/my_minecraft_stuff
    ```
!!! tip
    You can also specify your Minecraft root by using an enviroment variable.
    ```bash
    export MINECRAFT_ROOT=/path/to/my_minecraft_stuff
    ```
## Creating an EnderChest

When ready, run the command:

```bash
enderchest craft
```

to begin the guided setup process. This process will ask you about directories
to look for Minecraft installations inside. Note that these will be the
folders _containing_ `.minecraft`, not the `.minecraft` folders themselves.

You'll also be prompted for the address of another EnderChest installation
you want to sync with. For now, I'll assume that this is your first
EnderChest, so leave that answer blank. When you're ready to create another
EnderChest on another machine, the [Managing Remotes](#managing-remotes)
section will have you covered.

Once the installer finishes, you'll end up with a new folder inside your
current directory (or Minecraft root) named EnderChest along with a file inside
that folder named `enderchest.cfg`. Feel free to open up that file in your
favorite text editor and take a look. It's designed to be easily edited to make
it easy to, for example, manually add a tag to an instance.

!!! info
    When a given entry can have multiple values, you can separate those values
    by commas, _e.g._
    ```ini
    tags = vanilla_plus, modded, sodium
    ```
    or by putting each entry on its own (indented) line, _e.g._
    ```ini
    tags =
        aether
        modded
        optifine
    ```

### Registering Additional Instances

Once you have an EnderChest installed, you can register additional instances
at any time by using the `gather` action. Running:

```bash
enderchest gather instance <path>
```

will recursively search the provided directory for folders named `.minecraft`
and attempt to register them.

!!! tip
    You can control how much information gets displayed when running EnderChest
    commands by using the `--verbose` (`-v`) and `--quiet` (`-q`) flags.

## Creating Shulker Boxes

Once you've populated your EnderChest configuration with all the Minecraft
instances you want to manage, it's time to start crafting shulker boxes.

Running:

```bash
enderchest craft shulker_box <name>
```

will take you through a guided setup that will let to control how your shulker
box will know which instances will link to it along with what other remote
EnderChest installations will use it. At the conclusion of the process you'll
end up with a folder within your EnderChest that's pre-populated so as to
mirror what you'd see in a `.minecraft` folder.

### Moving Files into Your Shulker Box

If you have existing Minecraft installations, now is the time to start moving
the assets from those instances into your shulker box. Just put them in the
exact same place inside the shulker box that they'd be inside of `.minecraft`
(so resource packs go in `resourcepacks`, worlds go in `saves`, etc.)

### Linking Entire Folders

During the shulker box creation process, you were prompted to select any folders
that you wanted to symlink whole-hog. This is useful for things like screenshots
or logs where files will be _generated_ by the instance and not just accessed
or updated.

!!! warning "Important!"
    By default, for the purposes of linking EnderChest treats any folder
    that's not at the top level (_e.g._ `saves/my world`) as a _file_ that's
    symlinked in its entirety. You can change this behavior by setting the
    `max-link-depth` parameter in the shulker box config, but doing so should
    be considered highly experimental.

## Linking Your Instances

Once everything is set up, to actually link up all of your instances, you
just need to run:

```bash
enderchest place
```

!!! danger "Important!!"

    Starting with Minecraft 1.20, Mojang by default
    [no longer allows worlds to load if they are or if they contain symbolic links](https://help.minecraft.net/hc/en-us/articles/16165590199181).
    Obviously this will be a problem if you're using EnderChest to centralize
    and organize your world saves.

    By default, EnderChest will offer to create an `allowed_symlinks.txt` folder
    inside any 1.20+ instance that doesn't have one already and update the file to
    blanket-allow symbolic links into your EnderChest.

    **If you would prefer to do this by hand or not at all**, you can edit your
    `enderchest.cfg` and change the value for `offer-to-update-symlink-allowlist` to `False`.
    EnderChest will never create any file or symlink without your consent and will
    never place a symlink pointing directly to a place outside of your EnderChest.

    If you would like to get a full report of all symlinks EnderChest places,
    you can run:
    ```bash
    enderchest place --verbose
    ```
    to get a full audit.

As EnderChest places all your links, it will stop if at any point there's already
a file or a non-empty folder at that location. Sometimes that happens because
you forgot to clean out an existing instance. Other times, your shulker box
configurations might be [conflicting with each other](../suggestions#collisions-and-conflicts).
Regardless, rather than just overwriting your data, EnderChest will ask you
how you want to proceed. And once you've fixed the issue, you can just run

```bash
enderchest place
```

again--running `place` multiple times is completely safe (and is something you
should do regularly! and particularly after any shulker box modification or file
sync!).

## Managing Remotes

Once you've finished setting up an EnderChest on a given computer, the next
thing to consider is setting it up on _another_ one. To do that, you'll need
to set up some form of file transfer. **EnderChest's preferred transfer protocol
is [`rsync`](https://www.redhat.com/sysadmin/sync-rsync)**, an extremely efficient
open source tool for performing backups and generally moving files between
two locations. Most Linux distributions (including SteamOS) come with a
sufficiently recent version of `rsync` preinstalled (EnderChest requires **`rsync` 3.2 or newer**),
and Mac users can upgrade their `rsync` easily via
[homebrew](https://formulae.brew.sh/formula/rsync),
[MacPorts](https://ports.macports.org/port/rsync/) or
[conda](https://anaconda.org/conda-forge/rsync).

Windows users may be able to get EnderChest working with `rsync`
via [Cygwin](https://www.cygwin.com/packages/summary/rsync.html) or
[WSL](https://thedatafrog.com/en/articles/backup-rsync-windows-wsl/), but
[this is not currently supported](https://github.com/OpenBagTwo/EnderChest/issues/67),
and Windows users may be better off using
[a different protocol](../suggestions#other-syncing-protocols).

To register a remote with your EnderChest, you just need to run the following command:

```bash
enderchest gather enderchests <remote>
```

where `<remote>` is the URI to the remote chest.

### Understanding URIs
A [Uniform Resource Identifier](https://en.wikipedia.org/wiki/Uniform_Resource_Identifier),
or URI, is a way of referencing files or folders--oftentimes on other computers--
in a standard way. URLs, like you're familiar with from web browsers, are a type
of URI. The format of a URI typically follows the following schema:

```
<protocol>://[[<username>@]<host>[:port]<path>[?<query>]
```

The important bits right now are:
- the protocol must be one that's supported by both EnderChest and by your machine
- the host can be the local IP of your remote machine, but most home routers support
  connecting to machines via their hostname. This is much better for users whose
  routers don't assign machines statis IP addresses.
- the path must be [URL encoded](https://www.urlencoder.org/) to transform special
  characters (especially spaces) into a single unambiguous string
- the path must be _absolute_, (and in the URI syntax must start with a `/`),
  starting from the computer or service's root directory (hence the `/` for
  macOS and Linux users)
- the path does not point to an EnderChest, but to _the folder containing the
  EnderChest_.

As an example, let's say I have an EnderChest installed on my Steam Deck
(hostname: "steamdeck") directly inside my home directory (so `~/EnderChest`).
If I'm setting up an EnderChest on my couch gaming laptop and want to sync
with my Deck, the URI for it will be: `rsync://deck@steamdeck/home/deck`

!!! tip
    You can use [this website](https://www.urlencoder.org/) to encode any
    file name or
    [POSIX](https://www.oreilly.com/library/view/beginning-applescript/9780764574009/9780764574009_path_names_colon_traditional_mac_and_pos.html)
    path as a URI. You can also get the URI to your current directory in Python
    by running the following code:
    ```python
    >>> from pathlib import Path
    >>> print(Path().absolute().as_uri())
    ```
    While that will give you the [`file://` protocol](../suggestions#file-protocol),
    URI you can then just replace the `file://` part (make sure not to grab
    the third slash!) and replace it with the `protocol://[user@]hostname[:port]`
    of your choice.

## Syncing

Once you have some remote EnderChests set up, the way you sync with them is via
the `close` and `open` actions:

```bash
enderchest close
```

will push your local changes to all registered remote chests

```bash
enderchest open
```

will pull changes from your other EnderChests while

!!! info
    Where you have multiple remotes specified, `enderchest open` will only
    pull changes from one, prioritizing them in the order that they're listed,
    and stopping once it manages to sync successfully.

    In contrast, `enderchest close` will push changes _to all_ registered
    remotes.

    This is useful for when you have EnderChests running on laptops or handhelds
    that are not always on, or not always on the same network as the other devices,
    but it means you need to be careful that the first remote listed in your
    config is the one most likely to be up-to-date.

**Sync operations are destructive** and won't hesitate to wipe out all the files
in an EnderChest if you have your remote mis-configured. That's why all sync
operations support the `--dry-run` flag, which lets you preview the operations
that will be performed before they're actually run.

In fact, by default, all sync operations _will perform a dry run first_ and give
you five seconds to review the dry run log and interrupt the sync if things
are about to go sideways (documentation for overriding this behavior is available
in the [CLI docs](../cli/#enderchest-open)).

!!! tip "Bonus"
    Starting with v0.1.3, after a successful `enderchest open`, EnderChest will
    automatically update all of your instances' symlinks, saving you from needing
    to remember to run:

    ```bash
    enderchest place
    ```

    (this behavior can be disabled by editing the `place-after-open` setting in
    your `enderchest.cfg` file).

## Uninstalling

!!! info
    Even if you uninstall the EnderChest package, the symbolic links it
    created will continue working until you replace them or move your
    EnderChest / Minecraft folders.

If you ever decide that the symlink life isn't for you, run the command:

```bash
enderchest break
```

This will go through all of your instance folders, replacing any symlinks that
point into the EnderChest folder with hard copies of those resources.

!!! note
    If your EnderChest itself contained links pointing to _outside_ the
    EnderChest (say, `EnderChest/global/screenshots` → `~/Pictures/Screenshots`),
    then after breaking, your instances will simply contain _direct links_ to
    those files and folders.

After that completes, you can safely delete your EnderChest folder and remove
the package via your Python package manager, _e.g._
```bash
pipx uninstall enderchest
```
