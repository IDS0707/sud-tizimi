"""Excel parser (TZ section 2.4).

Reads every worksheet of an XLSX file. Each sheet becomes one ``ParsedPage``
(its cells flattened to tab-separated text) and one ``ParsedTable`` (rows/cols
preserved). Uses openpyxl in read-only mode for speed on large workbooks.
"""
from __future__ import annotations

from app.parsers.base import BaseParser, ParsedPage, ParseResult, ParsedTable
from app.utils.logger import get_logger

log = get_logger("udip.parsers.xlsx")

try:
    import openpyxl

    _HAS_OPENPYXL = True
except Exception:  # pragma: no cover
    _HAS_OPENPYXL = False

_MAX_ROWS = 5000  # safety cap for very large sheets


class XlsxParser(BaseParser):
    name = "xlsx"
    extensions = ("xlsx",)

    def parse(self, file_path: str, **kwargs) -> ParseResult:
        if not _HAS_OPENPYXL:
            return ParseResult(parser=self.name, metadata={"error": "openpyxl not installed"})

        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        pages: list[ParsedPage] = []
        tables: list[ParsedTable] = []

        for idx, sheet in enumerate(wb.worksheets, start=1):
            rows: list[list[str]] = []
            for r, row in enumerate(sheet.iter_rows(values_only=True)):
                if r >= _MAX_ROWS:
                    break
                cells = ["" if c is None else str(c) for c in row]
                if any(cells):
                    rows.append(cells)

            text = "\n".join("\t".join(r) for r in rows)
            pages.append(ParsedPage(
                page_number=idx,
                text=text,
                blocks=[{"type": "table", "rows": rows, "sheet": sheet.title}],
            ))
            if rows:
                tables.append(ParsedTable(page_number=idx, rows=rows))

        sheet_names = [p.blocks[0]["sheet"] for p in pages]
        wb.close()
        meta = {
            "page_count": len(pages),
            "sheets": sheet_names,
            "tables": len(tables),
        }
        log.info("Parsed XLSX %s: %d sheets", file_path, len(pages))
        return ParseResult(parser=self.name, pages=pages, tables=tables, metadata=meta)


xlsx_parser = XlsxParser()
