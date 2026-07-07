"""Tests for HWPXTextExtractorComponent paragraph extraction.

Builds a minimal but structurally faithful ``.hwpx`` (ZIP + OWPML XML)
including a table whose cells hold their own nested paragraphs — the key
regression case is that cell text must land in its innermost paragraph
only, without duplicating into the outer one.
"""

import zipfile

import pytest
from lfx_sapieparser.components.sapieparser.sapieparser_inline import HWPXTextExtractorComponent

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"

SECTION_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" xmlns:hp="{HP}">
  <hp:p><hp:run><hp:t>공문서 제목</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>□ 첫 번째 안내 문단입니다.</hp:t></hp:run></hp:p>
  <hp:p>
    <hp:run>
      <hp:tbl rows="1" cols="2">
        <hp:tr>
          <hp:tc><hp:subList>
            <hp:p><hp:run><hp:t>셀A 첫 줄</hp:t></hp:run></hp:p>
            <hp:p><hp:run><hp:t>◇ 셀A 둘째 줄</hp:t></hp:run></hp:p>
          </hp:subList></hp:tc>
          <hp:tc><hp:subList>
            <hp:p><hp:run><hp:t>셀B 내용</hp:t></hp:run></hp:p>
          </hp:subList></hp:tc>
        </hp:tr>
      </hp:tbl>
    </hp:run>
  </hp:p>
  <hp:p><hp:run><hp:t>○ 마지막 문단</hp:t></hp:run></hp:p>
</hs:sec>
"""

EXPECTED_PARAGRAPHS = [
    "공문서 제목",
    "□ 첫 번째 안내 문단입니다.",
    "셀A 첫 줄",
    "◇ 셀A 둘째 줄",
    "셀B 내용",
    "○ 마지막 문단",
]


def _write_fake_hwpx(path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")
        zf.writestr("Contents/section0.xml", SECTION_XML)


def test_extract_text_joins_paragraphs(tmp_path):
    hwpx = tmp_path / "sample.hwpx"
    _write_fake_hwpx(hwpx)

    component = HWPXTextExtractorComponent(hwpx_file=str(hwpx))
    message = component.extract_text()

    assert message.text == "\n".join(EXPECTED_PARAGRAPHS)


def test_extract_paragraphs_keeps_cell_paragraphs_separate(tmp_path):
    hwpx = tmp_path / "sample.hwpx"
    _write_fake_hwpx(hwpx)

    component = HWPXTextExtractorComponent(hwpx_file=str(hwpx))
    data = component.extract_paragraphs()

    assert data.data["paragraph_count"] == len(EXPECTED_PARAGRAPHS)
    assert data.data["paragraphs"] == EXPECTED_PARAGRAPHS
    assert data.data["file_name"] == "sample.hwpx"


def test_rejects_non_hwpx_zip(tmp_path):
    bogus = tmp_path / "bogus.hwpx"
    with zipfile.ZipFile(bogus, "w") as zf:
        zf.writestr("mimetype", "application/hwp+zip")

    component = HWPXTextExtractorComponent(hwpx_file=str(bogus))
    with pytest.raises(ValueError, match="section"):
        component.extract_text()
