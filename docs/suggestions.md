# Best Practices and Suggested Workflows

## Other Syncing Protocols

If you can't or don't want to use rsync, EnderChest supports additional
protocols (and has plans for more).

### SFTP Protocol
* **Scheme**: `sftp://`
* **Example URI**: `sftp://deck@steam-deck/home/deck/minecraft`
* **Platforms**: All (see note)
* **[Documentation](https://www.ssh.com/academy/ssh/sftp-ssh-file-transfer-protocol)**

Installing EnderChest
[with sftp support](../installation#installation-via-pip) uses
[Paramiko](https://www.paramiko.org/), a pure-Python SSH implementation, to
allow you to connect to remote EnderChests over SSH from machines where rsync
(or even SSH) isn't available.

!!! note "SSH on Windows"
    While Paramiko can provide a _client_ for initiating file syncs with remote
    EnderChests over SFTP, in order to use a Windows machine **as a remote**
    for connecting _from_ other EnderChests, you will need to install and
    configure [OpenSSH for Windows](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse)
    or a similar solution.

For example, say you have an ROG Ally running Windows and a Steam Deck running
SteamOS. With EnderChest installed on both machines, you can get away with not
running an SSH server on Windows by running all of your `open` and `close`
operations from the Ally (just remember to run `place` on the Steam Deck
afterwards to refresh any linking changes).

### File Protocol

* **Scheme**: `file://`
* **Example URI**: `file:///C:/Users/openbagtwo/My%20Minecraft%20Stuff`
* **Platforms**: All
* **[Documentation](https://learn.microsoft.com/en-us/previous-versions/windows/internet-explorer/ie-developer/platform-apis/jj710207(v=vs.85))**

You can use this protocol to have EnderChest sync between two folders on the
same machine. This can be useful if you're using a service like Dropbox or
Google Drive that automatically backups and synchronizes files in a specific
directory, and where using `enderchest open` to pull the files out of that
shared drive before using them can help avoid conflicts and corruption.

!!! warning "Limitation"
    EnderChest **does not** support using the file protocol to sync files between
    different computers, nor does it support authenticating as different users.

## Suggested Shulker Box Layouts

### Hierarchical

My personal strategy for effective, collision-free linking is to break down
one's Minecraft playing habits into a classification hierarchy:

1. These are the things I will want _every_ time I play Minecraft
1. These are the things I'll want whenever I want to play _a certain kind_ of
   Minecraft
1. These are the things I'll want whenever I'm playing _this particular_
   Minecraft
1. These are the things I only want when I'm playing Minecraft _on this
   particular computer_.

Remember that EnderChest respects a _priority order_ you set on each shulker
box, with lower priority boxes getting linked first, and higher priority ones
overwriting any links created by the earlier boxes. Use this when thinking about
what kinds of boxes to create, and about what items to put in each box.

!!! tip "Pro Tip"
    It's a good idea to give each Shulker Box a unique priority value. It's
    an even better idea to start off by making these priorities, say, multiples
    of 10 or 100 so that later on you can easily slot in new boxes without
    having to change the priority of every other box.

For example, here is how I have my boxes laid out (the number at the
start is their priority values):

* (-20) Global: This shulker box is configured to link to everything and
  contains my `usercache.json` and `usernamecache.json` files, a bunch of
  resource packs that work across  a wide swath of Minecraft versions,
  as well as the "Standard" linked folders (backups, logs, crash reports,
  screenshots, etc.)

    !!! note
        If you're creating your shulker box through the command-line interface,
        this is pretty much the only sort of box where I'd recommend selecting
        the "Global" set of linked-folders.

   This is also where I have a baseline `options.txt` file. It's almost certain
   to get replaced in the actual instance, but it saves me so much aggravation
   to be able to create and onboard a new instance and not have to remember to
   turn off `autoJump` before hopping into a world.

* (-10) Shaders: Because shaders tend to be compatible across pretty much any
  supported Minecraft version, this box is set up to link with any instance
  that has Optifine or Iris installed, which for me is just anything
  non-vanilla, so the `shulkerbox.cfg` looks like:
  ```ini
  [minecraft]
  *

  [modloader]
  forge
  fabric-like
  ```
  I also have another box ((-11) Modconfigs) where I put baseline configuration
  files for mods where the config format hasn't changed or is
  generally backwards / forwards compatible (so things like "Replay Mod: don't
  record single-player by default" or
  "[IndyPets](https://modrinth.com/mod/indypets): pets should not be independent
  by default"). Even though not every instance linked will use these configs,
  the files won't hurt anything by being there.

* (0) 1.20, and also:
    * (1) 1.12
    * (2) 1.16
    * (3) 1.18
    * (4) 20w14infinite
    * (5) 23w13a_or_b

    these version-specific shulker boxes contain all the resource packs that
    were built for just those Minecraft versions along with customized
    `options.txt` files that overwrite the one in the "(-20) Global" box.
    The last two boxes also contain the worlds for those versions, since
    it's not like there are modpacks for the April Fool's updates.

* (10) 1.20 Quilt, and also:
    * (11) 1.12 Forge
    * (12) 1.16 Forge
    * (13) 1.18 Fabric
    * (14) 1.18 Forge

    these boxes contain the optimization, performance and other "no regrets"
    mods that I would _always_ want installed for that version and modloader:
    things like Optifine, Sodium, Iris, Replay Mod,
    [Shulker Box Tooltip](https://modrinth.com/mod/shulkerboxtooltip?hl=en-US),
    etc.

* (100) [Better End](https://modrinth.com/mod/betterend), and also:
    * (110) [Fox Nap](https://modrinth.com/mod/foxnap)

    !!! note
        See how I jumped from priority 13 to 100? This is to make sure that
        there's plenty of space for future Minecraft version x modloader combos.

    This next level is for mods that I use across different instances but maybe
    not _all_ instances for a given loader and version. The matching is done
    via tag (as well as version and loader), and I have at times had sub-boxes
    (Better End 1.18, 1.19, 1.20; Fox Nap 1.19.0, 1.19.2, 1.19.3) to contain
    the most up-to-date mod-specific builds while the configuration files go
    in the main box.

* (200)-(299) Instance-specific boxes. Each instance then gets their own box that
    explicitly specifies each mod going into that instance, along with any
    tweaked options or configuration files.

* (300) Battlestation.local, and also:
    * (310) Couch-Gamer.local
    * (320) Steam-Deck.local

    These boxes contain computer-specific optimizations, such as overriding
    shaderpack settings and changing keybindings. These have the highest priority
    so as to get applied **last** (and consequently, I'll also sometimes have
    instance-specific, machine-specific boxes that further tweak these settings).
    You may find you have better luck giving "local" boxes _lower_ priority
    (in the -10 range) and then having your instance/machine-specific tweaks set
    at the instance or modpack priority level.

And yes, at the end of the day, I end up with _a lot_ of boxes
(45 as of this writng). And since the  system _relies_ on links overwriting
links as you go from broad to specific, it can be difficult to trace back
[where an individual file _actually comes from_](https://github.com/OpenBagTwo/EnderChest/issues/83)
or which other instances it is shared with.

But the advantage is that when I get notified that there's version of a mod,
I know exactly where to put it so that the right instances get the new build, and
the same goes for settings--I make a tweak to my
[Do A Barrel Roll](https://modrinth.com/mod/do-a-barrel-roll) settings? It gets
automatically applied to every Minecraft instance that works with that config.

### Chest Monster

The polar opposite of the careful hierarchical approach takes advantage of
the ability of _symlinks to point to other symlinks_.

This strategy relies on having a ***non-shulker-box*** folder that gets synced
within your EnderChest that contains every single mod, resource pack, world,
config file, etc. that you want to use, and _every version or permutation_ of
each of those files (so, for example, you could have `options.basic.txt`
alongside an `options.controller.txt` that remaps keybinds for instances running
on the Steam Deck or other handhelds).

!!! tip
    Name your Chest Monster something like "_Chest Monster" so that it shows up
    first (or last) when viewing your EnderChest contents alphabetically

From there, you then create a shulker box for each instance that contains
_symlinks_ pointing into the files that live in the EnderChest (_e.g._
`instance_shulker/options.txt -> _Chest Monster/options files/basic_options.txt`).

Each instance will probably want to use the "Global" set of linked folders so
that when an instance generates new screenshots, logs, crash reports, etc., they
go into the EnderChest, and by making the "folders" inside of the shulker boxes
_symlinks themselves_, they can point into either shared or separated folders
within the Chest Monster, _i.e._

* `instance_shulker/saves -> _Chest Monster/worlds`, vs.
* `instance_shulker/saves -> _Chest Monster/worlds/instance's worlds`

This strategy has the advantage of ensuring that there are no linking conflicts,
as in its purest form, each instance is linked to only one chest, and onboarding
an existing instance following this approach is comparatively
straightforward--just move all of the instance's contents into the shulker box,
then move each file one-by-one from the shulker into the Chest Monster, putting
a link in the shulker box in the place of each file.

The downside, however, is that this process needs to be carried out _every_ time
there's a new instance, and replacing a mod with a newer version of that mod
requires updating every single link in each of your shulker boxes.

!!! tip "Pro Tip"
    If you remove the build and mod-version information from a mod's filename,
    then when you replace that file with a newer build, all the existing links
    will still work.

    You can also accomplish a similar effect by creating symlinks named
    `<mod>.<minecraft_version>.latest.jar` that point to the actual latest
    version. Then you can have the links in your shulker boxes safely point to
    that "latest" file, and when you upgrade the mod, you only need to update
    one symlink.

The other downside is that you can end up with "orphaned" files in your Chest
Monster that are no longer linked to by any shulker box.

There are, of course, hybrid approaches (for example, even though I mostly
follow the hierarchical approach for my instances, all of my worlds actually
live within structured folders inside of a "Chest Monster" for ease of
[backup management](https://github.com/OpenBagTwo/gsb)), and if you come up
with a different workflow that works for you,
[I'd be delighted to hear about it.](https://github.com/OpenBagTwo/EnderChest/issues/new)


## Managing Servers

If you host your own Minecraft servers, EnderChest can be extremely helpful
in keeping your modlists and config files in sync, both between servers and
between servers and desktop instances. For this section we'll assume
you're running (or are planning to run) a Minecraft server on a dedicated
Linux box. After [installing the `enderchest` package](../installation)
on your dedicated server and verifying that it has
[a suitable version of Rsync](../installation/#installing-rsync),
you can either [set up a clean EnderChest](../usage/#creating-an-enderchest)
or use [`enderchest craft --from`](../cli/#enderchest-craft) to piggyback off
your desktop's configuration (see [here](../usage/#understanding-uris)
for details on specifying your desktop's URI).

with your chest crafted, you can register your server via the command

```bash
enderchest gather server <path-to-server-home>
```
where `<path-to-server-home>` is the working directory you call the `java`
command from to start your server.

!!! info
    Additional information about this action can be found in
    [the CLI docs](../cli/#enderchest-gather-server)

If your dedicated box hosts _multiple_ servers, you can register them via
subsequent calls to `enderchest gather server`.

At this point, your `EnderChest` folder should still be empty, save for your
configuration file, even if you used the `--from` flag during crafting.
Before syncing your files, read through the following sections to make sure
you're not about to make a giant mess.

### Dedicated Server Configuration

If you're paying for a dedicated server, you're likely paying a premium for
disk space and network bandwidth, meaning you _probably don't_ want to sync
your client-side mods, single-player worlds or screenshots.

To make sure these files don't get transferred back and forth, open up
the `enderchest.cfg` file on the server (inside the `EnderChest` folder) and
edit the `do-not-sync` entry in the top `[properties]` section to exclude any
shulker boxes, ["Chest Monsters"](#chest-monster), etc. that should not be
transferred to the server.

!!! tip
    [Here's a helpful guide](https://linuxize.com/post/how-to-exclude-files-and-directories-with-rsync/)
    on crafting Rsync `--exclude` patterns

### Excluding Servers from "Global" Shulker Boxes

The [hierarchical approach to shulker boxes](#hierarchical) recommended starting
with a "global" box that contains configurations and files you'll want
_wherever_ you're playing. If you configured that box as specified, its contents
will _also_ place links inside your server instances. That might not be something
you want (for example, if your "global" box contained your screenshots or
`options.txt`). Instead, make sure (on your desktop, before syncing, to add "!server"
to the `[tags]` section of every `shulkerbox.cfg` file that should only be
linked for client-side / single player instances).

### Creating Server-Specific Shulker Boxes

On the flip side, if you're operating multiple servers, you're almost certainly
going to want to share files and folders across _just_ your servers
(for example: banlists, log / backup folders, or even the server JARs themselves).

To create a shulker box that _only_ gets linked to by server folders, open
up the shulker box's `shulkerbox.cfg` and make sure the `[tags]` section reads:

```ini
[tags]
server
```

!!! warning "Note"
    Note that additional entries in each section (with the exception of
    exclusions) are _OR_ -ed, not _AND_ -ed), so, for example, specifying
    ```ini
    [tags]
    server
    *aether*
    ```
    would match to all registered servers _and additionally_ to all instances
    with "aether" in the tag name

Another recommendation is to make generous use of
[link-folders](../usage/#linking-entire-folders) in your server-specific
shulker boxes. This way, new files placed inside these folders will become
available to the server as soon as they're synced, rather than requiring an
`enderchest place`.

Finally, unless you're _only_ planning on running `enderchest open` from
the server (and never `enderchest close` from a desktop to push changes _to_
the server), **do not link your world folders**, as you never want to overwrite
world files while the game is running.

!!! tip
    On the other hand, if you run an auto-backup script, it's an _excellent_
    idea to link and sync _that_ folder so that you have off-site copies of
    your world

### Syncing Between Server and Desktop

Just as with any other multi-computer setup, you can use
[`enderchest gather enderchests`](../cli/#enderchest-gather-enderchests)
to register your server EnderChest to the one on your desktop, though
to reliably do the reverse you'll either need to contact your ISP about getting
a static IP, or you'll need to set up a
[dynamic DNS service](https://www.duckdns.org/) for your home
(you'll also need to run an Rsync (or [SFTP](#sftp-protocol)) server on your
desktop and expose your SSH port to traffic from the internet).

Planning to run all of your sync operations (`enderchest open` and
`enderchest close`) from the desktop is going to be simpler (and safer)
for most users, but because EnderChest only runs `enderchest place` after
an `open` operation, you'll need to log into your server to regenerate any new
symlinks after each desktop-side sync. Running the sync operations from the
desktop also means you won't be able to easily schedule your sync operations to
coordinate with server restarts.


## Effective Syncing

### Passwordless SSH Authentication
When connecting to an SSH server (rsync / sftp), it is both more secure and
more convenient to use **public key authentication** instead of a password.
Instructions for setting up pubkey authentication can be found
[here for Windows](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_keymanagement)
and
[here for macOS and Linux](https://www.redhat.com/sysadmin/key-based-authentication-ssh)

### Pointing Links Outside of Your EnderChest

While link-folders (entire folders inside of your shulker box that are linked
to from your Minecraft instances) are great for centralizing things like
backups, logs, and crash reports that you probably don't need to have
split by instance, you _probably don't_ need to sync them across different
computers. My suggestion is to structure your minecraft folder (the parent of
your EnderChest folder) as follows:

```
<minecraft root>: a single folder where all your minecraft data will live
 ├── instances: your MultiMC-type instances (most launchers let you set a custom location)
 ├── backups
 ├── crash reports
 ├── logs
 ├── EnderChest: the root directory for all resources managed by this package
 │   ├── global: shulker box that links to all instances
 │   │   ├── backups ↵ -> ../../../backups
 │   │   ├── crash-reports ↵ -> ../../../crash reports
 │   │   ├── logs ↵ -> ../../../logs
 │   │   ├── screenshots ↵ -> ~/Pictures/minecraft screenshots
```

Since backups, crash reports, logs and, in my example, screenshots, live _outside_
of the Enderchest, the contents won't actually be synced. Meanwhile, because
the links themselves _do_ sync, and because I've used
[relative links](https://feryn.eu/blog/relative-symlinks/), this EnderChest
configuration will work on any EnderChest installation that uses this folder
structure, and all without needing to muck with the `do-not-sync` settings
in the config file!

### Keeping Local Boxes Local

EnderChest's default behavior is to sync _all_ shulker boxes across _all_ installations,
even if that shulker box won't be used on other machines. This is done so that your
local files are backed up and available for reference wherever you're playing Minecraft.

But if you have a lot of EnderChests and a lot of local-only shulker boxes, that might
not be something that you want, at least not on every machine.

To exclude a folder (or file) from sync, open your `enderchest.cfg` file (inside your
EnderChest folder). Inside the top `[properties]` section you should see an entry named
"do-not-sync". By default it should look like this:

```ini
do-not-sync =
        EnderChest/enderchest.cfg
        EnderChest/.*
        .DS_Store
```

If there's a shulker box you want to exclude from syncing, just add it on a new line
(prefixing it with `EnderChest/` will help ensure that you're not excluding files with
that name in other boxes).

!!! tip "Pro Tip"
    If you use a consistent naming convention, such as giving all of your local-only
	shulker boxes names that end in ".local", you can exclude them all at once by adding
	the line:
	```ini
	EnderChest/*.local
	```

Note that this "do-not-sync" list _is only obeyed_ for sync commands run from
the lcoal machine / EnderChest--this means that while running `enderchest close`
from one machine may exclude a shulker box from being pushed, running `enderchest open`
from that that other machine may grab that box anyway.

## Version control with Git

As mentioned [above](#keeping-local-boxes-local), if a folder in your
EnderChest is prefixed with a "." then EnderChest by default _will not_ sync
it with other machines or place links into that folder. One reason for this
is to make it easier to create incremental backups and put your configurations
under full version control using something like [Git](https://git-scm.com/).

If you navigate _into_ your EnderChest folder and run the command

```bash
git init
```

then assuming you have Git installed on your system, it will turn your
entire EnderChest into a repository and store its version history in the
hidden ".git" folder. This isn't the place for a full tutorial, but
a handy cheat-sheet of the basic `git` commands can be found
[here](https://training.github.com/downloads/github-git-cheat-sheet/).

The relevant section for you is the one that reads "Make changes."
You probably don't want to be pushing your EnderChest (which probably
contains a large number of very large files) to GitHub, though adding
the ability for EnderChest to sync between installations directly
via the Git protocol is
[definitely under consideration](https://github.com/OpenBagTwo/EnderChest/issues/30).

!!! tip "Shameless Plug"
    If you like the idea of version controls and backups but are intimidated
    by the complexity of Git, have a look at one of my other projects:
    [**G**ame **S**ave **B**ackups](https://github.com/OpenBagTwo/gsb), which
    distills the all the essential backup management operations down to a few
    simple verbs.

!!! tip
    If following the [Chest Monster](#chest-monster) approach, you may want to
    add the Chest Monster's folder to your
    [`.gitignore`](https://www.atlassian.com/git/tutorials/saving-changes/gitignore)
    file to prevent changes from being tracked (I personally prefer to manage
    my world-save backups separately using `gsb`)

## Launcher Integration

### Startup and Shutdown Scripts

Launchers like [PrismLauncher](https://www.prismlauncher.org/) can be configured to run
commands before an  instance is launched or after it's closed. Consider putting
`enderchest open /path/to/minecraft_root` in your startup scripts and
`enderchest close /path/to/minecraft_root` in your shutdown scripts (where
"minecraft_root" is the location where you usually run the enderchest commands,
*i.e.* the parent of your EnderChest folder.
