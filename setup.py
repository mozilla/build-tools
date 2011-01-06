#! /usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="slavealloc",
    version="1.0",
    description="Mozilla RelEng Slave Allocator",
    author = "Release Engineers",
    author_email = "release@mozilla.com",

    # python packages are under lib/python
    packages = find_packages(),

    test_suite = 'slavealloc',

    install_requires = [
        'sqlalchemy',
        'argparse',
        'twisted',
    ],

    entry_points = {
        'console_scripts': [
            'slavealloc = slavealloc.scripts.main:main'
        ],
    }
)
