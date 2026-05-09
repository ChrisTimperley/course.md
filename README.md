# course.md

`course.md` is a reusable Python package for data-driven course repositories.
It provides a typed repository loader, a MkDocs adapter, and a single
`coursemd` CLI for validation, website builds, slide workflows, and optional
Canvas and GitHub operations.

The package is structured so course content lives in repository data files and
Markdown frontmatter, while adapters and sync commands consume one shared model
instead of reparsing source files independently.

Naming note: `course.md` is the distribution and project name. The Python
package, CLI command, and MkDocs plugin entry point remain `coursemd`.

## What It Owns

`course.md` currently supports:

- loading repository data from `data/*.yaml`, `assignments/*.md`, and `quizzes/*.md`
- validating repository content before build or sync steps run
- building and previewing MkDocs course websites
- generating assignment pages and assignment navigation for MkDocs
- rendering schedule and grading macros from preloaded repository data
- syncing assignments and quizzes to Canvas when the Canvas extra is installed
- running opt-in GitHub organization setup workflows
- building and previewing slide decks through the package CLI

Important current constraints:

- MkDocs is the only supported website integration in this release.
- Quizzes are source-only metadata and are never published as website pages.
- Canvas and GitHub are optional integrations, not required parts of the course repository contract.
- Slides are still driven by the configured slide project, not by a separate slide adapter model.

## Installation

For a course repository, install `course.md` in the same Python environment that
builds the course site. This lets MkDocs discover the plugin and keeps each
course pinned to a known `course.md` release.

Recommended from a tagged Git release with `uv`:

```toml
[project]
dependencies = [
    "course.md[mkdocs]",
    "mkdocs-material>=9.5.0",
]

[tool.uv.sources]
"course.md" = { git = "https://github.com/ChrisTimperley/course.md.git", tag = "v0.1.0" }
```

Canvas-enabled course repositories should add the Canvas extra:

```toml
[project]
dependencies = [
    "course.md[mkdocs,canvas]",
    "mkdocs-material>=9.5.0",
]
```

For local development across two sibling repositories:

```toml
[tool.uv.sources]
"course.md" = { path = "../coursemd", editable = true }
```

Equivalent `pip` installs:

```bash
pip install "course.md[mkdocs] @ git+https://github.com/ChrisTimperley/course.md.git@v0.1.0"
pip install "course.md[mkdocs,canvas] @ git+https://github.com/ChrisTimperley/course.md.git@v0.1.0"
```

Contributor install:

```bash
cd coursemd
pip install -e ".[dev]"
```

Run tests from the package directory:

```bash
pytest
```

## Dev Container Feature

This repository also hosts the reusable `course.md` devcontainer feature under `devcontainer-features/`.
It is intended for downstream course repositories that want the shared authoring toolchain without maintaining a custom Dockerfile.

To test the feature locally from this repository:

```bash
cd devcontainer-features
devcontainer features test -f course-md --base-image mcr.microsoft.com/devcontainers/base:debian .
```

## Repository Contract

A repository using `course.md` is configured with a root-level `.coursemd.yml`.
The CLI discovers that file by walking upward from the current working
directory.

Minimal example:

```yaml
timezone: America/New_York
integrations:
  mkdocs:
    base_url: https://example.edu/course
    project_dir: website
    assignments_url_path: assignments
  quarto:
    dir: slides
paths:
  data_dir: data
  assignments_dir: assignments
  quizzes_dir: quizzes
```

The core repository contract is:

- `timezone` is an IANA timezone name used for date-only timestamps and current-date checks
- `integrations.mkdocs.project_dir` points to the MkDocs project that consumes the package plugin
- `integrations.mkdocs.assignments_url_path` controls where generated assignment pages are published
- `integrations.quarto.dir` points to the Quarto slides project when slides commands are used
- YAML data files live under the configured `paths.data_dir`
- assignment source files live under the configured `paths.assignments_dir`
- quiz source files live under the configured `paths.quizzes_dir`
- assignment and quiz discovery is filename-agnostic; every Markdown file except `index.md` is loaded
- quiz files are loaded for schedule rendering and Canvas sync, but never exposed as standalone website pages
- Canvas-specific assignment and quiz frontmatter is only required when running Canvas sync commands
- `paths.env_file` may point to a repository-local environment file for secrets; it defaults to `.env`

Optional Canvas config:

```yaml
integrations:
  canvas:
    base_url: https://canvas.example.edu
    course_id: 12345
```

Optional GitHub organization setup config:

```yaml
integrations:
  github:
    organization: example-course-org
    instructors_team_slug: instructors
```

Secrets should stay in the environment or a repository-local `.env`, for
example `CANVAS_TOKEN`.

## MkDocs Integration

Add the plugin to the website project's `mkdocs.yml`:

```yaml
plugins:
  - coursemd:
      config_file: ../.coursemd.yml
  - search
```

The `config_file` setting is optional when `.coursemd.yml` can be discovered
from the website project directory or one of its parents.

The MkDocs adapter currently:

- loads the canonical repository once during configuration
- injects preloaded course data into the render environment
- generates assignment pages from assignment source files
- generates assignment navigation entries
- filters unreleased content outside preview mode

Macros render from preloaded repository data. They do not re-read YAML or
Markdown source files during page rendering.

Example page usage:

```markdown
# Course Schedule

{{ schedule_table(schedule) }}
```

## CLI

The package exposes one Typer CLI:

```bash
coursemd init
coursemd validate
coursemd site preview
coursemd site build --output-dir build/website
coursemd site build-preview --output-dir build/website/_preview/demo
coursemd slides preview
coursemd slides build --output-dir build/slides/html
coursemd github setup --dry-run
coursemd github setup --permissions-only
coursemd github setup --rulesets-only
coursemd sync canvas assignments --plan-only assignments/hw1.md
coursemd sync canvas quizzes --plan-only quizzes/week1.md
```

Command notes:

- `coursemd init` writes a starter `.coursemd.yml` and refuses to overwrite an existing config unless you pass `--force`
- `coursemd init --include-canvas` includes Canvas sync settings in the starter config
- `coursemd validate` checks YAML data files plus assignment and quiz frontmatter through the shared loaders
- `coursemd site ...` requires the `mkdocs` extra and a Python environment that also has the website project's MkDocs plugins installed
- `coursemd slides ...` requires Quarto on `PATH`
- `coursemd sync canvas ...` requires the `canvas` extra and Canvas config or explicit `--course-id`
- `coursemd github setup` is an advanced opt-in workflow that requires authenticated GitHub CLI access with org-admin permissions

During development in a larger workspace or submodule checkout, run the same
CLI through the environment that has `course.md` installed:

```bash
uv run coursemd validate
uv run coursemd site preview
uv run coursemd sync canvas assignments --plan-only assignments/hw1.md
```

## Environment

Recognized environment variables include:

- `TZ` for legacy timezone handling when no course config has been loaded
- `CURRENT_DATE_OVERRIDE` for deterministic testing and preview behavior
- `CANVAS_TOKEN` for Canvas API access

Repository-local environment files are loaded from `paths.env_file` when
configured. Secrets should not be committed.

## License

MIT
