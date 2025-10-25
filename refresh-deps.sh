#!/bin/bash
echo "Checking for pip update ..."
pip install --upgrade pip
echo "Updating core requirements ..."
pip install -qr requirements.txt --upgrade
echo "Updating test requirements ..."
pip install -qr requirements_test.txt --upgrade
echo "Updating docs requirements ..."
pip install -qr requirements_docs.txt --upgrade
echo "Pre-commit autoupdate ..."
pre-commit autoupdate
