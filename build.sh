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

# Install dependencies into the package directory using a Docker container to ensure binary compatibility with Lambda
# We run as the current user to avoid permission issues
docker run --rm --network host -u "$(id -u):$(id -g)" -v "$(pwd):/var/task" public.ecr.aws/sam/build-python3.11 \
    /bin/sh -c "pip install --target $BUILD_DIR/$HANDLER_PACKAGE_DIR -r $HANDLER_CODE_DIR/requirements.txt && \
               pip install --target $BUILD_DIR/$WORKER_PACKAGE_DIR -r $WORKER_CODE_DIR/requirements.txt"

# Clean up unnecessary files to reduce package size
find "$BUILD_DIR/$HANDLER_PACKAGE_DIR" -type d -name "__pycache__" -exec rm -rf {} +
find "$BUILD_DIR/$HANDLER_PACKAGE_DIR" -type d -name "*.dist-info" -exec rm -rf {} +
find "$BUILD_DIR/$WORKER_PACKAGE_DIR" -type d -name "__pycache__" -exec rm -rf {} +
find "$BUILD_DIR/$WORKER_PACKAGE_DIR" -type d -name "*.dist-info" -exec rm -rf {} +
find "$BUILD_DIR/$WORKER_PACKAGE_DIR" -type d -name "*.egg-info" -exec rm -rf {} +
find "$BUILD_DIR/$WORKER_PACKAGE_DIR" -name "*.pyc" -delete

# Create the ZIP files using the python utility
python3 zip_util.py "$BUILD_DIR/$HANDLER_PACKAGE_DIR" "$BUILD_DIR/$HANDLER_ZIP_FILE"
python3 zip_util.py "$BUILD_DIR/$WORKER_PACKAGE_DIR" "$BUILD_DIR/$WORKER_ZIP_FILE"
