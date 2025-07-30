# ubuntu-devcontainer

Opinionated Ubuntu based devcontainer for python and EPICS development, tagged in step with upstream ubuntu for runtime.

Features:
- User customisable bash/zsh environment
- Cross container persistent shell history
- git, curl make and other build-essentials
- uv for python environment management
- ssh, gdb and busybox for runtime debugging

## How to use from the commandline

To try it out without persistent shell history:

```bash
podman run -it ghcr.io/diamondlightsource/ubuntu-devcontainer
```

To keep the history and allow shell customisation:

```bash
mkdir -p $HOME/.config/terminal-config
podman run --mount type=bind,src=$HOME/.config/terminal-config,target=/user-terminal-config -it ghcr.io/diamondlightsource/ubuntu-devcontainer 
```

To do the above but with zsh:

```bash
mkdir -p $HOME/.config/terminal-config
podman run --mount type=bind,src=$HOME/.config/terminal-config,target=/user-terminal-config -it ghcr.io/diamondlightsource/ubuntu-devcontainer zsh
```

## How to customize your shell

When mounting in `$HOME/.config/terminal-config`, the container will create the following files in the directory:
- `bashrc`: loading some bash defaults
- `zshrc`: loading some zsh defaults
- `inputrc`: to customize the behaviour of up arrow etc in both shells

You are free to edit any of these files, adding overrides before or after the loading of the defaults, or even removing the loading of the defaults altogether.

History is also stored in this directory, in `.bash_eternal_history` and `.zsh_eternal_history` respectively.

## How to use as a devcontainer

See [this repo's `.devcontainer.json`](./.devcontainer.json) for an example on how to use as a devcontainer. Or clone this repo, open in vscode and click "reopen in container"

## How to use in the build stage of a Dockerfile

If you are using this during the build stage of a Dockerfile, then you should select the upstream `ubuntu` container for the runtime.

For instance:

```Dockerfile
# The developer stage is used as a devcontainer including dev versions
# of the build dependencies
FROM ghcr.io/diamondlightsource/ubuntu-devcontainer:noble AS developer
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    libevent-dev \
    libreadline-dev

# The build stage makes some assets using the developer tools
FROM developer AS build
RUN my-build-script.sh /assets

# The runtime stage installs runtime deps then copies in built assets
# This time we remove the apt lists to save disk space
FROM ubuntu:noble as runtime 
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    libevent \
    libreadline \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /assets /
```

