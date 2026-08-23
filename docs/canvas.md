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

Canvas assignment descriptions contain a link to the course website, any explicit Canvas
`notes`, and the configured submission checklist. The Markdown assignment or lab body remains
on the course website and is not copied into Canvas.

## Typed rubrics

A typed rubric gives every section and criterion a stable slug. Canvas integrations select a
section by slug, while labels, display order, and point values can change independently. Its
top-level `type` is the default scoring mode for every item:

```yaml
integrations:
  canvas:
    points: 10
    rubric_section: setup
rubric:
  type: pass-fail
  sections:
    - slug: setup
      section: Setup
      points: 10
      criteria:
        - slug: clean-start
          points: 10
          desc: The project starts successfully from a clean checkout.
```

Each pass/fail criterion becomes a full-credit `Pass` rating and a zero-credit `Fail` rating in
Canvas. An individual criterion may override the default with `type: tiered` and explicit
ratings, or with `type: range` and an optional `min_points` (zero by default):

```yaml
        - slug: heldout-cases
          type: range
          points: 20
          desc: The implementation succeeds across the staff-held-out cases.
        - slug: design-quality
          type: tiered
          points: 10
          desc: The design is coherent, focused, and maintainable.
          tiers:
            - {points: 10, label: Strong, desc: Meets the full specification.}
            - {points: 5, label: Developing, desc: Meets the core specification with gaps.}
            - {points: 0, label: Insufficient, desc: Does not meet the core specification.}
```

Range items accept any point score between their minimum and maximum. Tiered items require
unique ratings that include both full-credit and zero-credit tiers. Section and criterion slugs
must be lowercase kebab case and unique within their scope. Criteria must total the section's
declared points, and a Canvas assignment's points must equal the selected criteria total.

On an MkDocs assignment page, render the same rubric with
`{{ rubric_table(page.meta.rubric) | safe }}`. Typed rubrics use compact outcome rows and expand
only the items with explicit tiers; legacy list-form rubrics retain their existing rendering.

## Submission checklists

Keep each checkpoint's student-facing checklist with its canonical due and last-accepted times,
and configure the shared section copy in a top-level `submission` map. Canvas uses `due_at` for
late-status calculations and `close_at` for the submission lock. If `close_at` is omitted,
Canvas locks the submission at `due_at`:

```yaml
checkpoints:
  - date: 2026-08-30
    title: "Checkpoint A"
    due_at: "2026-08-30T23:59:00-04:00"
    close_at: "2026-09-03T23:59:00-04:00"
    doc_anchor: checkpoint-a
    deliverables:
      - Preserve the exact revision to be graded.
      - Submit the revision URL and required evidence.
submission:
  intro: Complete each checklist and use the corresponding Canvas submission.
  timezone: ET
  ai_disclosure: Name the AI tools used, or write **No AI tools used.**
integrations:
  canvas:
    checkpoints:
      - name: "HW1A: Baseline"
        doc_anchor: checkpoint-a
```

Render the whole section with `{{ submission_checklists(page.meta) | safe }}`. The macro joins
checkpoint and Canvas data by `doc_anchor`, renders clickable task lists plus both deadline
labels, adds the compact Canvas action, and presents the disclosure text in a reusable admonition.

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
