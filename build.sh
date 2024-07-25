#!/bin/bash

set -ex

# Set up variables
PACKAGE_DIR="lambda_package"
ZIP_FILE="function.zip"
EXCLUDE_DIR="venv/*"

# Clean up any existing package directory and ZIP file
rm -rf $PACKAGE_DIR $ZIP_FILE

# Create the package directory
mkdir -p $PACKAGE_DIR

# Copy the Python script to the package directory
cp *.py $PACKAGE_DIR/

# Install dependencies into the package directory
pip install --target $PACKAGE_DIR -r requirements.txt

# Create the ZIP file, excluding the specified directory
cd $PACKAGE_DIR
zip -r ../$ZIP_FILE . -x "$EXCLUDE_DIR"
cd ..

# Verify the contents of the ZIP file
unzip -l $ZIP_FILE
