from xml.dom import minidom
from pathlib import Path

from setuptools import setup

POSTFIX = '.1'

version = minidom.parse('apriltags/package.xml').getElementsByTagName("version")[0].childNodes[0].data

description = (Path(__file__).parent / 'README.md').read_text()

setup(
    name='pyapriltags',
    version=version+POSTFIX,
    author='Aleksandar Petrov',
    author_email='alpetrov@ethz.ch',
    maintainer='Will Barber',
    description="Python bindings for the Apriltags library",
    long_description=description,
    long_description_content_type='text/markdown',
    license='BSD',
    url="https://github.com/WillB97/pyapriltags",
    install_requires=['numpy'],
    packages=['pyapriltags'],
    include_package_data=True,
)
