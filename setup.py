from pathlib import Path

from setuptools import setup

import versioneer

long_description = (Path(__file__).parent / "README.md").read_text()

setup(
    name="enderchest",
    python_requires=">=3.10",
    description="syncing and linking for all your Minecraft instances",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='Gili "OpenBagTwo" Barlev',
    url="https://github.com/OpenBagTwo/EnderChest",
    packages=[
        "enderchest",
        "enderchest.sync",
        "enderchest.test",
        "enderchest.test.testing_files",
    ],
    package_data={
        "enderchest.test": [
            "testing_files/*.cfg",
            "testing_files/*.json",
            "testing_files/*.txt",
        ]
    },
    entry_points={
        "console_scripts": [
            "enderchest = enderchest.cli:main",
        ]
    },
    license="GPL v3",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    install_requires=["semantic-version>=2.7", "pathvalidate>=2.5"],
    extras_require={
        "test": ["pytest>=7", "coverage>=7"],
        "sftp": ["paramiko>=3.3"],
    },
)
