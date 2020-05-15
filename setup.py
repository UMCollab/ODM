import os

from setuptools import setup
from subprocess import check_output

version = check_output(['bash', os.path.join(os.path.dirname(__file__), 'version.sh')]).decode('utf-8')

setup(
    version=version,
)
