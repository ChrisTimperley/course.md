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
coursemd quarto export slides/observability.qmd --output-dir build/observability
```

If no output directory is passed, slides are written under `build/slides/html`.

The `export` command renders a single Reveal deck to a stable bundle for agent workflows:

```text
build/observability/
  deck.html
  deck.pdf
  screenshots/
    slide-001.png
    slide-002.png
  index.yml
```

`index.yml` records `deck.html`, `deck.pdf`, and each slide number, title, and screenshot path.
PDF and screenshot export require a Chromium-compatible browser such as Chrome or Chromium; pass
`--browser-path` if it is not on `PATH` or in a standard application location.
