"""lfx-sapieparser: Sapie HWP/HWPX parsing bundle.

This package is the distribution unit ``lfx-sapieparser``. At runtime
Langflow's loader discovers ``extension.json`` shipped alongside this
``__init__.py`` and registers the components under namespaced IDs
(``ext:sapieparser:<ClassName>@<origin>``).

Components:
- ``HWPParserRemoteComponent`` (sapieparser_remote) — remote conversion
  (HTML/Markdown/PDF) via a running HwpParser service
  (LibreOffice + H2Orestart).
- ``HWPXTextExtractorComponent`` (sapieparser_inline) — inline paragraph
  extraction from ``.hwpx`` files, no external service required.
"""

from lfx_sapieparser.components.sapieparser.sapieparser_inline import HWPXTextExtractorComponent
from lfx_sapieparser.components.sapieparser.sapieparser_remote import HWPParserRemoteComponent

__all__ = ["HWPParserRemoteComponent", "HWPXTextExtractorComponent"]
