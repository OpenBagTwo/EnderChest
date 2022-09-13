# EnderChest

A folder structure and series of accompanying scripts to manage your minecraft installations across instances and installations

## Motivation

With the arrival of my Steam Deck, I find myself in the very First World problem of having a few too many Minecraft installations
across a few too many computers that I want to keep synced and backed up. This isn't as simple of a problem as just having a
central repository of files to keep in sync, as the machines I've got running Minecraft range fromn an Rasperry Pi, to an
M1 Mac to the controller-operated Steam Deck to an absolute beast of a desktop battlestation, so even though all run some
variant of MultiMC, each need their own settings and client mod tweaks for optimal gameplay.

Futhermore, since I do mod development and have content creation aspirations, several of my machines each have multiple instance
variants that are, for example, streamlined for development and testing, or otpimized for ReplayMod rendering, but that will
will want share some mods, resourcepacks and worlds between them.

And finally, there are some instances that I want to run on a server--either local or hosted--that I want to be able to play on
with my wife and kid.

In short, there are three different levels of file-sharing that need to take place:
1. Selective sharing across different computers
1. Selective sharing across different instances on the same computer
1. Selective sharing across server and client installations
 

## Directory Tree
To that end, the basic folder layout is split out by the context of which instances / installations will need to sync these files.

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



