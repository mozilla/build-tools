#! /usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="buildtools",
    version="1.0",
    description="Mozilla RelEng Toolkit",
    author = "Release Engineers",
    author_email = "release@mozilla.com",

    # python packages are under lib/python
    packages = find_packages("lib/python"),
    package_dir = { '' : "lib/python" },

    test_suite = 'buildtools.test',
)
