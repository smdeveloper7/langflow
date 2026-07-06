from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FileInput, IntInput, Output, StrInput
from lfx.schema.message import Message
from lfx.utils.util import transform_localhost_url


class HWPParserRemoteComponent(Component):
    display_name = "HWP Parser"
    description = (
        "Convert HWP/HWPX documents to clean HTML, Markdown, or PDF "
        "by connecting to your instance of the HwpParser service."
    )
    documentation = "https://github.com/sangmoonjeon/hwpparser"
    icon = "file-text"
    name = "HWPParserRemote"

    _FORMAT_ENDPOINTS = {
        "HTML": "/hwp2html/clean",
        "Markdown": "/hwp2md/convert",
        "PDF": "/hwp2pdf/convert",
    }

    inputs = [
        FileInput(
            name="hwp_file",
            display_name="HWP File",
            file_types=["hwp", "hwpx"],
            info="Upload an HWP or HWPX document to convert.",
            required=True,
        ),
        StrInput(
            name="api_url",
            display_name="HwpParser URL",
            value="http://localhost:40000",
            info="Base URL of a running HwpParser service (start it with `docker compose up -d --build`).",
            required=True,
        ),
        DropdownInput(
            name="output_format",
            display_name="Output Format",
            options=list(_FORMAT_ENDPOINTS),
            value="HTML",
            info=(
                "HTML keeps table structure (colspan/rowspan); Markdown is flatter but lighter. "
                "PDF preserves the original layout — the message text carries the saved file path."
            ),
        ),
        IntInput(
            name="timeout",
            display_name="Timeout (seconds)",
            value=120,
            info="How long to wait for the conversion. Large documents can take a while.",
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="content", display_name="Content", method="convert_document"),
    ]

    def convert_document(self) -> Message:
        resolved_path = Path(self.resolve_path(self.hwp_file))
        if not resolved_path.exists():
            msg = f"File not found: {resolved_path}"
            raise ValueError(msg)

        endpoint = self._FORMAT_ENDPOINTS.get(self.output_format)
        if endpoint is None:
            msg = f"Unsupported output format: {self.output_format}"
            raise ValueError(msg)

        base_url = transform_localhost_url(self.api_url).rstrip("/")
        url = f"{base_url}{endpoint}"
        file_name = Path(self.hwp_file).name

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, files={"file": (file_name, resolved_path.read_bytes())})
                response.raise_for_status()
        except httpx.ConnectError as e:
            msg = (
                f"Could not reach the HwpParser service at {base_url}. "
                "Make sure it is running (`docker compose up -d --build`) and the URL is correct."
            )
            raise ValueError(msg) from e
        except httpx.TimeoutException as e:
            msg = f"The HwpParser service did not respond within {self.timeout}s. Try raising the timeout."
            raise ValueError(msg) from e
        except httpx.HTTPStatusError as e:
            msg = f"HwpParser returned an error for {file_name}: {e.response.status_code} {e.response.text[:500]}"
            raise ValueError(msg) from e

        if self.output_format == "PDF":
            # Binary output: persist to a file and hand the path downstream
            # (Message.text and Message.files both carry it).
            pdf_name = f"{Path(file_name).stem}.pdf"
            pdf_path = Path(tempfile.mkdtemp(prefix="hwp2pdf_")) / pdf_name
            pdf_path.write_bytes(response.content)
            self.status = f"Converted {file_name} to PDF ({len(response.content)} bytes) → {pdf_path}"
            return Message(text=str(pdf_path), files=[str(pdf_path)])

        content = response.text
        self.status = f"Converted {file_name} to {self.output_format} ({len(content)} chars)."
        return Message(text=content)
