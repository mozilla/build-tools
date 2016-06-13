#! /usr/bin/env python

from pip.req import parse_requirements
from setuptools import setup, find_packages
import os
import sys

deps = [
    'sqlalchemy',
    'argparse',
    'simplejson',
    'furl',
    'requests',
    'docopt',
    'python-dateutil',
    'jinja2',
    'redo',
    'six',
]

if sys.version_info[:2] == (2, 7):
    deps.extend([
        'poster',
        'Twisted==10.1.0',
    ])

if sys.version_info >= (3, 5):
    """If running on py3, you need to `pip install -r requirements-py3.txt` after
    running setup.py, until the dependencies either support py3 or we drop their
    use."""
    pass

setup(
    name="buildtools",
    version="1.0.6",
    description="Mozilla RelEng Toolkit",
    author="Release Engineers",
    author_email="release@mozilla.com",

    # python packages are under lib/python.  Note that there are several
    # top-level packages here -- not just a buildtools package

    packages=find_packages("lib/python"),
    package_dir={'': "lib/python"},

    test_suite='mozilla_buildtools.test',

    install_requires=deps,

    entry_points={
        'console_scripts': [
            'slavealloc = slavealloc.scripts.main:main'
        ],
    },

    scripts=["buildfarm/maintenance/reboot-idle-slaves.py"],

    # include files listed in MANIFEST.in
    include_package_data=True,
)
