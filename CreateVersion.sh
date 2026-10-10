#!/bin/sh
# Packs the app into NewVersion.tgz for a USB update (copy it to FLICUpdates/ on a stick).
cd "$(dirname "$(readlink -f "$0")")"
/bin/tar --exclude='./FLICData' --exclude='./FLICPrograms' --exclude='./docs' --exclude='./.git' \
    --exclude='./.venv' --exclude='./__pycache__' --exclude='./.vscode' --exclude='./.lgd-nfy*' \
    --exclude='./theme.txt' --exclude='./NewVersion.tgz' -zcvf ./NewVersion.tgz .
