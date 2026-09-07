"""Regression coverage for preview connections held by idle tabs."""

from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.client import HTTPConnection
from pathlib import Path

from mkdocs.livereload import LiveReloadServer

from coursemd.integrations.mkdocs.plugin import CoursemdPlugin


def test_idle_preview_polls_release_connections_without_requesting_reload(tmp_path: Path) -> None:
    server = LiveReloadServer(lambda: None, "127.0.0.1", 0, str(tmp_path))
    CoursemdPlugin().on_serve(server)
    server.server_bind()
    server.server_activate()
    server.serve_thread.start()
    epoch = server._visible_epoch

    def poll(request_id: int) -> bytes:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        try:
            connection.request("GET", f"/livereload/{epoch}/{request_id}")
            response = connection.getresponse()
            assert response.status == HTTPStatus.OK
            return response.read()
        finally:
            connection.close()

    try:
        # Browsers can have six connections tied up by visible preview tabs.
        # All idle polls must finish promptly without falsely signalling a new build.
        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(poll, range(6)))
        assert results == [str(epoch).encode()] * 6
    finally:
        server.shutdown()
        server.serve_thread.join(timeout=3)
