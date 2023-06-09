# Best Practices and Suggested Workflows

## Other Syncing Protocols

If you can't or don't want to use rsync, EnderChest supports additional
protocols (and has plans for more).

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


## Collisions and Conflicts

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

## Managing Backups

### Version control with `git`

As mentioned [above](#keeping-local-boxes-local), if a folder in your
EnderChest is prefixed with a "." then EnderChest by default _will not_ sync
it with other machines or place links into that folder. One reason for this
is to make it easier to create incremental backups and put your configurations
under full version control using something like [git](https://git-scm.com/).

If you navigate _into_ your EnderChest folder and run the command

```bash
git init
```

then assuming you have `git` installed on your system, it will turn your
entire EnderChest into a repository and store its version history in the
hidden ".git" folder. This isn't the place for a full tutorial, but
a handy cheat-sheet of the basic `git` commands can be found
[here](https://training.github.com/downloads/github-git-cheat-sheet/).

The relevant section for you is the one that reads "Make changes."
You probably don't want to be pushing your EnderChest (which probably
contains a large number of very large files) to GitHub, though adding
the ability for EnderChest to sync between installations directly
via the `git` protocol is
[definitely under consideration](https://github.com/OpenBagTwo/EnderChest/issues/30).


## Integration with Auto-Update Tools

### Startup and Shutdown Scripts

Launchers like PrismLauncher can be configured to run commands
before an  instance is launched or after it's closed. Consider putting
`enderchest open /path/to/minecraft_root` in your startup scripts and
`enderchest close /path/to/minecraft_root` in your shutdown scripts (where
"minecraft_root" is the location where you usually run the enderchest commands,
*i.e.* the parent of your EnderChest folder.
