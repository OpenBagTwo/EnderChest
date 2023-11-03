# EnderChest

[![Python](https://img.shields.io/badge/Python-3.10,3.11,3.12-3776AB.svg?style=flat&logo=python&logoColor=white&color=ffdc53&labelColor=3d7aaa)](https://www.python.org)
![Linux](https://img.shields.io/badge/GNU/Linux-000000?style=flat-square&logo=linux&logoColor=white&color=eda445)
![SteamOS](https://img.shields.io/badge/SteamOS-3776AB.svg?style=flat-square&logo=steamdeck&logoColor=white&color=7055c3)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows&logoColor=white)
![MacOS](https://img.shields.io/badge/mac%20os-000000?style=flat-square&logo=apple&logoColor=white&color=434334)
![RaspberryPi](https://img.shields.io/badge/Raspberry%20Pi-000000?style=flat-square&logo=raspberrypi&logoColor=white&color=c51a4a)

Welcome to the documentation for EnderChest, a Python package for syncing
and linking all your Minecraft instances.

Use the nav bar on the side of the page to access tutorials, how-to guides
or the full API docs.

The source code for this project is
[freely available on GitHub](https://github.com/OpenBagTwo/EnderChest).

If you encounter a bug or have a suggestion,
[open an issue](https://github.com/OpenBagTwo/EnderChest/issues/new/choose)!

!!! danger "Important!!"

    EnderChest is based around the use of symbolic links.

    Starting with Minecraft 1.20, Mojang by default
    [no longer allows worlds to load if they are or if they contain symbolic links](https://help.minecraft.net/hc/en-us/articles/16165590199181).
    While it is true that an improper symlink could cause Minecraft to write data
    to a place it shouldn't, nothing in EnderChest will ever generate a symlink whose
    target is outside of your EnderChest folder _unless you place_ a symbolic link in
    your EnderChest pointing to somewhere else (which you may want to do so that your
    screenshots, for example, point to your "My Pictures" folder).

    If you still have concerns about symlinks or questions about how they work,
    read through
    [this guide](https://www.makeuseof.com/tag/what-is-a-symbolic-link-what-are-its-uses-makeuseof-explains/)
    or [watch this explainer](https://www.youtube.com/watch?v=mA08E59-zo8), and if
    you still have questions, feel free to
    [open an issue](https://github.com/OpenBagTwo/EnderChest/issues/new?assignees=OpenBagTwo&labels=question&title=symlink%20question).
