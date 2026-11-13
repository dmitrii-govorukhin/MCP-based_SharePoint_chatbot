import json
import requests

from requests_negotiate_sspi import HttpNegotiateAuth
from mcp.server.mcpserver import MCPServer
from io import BytesIO
from docx import Document
from pypdf import PdfReader
from openpyxl import load_workbook


mcp = MCPServer("SharePoint MCP Server")


@mcp.tool()
def health_check() -> str:
    """Check whether the SharePoint MCP server is responding."""
    return "SharePoint MCP Server is running."


@mcp.tool()
def search_sharepoint(query: str) -> str:
    """Search SharePoint documents using SharePoint Search REST API.

    Args:
        query: Keywords to search for in SharePoint.
    """
    url = "http://calsawsproject/_api/search/query"

    params = {
        "querytext": f"'{query}'"
    }

    response = requests.get(
        url,
        params=params,
        auth=HttpNegotiateAuth(),
        headers={
            "Accept": "application/json;odata=verbose"
        },
        timeout=30,
    )

    response.raise_for_status()
    data = response.json()

    rows = data["d"]["query"]["PrimaryQueryResult"][
        "RelevantResults"
    ]["Table"]["Rows"]["results"]

    results = []

    for row in rows:
        cells = {
            cell["Key"]: cell["Value"]
            for cell in row["Cells"]["results"]
        }

        results.append({
            "title": cells.get("Title"),
            "path": cells.get("Path"),
            "file_type": cells.get("FileType"),
            "rank": cells.get("Rank"),
            "snippet": cells.get("HitHighlightedSummary"),
        })

    return json.dumps(results, ensure_ascii=False)


def get_pdf_text(url: str) -> str:
    """Download a PDF from SharePoint and extract its text."""

    response = requests.get(
        url,
        auth=HttpNegotiateAuth(),
        timeout=60,
    )
    response.raise_for_status()

    reader = PdfReader(BytesIO(response.content))

    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        if text.strip():
            pages.append(f"[Page {page_number}]\n{text}")

    return "\n\n".join(pages)


def get_docx_text(url: str) -> str:
    """Download a DOCX file from SharePoint and extract its text."""

    response = requests.get(
        url,
        auth=HttpNegotiateAuth(),
        timeout=60,
    )
    response.raise_for_status()

    document = Document(BytesIO(response.content))

    parts = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()

        if text:
            parts.append(text)

    for table_number, table in enumerate(document.tables, start=1):
        parts.append(f"[Table {table_number}]")

        for row in table.rows:
            cells = [
                cell.text.strip().replace("\n", " ")
                for cell in row.cells
            ]
            parts.append(" | ".join(cells))

    return "\n\n".join(parts)


def get_xlsx_text(url: str) -> str:
    """Download an XLSX file from SharePoint and extract its contents."""

    response = requests.get(
        url,
        auth=HttpNegotiateAuth(),
        timeout=60,
    )
    response.raise_for_status()

    workbook = load_workbook(
        BytesIO(response.content),
        read_only=True,
        data_only=True,
    )

    parts = []

    try:
        for worksheet in workbook.worksheets:
            parts.append(f"[Sheet: {worksheet.title}]")

            for row in worksheet.iter_rows(values_only=True):
                values = [
                    "" if value is None else str(value)
                    for value in row
                ]

                if any(value.strip() for value in values):
                    parts.append(" | ".join(values))

    finally:
        workbook.close()

    return "\n".join(parts)
    

@mcp.tool()
def fetch_document_text(url: str, file_type: str) -> str:
    """Download a PDF, DOCX, or XLSX document from SharePoint and extract its text.

    Args:
        url: The document URL returned by SharePoint Search.
        file_type: The document type: pdf, docx, or xlsx.
    """

    normalized_type = file_type.lower().strip()

    if normalized_type == "pdf":
        return get_pdf_text(url)

    if normalized_type == "docx":
        return get_docx_text(url)

    if normalized_type == "xlsx":
        return get_xlsx_text(url)

    raise ValueError(
        f"Unsupported file type: {file_type}. "
        "Supported types: pdf, docx, xlsx."
    )
    

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=8002,
    )
