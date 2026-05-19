# Quarto Integration

The Quarto integration builds or previews a course slide project from the `coursemd` CLI.

## Install

Install `course.md` in your course environment and make sure the `quarto` command is available on `PATH`.

## Configure

Add the slide directory to `.coursemd.yml`:

```yaml
integrations:
  quarto:
    dir: slides
```

The configured directory should contain a Quarto project, including `_quarto.yml`.

## Use

```bash
coursemd quarto preview
coursemd quarto build --output-dir build/slides/html
```

If no output directory is passed, slides are written under `build/slides/html`.
