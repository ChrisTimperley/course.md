from __future__ import annotations

import os
import subprocess
from pathlib import Path
from textwrap import dedent

from mkdocs.commands.build import build as mkdocs_build
from mkdocs.config import load_config
from typer.testing import CliRunner

import coursemd.cli.site
import coursemd.cli.slides
import coursemd.github.client
import coursemd.github.setup
from coursemd import cli
from coursemd.core.config import load_coursemd_config
from coursemd.core.loaders.dates import normalize_release_date

runner = CliRunner()


def _write_file(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(contents), encoding="utf-8")


def _build_repo_fixture(repo_root: Path) -> None:
    _write_file(
        repo_root / ".coursemd.yml",
        """
        site:
          backend: mkdocs
          base_url: https://example.edu/course
          project_dir: website
        github:
          organization: example-course-org
          instructors_team_slug: instructors
        canvas:
          base_url: https://canvas.example.edu
          course_id: 12345
        paths:
          data_dir: data
          assignments_dir: assignments
          quizzes_dir: quizzes
        """,
    )
    _write_file(
        repo_root / "data" / "schedule.yaml",
        """
        course:
          start_date: 2026-01-12
          end_date: 2026-01-16
          title: Test Course
          canvas_course_id: 12345
        events:
          - kind: lecture
            date: 2026-01-12
            title: Course Introduction
        """,
    )
    _write_file(
        repo_root / "assignments" / "hw1.md",
        """
        ---
        title: Homework 1
        kind: homework
        release_date: 2026-01-12
        due_date: 2026-01-16
        assignments:
          - name: Homework 1
            due_at: "2026-01-16T23:59:00-05:00"
            points: 100
        ---

        # Homework 1
        """,
    )
    _write_file(
        repo_root / "quizzes" / "week1.md",
        """
        ---
        title: Week 1 Reading Quiz
        type: reading
        release_date: 2026-01-12
        due_at: "2026-01-16T23:59:00-05:00"
        questions:
          - question_type: multiple_choice
            question_text: What is quality?
            answers:
              - text: Fitness for purpose
                correct: true
              - text: Just test coverage
                correct: false
        ---

        # Quiz
        """,
    )
    _write_file(
        repo_root / "website" / "mkdocs.yml",
        """
        site_name: Test Course
        plugins:
          - coursemd:
              config_file: ../.coursemd.yml
        markdown_extensions:
          - tables
        nav:
          - Home: index.md
        """,
    )
    _write_file(
        repo_root / "website" / "docs" / "index.md",
        """
        # Home

        {{ schedule_table(schedule) }}
        """,
    )
    _write_file(
        repo_root / "slides" / "_quarto.yml",
        """
        project:
          type: website
        """,
    )
    _write_file(
        repo_root / "slides" / "index.qmd",
        """
        # Slides
        """,
    )


def test_validate_uses_repository_defaults(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    nested_dir = tmp_path / "website" / "docs"
    nested_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(nested_dir)

    result = runner.invoke(cli.app, ["validate"])

    assert result.exit_code == 0
    assert "Validated 1 data file(s), 1 assignment spec(s), and 1 quiz spec(s)." in result.stdout
    assert "Validation passed." in result.stdout


def test_validate_discovers_assignment_files_without_hw_prefix(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    (tmp_path / "assignments" / "hw1.md").unlink()
    _write_file(
        tmp_path / "assignments" / "phase-a.md",
        """
        ---
        title: Phase A
        kind: homework
        release_date: 2026-01-12
        due_date: 2026-01-16
        assignments:
          - name: Phase A
            due_at: "2026-01-16T23:59:00-05:00"
            points: 100
        ---

        # Phase A
        """,
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli.app, ["validate"])

    assert result.exit_code == 0
    assert "Validated 1 data file(s), 1 assignment spec(s), and 1 quiz spec(s)." in result.stdout


def test_validate_allows_multiple_schedule_events_on_same_date(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    _write_file(
        tmp_path / "data" / "schedule.yaml",
        "\n".join(
            [
                "course:",
                "  start_date: 2026-01-12",
                "  end_date: 2026-01-16",
                "  title: Test Course",
                "  canvas_course_id: 12345",
                "events:",
                "  - kind: lecture",
                "    date: 2026-01-12",
                "    title: Course Introduction",
                "  - kind: workshop",
                "    date: 2026-01-12",
                "    title: Duplicate Slot",
                "",
            ]
        ),
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli.app, ["validate"])

    assert result.exit_code == 0
    assert "Validation passed." in result.stdout


def test_validate_fails_for_assignment_missing_release_date(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    _write_file(
        tmp_path / "assignments" / "hw1.md",
        """\
---
title: Homework 1
kind: homework
due_date: 2026-01-16
assignments:
  - name: Homework 1
    due_at: "2026-01-16T23:59:00-05:00"
    points: 100
---

# Homework 1
""",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli.app, ["validate"])

    assert result.exit_code == 1
    assert "'release_date' must be a valid date or ISO-8601 timestamp" in result.output


def test_validate_fails_for_assignment_checkpoint_outside_assignment_window(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _build_repo_fixture(tmp_path)
    _write_file(
        tmp_path / "assignments" / "hw1.md",
        """\
---
title: Homework 1
kind: homework
release_date: 2026-01-12
due_date: 2026-01-16
checkpoints:
  - date: 2026-01-20
    title: Late checkpoint
assignments:
  - name: Homework 1
    due_at: "2026-01-16T23:59:00-05:00"
    points: 100
---

# Homework 1
""",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli.app, ["validate"])

    assert result.exit_code == 1
    assert "checkpoints[0].date must fall between 'release_date' and 'due_date'" in result.output


def test_validate_fails_for_quiz_missing_release_date(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    _write_file(
        tmp_path / "quizzes" / "week1.md",
        "\n".join(
            [
                "---",
                "title: Week 1 Reading Quiz",
                "type: reading",
                'due_at: "2026-01-16T23:59:00-05:00"',
                "questions:",
                "  - question_type: multiple_choice",
                "    question_text: What is quality?",
                "    answers:",
                "      - text: Fitness for purpose",
                "        correct: true",
                "      - text: Just test coverage",
                "        correct: false",
                "---",
                "",
                "# Quiz",
                "",
            ]
        ),
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli.app, ["validate"])

    assert result.exit_code == 1
    assert "'release_date' must be a valid date or ISO-8601 timestamp" in result.output


def test_init_writes_starter_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli.app, ["init"])

    assert result.exit_code == 0
    assert "Wrote starter config" in result.stdout
    assert (tmp_path / ".coursemd.yml").exists()


def test_init_refuses_to_overwrite_existing_config(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli.app, ["init"])

    assert result.exit_code == 1
    assert "already exists" in result.output


def test_legacy_assignment_wrapper_routes_through_typer_cli(tmp_path: Path, capsys) -> None:
    _build_repo_fixture(tmp_path)

    exit_code = cli.main_sync_canvas_assignments(["--plan-only"], repo_root=tmp_path)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Loaded 1 assignment spec(s) for the Canvas integration:" in captured.out
    assert "Homework 1" in captured.out


def test_sync_command_discovers_config_in_parent_directory(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    nested_dir = tmp_path / "website" / "docs"
    nested_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(nested_dir)

    result = runner.invoke(
        cli.app,
        [
            "canvas",
            "assignments",
            "--plan-only",
            "assignments/hw1.md",
        ],
    )

    assert result.exit_code == 0
    assert "Loaded 1 assignment spec(s) for the Canvas integration:" in result.stdout


def test_github_setup_uses_repository_defaults_in_dry_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _build_repo_fixture(tmp_path)
    local_runner = CliRunner()
    commands: list[tuple[list[str], str | None]] = []

    def fake_run_command(
        args: list[str] | tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        argv = list(args)
        commands.append((argv, input_text))
        if argv == ["gh", "auth", "status"]:
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[-1] == "/orgs/example-course-org/teams/instructors":
            return subprocess.CompletedProcess(argv, 0, '{"id": 42}', "")
        if argv[-1] == "/orgs/example-course-org":
            return subprocess.CompletedProcess(
                argv,
                0,
                '{"default_repository_permission": "read"}',
                "",
            )
        raise AssertionError(f"Unexpected command: {argv}")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(coursemd.github.setup, "_run_command", fake_run_command)
    monkeypatch.setattr(
        coursemd.github.client.shutil,
        "which",
        lambda program: "/usr/bin/gh",
    )

    result = local_runner.invoke(cli.app, ["github", "setup", "--dry-run"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert "Resolved team 'instructors' in org 'example-course-org' (ID: 42)." in result.stdout
    assert "Default repository permission: 'read' -> 'none'" in result.stdout
    assert "Dry run: would update organization default repository permission." in result.stdout
    assert "Dry run: would configure ruleset 'Protect main branch'" in result.stdout
    assert not any("--method" in command and "PATCH" in command for command, _ in commands)
    assert not any("--input" in command for command, _ in commands)


def test_validate_fails_without_coursemd_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli.app, ["validate"])

    assert result.exit_code == 1
    assert "Could not find .coursemd.yml" in result.output


def test_optional_site_commands_report_missing_mkdocs_dependency(monkeypatch) -> None:
    local_app = coursemd.cli.typer.Typer(no_args_is_help=True)

    def fake_loader(module_name: str, function_name: str) -> object:
        raise ModuleNotFoundError("No module named 'mkdocs'", name="mkdocs")

    monkeypatch.setattr(coursemd.cli, "_load_register_function", fake_loader)

    coursemd.cli._register_optional_group_commands(
        local_app,
        loaders=[("coursemd.cli.site", "register_site_commands")],
        fallback_commands=["coursemd site build", "coursemd site preview"],
        optional_modules={"mkdocs"},
        extra_name="mkdocs",
    )

    result = runner.invoke(local_app, ["preview"])

    assert result.exit_code == 1
    assert "coursemd[mkdocs]" in result.output


def test_optional_canvas_commands_report_missing_canvas_dependency(monkeypatch) -> None:
    local_app = coursemd.cli.typer.Typer(no_args_is_help=True)

    def fake_loader(module_name: str, function_name: str) -> object:
        raise ModuleNotFoundError("No module named 'requests'", name="requests")

    monkeypatch.setattr(coursemd.cli, "_load_register_function", fake_loader)

    coursemd.cli._register_optional_group_commands(
        local_app,
        loaders=[
            ("coursemd.cli.sync_canvas_assignments", "register_sync_canvas_assignments_command"),
            ("coursemd.cli.sync_canvas_quizzes", "register_sync_canvas_quizzes_command"),
        ],
        fallback_commands=["coursemd canvas assignments", "coursemd canvas quizzes"],
        optional_modules={"requests"},
        extra_name="canvas",
    )

    result = runner.invoke(local_app, ["assignments"])

    assert result.exit_code == 1
    assert "coursemd[canvas]" in result.output


def test_init_writes_root_level_content_paths_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli.app, ["init"])

    assert result.exit_code == 0
    config_text = (tmp_path / ".coursemd.yml").read_text(encoding="utf-8")
    assert "backend: mkdocs" in config_text
    assert "project_dir: website" in config_text
    assert "assignments_url_path: assignments" in config_text
    assert "slides:" in config_text
    assert "dir: slides" in config_text
    assert "data_dir: data" in config_text
    assert "assignments_dir: assignments" in config_text
    assert "quizzes_dir: quizzes" in config_text
    assert "timezone: America/New_York" in config_text
    assert "canvas:" not in config_text


def test_init_can_include_canvas_settings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        cli.app,
        [
            "init",
            "--include-canvas",
            "--canvas-base-url",
            "https://canvas.example.edu",
            "--canvas-course-id",
            "12345",
        ],
    )

    assert result.exit_code == 0
    config_text = (tmp_path / ".coursemd.yml").read_text(encoding="utf-8")
    assert "canvas:" in config_text
    assert "base_url: https://canvas.example.edu" in config_text
    assert "course_id: '12345'" in config_text


def test_init_rejects_invalid_timezone(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli.app, ["init", "--timezone", "Not/A_Timezone"])

    assert result.exit_code == 1
    assert "timezone must be a valid IANA timezone" in result.output
    assert not (tmp_path / ".coursemd.yml").exists()


def test_config_defaults_site_backend_to_mkdocs(tmp_path: Path) -> None:
    _build_repo_fixture(tmp_path)
    config_path = tmp_path / ".coursemd.yml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace("  backend: mkdocs\n", ""),
        encoding="utf-8",
    )

    config = load_coursemd_config(start_dir=tmp_path / "website")

    assert config.site_backend == "mkdocs"


def test_config_reads_explicit_site_backend(tmp_path: Path) -> None:
    _build_repo_fixture(tmp_path)

    config = load_coursemd_config(start_dir=tmp_path / "website")

    assert config.site_backend == "mkdocs"


def test_config_reads_course_timezone(tmp_path: Path) -> None:
    _build_repo_fixture(tmp_path)
    config_path = tmp_path / ".coursemd.yml"
    config_path.write_text(
        "timezone: America/Los_Angeles\n" + config_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    config = load_coursemd_config(start_dir=tmp_path / "website")

    assert config.timezone == "America/Los_Angeles"


def test_config_rejects_invalid_timezone(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    config_path = tmp_path / ".coursemd.yml"
    config_path.write_text(
        "timezone: Not/A_Timezone\n" + config_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli.app, ["validate"])

    assert result.exit_code == 1
    assert "timezone must be a valid IANA timezone" in result.output


def test_release_date_normalization_uses_configured_timezone_dst(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _build_repo_fixture(tmp_path)
    config_path = tmp_path / ".coursemd.yml"
    config_path.write_text(
        "timezone: America/New_York\n" + config_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli.app, ["validate"])

    assert result.exit_code == 0
    assert normalize_release_date("2026-01-12", tmp_path / "jan.md") == "2026-01-12T00:00:00-05:00"
    assert normalize_release_date("2026-07-01", tmp_path / "jul.md") == "2026-07-01T00:00:00-04:00"


def test_config_allows_repositories_without_canvas(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    config_path = tmp_path / ".coursemd.yml"
    config_path.write_text(
        """
        site:
          backend: mkdocs
          base_url: https://example.edu/course
          project_dir: website
        paths:
          data_dir: data
          assignments_dir: assignments
          quizzes_dir: quizzes
        """,
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    config = load_coursemd_config(start_dir=tmp_path)
    result = runner.invoke(cli.app, ["validate"])

    assert config.canvas is None
    assert result.exit_code == 0
    assert "Validation passed." in result.stdout


def test_repository_load_allows_non_canvas_content(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    _write_file(
        tmp_path / ".coursemd.yml",
        """
        site:
          backend: mkdocs
          base_url: https://example.edu/course
          project_dir: website
        paths:
          data_dir: data
          assignments_dir: assignments
          quizzes_dir: quizzes
        """,
    )
    _write_file(
        tmp_path / "assignments" / "hw1.md",
        """
        ---
        title: Homework 1
        kind: homework
        release_date: 2026-01-12
        due_date: 2026-01-16
        ---

        # Homework 1
        """,
    )
    _write_file(
        tmp_path / "quizzes" / "week1.md",
        """
        ---
        title: Week 1 Reading Quiz
        release_date: 2026-01-12
        due_at: "2026-01-16T23:59:00-05:00"
        link: https://example.edu/quiz
        ---

        # Quiz
        """,
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli.app, ["validate"])

    assert result.exit_code == 0
    assert "Validated 1 data file(s), 0 assignment spec(s), and 0 quiz spec(s)." in result.stdout
    assert "Validation passed." in result.stdout


def test_config_reads_site_url_paths(tmp_path: Path) -> None:
    _build_repo_fixture(tmp_path)
    config_path = tmp_path / ".coursemd.yml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "  project_dir: website\n",
            "  project_dir: website\n  assignments_url_path: coursework\n",
        ),
        encoding="utf-8",
    )

    config = load_coursemd_config(start_dir=tmp_path / "website")

    assert config.site_assignments_url_path == "coursework"


def test_site_build_uses_project_dir_from_config(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    recorded: dict[str, object] = {}

    class FakePlugins:
        def on_startup(self, *, command: str, dirty: bool) -> None:
            recorded["startup"] = {"command": command, "dirty": dirty}

        def on_shutdown(self) -> None:
            recorded["shutdown"] = True

    class FakeConfig:
        def __init__(self) -> None:
            self.plugins = FakePlugins()

    def fake_load_config(
        *,
        config_file: str,
        site_dir: str | None = None,
        strict: bool,
    ) -> FakeConfig:
        recorded["load_config"] = {
            "config_file": config_file,
            "site_dir": site_dir,
            "strict": strict,
            "cwd": str(Path.cwd()),
        }
        return FakeConfig()

    def fake_build(config: FakeConfig, *, dirty: bool, serve_url: str | None = None) -> None:
        recorded["build"] = {
            "dirty": dirty,
            "serve_url": serve_url,
            "cwd": str(Path.cwd()),
            "config": config,
        }

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(coursemd.cli.site, "load_config", fake_load_config)
    monkeypatch.setattr(coursemd.cli.site, "mkdocs_build", fake_build)

    result = runner.invoke(cli.app, ["site", "build", "--output-dir", "build/website", "--strict"])

    assert result.exit_code == 0
    assert recorded["load_config"] == {
        "config_file": str(tmp_path / "website" / "mkdocs.yml"),
        "site_dir": str((tmp_path / "build" / "website").resolve()),
        "strict": True,
        "cwd": str(tmp_path / "website"),
    }
    assert recorded["startup"] == {"command": "build", "dirty": False}
    assert recorded["build"] == {
        "dirty": False,
        "serve_url": None,
        "cwd": str(tmp_path / "website"),
        "config": recorded["build"]["config"],
    }
    assert recorded["shutdown"] is True


def test_site_preview_sets_current_date_override(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    recorded: dict[str, object] = {}

    def fake_serve(
        *,
        config_file: str | None = None,
        livereload: bool = True,
        build_type: str | None = None,
        watch_theme: bool = False,
        watch: list[str] = [],
        open_in_browser: bool = False,
        **kwargs: object,
    ) -> None:
        recorded["serve"] = {
            "config_file": config_file,
            "livereload": livereload,
            "build_type": build_type,
            "watch_theme": watch_theme,
            "watch": watch,
            "open_in_browser": open_in_browser,
            "kwargs": kwargs,
            "cwd": str(Path.cwd()),
            "current_date_override": os.environ.get("CURRENT_DATE_OVERRIDE"),
            "coursemd_preview": os.environ.get("COURSEMD_PREVIEW"),
        }

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(coursemd.cli.site, "mkdocs_serve", fake_serve)

    result = runner.invoke(cli.app, ["site", "preview", "--dev-addr", "127.0.0.1:9000", "--dirty"])

    assert result.exit_code == 0
    assert "Previewing site at http://127.0.0.1:9000/" in result.stdout
    assert recorded["serve"] == {
        "config_file": str(tmp_path / "website" / "mkdocs.yml"),
        "livereload": True,
        "build_type": "dirty",
        "watch_theme": False,
        "watch": [],
        "open_in_browser": False,
        "kwargs": {"dev_addr": "127.0.0.1:9000"},
        "cwd": str(tmp_path / "website"),
        "current_date_override": "2999-12-12",
        "coursemd_preview": "1",
    }


def test_site_build_preview_sets_coursemd_preview_mode(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    recorded: dict[str, object] = {}

    class SearchPlugin:
        def on_startup(self, *, command: str, dirty: bool) -> None:
            recorded["startup"] = {"command": command, "dirty": dirty}

        def on_shutdown(self) -> None:
            recorded["shutdown"] = True

    class FakeConfig:
        def __init__(self) -> None:
            plugins = coursemd.cli.site.PluginCollection()
            plugins["search"] = SearchPlugin()
            self.plugins = plugins

    def fake_load_config(
        *,
        config_file: str,
        site_dir: str | None = None,
        strict: bool,
    ) -> FakeConfig:
        recorded["load_config"] = {
            "config_file": config_file,
            "site_dir": site_dir,
            "strict": strict,
            "cwd": str(Path.cwd()),
            "current_date_override": os.environ.get("CURRENT_DATE_OVERRIDE"),
            "coursemd_preview": os.environ.get("COURSEMD_PREVIEW"),
        }
        return FakeConfig()

    def fake_build(config: FakeConfig, *, dirty: bool, serve_url: str | None = None) -> None:
        recorded["build"] = {
            "dirty": dirty,
            "serve_url": serve_url,
            "cwd": str(Path.cwd()),
            "current_date_override": os.environ.get("CURRENT_DATE_OVERRIDE"),
            "coursemd_preview": os.environ.get("COURSEMD_PREVIEW"),
            "plugins": tuple(config.plugins.keys()),
        }

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(coursemd.cli.site, "load_config", fake_load_config)
    monkeypatch.setattr(coursemd.cli.site, "mkdocs_build", fake_build)

    result = runner.invoke(
        cli.app,
        ["site", "build-preview", "--output-dir", "build/website/_preview/test"],
    )

    assert result.exit_code == 0
    assert recorded["load_config"] == {
        "config_file": str(tmp_path / "website" / "mkdocs.yml"),
        "site_dir": str((tmp_path / "build" / "website" / "_preview" / "test").resolve()),
        "strict": False,
        "cwd": str(tmp_path / "website"),
        "current_date_override": "2999-12-12",
        "coursemd_preview": "1",
    }
    assert recorded["startup"] == {"command": "build", "dirty": False}
    assert recorded["build"] == {
        "dirty": False,
        "serve_url": None,
        "cwd": str(tmp_path / "website"),
        "current_date_override": "2999-12-12",
        "coursemd_preview": "1",
        "plugins": ("search",),
    }
    assert recorded["shutdown"] is True


def test_slides_build_uses_default_output_dir(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    recorded: dict[str, object] = {}

    def fake_run(args: list[str], *, cwd: Path, check: bool) -> subprocess.CompletedProcess[str]:
        recorded["run"] = {
            "args": args,
            "cwd": str(cwd),
            "check": check,
        }
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(coursemd.cli.slides.subprocess, "run", fake_run)

    result = runner.invoke(cli.app, ["slides", "build"])

    assert result.exit_code == 0
    assert recorded["run"] == {
        "args": [
            "quarto",
            "render",
            ".",
            "--output-dir",
            str((tmp_path / "build" / "slides" / "html").resolve()),
        ],
        "cwd": str(tmp_path / "slides"),
        "check": False,
    }


def test_slides_preview_uses_configured_directory(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    _write_file(
        tmp_path / ".coursemd.yml",
        """
        site:
          backend: mkdocs
          base_url: https://example.edu/course
          project_dir: website
        slides:
                    dir: lecture-slides
        canvas:
          base_url: https://canvas.example.edu
          course_id: 12345
        paths:
          data_dir: data
          assignments_dir: assignments
          quizzes_dir: quizzes
        """,
    )
    _write_file(
        tmp_path / "lecture-slides" / "_quarto.yml",
        """
        project:
          type: website
        """,
    )
    recorded: dict[str, object] = {}

    def fake_run(args: list[str], *, cwd: Path, check: bool) -> subprocess.CompletedProcess[str]:
        recorded["run"] = {
            "args": args,
            "cwd": str(cwd),
            "check": check,
        }
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(coursemd.cli.slides.subprocess, "run", fake_run)

    result = runner.invoke(cli.app, ["slides", "preview", "--output-dir", "build/slides/preview"])

    assert result.exit_code == 0
    assert recorded["run"] == {
        "args": [
            "quarto",
            "preview",
            ".",
            "--output-dir",
            str((tmp_path / "build" / "slides" / "preview").resolve()),
        ],
        "cwd": str(tmp_path / "lecture-slides"),
        "check": False,
    }


def test_slides_preview_accepts_legacy_project_dir_key(tmp_path: Path, monkeypatch) -> None:
    _build_repo_fixture(tmp_path)
    _write_file(
        tmp_path / ".coursemd.yml",
        """
        site:
          backend: mkdocs
          base_url: https://example.edu/course
          project_dir: website
        slides:
          project_dir: legacy-slides
        canvas:
          base_url: https://canvas.example.edu
          course_id: 12345
        paths:
          data_dir: data
          assignments_dir: assignments
          quizzes_dir: quizzes
        """,
    )
    _write_file(
        tmp_path / "legacy-slides" / "_quarto.yml",
        """
        project:
          type: website
        """,
    )
    recorded: dict[str, object] = {}

    def fake_run(args: list[str], *, cwd: Path, check: bool) -> subprocess.CompletedProcess[str]:
        recorded["run"] = {
            "args": args,
            "cwd": str(cwd),
            "check": check,
        }
        return subprocess.CompletedProcess(args=args, returncode=0)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(coursemd.cli.slides.subprocess, "run", fake_run)

    result = runner.invoke(cli.app, ["slides", "build"])

    assert result.exit_code == 0
    assert recorded["run"] == {
        "args": [
            "quarto",
            "render",
            ".",
            "--output-dir",
            str((tmp_path / "build" / "slides" / "html").resolve()),
        ],
        "cwd": str(tmp_path / "legacy-slides"),
        "check": False,
    }


def test_coursemd_mkdocs_plugin_builds_without_symlinked_content(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _build_repo_fixture(tmp_path)
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-01-13")
    monkeypatch.chdir(tmp_path / "website")

    config = load_config(config_file="mkdocs.yml", site_dir=str(tmp_path / "site"))
    config.plugins.on_startup(command="build", dirty=False)
    try:
        mkdocs_build(config, dirty=False)
    finally:
        config.plugins.on_shutdown()

    assert (tmp_path / "site" / "assignments" / "hw1" / "index.html").is_file()
    assert not (tmp_path / "site" / "quizzes" / "week1" / "index.html").exists()
    index_html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "Homework 1" in index_html
    assert "Week 1 Reading Quiz" in index_html
    assert "quizzes/week1" not in index_html


def test_coursemd_mkdocs_plugin_builds_non_canvas_course(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _build_repo_fixture(tmp_path)
    _write_file(
        tmp_path / ".coursemd.yml",
        """
        site:
          backend: mkdocs
          base_url: https://example.edu/course
          project_dir: website
        paths:
          data_dir: data
          assignments_dir: assignments
          quizzes_dir: quizzes
        """,
    )
    _write_file(
        tmp_path / "data" / "schedule.yaml",
        """
        course:
          start_date: 2026-01-12
          end_date: 2026-01-16
          title: Test Course
        events:
          - kind: lecture
            date: 2026-01-12
            title: Course Introduction
        """,
    )
    _write_file(
        tmp_path / "assignments" / "hw1.md",
        """
        ---
        title: Homework 1
        kind: homework
        release_date: 2026-01-12
        due_date: 2026-01-16
        ---

        # Homework 1
        """,
    )
    _write_file(
        tmp_path / "quizzes" / "week1.md",
        """
        ---
        title: Week 1 Reading Quiz
        release_date: 2026-01-12
        due_at: "2026-01-16T23:59:00-05:00"
        link: https://example.edu/quiz
        ---

        # Quiz
        """,
    )
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-01-13")
    monkeypatch.chdir(tmp_path / "website")

    config = load_config(config_file="mkdocs.yml", site_dir=str(tmp_path / "site"))
    config.plugins.on_startup(command="build", dirty=False)
    try:
        mkdocs_build(config, dirty=False)
    finally:
        config.plugins.on_shutdown()

    assert (tmp_path / "site" / "assignments" / "hw1" / "index.html").is_file()
    index_html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "Homework 1" in index_html
    assert "Week 1 Reading Quiz" in index_html
    assert "https://example.edu/quiz" in index_html


def test_coursemd_mkdocs_plugin_does_not_generate_quiz_nav(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _build_repo_fixture(tmp_path)
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-01-13")
    monkeypatch.chdir(tmp_path / "website")

    config = load_config(config_file="mkdocs.yml", site_dir=str(tmp_path / "site"))
    config.plugins.on_startup(command="build", dirty=False)
    try:
        mkdocs_build(config, dirty=False)
    finally:
        config.plugins.on_shutdown()

    index_html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "Assignments" in index_html
    assert "Homework 1" in index_html
    assert ">Quizzes<" not in index_html
    assert "quizzes/week1" not in index_html


def test_coursemd_mkdocs_plugin_filters_future_generated_pages(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _build_repo_fixture(tmp_path)
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-01-01")
    monkeypatch.chdir(tmp_path / "website")

    config = load_config(config_file="mkdocs.yml", site_dir=str(tmp_path / "site"))
    config.plugins.on_startup(command="build", dirty=False)
    try:
        mkdocs_build(config, dirty=False)
    finally:
        config.plugins.on_shutdown()

    assert not (tmp_path / "site" / "assignments" / "hw1" / "index.html").exists()


def test_coursemd_mkdocs_plugin_renders_injected_assignment_includes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _build_repo_fixture(tmp_path)
    _write_file(
        tmp_path / "website" / "docs" / "partials" / "note.md",
        """
        Included {{ page.meta.title }}
        """,
    )
    _write_file(
        tmp_path / "assignments" / "hw1.md",
        """
        ---
        title: Homework 1
        kind: homework
        release_date: 2026-01-12
        due_date: 2026-01-16
        assignments:
          - name: Homework 1
            due_at: "2026-01-16T23:59:00-05:00"
            points: 100
        ---

        # Homework 1

        {% include "partials/note.md" %}
        """,
    )
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-01-13")
    monkeypatch.chdir(tmp_path / "website")

    config = load_config(config_file="mkdocs.yml", site_dir=str(tmp_path / "site"))
    config.plugins.on_startup(command="build", dirty=False)
    try:
        mkdocs_build(config, dirty=False)
    finally:
        config.plugins.on_shutdown()

    html = (tmp_path / "site" / "assignments" / "hw1" / "index.html").read_text(encoding="utf-8")
    assert "Included Homework 1" in html


def test_coursemd_mkdocs_plugin_uses_configured_urls(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _build_repo_fixture(tmp_path)
    config_path = tmp_path / ".coursemd.yml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "  project_dir: website\n",
            "  project_dir: website\n  assignments_url_path: coursework\n",
        ),
        encoding="utf-8",
    )
    _write_file(
        tmp_path / "assignments" / "hw1.md",
        "\n".join(
            [
                "---",
                "title: Homework 1",
                "kind: homework",
                "release_date: 2026-01-12",
                "due_date: 2026-01-16",
                "assignments:",
                "  - name: Homework 1",
                '    due_at: "2026-01-16T23:59:00-05:00"',
                "    points: 100",
                "    integrations:",
                "      canvas:",
                "        id: 456",
                "---",
                "",
                "# Homework 1",
                "",
                "{{ canvas_submission(456) }}",
                "",
            ]
        ),
    )
    _write_file(
        tmp_path / "quizzes" / "week1.md",
        "\n".join(
            [
                "---",
                "title: Week 1 Reading Quiz",
                "type: reading",
                "release_date: 2026-01-12",
                'due_at: "2026-01-16T23:59:00-05:00"',
                "integrations:",
                "  canvas:",
                "    id: 987",
                "questions:",
                "  - question_type: multiple_choice",
                "    question_text: What is quality?",
                "    answers:",
                "      - text: Fitness for purpose",
                "        correct: true",
                "      - text: Just test coverage",
                "        correct: false",
                "---",
                "",
                "# Quiz",
                "",
            ]
        ),
    )
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-01-13")
    monkeypatch.chdir(tmp_path / "website")

    config = load_config(config_file="mkdocs.yml", site_dir=str(tmp_path / "site"))
    config.plugins.on_startup(command="build", dirty=False)
    try:
        mkdocs_build(config, dirty=False)
    finally:
        config.plugins.on_shutdown()

    assert (tmp_path / "site" / "coursework" / "hw1" / "index.html").is_file()
    assignment_html = (tmp_path / "site" / "coursework" / "hw1" / "index.html").read_text(
        encoding="utf-8"
    )
    index_html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "https://canvas.example.edu/courses/12345/assignments/456" in assignment_html
    assert "https://canvas.example.edu/courses/12345/quizzes/987" in index_html
    assert "/coursework/hw1/" in index_html


def test_coursemd_macros_do_not_discover_quizzes_from_docs_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _build_repo_fixture(tmp_path)
    _write_file(
        tmp_path / "website" / "docs" / "quizzes" / "week99.md",
        """
        ---
        title: Public Quiz Leak
        type: reading
        release_date: 2026-01-12
        due_at: "2026-01-16T23:59:00-05:00"
        questions:
          - question_type: multiple_choice
            question_text: Should this be public?
            answers:
              - text: No
                correct: true
              - text: Yes
                correct: false
        ---

        # Public Quiz Leak
        """,
    )
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-01-13")
    monkeypatch.chdir(tmp_path / "website")

    config = load_config(config_file="mkdocs.yml", site_dir=str(tmp_path / "site"))
    config.plugins.on_startup(command="build", dirty=False)
    try:
        mkdocs_build(config, dirty=False)
    finally:
        config.plugins.on_shutdown()

    index_html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "Public Quiz Leak" not in index_html


def test_coursemd_mkdocs_plugin_uses_preloaded_quiz_schedule_data(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _build_repo_fixture(tmp_path)
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-01-13")
    monkeypatch.chdir(tmp_path / "website")

    config = load_config(config_file="mkdocs.yml", site_dir=str(tmp_path / "site"))
    plugin = config.plugins["coursemd"]
    plugin.on_config(config)
    (tmp_path / "quizzes" / "week1.md").unlink()
    registry = plugin._macro_registry(config=config, page=None)

    rendered = registry.macros["schedule_table"](plugin.course_data["schedule"])

    assert "Week 1 Reading Quiz" in rendered


def test_coursemd_mkdocs_plugin_loads_all_yaml_data_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _build_repo_fixture(tmp_path)
    _write_file(
        tmp_path / "data" / "resources.yaml",
        """
        message: Extra data works
        """,
    )
    _write_file(
        tmp_path / "website" / "docs" / "index.md",
        """
        # Home

        {{ resources.message }}
        """,
    )
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-01-13")
    monkeypatch.chdir(tmp_path / "website")

    config = load_config(config_file="mkdocs.yml", site_dir=str(tmp_path / "site"))
    config.plugins.on_startup(command="build", dirty=False)
    try:
        mkdocs_build(config, dirty=False)
    finally:
        config.plugins.on_shutdown()

    index_html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "Extra data works" in index_html


def test_grade_boundaries_table_without_grading_data_returns_empty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _build_repo_fixture(tmp_path)
    _write_file(
        tmp_path / "website" / "docs" / "index.md",
        """
        # Home

        before
        {{ grade_boundaries_table() }}
        after
        """,
    )
    monkeypatch.setenv("CURRENT_DATE_OVERRIDE", "2026-01-13")
    monkeypatch.chdir(tmp_path / "website")

    config = load_config(config_file="mkdocs.yml", site_dir=str(tmp_path / "site"))
    config.plugins.on_startup(command="build", dirty=False)
    try:
        mkdocs_build(config, dirty=False)
    finally:
        config.plugins.on_shutdown()

    index_html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "before" in index_html
    assert "after" in index_html
