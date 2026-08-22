"""MkDocs macros for course websites."""

from __future__ import annotations

import typing as t
from datetime import datetime
from html import escape

from jinja2 import Environment, FileSystemLoader, select_autoescape

from coursemd.core.loaders.dates import parse_date as _parse_date
from coursemd.core.schedule import Schedule
from coursemd.core.utils import current_date
from coursemd.integrations.canvas.config import DEFAULT_CANVAS_BASE_URL
from coursemd.integrations.mkdocs.schedule import render_schedule
from coursemd.integrations.mkdocs.schedule_cards import (
    render_schedule_cards,
    render_this_week_card,
)

if t.TYPE_CHECKING:
    from coursemd.core.models.assignment import Assignment
    from coursemd.core.models.lab import Lab
    from coursemd.core.models.staff import StaffMember

_TH_EXCEPTION_MIN = 11  # 11th, 12th, 13th are exceptions to ordinal suffix rules
_TH_EXCEPTION_MAX = 13
_DEFAULT_STAFF_PHOTO_BASE_PATH = "/assets/images"
_DEFAULT_STAFFER_TEMPLATE = """
{%- macro render_staffer(person) -%}
<div class="staffer card">
    <div class="container">
        {% if person.photo %}
        <img class="staffer-image" src="{{ photo_base_path }}/{{ person.photo }}" alt="">
        {% else %}
        <div class="staffer-image-placeholder"></div>
        {% endif %}
        <div>
            <h3 class="staffer-name">
                {{ person.name }}
            </h3>
            <div class="staffer-links">
                {% if person.email %}
                <a href="mailto:{{ person.email }}"><span class="material-symbols-outlined">
                    mail
                </span></a>
                {% endif %}
                {% if person.website %}
                <a href="{{ person.website }}" target="_blank">
                    <span class="material-symbols-outlined">
                    public
                    </span>
                </a>
                {% endif %}
            </div>
        </div>
    </div>
</div>
{%- endmacro -%}
""".strip()


def _configured_canvas_base_url(env: t.Any) -> str:
    raw_value = env.conf.get("extra", {}).get("canvas_base_url") or DEFAULT_CANVAS_BASE_URL
    return str(raw_value).rstrip("/")


def _format_submission_due_at(value: t.Any, timezone: str) -> str | None:
    """Format a checkpoint due time for a student-facing submission heading."""
    if isinstance(value, datetime):
        due_at = value
    elif isinstance(value, str):
        try:
            due_at = datetime.fromisoformat(value.strip())
        except ValueError:
            return None
    else:
        return None

    hour = due_at.strftime("%I").lstrip("0") or "0"
    minute = due_at.strftime("%M")
    meridiem = due_at.strftime("%p").lower()
    timezone_suffix = f" {timezone.strip()}" if timezone.strip() else ""
    return (
        f"{due_at.strftime('%A, %B')} {due_at.day} at {hour}:{minute} {meridiem}{timezone_suffix}"
    )


def _template_environment(env: t.Any) -> Environment:
    docs_dir = env.conf.get("docs_dir")
    template_env = Environment(
        loader=FileSystemLoader(str(docs_dir)) if docs_dir else None,
        autoescape=select_autoescape(),
    )
    template_env.globals.update(getattr(env, "variables", {}))
    template_env.globals.update(getattr(env, "macros", {}))
    return template_env


def _staffer_template(
    env: t.Any,
    *,
    template_path: str | None,
    photo_base_path: str,
) -> t.Any:
    template_env = _template_environment(env)
    template_env.globals["photo_base_path"] = photo_base_path.rstrip("/")
    return (
        template_env.get_template(template_path)
        if template_path
        else template_env.from_string(_DEFAULT_STAFFER_TEMPLATE)
    )


def _render_staffer(
    env: t.Any,
    *,
    person: StaffMember,
    template_path: str | None,
    photo_base_path: str,
) -> str:
    template = _staffer_template(
        env,
        template_path=template_path,
        photo_base_path=photo_base_path,
    )
    module = template.make_module({"photo_base_path": photo_base_path.rstrip("/")})
    return t.cast("str", module.render_staffer(person))


def _current_page_url(env: t.Any) -> str | None:
    page = getattr(env, "variables", {}).get("page")
    url = getattr(page, "url", None)
    return str(url) if url is not None else None


def define_env(env: t.Any) -> None:
    """
    Define MkDocs macros for use in course websites.

    This function is called by the coursemd MkDocs plugin or mkdocs-macros-plugin
    compatibility setups to register macros.
    """

    @env.macro
    def instructor_only(caller: t.Callable[[], str] | None = None) -> str:
        """Render a call block only when coursemd is building a preview site.

        Usage::

            {% call instructor_only() %}
            Content visible only in ``coursemd site preview`` and
            ``coursemd site build-preview``.
            {% endcall %}
        """
        if not env.variables.get("coursemd_preview", False):
            return ""
        return caller() if caller is not None else ""

    @env.macro
    def schedule_table(schedule: dict[str, t.Any]) -> str:
        """
        Render a course schedule table from schedule data.

        Args:
            schedule: Dictionary containing course, events, breaks, assignments, and quizzes

        Returns:
            HTML string for the schedule table
        """
        return render_schedule(
            Schedule.build(
                earliest_date=schedule["course"]["start_date"],
                latest_date=schedule["course"]["end_date"],
                events=schedule.get("events", []),
                breaks=schedule.get("breaks", []),
                assignments=schedule.get("assignments", []),
                quizzes=schedule.get("quizzes", []),
            )
        )

    @env.macro
    def schedule_cards(
        schedule: dict[str, t.Any],
        show_learning_goals: bool = True,
        show_upcoming_lectures: bool = False,
        show_upcoming_exams: bool = False,
    ) -> str:
        """
        Render a course schedule as weekly cards from schedule data.

        Groups the schedule into weekly cards, each listing that week's events
        and the homework released that week. An alternative to ``schedule_table``.

        Args:
            schedule: Dictionary containing course, events, breaks, assignments, and quizzes
            show_learning_goals: Whether lecture rows expand to show their learning goals
            show_upcoming_lectures: Whether to show every upcoming lecture
            show_upcoming_exams: Whether to show every upcoming exam or midterm

        Returns:
            HTML string for the weekly schedule cards
        """
        return render_schedule_cards(
            Schedule.build(
                earliest_date=schedule["course"]["start_date"],
                latest_date=schedule["course"]["end_date"],
                events=schedule.get("events", []),
                breaks=schedule.get("breaks", []),
                assignments=schedule.get("assignments", []),
                quizzes=schedule.get("quizzes", []),
                show_upcoming_lectures=show_upcoming_lectures,
                show_upcoming_exams=show_upcoming_exams,
                show_all_content=bool(env.variables.get("coursemd_preview", False)),
            ),
            meeting_days=schedule.get("meeting_days"),
            labs=schedule.get("labs", []),
            preview_spec_links=schedule.get("preview_spec_links"),
            current_page_url=_current_page_url(env),
            show_learning_goals=show_learning_goals,
        )

    @env.macro
    def this_week_card(
        schedule: dict[str, t.Any],
        show_learning_goals: bool = True,
        show_upcoming_lectures: bool = False,
        show_upcoming_exams: bool = False,
    ) -> str:
        """
        Render a single weekly card for the current week (or nearest upcoming week).

        Intended for a compact "This Week" preview, e.g. in a page hero. Reuses the
        same card markup as ``schedule_cards``.

        Args:
            schedule: Dictionary containing course, events, breaks, assignments, and quizzes
            show_learning_goals: Whether lecture rows expand to show their learning goals
            show_upcoming_lectures: Whether to show every upcoming lecture
            show_upcoming_exams: Whether to show every upcoming exam or midterm

        Returns:
            HTML string for a single week card, or an empty string if there is nothing to show
        """
        return render_this_week_card(
            Schedule.build(
                earliest_date=schedule["course"]["start_date"],
                latest_date=schedule["course"]["end_date"],
                events=schedule.get("events", []),
                breaks=schedule.get("breaks", []),
                assignments=schedule.get("assignments", []),
                quizzes=schedule.get("quizzes", []),
                show_upcoming_lectures=show_upcoming_lectures,
                show_upcoming_exams=show_upcoming_exams,
                show_all_content=bool(env.variables.get("coursemd_preview", False)),
            ),
            meeting_days=schedule.get("meeting_days"),
            labs=schedule.get("labs", []),
            preview_spec_links=schedule.get("preview_spec_links"),
            current_page_url=_current_page_url(env),
            show_learning_goals=show_learning_goals,
        )

    @env.macro
    def released_assignments(schedule: dict[str, t.Any]) -> list[Assignment]:
        """
        Return a list of assignments that have been released.

        Args:
            schedule: Dictionary containing schedule data

        Returns:
            List of assignment dictionaries that have been released
        """
        now = current_date()
        assignments = t.cast("list[Assignment]", schedule.get("assignments", []))
        return [assignment for assignment in assignments if assignment.release_date <= now]

    @env.macro
    def released_labs(schedule: dict[str, t.Any]) -> list[Lab]:
        """
        Return a list of labs whose release date has passed.

        Args:
            schedule: Dictionary containing schedule data

        Returns:
            List of lab objects whose release date is on or before today
        """
        now = current_date()
        labs = t.cast("list[Lab]", schedule.get("labs", []))
        return [lab for lab in labs if lab.reveal_on <= now]

    @env.macro
    def grade_table(
        platinum_min_score: int = 93,
        platinum_grade_points: int = 10,
        gold_min_score: int = 85,
        gold_grade_points: int = 9,
        silver_min_score: int = 80,
        silver_grade_points: int = 8,
        bronze_min_score: int = 70,
        bronze_grade_points: int = 7,
        copper_min_score: int = 60,
        copper_grade_points: int = 6,
        max_score: int = 100,
    ) -> str:
        """
        Generate a Markdown table showing grade tiers and their requirements.

        Args:
            platinum_min_score: Minimum score for platinum tier
            platinum_grade_points: Points awarded for platinum tier
            ... (similar for other tiers)
            max_score: Maximum possible score

        Returns:
            Markdown string for the grade table
        """
        rows = [
            (
                "platinum",
                "Platinum",
                platinum_grade_points,
                platinum_min_score,
                ":material-trophy:",
            ),
            ("gold", "Gold", gold_grade_points, gold_min_score, ":material-medal:"),
            ("silver", "Silver", silver_grade_points, silver_min_score, ":material-medal-outline:"),
            ("bronze", "Bronze", bronze_grade_points, bronze_min_score, ":material-medal-outline:"),
            (
                "copper",
                "Copper",
                copper_grade_points,
                copper_min_score,
                ":material-certificate-outline:",
            ),
        ]

        out = [
            f"| Grade | Points | Minimum Score (out of {int(max_score)}) |",
            "|:--:|:--:|:--:|",
        ]

        for key, label, pts, cutoff, icon in rows:
            chip = f'<span class="chip" data-grade="{key}">{icon} {label}</span>'
            out.append(f"| {chip} | **{pts}** | ≥ {int(cutoff)} |")

        fail = '<span class="chip" data-grade="fail">:material-alert-circle-outline: Fail</span>'
        out.append(f"| {fail} | **0** | < {int(copper_min_score)} |")

        return "\n".join(out)

    @env.macro
    def grade_table_from_component(component: dict[str, t.Any]) -> str:
        """
        Generate a grade boundaries table from a grading component dict.

        The component should have ``raw_max`` and a ``tiers`` list whose entries
        each have ``name``, ``min_score``, and ``points``.  Tiers should be ordered
        from best (Platinum) to worst (Fail); the last tier is treated as Fail and
        rendered separately.

        Usage in Markdown: {{ grade_table_from_component(page.meta.grading) }}

        Args:
            component: A grading component dict (e.g. from page frontmatter).

        Returns:
            Markdown string for the grade boundaries table.
        """
        tier_styles: dict[str, tuple[str, str]] = {
            "platinum": ("platinum", ":material-trophy:"),
            "gold": ("gold", ":material-medal:"),
            "silver": ("silver", ":material-medal-outline:"),
            "bronze": ("bronze", ":material-medal-outline:"),
            "copper": ("copper", ":material-certificate-outline:"),
        }

        raw_max: int = int(component.get("raw_max", 100))
        tiers: list[dict[str, t.Any]] = component.get("tiers", [])
        # Last tier is "Fail"; all others are scored tiers
        scored_tiers = tiers[:-1]
        fail_tier = tiers[-1] if tiers else None

        out = [
            f"| Grade | Points | Minimum Score (out of {raw_max}) |",
            "|:--:|:--:|:--:|",
        ]

        for tier in scored_tiers:
            name: str = tier.get("name", "")
            key = name.lower()
            style_key, icon = tier_styles.get(key, (key, ":material-star:"))
            pts = int(tier.get("points", 0))
            min_score = int(tier.get("min_score", 0))
            chip = f'<span class="chip" data-grade="{style_key}">{icon} {name}</span>'
            out.append(f"| {chip} | **{pts}** | ≥ {min_score} |")

        if fail_tier is not None:
            copper_min = int(scored_tiers[-1].get("min_score", 0)) if scored_tiers else 0
            fail_chip = (
                '<span class="chip" data-grade="fail">:material-alert-circle-outline: Fail</span>'
            )
            out.append(f"| {fail_chip} | **0** | < {copper_min} |")

        return "\n".join(out)

    @env.macro
    def grade_boundaries_table() -> str:
        """
        Generate a Markdown table showing letter grade boundaries from preloaded grading data.

        Returns:
            Markdown string for the grade boundaries table
        """
        grading_data = env.variables.get("grading")
        if grading_data is None:
            return ""

        out = [
            "| Course Grade | Minimum Points |",
            "|:--:|:--:|",
        ]

        out.extend(
            f"| **{boundary['letter']}** | **{boundary['min']}** |"
            for boundary in grading_data["scale"]
        )

        out.append(f"| **R** | < {grading_data['scale'][-1]['min']} |")

        return "\n".join(out)

    @env.macro
    def rubric_table(rubric: list[dict[str, t.Any]] | dict[str, t.Any]) -> str:
        """
        Render a rubric from structured front-matter data.

        Legacy list rubrics render expandable tier tables. Typed rubrics render
        compact rows; individual criteria may be pass/fail, tiered, or ranges.

        Args:
            rubric: Rubric data from page front matter.

        Returns:
            HTML string for the rubric
        """
        rubric_type = str(rubric.get("type", "tiered")) if isinstance(rubric, dict) else "tiered"
        sections = rubric.get("sections", []) if isinstance(rubric, dict) else rubric
        if not isinstance(sections, list):
            return ""
        total_points = sum(
            int(section.get("points", 0)) for section in sections if isinstance(section, dict)
        )
        point_label = "point" if total_points == 1 else "points"
        summary = (
            '<p class="rubric__summary">The assignment is worth '
            f"<strong>{total_points} {point_label}</strong>.</p>"
        )

        if isinstance(rubric, dict):
            html_parts = [
                f'<div class="rubric rubric--typed rubric--{escape(rubric_type)}">',
                summary,
            ]
            for section in sections:
                if not isinstance(section, dict):
                    continue
                section_name = escape(str(section.get("section", "")))
                section_slug = escape(str(section.get("slug", "")), quote=True)
                section_points = int(section.get("points", 0))
                criteria = section.get("criteria", [])
                if not isinstance(criteria, list):
                    continue
                html_parts.append(
                    f'<section class="rubric-section" id="rubric-{section_slug}" '
                    f'data-rubric-section="{section_slug}">'
                    f'<h3 class="rubric-section__title">{section_name}'
                    f'<span class="rubric-section__points">{section_points} pts</span>'
                    f'</h3><ul class="rubric-checklist">'
                )
                for criterion in criteria:
                    if not isinstance(criterion, dict):
                        continue
                    criterion_slug = escape(str(criterion.get("slug", "")), quote=True)
                    item_key = f"{section_slug}.{criterion_slug}"
                    criterion_type = escape(str(criterion.get("type", rubric_type)), quote=True)
                    criterion_points = int(criterion.get("points", 0))
                    point_label = "pt" if criterion_points == 1 else "pts"
                    checkbox_id = f"rubric-check-{section_slug}-{criterion_slug}"
                    points_id = f"rubric-points-{section_slug}-{criterion_slug}"
                    min_points = int(criterion.get("min_points", 0))
                    points_text = (
                        f"{min_points}&ndash;{criterion_points} pts"
                        if criterion_type == "range"
                        else f"{criterion_points} {point_label}"
                    )
                    description = escape(str(criterion.get("desc") or criterion.get("name") or ""))
                    html_parts.append(
                        f'<li class="rubric-checklist__item '
                        f'rubric-checklist__item--{criterion_type}" '
                        f'id="rubric-{section_slug}-{criterion_slug}" '
                        f'data-rubric-item="{item_key}" '
                        f'data-rubric-type="{criterion_type}">'
                        f'<input class="rubric-checklist__checkbox" type="checkbox" '
                        f'id="{checkbox_id}" aria-describedby="{points_id}">'
                        f'<label class="rubric-checklist__description" '
                        f'for="{checkbox_id}">{description}</label>'
                        f'<span class="rubric-checklist__points" id="{points_id}">'
                        f"{points_text}</span>"
                    )
                    tiers = criterion.get("tiers", [])
                    if criterion_type == "tiered" and isinstance(tiers, list):
                        html_parts.append(
                            '<details class="rubric-checklist__tiers">'
                            "<summary>Scoring levels</summary>"
                            '<table class="rubric-criterion__table">'
                            "<thead><tr><th>Points</th><th>Level</th>"
                            "<th>Description</th></tr></thead><tbody>"
                        )
                        for tier in tiers:
                            if not isinstance(tier, dict):
                                continue
                            tier_points = int(tier.get("points", 0))
                            tier_class = (
                                "rubric-tier--top"
                                if tier_points == criterion_points
                                else ("rubric-tier--zero" if tier_points == 0 else "")
                            )
                            html_parts.append(
                                f'<tr class="rubric-tier {tier_class}">'
                                f'<td class="rubric-tier__points">{tier_points}</td>'
                                f'<td class="rubric-tier__label">'
                                f"{escape(str(tier.get('label', '')))}</td>"
                                f'<td class="rubric-tier__desc">'
                                f"{escape(str(tier.get('desc', '')))}</td></tr>"
                            )
                        html_parts.append("</tbody></table></details>")
                    html_parts.append("</li>")
                html_parts.append("</ul></section>")
            html_parts.append("</div>")
            return "\n".join(html_parts)

        html_parts = [summary]

        for section in sections:
            if not isinstance(section, dict):
                continue
            section_name = section["section"]
            section_points = section["points"]
            criteria = section.get("criteria", [])

            html_parts.append(
                f'<div class="rubric-section">'
                f'<h3 class="rubric-section__title">'
                f"{section_name}"
                f'<span class="rubric-section__points">{section_points} pts</span>'
                f"</h3>"
            )

            for criterion in criteria:
                crit_name = criterion["name"]
                crit_points = criterion["points"]
                crit_desc = criterion.get("desc", "")
                tiers = criterion.get("tiers", [])

                desc_html = (
                    f'<span class="rubric-criterion__desc">{crit_desc}</span>' if crit_desc else ""
                )

                html_parts.append(
                    f'<details class="rubric-criterion">'
                    f'<summary class="rubric-criterion__header">'
                    f'<span class="rubric-criterion__summary">'
                    f'<span class="rubric-criterion__name">{crit_name}</span>'
                    f"{desc_html}"
                    f"</span>"
                    f'<span class="rubric-criterion__points">{crit_points} pts</span>'
                    f"</summary>"
                    f'<table class="rubric-criterion__table">'
                    f"<thead><tr>"
                    f"<th>Points</th><th>Level</th><th>Description</th>"
                    f"</tr></thead>"
                    f"<tbody>"
                )

                for tier in tiers:
                    tier_points = tier["points"]
                    tier_label = tier["label"]
                    tier_desc = tier["desc"]
                    is_top = tier_points == crit_points
                    is_zero = tier_points == 0
                    tier_class = (
                        "rubric-tier--top" if is_top else ("rubric-tier--zero" if is_zero else "")
                    )
                    html_parts.append(
                        f'<tr class="rubric-tier {tier_class}">'
                        f'<td class="rubric-tier__points">{tier_points}</td>'
                        f'<td class="rubric-tier__label">{tier_label}</td>'
                        f'<td class="rubric-tier__desc">{tier_desc}</td>'
                        f"</tr>"
                    )

                html_parts.append("</tbody></table></details>")

            html_parts.append("</div>")

        return "\n".join(html_parts)

    @env.macro
    def render_staffer(
        person: StaffMember,
        template_path: str | None = None,
        photo_base_path: str = _DEFAULT_STAFF_PHOTO_BASE_PATH,
    ) -> str:
        """
        Render a single staff member using the built-in staffer template.

        Args:
            person: Staff member loaded from .coursemd.yml.
            template_path: Optional template path relative to the MkDocs docs directory.
            photo_base_path: URL path prefix for staff photos.

        Returns:
            HTML string for the staff member card.
        """
        return _render_staffer(
            env,
            person=person,
            template_path=template_path,
            photo_base_path=photo_base_path,
        )

    @env.macro
    def ta_team_table(staff: list[StaffMember]) -> str:
        """
        Render a Markdown table mapping TAs to their assigned teams.

        Only teaching assistants with assigned teams are included.

        Args:
            staff: List of staff members loaded from .coursemd.yml.

        Returns:
            Markdown string for the TA-team mapping table.
        """
        rows = [
            "| TA | Teams |",
            "| --- | --- |",
        ]
        for person in staff:
            if person.role != "teaching-assistant":
                continue
            if not person.teams or person.email is None:
                continue
            teams_str = ", ".join(person.teams)
            rows.append(f"| [{person.name}](mailto:{person.email}) | {teams_str} |")
        return "\n".join(rows)

    @env.macro
    def checkpoints_list(heading: str = "Checkpoints and Deadlines") -> str:
        """
        Render a heading and Markdown bullet list of checkpoints for an assignment page.

        Reads ``checkpoints`` from the current page's frontmatter. Each entry should
        have a ``title`` and optionally ``doc_anchor`` (for an in-page link) and
        ``due_at`` (ISO datetime string, used to format the due date).
        Entries without ``due_at`` are listed without a date.

        The ``heading`` argument controls the ``##`` heading text.

        Usage in Markdown: {{ checkpoints_list() }}

        Returns:
            Markdown string with a ## heading and bullet list.
        """
        page = env.variables.get("page")
        if page is None:
            return ""

        checkpoints: list[dict[str, t.Any]] = getattr(page, "meta", {}).get("checkpoints", [])
        if not checkpoints:
            return ""

        lines: list[str] = [f"## {heading}", ""]
        for cp in checkpoints:
            name: str = cp.get("title", "")
            anchor: str = cp.get("doc_anchor", "")
            due_at_raw = cp.get("due_at", "")
            due_date = _parse_date(due_at_raw) if due_at_raw else None

            if due_date:
                day_name = due_date.strftime("%A")
                month_name = due_date.strftime("%B")
                day = due_date.day
                suffix = (
                    "th"
                    if _TH_EXCEPTION_MIN <= day <= _TH_EXCEPTION_MAX
                    else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
                )
                date_str = f"{day_name}, {month_name} {day}{suffix}"
                due_str = f"due {date_str} at 11:59 pm ET"
            else:
                due_str = ""

            suffix_str = f" ({due_str})" if due_str else ""
            if anchor:
                lines.append(f"* [**{name}**](#{anchor}){suffix_str}")
            else:
                lines.append(f"* **{name}**{suffix_str}")

        return "\n".join(lines)

    @env.macro
    def gdoc_copy(doc_id: str) -> str:
        """
        Return a Google Doc "make a copy" link for a document id.

        Usage in Markdown: {{ gdoc_copy(page.meta.quality_plan_gdoc_id) }}
        """
        if not doc_id:
            return ""
        return f"https://docs.google.com/document/d/{doc_id}/copy"

    @env.macro
    def canvas_submission(
        target: int | str,
        *,
        show_form: bool = True,
    ) -> str:
        """
        Render a Canvas submission callout for a specific assignment or checkpoint.

        ``target`` may be a numeric Canvas assignment ID or a stable ``doc_anchor``
        (or name) from the page's Canvas integration metadata. Looking up a
        checkpoint by anchor lets its Markdown call site remain stable when Canvas
        sync first assigns, or later changes, the numeric ID.

        The macro renders a direct assignment link when an ID is available. Before
        the first sync, it links to the course assignment list instead of emitting a
        broken URL.

        When the Canvas submission defines a ``submission_form`` list, each field is
        rendered as a labelled item so students know exactly what to paste into
        the Canvas text-entry box. Set ``show_form`` to false when the surrounding
        document already provides a deliverables checklist; this renders a compact
        action instead of the full admonition.

        Usage in Markdown::

            {{ canvas_submission(958737) }}
            {{ canvas_submission("checkpoint-a", show_form=false) }}

        Args:
            target: Canvas assignment ID, checkpoint anchor, or assignment name.
            show_form: Whether to render the configured submission form fields.

        Returns:
            Markdown string for the submission admonition.
        """
        canvas_course_id: int | None = env.conf.get("extra", {}).get(
            "canvas_course_id"
        ) or env.variables.get("schedule", {}).get("course", {}).get("canvas_course_id")
        canvas_base_url = _configured_canvas_base_url(env)
        # Try to find the Canvas submission config from the current page first,
        # then from any assignment list injected into the page.
        assignment_cfg: dict[str, t.Any] = {}
        target_value = str(target).strip()

        def matches(candidate: dict[str, t.Any]) -> bool:
            candidate_id = candidate.get("canvas_id") or candidate.get("id")
            return (
                (candidate_id is not None and str(candidate_id) == target_value)
                or candidate.get("doc_anchor") == target_value
                or candidate.get("name") == target_value
                or candidate.get("title") == target_value
            )

        page = env.variables.get("page")
        if page is not None:
            page_meta = getattr(page, "meta", {})
            page_integrations = page_meta.get("integrations", {})
            if isinstance(page_integrations, dict):
                page_canvas = page_integrations.get("canvas", {})
                if isinstance(page_canvas, dict):
                    checkpoints = page_canvas.get("checkpoints", [])
                    if isinstance(checkpoints, list):
                        for checkpoint in checkpoints:
                            if not isinstance(checkpoint, dict):
                                continue
                            if matches(checkpoint):
                                assignment_cfg = checkpoint
                                break
                    if not assignment_cfg and matches(page_canvas):
                        assignment_cfg = page_canvas
            assignments = getattr(page, "meta", {}).get("assignments", [])
            if not assignment_cfg:
                for assignment in assignments:
                    integration_map = assignment.get("integrations", {})
                    if not isinstance(integration_map, dict):
                        continue
                    canvas = integration_map.get("canvas", {})
                    if not isinstance(canvas, dict):
                        continue
                    if matches(canvas) or matches(assignment):
                        assignment_cfg = {**assignment, **canvas}
                        break

        canvas_id = assignment_cfg.get("canvas_id") or assignment_cfg.get("id")
        if canvas_id is None and target_value.isdigit():
            canvas_id = target_value

        if canvas_course_id and canvas_id is not None:
            url = f"{canvas_base_url}/courses/{canvas_course_id}/assignments/{canvas_id}"
        elif canvas_id is not None:
            url = f"{canvas_base_url}/assignments/{canvas_id}"
        elif canvas_course_id:
            url = f"{canvas_base_url}/courses/{canvas_course_id}/assignments"
        else:
            url = f"{canvas_base_url}/assignments"

        name_value = assignment_cfg.get("name") or assignment_cfg.get("title")
        name = str(name_value) if name_value else None
        short_name = name.split(":", 1)[0].strip() if name else "assignment"
        if not show_form:
            compact_label = f"Open {short_name} in Canvas"
            return (
                '<p class="canvas-submission">'
                f'<a class="canvas-submission__link" href="{escape(url, quote=True)}">'
                f"<span>{escape(compact_label)}</span>"
                '<span class="canvas-submission__arrow" aria-hidden="true">&rarr;</span>'
                "</a></p>"
            )

        if canvas_id is not None:
            link_text = f"Click here to submit {name}" if name else "Click here to submit"
        else:
            link_text = f"Open Canvas assignments for {name}" if name else "Open Canvas assignments"

        # Build submission form field lines.
        form_fields: list[dict[str, t.Any]] = assignment_cfg.get("submission_form", [])
        field_icons: dict[str, str] = {
            "url": ":material-link:",
            "gdoc": ":material-google-drive:",
            "text": ":material-text:",
            "confirm": ":material-checkbox-marked-outline:",
        }
        lines: list[str] = [
            '!!! warning "Canvas Submission"',
            f"    [**{link_text}**]({url})",
        ]
        if form_fields:
            lines.append("")
            lines.append("    **What to include in your submission:**")
            lines.append("")
            for field in form_fields:
                field_label: str = field.get("label", "")
                field_type: str = str(field.get("type", "text")).lower()
                field_hint: str = field.get("hint", "")
                icon = field_icons.get(field_type, ":material-text:")
                label_md = f"**{field_label}**" if field_label else ""
                hint_md = f" — *{field_hint}*" if field_hint else ""
                lines.append(f"    - {icon} {label_md}{hint_md}")

        return "\n".join(lines)

    @env.macro
    def submission_checklists(metadata: dict[str, t.Any]) -> str:
        """Render an assignment's complete submission section from front matter.

        Canonical checkpoint entries provide the anchor, deadline, and
        ``deliverables`` checklist. Matching ``integrations.canvas.checkpoints``
        entries provide the Canvas assignment name and link. The optional
        top-level ``submission`` map configures the section heading, introduction,
        timezone label, and reusable AI-disclosure admonition.

        Usage in Markdown::

            {{ submission_checklists(page.meta) | safe }}

        Args:
            metadata: Current page front matter.

        Returns:
            Markdown for the complete submission and deliverables section.
        """
        if not isinstance(metadata, dict):
            return ""

        submission_cfg = metadata.get("submission", {})
        if not isinstance(submission_cfg, dict):
            submission_cfg = {}
        checkpoints = metadata.get("checkpoints", [])
        if not isinstance(checkpoints, list) or not checkpoints:
            return ""

        canvas_checkpoints: list[dict[str, t.Any]] = []
        integrations = metadata.get("integrations", {})
        if isinstance(integrations, dict):
            canvas = integrations.get("canvas", {})
            if isinstance(canvas, dict) and isinstance(canvas.get("checkpoints"), list):
                canvas_checkpoints = [
                    item for item in canvas["checkpoints"] if isinstance(item, dict)
                ]

        canvas_by_anchor = {
            str(item["doc_anchor"]): item for item in canvas_checkpoints if item.get("doc_anchor")
        }
        heading = str(submission_cfg.get("heading") or "Submission and Deliverables")
        intro = str(submission_cfg.get("intro") or "").strip()
        timezone = str(submission_cfg.get("timezone") or "").strip()
        valid_checkpoints = [
            checkpoint for checkpoint in checkpoints if isinstance(checkpoint, dict)
        ]
        single_checkpoint = len(valid_checkpoints) == 1
        section_anchor = ""
        if single_checkpoint:
            anchor = str(valid_checkpoints[0].get("doc_anchor") or "").strip()
            section_anchor = f" {{ #{anchor} }}" if anchor else ""

        lines = [f"## {heading}{section_anchor}", ""]
        if intro:
            lines.extend([intro, ""])

        for checkpoint in valid_checkpoints:
            anchor = str(checkpoint.get("doc_anchor") or "").strip()
            canvas_checkpoint = canvas_by_anchor.get(anchor, {})
            if not single_checkpoint:
                title = str(
                    canvas_checkpoint.get("name") or checkpoint.get("title") or "Checkpoint"
                )
                anchor_attr = f" {{ #{anchor} }}" if anchor else ""
                lines.extend([f"### {title}{anchor_attr}", ""])

            due_label = _format_submission_due_at(checkpoint.get("due_at"), timezone)
            if due_label:
                lines.extend([f"**Due {due_label}.**", ""])

            deliverables = checkpoint.get("deliverables", [])
            if isinstance(deliverables, list):
                for deliverable in deliverables:
                    text = str(deliverable).strip()
                    if text:
                        lines.append(f"* [ ] {text}")
                if deliverables:
                    lines.append("")

            canvas_target: int | str | None = anchor or canvas_checkpoint.get("canvas_id")
            if canvas_target is None:
                canvas_target = canvas_checkpoint.get("id") or canvas_checkpoint.get("name")
            if canvas_target is not None:
                lines.extend([canvas_submission(canvas_target, show_form=False), ""])

        disclosure = submission_cfg.get("ai_disclosure")
        if disclosure:
            lines.append('!!! info "AI-use disclosure"')
            lines.extend(
                f"    {disclosure_line}" if disclosure_line else ""
                for disclosure_line in str(disclosure).splitlines()
            )

        return "\n".join(lines).rstrip()
