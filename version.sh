#!/bin/bash

cd $(readlink -fn $(dirname "$BASH_SOURCE"))

if [ -d .git ]; then
    version=$(git describe --tags | perl -pe 'chomp; s/-/./; s/-.*//' | tee VERSION)
elif [ -s VERSION ]; then
    version=$(cat VERSION)
else
    printf -v version %s UNKNOWN
fi

cat > odm/version.py <<EOF
#!/usr/bin/env python3

VERSION = '$version'
EOF

printf %s $version
