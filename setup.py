from setuptools import setup

import versioneer

setup(
    name="enderchest",
    python_requires="3.10",
    description="syncing and linking for all your Minecraft instances",
    author='Gili "OpenBagTwo" Barlev',
    url="https://github.com/OpenBagTwo/EnderChest",
    packages=["ennderchest"],
    license="GPL v3",
    include_package_data=True,
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
)
