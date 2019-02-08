* Update the changelog
* Tag the release
* `python setup.py sdist`
* `twine upload dist/odm-<version>.tar.gz`
* Create Github release from the tag with the dist tarball as an attachment
