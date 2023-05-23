# About EnderChest

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

## Symlinks to the Rescue!

The first and most important bit--making it so that changing a file in one place
changes it everywhere else--is why [MIT](https://gunkies.org/wiki/Symbolic_link)
invented symbolic links, where each file is stored in exactly one location, and
everywhere else that file is expected is basically just a forwarding address to
that file.  Since I'm almost never going to be running _two_ instances of
Minecraft at once, there's no worrying about file locks or simultaneous writes,
so making it so that there's only one _true_ copy of every file on a file system
is the ideal solution for keeping everything in sync.

And if we're already talking about symlinking all the things, and we know we
need to be able to sync files _between_ filesystems, it makes sense to store
all of those true copies in one centralized place. Hence, the EnderChest.

## Automagic Linking

One could just stop there--designate a folder for all your Minecraft files, sync
that folder between your computers, and then manually put links in each of your
Minecraft instances pointing into the EnderChest. But dang it there are _a lot_
of mods out there and having to create new links by hand every time you want to
try out a new resource pack is very few people's idea of a fun time.

And that's where the magic of scripting languages comes into play (and why
is a Python package and not a "how-to" guide). With a few short terminal commands,
you can set it up so that updating Sodium across all of your compatible Minecraft
instances is a simple matter of dragging in the file and running the
command `enderchest place`.

## Organizing the EnderChest Monster with Shulker Boxes

The original implementation of EnderChest was a giant mess, with every file for
every instance just thrown into one of a small number of folders. After a few
months of using it, I found myself absolutely dreading the process of creating
a new Minecraft instance, knowing I'd have to update the configuration of every
single file I'd want to link.

The next iteration of this concept was probably obvious to anyone who's
used an ender chest in the game after beating
[Jean](https://minecraft.fandom.com/wiki/Ender_Dragon):
by grouping my files into purpose-specific "Shulker Boxes," I could
onboard a new Minecraft instance by editing just a handful of box-configs. Or
even better--I could just tag the new instance in a way that it would get matched
to the folders _automatically_.
