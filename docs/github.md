# GitHub Integration

The GitHub integration is an opt-in organization setup workflow for course staff.
It can manage the organization default repository permission and a main-branch ruleset.

## Configure

Add GitHub settings to `.coursemd.yml`:

```yaml
integrations:
  github:
    organization: example-course-org
    instructors_team_slug: instructors
```

Optional settings:

```yaml
integrations:
  github:
    organization: example-course-org
    instructors_team_slug: instructors
    ruleset_name: Protect main branch
    default_repository_permission: none
```

## Use

Preview changes first:

```bash
coursemd github setup --dry-run
```

Apply only one part of the setup:

```bash
coursemd github setup --permissions-only
coursemd github setup --rulesets-only
```

This workflow requires authenticated GitHub access with permission to manage the target organization.
