# husky-musher

This is a fork of the original Husky Musher redirecting service for the
UW Husky Coronavirus Testing study. This fork only adapts the survey
redirect modules, but also productionizes the application for
deployment.


## Developer requirements

- Follow the [first-time use instructions](#first-time-use)

## Running from docker

### Run an existing build

As long as you have a docker client, you can run an existing build.

1. [View the package in Github](https://github.com/UWIT-IAM/husky-musher/blob/main/husky_musher/settings.py#L8)
2. Find the tag you are interested in running (usually the newest tag is your best
   option) and copy it to your clipboard
3. In your terminal, run `docker pull ghcr.io/uwit-iam/husky-musher:<tag>`
4. Then, run `docker run -it -p 8000:8000 ghcr.io/uwit-iam/husky-musher:<tag>`
    - Replace `<tag>` with the tag you copied to your clipboard.
    - Add `--env-file local.env` before the `ghcr` argument if you followed the
      [environment variables](#environment-variables)
      instructions and have all the necessary variables handy.

### Run from local source

#### If you have `bash` installed:

Recommended; this will typically build faster because
it is dependency-aware and uses some common optimization practices
shared between UW-IT IAM projects.

```
./scripts/build-images.sh --run
```

This will automatically look for a `local.env` file if you don't provide an
`--env-file` argument; if `local.env` is not found, the application will boot
but may not actually do much.

### Using just docker:

```
docker build . -t husky-musher:local
docker run  \
   # Omit the --env-file argument if you have not generated an env-file to use
   --env-file local.dotenv \
   # Omit the `--mount` argument if you do not want to sync
   # the running container with your local changes
   --mount type=bind,source=$(pwd)/husky_musher,target=/musher/husky_musher"
   -p 8000:8000 \
   -it husky-musher:local
```

## Running without docker

If you are actively developing, you may be interested in running this
directly from source without docker, for debugging purposes.

No problem!

**If this is your first time running locally**, follow [first-time use](#first-time-use).

Then:

```
set -a               # Export all vars sourced in the next line
source local.env     
set +a               # Stop var exporting to avoid side effects in any future commands
poetry run flask run
```

### First-time use


#### Recommended setup:


If you are running a unix- or linux-like termina,
and have both `poetry` and `pyenv`, you can paste the
following into your terminal to configure your environment:

```bash
pyenv install 3.8.6
poetry env use ~/.pyenv/versions/3.8.6/bin/python
poetry install
```

You should also think about creating an env file to export
environment variables; see [environment variables](#environment-variables).

Otherwise . . .

#### Manual setup:

First, [get poetry](https://python-poetry.org/docs/#installation). Poetry makes it easy
to manage application versions and dependency versions consistently and safely.

Set up your local environment to use python version 3.7+. If you don't
know how to manage python versions,
see [managing python versions](#managing-python-versions).

```
poetry env use /path/to/python
poetry install
```

You should also think about creating an env file to export
environment variables; see [environment variables](#environment-variables).


#### Managing python versions

[pyenv](https://github.com/pyenv/pyenv) is great for this, as long as you
are not using Windows. If you are using Windows, please see the notes in
the pyenv installation docs.

```
pyenv install 3.8.6
# Test the install:
~/.pyenv/versions/3.8.6/bin/python --version
```

## Environment Variables

Environment variable documentation can be found in 
[docs/configuration.md](docs/configuration.md).


## Maintainer Information

For maintainers, see the [docs/](docs) directory!


## Attributions
"[Paw Print](https://thenounproject.com/search/?q=dog+paw&i=3354750)" icon By Humantech from [the Noun Project](http://thenounproject.com/).
