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

Coming soon!

### Managing Backups

Coming soon!

## Integration with Auto-Update Tools

### Startup and Shutdown Scripts

Launchers like PrismLauncher can be configured to run commands
before an  instance is launched or after it's closed. Consider putting
`enderchest open /path/to/minecraft_root` in your startup scripts and
`enderchest close /path/to/minecraft_root` in your shutdown scripts (where
"minecraft_root" is the location where you usually run the enderchest commands,
*i.e.* the parent of your EnderChest folder.
