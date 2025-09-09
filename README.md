# Gitlab Migration Helper

A lightweight CLI tool to help move code repositories and surrounding
Gitlab resources from one Gitlab instance to another.

**Features:**

- CLI driven wizard to migrate repositories of a given group
- Batch migration of all repositories of a group
- Repositories from subgroups can be included
- Pruning of the original project, i.e. branches, releases and pipeline runs
- Additional Gitlab resources, that are migrated:
  - CI/CD Variables from within the project (inherited variables are not migrated)
  - Releases

> [!IMPORTANT]
> In order to keep the volume of the transfered data within the given Gitlab size
> the releases, tags and pipeline runs are pruned in the origin repositories. Refer
> to the "project preservation parameters" for details.

## How-to: Use this Helper

Before conducting the following steps make sure that you have set this project
up properly including the virtual environment, dependencies etc. Refer to the
[Preparation](#preparation) section for instructions.

### Caution Before Running

The CLI command can be invoked with just

```bash
    uv run gmh --help
```

This will bring up the CLI help also highlighting the parameters which can be
exposed as environment variables.

> [!IMPORTANT]
> Mind, that the CLI won't execute any permanent action unless one
> explicitly runs it with the `--no-dry-run` parameter to prevent accidental
> damage.

> [!CAUTION]
> It is also highly recommended to have a close look at the
> `Project preservation parameters` in the help message as they determine the
> deletion of releases and pipelines in the origin Gitlab **permanently**.

Last, but not least, using the string names of Gitlab groups is **discouraged**,
because Gitlab does not enforce uniqueness of the names. If in doubt, rather use
the group ID, which can be found in the web UI in the kebap menu `more actions`
on the top right of the group's main page.

`PROTECTED_BRANCHES` or `--pb` also accepts a whitespace separated list of
branches, e.g. "production main master". Mark, that only actually
matching names protect the branch, so be sure to have no typos. 'Main' and
'master' branch are kept regardlessly.

### Execution

... is then as simple as

```bash
    uv run gmh \
      --origin-group 1042 \
      --destination-group 17060 \
      --keep-latest-items 10 \
      --prompt
```

or with explicit environment setup
```bash
    uv run gmh \
      --origin-gitlab "http://url.to.your.gitlab.instance" \
      --origin-certificate "/path/to/your/cert.pem" \
      --origin-key "/path/to/your/key.pem" \
      --origin-token "your-token-value" \
      --destination-gitlab "http://url.to.your.gitlab.instance" \
      --destination-certificate "/path/to/your/cert.pem" \
      --destination-key "/path/to/your/key.pem" \
      --destination-token "your-token-value"\
      --origin-group 1042 \
      --destination-group 17060 \
      --keep-latest-items 10 \
      --prompt
```

## Preparation

### Setup

It is recommended to set the following environment variables up, which can
alternatively be provided as CLI:

- ORIGIN_TOKEN="your-token-value"
- ORIGIN_KEY="/path/to/your/key.pem"
- ORIGIN_CERTIFICATE="/path/to/your/cert.pem"
- ORIGIN_GITLAB="http://url.to.your.gitlab.instance"
- DESTINATION_TOKEN="your-token-value"
- DESTINATION_KEY="/path/to/your/key.pem"
- DESTINATION_CERTIFICATE="/path/to/your/cert.pem"
- DESTINATION_GITLAB="http://url.to.your.gitlab.instance"
- PROTECTED_BRANCHES="production main master"

See to the help message for their explanation:

```bash
    uv run gmh --help
```

### Necessary Tooling

This project uses `uv` for dependency and python version management and `poe`
for task running.

- If you don't have uv installed, see the
  [uv documentation](https://docs.astral.sh/uv/getting-started/installation/).
- if you don't have poe installed (see
  [poe documentation](https://poethepoet.natn.io/installation.html)), we
  recommend installing it using `uv`:

```bash
uv tool install poethepoet
```

uv automatically ensures that the correct python version specified in your
`pyproject.toml` is installed.

### Development Setup

All you need is:

```bash
poe dev-setup
```

That will:

1. Ensure a correct Python version is available and install it, if there isn't.
2. Create a new virtualenv.
3. Install all dependencies including dev dependencies (defined in the
   `project.optional-dependencies` section of your `pyproject.toml`).
4. Install the project in editable mode.
5. Configure git pre-commit hooks.

The pre-commit hooks are defined in
[.pre-commit-config.yaml](.pre-commit-config.yaml) as usual.

## Common Tasks

All common tasks can be run through `poe`, such as:

- Run linting, type checking, and all tests:
  ```bash
  poe check
  ```
  Linting and type checking are also run automatically on each commit via
  pre-commit hooks. If you want to skip running the pre-commit hooks, use
  ```commandline
  git commit --no-verify -m "your commit message here"
  ```
- Build the docs and open a browser with the latest version.
  ```bash
  poe docs-serve
  ```
  If you want to inspect the generated docs, build them with `poe docs-build`
  and check the `site/` directory.
- Find out what other commands exist.
  ```bash
  poe --help
  ```

### Running a Python Command

To run a Python in the virtualenv managed by `uv`, use:

```bash
uv run python your_script.py
```

For more info, see the
[uv docs](https://docs.astral.sh/uv/reference/cli/#uv-run).

### Adding a Dependency

Adding a core dependency:

```bash
uv add pytest
```

Adding a dependency to an optional group, e.g. the dev group:

```bash
uv add pytest --optional dev
```

For more info, see the
[uv docs](https://docs.astral.sh/uv/concepts/dependencies/)

### Installing Core Dependencies and an Additional Dependency Group

For example, to install the `docs` group in addition to core dependencies:

```bash
uv sync --extra docs
```

### Updating the Lock File

`uv` updates your `uv.lock` file automatically whenever you execute a "project
command" such as `uv run` or `uv sync`. If you want to do this step manually,
you can run Add new libraries without updating installed libraries

```bash
uv lock
```

or update everything with

```bash
uv upgrade
```

see `uv lock --help` for more information.

### Use a Different Python for the Virtualenv

uv supports setting which Python version should be used for your virtualenv (see
[documentation](https://docs.astral.sh/uv/concepts/python-versions/) for more
information) **Note:** These options should only be necessary in special cases.
By default, uv ensures that the Python version specified in your
`pyproject.toml` is installed and use it whenever you execute a command with uv
(or `poe`).

## Conventional Commits

[Conventional commits](https://www.conventionalcommits.org) is a specification
for adding human and machine readable meaning to commit messages, allowing
structured processing e.g. for changelogs.

Whenever you would commit using

```bash
git commit ...
```

You call instead:

```bash
cz commit
```

which guides the commit message creation through a set of questions. If the
commit failed (e.g. because the pre-commit hooks failed), you can retry
committing:

```bash
cz commit --retry
```

### Versioning

Versions are pinned on the project using git tags. Tags provide the best
traceability and are acknowledged to be industry standard. The recommended way
to create new tags is using commitizen which with calculate the version from
conventional commit messages in the git history.

The command to do that is

```bash
cz bump
```

You can check the new version with

```bash
uv sync
```

_Note:_ The resulting list is sorted alphabetically. For your own package, check
the entries starting with `~`.

This will by default configuration also automatically create or update the
CHANGELOG.md file based on the template file 'templates/CHANGELOG.md.j2'.

## Logging

Logging is done in a structured way. For this logging needs to be configured
once at the entrypoint of your application with

```python
from gitlab_migration_helper.loggingconfig import setup_logging

# set the logging configuration
setup_logging()
```

Afterwards you can use the logger with

```python
import logging

logger = logging.getLogger(__name__)

logger.info(
    "generic info",
    extra={
        "key": "value",
    },
)
```

(for a working example see also `src/gitlab_migration_helper/main.py`)
