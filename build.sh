#!/bin/bash

set -ex

# Set up variables
BUILD_DIR="build"

HANDLER_CODE_DIR="poker_handler"
HANDLER_PACKAGE_DIR="handler_package"
HANDLER_ZIP_FILE="handler.zip"

WORKER_CODE_DIR="poker_worker"
WORKER_PACKAGE_DIR="worker_package"
WORKER_ZIP_FILE="worker.zip"

# Clean up any existing package directory and ZIP file
rm -rf "$BUILD_DIR"/"$HANDLER_PACKAGE_DIR" "$BUILD_DIR"/"$HANDLER_ZIP_FILE"
rm -rf "$BUILD_DIR"/"$WORKER_PACKAGE_DIR" "$BUILD_DIR"/"$WORKER_ZIP_FILE"

# Create the package directories
mkdir -p "$BUILD_DIR"/"$WORKER_PACKAGE_DIR"
mkdir -p "$BUILD_DIR"/"$HANDLER_PACKAGE_DIR"

# Copy the Python scripts to the package directories
cp "$HANDLER_CODE_DIR"/*.py "$BUILD_DIR/$HANDLER_PACKAGE_DIR"
cp "$WORKER_CODE_DIR"/*.py "$BUILD_DIR/$WORKER_PACKAGE_DIR"

# Install dependencies into the package directory
pip install --target "$BUILD_DIR/$HANDLER_PACKAGE_DIR" -r "$HANDLER_CODE_DIR/requirements.txt"
pip install --target "$BUILD_DIR/$WORKER_PACKAGE_DIR" -r "$WORKER_CODE_DIR/requirements.txt"

# Create the ZIP files using the python utility
python3 zip_util.py "$BUILD_DIR/$HANDLER_PACKAGE_DIR" "$BUILD_DIR/$HANDLER_ZIP_FILE"
python3 zip_util.py "$BUILD_DIR/$WORKER_PACKAGE_DIR" "$BUILD_DIR/$WORKER_ZIP_FILE"
