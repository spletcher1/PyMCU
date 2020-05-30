#!/bin/bash
cd /home/pi/PyMCU/PyMCU
/bin/tar --exclude='./FLICData' --exclude='./FLICPrograms' --exclude='./RS485' --exclude='./.git' --exclude='./__pycache__' --exclude='./Notes.txt' --exclude='./.vs' --exclude='./.vscode'  --exclude='./.vscode' -zcvf ./NewVersion.tgz .
