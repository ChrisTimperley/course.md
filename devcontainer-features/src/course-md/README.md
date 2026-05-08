# course.md Authoring Toolchain

Installs the shared authoring toolchain used by `course.md`-based course repositories.

This Feature installs the reusable Python runtime for course repositories directly into the container, including the `course.md` package, the `coursemd` CLI, `mkdocs-material`, `pre-commit`, and the shared authoring tools that would otherwise live in a repo-local Dockerfile.
It is intended to compose with upstream Features for Quarto and GitHub CLI.

## Example Usage

```json
{
  "image": "mcr.microsoft.com/devcontainers/base:debian",
  "features": {
    "ghcr.io/christimperley/course.md/course-md:1": {
      "version": "v0.1.0",
      "slides": true,
      "ocr": true,
      "linters": true
    },
    "ghcr.io/rocker-org/devcontainer-features/quarto-cli:1": {
      "installChromium": false
    },
    "ghcr.io/devcontainers/features/github-cli:1": {}
  }
}
```

## Options

| Option | Description | Default |
| --- | --- | --- |
| `version` | Git tag or ref of `course.md` to install into the container. | `v0.1.0` |
| `slides` | Installs Chromium and Bubblewrap for slide preview/export workflows. | `true` |
| `ocr` | Installs `tesseract-ocr` for OCR-based authoring workflows. | `false` |
| `latex` | Installs a minimal LaTeX toolchain. | `false` |
| `linters` | Installs shared Node.js-based linting and formatting tools such as `markdownlint-cli` and `prettier`. | `true` |

## Ownership Boundary

This Feature owns reusable authoring packages.
Consumer repositories should continue to own their own VS Code extensions, lifecycle hooks, forwarded ports, mounts, secrets, and any course-specific environment configuration.
