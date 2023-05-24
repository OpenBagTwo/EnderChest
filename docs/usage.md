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
enderchest gather <path>
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
enderchest craft shulker_box
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

## Managing Remotes

_TODO_

## Syncing

_TODO_
