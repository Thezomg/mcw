import os
from setuptools import setup

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "an_example_pypi_project",
    version = "0.1",
    author = "Deaygo, Ed Kellett, Tom Powell",
    author_email = "mcw@thezomg.com",
    description = ("A minecraft server wrapper."),
    license = "",
    keywords = "minecraft server wrapper",
    url = "https://github.com/Thezomg/mcw",
    packages=['mcw', 'tests'],
    long_description=read('README.md'),
)
