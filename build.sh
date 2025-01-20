#!/bin/bash

set -ex

# Set up variables
BUILD_DIR="build"
EXCLUDE_DIR="venv/*"

WORKER_CODE_DIR="worker_lambda"
WORKER_PACKAGE_DIR="worker_package"
WORKER_ZIP_FILE="worker.zip"

HANDLER_CODE_DIR="request_handler_lambda"
HANDLER_PACKAGE_DIR="handler_package"
HANDLER_ZIP_FILE="handler.zip"

# Clean up any existing package directory and ZIP file
rm -rf "$BUILD_DIR"/*

# Create the package directories
mkdir -p "$BUILD_DIR"/"$WORKER_PACKAGE_DIR"
mkdir -p "$BUILD_DIR"/"$HANDLER_PACKAGE_DIR"

# Copy the Python script to the package directories
cp "$HANDLER_CODE_DIR"/*.py "$BUILD_DIR/$HANDLER_PACKAGE_DIR"
cp "$WORKER_CODE_DIR"/*.py "$BUILD_DIR/$WORKER_PACKAGE_DIR"

# Install dependencies into the package directory
pip install --target "$BUILD_DIR/$HANDLER_PACKAGE_DIR" -r "$HANDLER_CODE_DIR/requirements.txt"
pip install --target "$BUILD_DIR/$WORKER_PACKAGE_DIR" -r "$WORKER_CODE_DIR/requirements.txt"

# Create the ZIP files, excluding the specified directory
cd "$BUILD_DIR/$HANDLER_PACKAGE_DIR"
zip -r ../$HANDLER_ZIP_FILE . -x "$EXCLUDE_DIR"
cd ../..

cd "$BUILD_DIR/$WORKER_PACKAGE_DIR"
zip -r ../$WORKER_ZIP_FILE . -x "$EXCLUDE_DIR"
cd ../..

# Verify the contents of the ZIP file
# unzip -l $ZIP_FILE
