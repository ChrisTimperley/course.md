# MkDocs Integration

The MkDocs integration turns a course repository into a course website.
It loads the shared `coursemd` model, makes course data available to pages, generates assignment pages, and can hide unreleased content outside preview mode.

## Install

```bash
pip install "course.md[mkdocs] @ git+https://github.com/ChrisTimperley/course.md.git@v0.1.0"
```

## Configure

Add MkDocs settings to `.coursemd.yml`:

```yaml
integrations:
  mkdocs:
    base_url: https://example.edu/courses/example-101
    project_dir: website
    assignments_url_path: assignments
```

Then enable the plugin in `website/mkdocs.yml`:

```yaml
plugins:
  - coursemd:
      config_file: ../.coursemd.yml
  - search
```

`config_file` is optional when `.coursemd.yml` can be discovered from the MkDocs project directory or one of its parents.

## Use

```bash
coursemd site preview
coursemd site build --output-dir build/website
coursemd site build-preview --output-dir build/website-preview
```

Course data is available to Markdown pages through Jinja-style macros.
For example:

```markdown
# Schedule

{{ schedule_table(schedule) }}
```

Assignment Markdown files are read from the configured `paths.assignments` directory and published under `assignments_url_path`.
