# course.md

`course.md` is a work-in-progress toolkit for building data-driven course repositories:
It keeps course facts, assignments, quizzes, schedules, and integration settings in one repository model, then lets integrations use that model to build or sync the pieces they own.

The current shape is intentionally small:

- keep canonical course data in YAML and Markdown files
- validate that data before publishing or syncing
- build course websites with MkDocs
- sync assignments, labs, and quizzes to Canvas
- build slide decks with Quarto
- run optional GitHub organization setup workflows

APIs, config, and integration behavior may change while the project settles.

## Example

A course repository usually has a `.coursemd.yml` at the root:

```yaml
timezone: America/New_York

schedule:
  start_date: 2026-01-12
  end_date: 2026-04-28

integrations:
  mkdocs:
    base_url: https://example.edu/courses/example-101
    project_dir: website
    assignments_url_path: assignments
  canvas:
    base_url: https://canvas.example.edu
    course_id: "12345"
  quarto:
    dir: slides

paths:
  data: data
  assignments: assignments
  labs: labs
  quizzes: quizzes
```

An assignment can live in `assignments/hw1.md`:

```markdown
---
title: Homework 1
release_date: 2026-01-20
due_at: 2026-01-27T23:59:00-05:00
---

Build a small command-line tool and submit your repository link.
```

The same assignment can then appear on the MkDocs site, in schedule macros, and in Canvas sync plans.

## Install In Your Course

Install `course.md` in the Python environment that builds your course:

```toml
[project]
dependencies = [
    "course.md[mkdocs]",
    "mkdocs-material>=9.5.0",
]

[tool.uv.sources]
"course.md" = { git = "https://github.com/ChrisTimperley/course.md.git", tag = "v0.1.0" }
```

For Canvas support, include the Canvas extra:

```toml
[project]
dependencies = [
    "course.md[mkdocs,canvas]",
    "mkdocs-material>=9.5.0",
]
```

With `pip`:

```bash
pip install "course.md[mkdocs] @ git+https://github.com/ChrisTimperley/course.md.git@v0.1.0"
```

Then add `.coursemd.yml`, create the directories named in `paths`, and run:

```bash
coursemd validate
```

## Integrations

`coursemd` is designed to grow through integrations.
Each integration should own the smallest useful workflow for one external tool, while the core package keeps the shared course model consistent.

Current integration docs:

- [MkDocs](docs/mkdocs.md)
- [Canvas](docs/canvas.md)
- [Quarto](docs/quarto.md)
- [GitHub](docs/github.md)

As more integrations are added, their user docs should live in `docs/*.md`.

## Common Commands

```bash
coursemd validate
coursemd site preview
coursemd site build --output-dir build/website
coursemd canvas assignments --plan-only
coursemd canvas labs --plan-only
coursemd canvas quizzes --plan-only
coursemd quarto build --output-dir build/slides/html
coursemd github setup --dry-run
```

## License

MIT
