#!/bin/sh
# Builds PyMCU_<version>.mcu (a .tar.gz), the USB update package (see docs/Packaging.md).
# The package holds the last commit, not uncommitted edits, so every update is reproducible.
cd "$(dirname "$(readlink -f "$0")")"
VERSION=$(git show HEAD:MainViewModel.py | sed -n 's/^APP_VERSION = "\(.*\)"/\1/p')
if [ -z "$VERSION" ]; then echo "Could not read APP_VERSION from MainViewModel.py"; exit 1; fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "Warning: there are uncommitted changes. They are NOT in the package; commit them first."
fi
OUT="PyMCU_$VERSION.mcu"
# Local data, user programs and the theme setting on each MCU are left alone.
git archive --format=tar.gz --prefix=./ -o "$OUT" HEAD -- . \
    ':(exclude)docs' ':(exclude)tests' ':(exclude)FLICPrograms' ':(exclude)theme.txt' ':(exclude).vscode' ':(exclude).gitignore'
echo "Created $OUT (version $VERSION, commit $(git rev-parse --short HEAD))."
echo "Send it to the user: they copy it onto a USB stick and press Update in the MCU settings."
