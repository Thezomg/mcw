from setuptools import setup
import sys

requirements = [
    'clize>=3.0a1'
]

if sys.version_info < (3, 3):
    raise Exception("this version of python is too old")
elif sys.version_info < (3, 4):
    requirements.append('asyncio')

setup(
    name='mcw',
    version='0.1a1',
    description='minimalist minecraft server wrapper',
    packages=['mcw'],
    zip_safe=True,
    entry_points={
        'console_scripts': [
            'mcw = mcw.cli:main',
        ]
    },
    install_requires=requirements,
    author='Deaygo, Ed Kellett, Tom Powell',
    author_email='edk@kellett.im',
    url='https://github.com/Thezomg/mcw',
    long_description='TBA',
)
