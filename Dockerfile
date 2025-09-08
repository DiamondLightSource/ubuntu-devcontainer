# The devcontainer should use the developer target and run as root with podman
# or docker with user namespaces.
FROM ubuntu:noble-20250714

# Add any system dependencies for the developer/build environment here
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    busybox \
    ca-certificates \
    curl \
    gdb \
    git \
    man-db \
    ssh-client \
    zsh

# Add oh my zsh
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

# Use busybox to provide any missing commands
# This is useful for commands like `telnet` that are not available in the base image
RUN busybox --install -s

# Copy in the default bash configuration
COPY terminal-config /root/terminal-config
ENV USER_TERMINAL_CONFIG=/user-terminal-config

# Make sure that $USER_TERMINAL_CONFIG exists so we can link to it
# and add hooks to all the files we reference
# This can be overridden by the user mounting a different folder over the top
RUN /root/terminal-config/ensure-user-terminal-config.sh && \
    echo '/root/terminal-config/ensure-user-terminal-config.sh' >> /root/.bashrc && \
    echo 'source ${USER_TERMINAL_CONFIG}/bashrc' >> /root/.bashrc && \
    echo '/root/terminal-config/ensure-user-terminal-config.sh' > /root/.zshrc && \
    echo 'source ${USER_TERMINAL_CONFIG}/zshrc' >> /root/.zshrc && \
    ln -fs $USER_TERMINAL_CONFIG/inputrc /root/.inputrc

# Install uv using the official image
# See https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/
