import os
import sys

from setuptools import setup
from subprocess import check_output

version = check_output(['bash', os.path.join(os.path.dirname(__file__), 'version.sh')])

with open('README.md', 'r') as f:
    long_description = f.read()

setup(
    name = 'odm',
    version = version,
    description = 'Storage Magic',
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    url = 'https://github.com/UMCollab/ODM',
    author = 'Ezekiel Hendrickson',
    author_email = 'ezekielh@umich.edu',
    license = 'MIT',
    packages = [
        'odm',
        'odm.libexec',
    ],
    install_requires = [
        'beautifulsoup4',
        'google-auth',
        'lxml',
        'kitchen',
        'python-dateutil',
        'pyyaml',
        'requests',
        'requests_oauthlib',
        'requests_toolbelt',
        'svgwrite',
    ],
    entry_points = {
        'console_scripts': [
            'odm=odm.libexec.wrapper:main',
            'gdm=odm.libexec.wrapper:main',
        ]
    },
    include_package_data = True,
    zip_safe = False,
)
