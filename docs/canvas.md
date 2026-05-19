# Canvas Integration

The Canvas integration syncs assignment and quiz specs from the course repository into Canvas.
It is optional and only needed for repositories that publish to Canvas.

## Install

```bash
pip install "course.md[mkdocs,canvas] @ git+https://github.com/ChrisTimperley/course.md.git@v0.1.0"
```

## Configure

Add Canvas settings to `.coursemd.yml`:

```yaml
integrations:
  canvas:
    base_url: https://canvas.example.edu
    course_id: "12345"
```

Set your Canvas token in the environment or in the repository-local environment file:

```bash
export CANVAS_TOKEN=...
```

## Use

Start with plan-only mode.
It parses local files and prints what would sync without contacting Canvas:

```bash
coursemd canvas assignments --plan-only
coursemd canvas quizzes --plan-only
```

To contact Canvas without creating or updating content:

```bash
coursemd canvas assignments --dry-run
coursemd canvas quizzes --dry-run
```

To sync selected files:

```bash
coursemd canvas assignments assignments/hw1.md
coursemd canvas quizzes quizzes/week1.md
```

After a non-dry-run sync, `coursemd` writes Canvas IDs back into the source frontmatter so later runs update the same Canvas objects.
