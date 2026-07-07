from __future__ import annotations

import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from defusedxml import ElementTree
from lfx.custom.custom_component.component import Component
from lfx.io import FileInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element


class HWPXTextExtractorComponent(Component):
    display_name = "HWPX Text Extractor"
    description = "Extract paragraph text from a Korean HWPX (.hwpx) document."
    documentation = "https://github.com/sangmoonjeon/sapie-hwp-parser"
    icon = "file-text"
    name = "HWPXTextExtractor"

    inputs = [
        FileInput(
            name="hwpx_file",
            display_name="HWPX File",
            file_types=["hwpx"],
            info="Upload an HWPX document. Legacy binary .hwp files are not supported.",
            required=True,
        ),
    ]

    outputs = [
        Output(name="text", display_name="Text", method="extract_text"),
        Output(name="paragraphs", display_name="Paragraphs", method="extract_paragraphs"),
    ]

    def _read_paragraphs(self) -> list[str]:
        resolved_path = Path(self.resolve_path(self.hwpx_file))
        if not resolved_path.exists():
            msg = f"File not found: {resolved_path}"
            raise ValueError(msg)

        try:
            with zipfile.ZipFile(resolved_path) as archive:
                section_names = sorted(
                    name for name in archive.namelist() if name.startswith("Contents/section") and name.endswith(".xml")
                )
                if not section_names:
                    msg = f"Not a valid HWPX document (no Contents/section*.xml): {resolved_path.name}"
                    raise ValueError(msg)
                paragraphs: list[str] = []
                for name in section_names:
                    root = ElementTree.fromstring(archive.read(name))
                    paragraphs.extend(self._collect_paragraphs(root))
        except zipfile.BadZipFile as e:
            msg = f"Not a valid HWPX document (not a ZIP archive): {resolved_path.name}"
            raise ValueError(msg) from e
        return paragraphs

    @staticmethod
    def _collect_paragraphs(root: Element) -> list[str]:
        """Collect text per <hp:p> paragraph, keeping table-cell paragraphs separate.

        Paragraphs can nest (a table cell inside a paragraph holds its own
        paragraphs), so a buffer stack ensures each <hp:t> text lands in its
        innermost paragraph only, without duplicating into the outer one.
        """
        paragraphs: list[str] = []
        buffers: list[list[str]] = []

        def walk(element: Element) -> None:
            tag = element.tag.rsplit("}", 1)[-1]
            if tag == "p":
                buffers.append([])
            elif tag == "t" and buffers:
                buffers[-1].append("".join(element.itertext()))
            for child in element:
                walk(child)
            if tag == "p":
                text = "".join(buffers.pop())
                if text.strip():
                    paragraphs.append(text)

        walk(root)
        return paragraphs

    def extract_text(self) -> Message:
        paragraphs = self._read_paragraphs()
        text = "\n".join(paragraphs)
        self.status = f"Extracted {len(paragraphs)} paragraphs."
        return Message(text=text)

    def extract_paragraphs(self) -> Data:
        paragraphs = self._read_paragraphs()
        result = Data(
            data={
                "file_name": Path(self.hwpx_file).name,
                "paragraph_count": len(paragraphs),
                "paragraphs": paragraphs,
            }
        )
        self.status = result
        return result
