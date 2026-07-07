"""Tests for HWPParserRemoteComponent HTTP plumbing.

A stdlib mock server stands in for the HwpParser service at the same
boundary production calls (HTTP), per the project's mocking policy.
The mock does not parse HWP — these tests cover multipart upload,
per-format endpoint routing, PDF file persistence, and error surfacing.
"""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from lfx_sapieparser.components.sapieparser.sapieparser_remote import HWPParserRemoteComponent

CANNED = {
    "/hwp2html/clean": (
        "text/html; charset=utf-8",
        b"<html><body><table><tr><td colspan='2'>merged</td></tr></table></body></html>",
    ),
    "/hwp2md/convert": ("text/markdown; charset=utf-8", "# 공문서\n\n본문".encode()),
    "/hwp2pdf/convert": ("application/pdf", b"%PDF-1.7 fake-pdf-bytes"),
}


class _MockHwpParser(BaseHTTPRequestHandler):
    received: dict[str, bytes] = {}

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        _MockHwpParser.received[self.path] = body
        if self.path not in CANNED:
            self.send_response(404)
            self.end_headers()
            return
        media_type, payload = CANNED[self.path]
        self.send_response(200)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@pytest.fixture
def mock_server():
    server = HTTPServer(("127.0.0.1", 0), _MockHwpParser)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def hwp_file(tmp_path):
    path = tmp_path / "doc.hwp"
    path.write_bytes(b"fake hwp bytes")
    return str(path)


def _component(hwp_file, api_url, output_format):
    return HWPParserRemoteComponent(hwp_file=hwp_file, api_url=api_url, output_format=output_format, timeout=10)


def test_html_conversion_uploads_multipart(mock_server, hwp_file):
    message = _component(hwp_file, mock_server, "HTML").convert_document()

    assert "colspan" in message.text
    assert b"doc.hwp" in _MockHwpParser.received["/hwp2html/clean"]


def test_markdown_conversion_routes_to_md_endpoint(mock_server, hwp_file):
    message = _component(hwp_file, mock_server, "Markdown").convert_document()

    assert message.text.startswith("# 공문서")


def test_pdf_conversion_persists_file(mock_server, hwp_file):
    message = _component(hwp_file, mock_server, "PDF").convert_document()

    saved = Path(message.text)
    assert saved.exists()
    assert saved.suffix == ".pdf"
    assert saved.read_bytes().startswith(b"%PDF-")
    assert message.files == [str(saved)]


def test_connection_error_gives_actionable_message(hwp_file):
    # Grab a port with no listener by opening and immediately closing a server.
    server = HTTPServer(("127.0.0.1", 0), _MockHwpParser)
    dead_url = f"http://127.0.0.1:{server.server_address[1]}"
    server.server_close()

    with pytest.raises(ValueError, match="docker compose"):
        _component(hwp_file, dead_url, "HTML").convert_document()
