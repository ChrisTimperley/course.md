"""MkDocs plugin to hide draft content and enforce release dates."""

import datetime as dt
import typing as t

import frontmatter
from mkdocs.plugins import BasePlugin
from mkdocs.structure.files import Files as MkDocsFiles
from mkdocs.structure.nav import Navigation as MkDocsNavigation

from coursemd.core.loaders.dates import parse_date as _parse_date
from coursemd.core.utils import current_date


class DraftsPlugin(BasePlugin):
    """
    MkDocs plugin that filters out draft content and unreleased materials.

    Files are hidden if:
    - They have `draft: true` in their frontmatter
    - They have a `release_date` in the future

    In preview mode (mkdocs serve), all content is shown.
    In production mode (mkdocs build), drafts and unreleased content are hidden.
    """

    current_date: dt.date
    in_preview: bool
    removed_files: set[str]

    def on_startup(self, command: str, *args: t.Any, **kwargs: t.Any) -> None:  # noqa: ARG002
        """Initialize plugin state when MkDocs starts."""
        self.in_preview = command == "serve"
        self.removed_files = set()
        self.current_date = current_date()

    @property
    def in_production(self) -> bool:
        """Check if we're in production mode (not preview)."""
        return not self.in_preview

    def should_remove_file(self, file: t.Any, metadata: dict[str, t.Any]) -> bool:  # noqa: ARG002
        """
        Determine if a file should be removed from the build.

        Args:
            file: The MkDocs file object
            metadata: Parsed frontmatter metadata

        Returns:
            True if the file should be removed, False otherwise
        """
        if metadata.get("draft"):
            return True

        # Prefer reveal date over release date for determining visibility
        check_date = _parse_date(metadata.get("reveal_date") or metadata.get("release_date"))
        return bool(check_date and check_date > self.current_date)

    def on_files(self, files: MkDocsFiles, *args: t.Any, **kwargs: t.Any) -> MkDocsFiles:  # noqa: ARG002
        """
        Filter files based on draft status and release dates.

        Called by MkDocs during the build process.
        """
        if self.in_production:
            for file in files.documentation_pages():
                metadata = frontmatter.load(file.abs_src_path)
                if self.should_remove_file(file, metadata):
                    print(f"Removing file: {file.src_path}")
                    self.removed_files.add(file.src_path)
                    files.remove(file)

        return files

    def on_nav(self, nav: MkDocsNavigation, *args: t.Any, **kwargs: t.Any) -> MkDocsNavigation:  # noqa: ARG002
        """
        Filter navigation items that point to removed files.

        Called by MkDocs after files are processed.
        """
        if self.in_production and self.removed_files:
            nav.items = list(self._filter_nav_items(nav.items))
        return nav

    def _filter_nav_items(self, items: t.Iterable[t.Any]) -> t.Iterator[t.Any]:
        """
        Recursively filter navigation items.

        Args:
            items: Navigation items to filter

        Yields:
            Navigation items that should be kept
        """
        for item in items:
            # Skip items that should be removed
            if hasattr(item, "url") and item.url in self.removed_files:
                continue

            # If item has children, filter them recursively
            if hasattr(item, "children") and item.children:
                filtered_children = list(self._filter_nav_items(item.children))
                if filtered_children:
                    item.children = filtered_children
                    yield item
            # Leaf item
            else:
                yield item
