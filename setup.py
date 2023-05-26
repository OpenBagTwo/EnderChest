from setuptools import setup

import versioneer

setup(
    name="enderchest",
    python_requires=">=3.10",
    description="syncing and linking for all your Minecraft instances",
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
    extras_require={"test": ["pytest>=7", "pytest-cov>=4"]},
)
