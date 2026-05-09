"""GitHub ruleset payload builders."""

from __future__ import annotations

from typing import Any


def build_main_branch_ruleset_payload(*, team_id: int, ruleset_name: str) -> dict[str, Any]:
    """Build the organization ruleset payload used to protect main branches."""

    return {
        "name": ruleset_name,
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [
            {
                "actor_id": team_id,
                "actor_type": "Team",
                "bypass_mode": "always",
            },
            {
                "actor_id": 1,
                "actor_type": "OrganizationAdmin",
                "bypass_mode": "always",
            },
        ],
        "conditions": {
            "repository_name": {
                "include": ["~ALL"],
                "exclude": [],
                "protected": False,
            },
            "ref_name": {
                "include": ["refs/heads/main"],
                "exclude": [],
            },
        },
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "creation"},
            {"type": "required_linear_history"},
            {
                "type": "update",
                "parameters": {
                    "update_allows_fetch_and_merge": False,
                },
            },
        ],
    }
