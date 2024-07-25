# [Choice] Python version (use -bullseye variants on local arm64/Apple Silicon): 3, 3.10, 3.9, 3.8, 3.7, 3.6
ARG VARIANT="3.11-bullseye"
FROM mcr.microsoft.com/vscode/devcontainers/python:0-${VARIANT}

# Install MySQL client
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install default-mysql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install any additional packages or dependencies you need

# [Optional] If your requirements.txt file is in a different location, change the 'source' argument.
COPY ./requirements.txt /tmp/pip-tmp/
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /tmp/pip-tmp/requirements.txt \
    && rm -rf /tmp/pip-tmp

# Clean up
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# [Optional] Uncomment this section to ensure your local git credentials are used inside the container
# ARG USERNAME=vscode
# COPY --chown=${USERNAME}:vscode .devcontainer/scripts/setup-git.sh /tmp/setup-git.sh
# RUN /tmp/setup-git.sh && rm /tmp/setup-git.sh
