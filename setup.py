from setuptools import setup

import versioneer

setup(
    name="enderchest",
    python_requires=">=3.10",
    description="syncing and linking for all your Minecraft instances",
    author='Gili "OpenBagTwo" Barlev',
    url="https://github.com/OpenBagTwo/EnderChest",
    packages=["enderchest", "enderchest/test"],
    entry_points={
        "console_scripts": [
            "enderchest = enderchest.cli:main",
        ]
    },
    license="GPL v3",
    include_package_data=True,
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    install_requires=["semantic-version>=2.7", "pathvalidate>=2.5"],
    extras_require={"test": ["pytest>=7", "pytest-cov>=4"]},
)
