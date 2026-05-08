# course.md Roadmap

This roadmap reflects the package as it exists today, not the initial proposal.
`course.md` already has a shared repository loader, a package CLI, a MkDocs
adapter, and reusable Canvas and GitHub workflows. The remaining work is about
making those boundaries explicit enough for reuse across course repositories.

## Current State

Implemented today:

- a typed `CourseRepository` loader that reads root-level YAML plus assignment and quiz Markdown files
- a single `coursemd` CLI for `init`, `validate`, website builds, slide commands, GitHub setup, and Canvas sync
- a MkDocs plugin that loads the canonical repository once and injects preloaded data into templates
- schedule rendering that uses preloaded repository data instead of re-reading source files at macro render time
- configurable assignment publish paths that are decoupled from source file locations
- quiz handling as source-only metadata for schedule rendering and sync workflows, never as public website pages
- optional dependency groups for core, MkDocs, Canvas, and full installs
- Canvas configuration is optional for courses that only need validation, site builds, or slides
- schedule events allow course-specific event kinds and multiple same-day events

This is a meaningful shift from the earlier "MkDocs helpers plus repo scripts"
shape. The package now owns the core repository-loading path and a reusable CLI
surface.

## Extraction Goal

The next milestone is to make `course.md` comfortable to extract from this
repository and consume as a reusable Git submodule or pinned package dependency.
That means the package should have:

- a documented repository contract that is smaller than this course's full workflow
- package-local tests that can run without relying on the parent repository layout
- adapter boundaries that keep MkDocs, Canvas, GitHub, and slides optional
- stable command names and option semantics before downstream courses depend on them
- a clear release or tag strategy for courses that pin the package from Git

## Near-Term Priorities

### 1. Strengthen the shared repository contract

The current loaders are useful, but validation is still relatively light.
Priority work here is:

- tightening schema checks for schedule data, quiz metadata, and assignment metadata
- surfacing clearer validation failures for missing required fields and malformed dates
- validating cross-file relationships such as schedule references to missing content
- reducing reliance on adapter-specific assumptions in repository data structures
- documenting extension points for course-specific schedule kinds and rendering styles

### 2. Make the package extraction-friendly

Before moving the code into a reusable submodule, priority work here is:

- confirming package tests run from inside `coursemd/` without parent-repository imports
- keeping examples, fixtures, and generated outputs either package-local or explicitly external
- documenting the expected install modes: editable path, Git tag, and optional extras
- checking that CLI commands discover `.coursemd.yml` consistently from course and website directories
- reviewing public module names for imports that downstream repositories may reasonably copy

### 3. Bring slide workflows onto the shared model

Slides are available through the CLI today, but they are not yet modeled as a
first-class adapter in the same way the MkDocs site is.

Priority work here is:

- defining a clearer slide metadata contract
- connecting slide outputs and lecture metadata to the same repository model used by the website
- reducing duplicated release and linkage logic between schedule data and slide configuration

### 4. Normalize plan/apply behavior across sync commands

Canvas workflows already expose planning-oriented paths, but the broader sync
surface should feel more consistent.

Priority work here is:

- making dry-run and planning behavior uniform across external-system commands
- improving command output so instructors can understand intended changes before apply steps
- keeping adapter-specific side effects behind explicit CLI boundaries
- keeping Canvas and GitHub setup flows visibly opt-in and separate from the core repository contract

### 5. Expand portability for other course repositories

The package is more reusable than it was, but it still carries assumptions from
this repository's structure and workflow.

Priority work here is:

- testing against additional repository layouts, including at least one non-Canvas course
- documenting the minimum required repository contract more clearly
- continuing to remove course-specific defaults that belong in configuration rather than code

## Longer-Term Opportunities

These are plausible next layers once the shared model is more stable:

- a dedicated slide adapter layer rather than thin CLI wrapping
- richer GitHub automation around repository provisioning and permissions
- schedule-driven generation of LMS structures such as modules or linked resources
- additional publishing backends that consume the same repository model
- broader grading-tool integration if it can be grounded in the shared content model

## Non-Goals For Now

Not current priorities:

- building a general LMS abstraction layer
- supporting every institution's policy or roster model
- replacing grading systems or building instructor-facing grading UIs
- turning `course.md` into a full platform with its own content authoring interface

The package should stay focused on being a reusable, content-driven course
operations toolkit.

## Practical Next Steps

The best next implementation sequence is:

1. Tighten validation around schedule, assignment, and quiz schema contracts.
2. Run package tests from `coursemd/` and remove any parent-repository coupling that appears.
3. Confirm editable-path, Git-tag, and optional-extra install examples work for a consuming course.
4. Define clearer slide metadata and connect slide workflows to the shared repository model.
5. Standardize plan versus apply behavior and output across sync commands.
6. Add portability tests against a second repository layout that differs from this one.
7. Revisit broader integrations only after those contracts are stable.
