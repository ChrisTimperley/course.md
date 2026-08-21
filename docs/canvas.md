# Canvas Integration

The Canvas integration syncs assignment, lab, and quiz specs from the course repository into Canvas.
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
coursemd canvas labs --plan-only
coursemd canvas quizzes --plan-only
```

To contact Canvas without creating or updating content:

```bash
coursemd canvas assignments --dry-run
coursemd canvas labs --dry-run
coursemd canvas quizzes --dry-run
```

To sync selected files:

```bash
coursemd canvas assignments assignments/hw1.md
coursemd canvas labs labs/lab01.md
coursemd canvas quizzes quizzes/week1.md
```

After a non-dry-run sync, `coursemd` writes Canvas IDs back into the source frontmatter so later runs update the same Canvas objects.
The stored ID is authoritative: if it no longer exists in the configured Canvas course, sync
stops rather than matching by name or creating a replacement. Correct or deliberately remove
the ID before retrying.

## Lab submissions

Labs sync as Canvas assignments through the dedicated `labs` command. A lab accepts a URL
submission by default and is worth one point by default, which suits pass/fail grading. Configure
its due and unlock times explicitly so Canvas receives timezone-aware deadlines:

```yaml
---
kind: lab
title: CI Guardrails
date: 2026-09-04
release_date: 2026-08-31
due_at: 2026-09-04T23:59:00-04:00
integrations:
  canvas:
    assignment_group: Labs
    points: 1
    submission_types: [online_url]
    submission_form:
      - label: Final commit URL
        hint: Submit the URL of the specific commit in your fork.
---
```

The lab's `date`, `release_date`, and `due_at` are canonical course facts shared by the schedule
and integrations. Canvas-specific submission settings stay under `integrations.canvas`; the
Canvas name, unlock time, and due time are derived from the top-level `title`, `release_date`,
and `due_at` fields. Defining `integrations.canvas.name`, `integrations.canvas.unlock_at`, or
`integrations.canvas.due_at` is rejected to prevent competing sources of truth. As with
assignments, labs default to unpublished; pass `--publish` when the synchronized items should
be published.
