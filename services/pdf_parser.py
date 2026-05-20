from pathlib import Path
import re

try:
    import fitz
except ImportError as exc:
    raise ImportError(
        "PyMuPDF is required to parse PDFs. Install it with: python -m pip install PyMuPDF"
    ) from exc


def extract_candidate_headings(text: str) -> list[str]:
    headings = []

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if len(line) > 120:
            continue

        if len(line.split()) > 14:
            continue

        looks_numbered = bool(re.match(r"^(\d+\.|\d+\.\d+|chapter\s+\d+)", line, re.I))
        looks_heading_case = line[:1].isupper() and not line.endswith(".")
        looks_upper = line.isupper() and len(line) > 3

        if looks_numbered or looks_heading_case or looks_upper:
            headings.append(line)

    seen = set()
    unique_headings = []

    for heading in headings:
        key = heading.lower()
        if key not in seen:
            seen.add(key)
            unique_headings.append(heading)

    return unique_headings[:30]


def parse_pdf(pdf_path: str, max_pages: int | None = None) -> dict:
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError("The selected file is not a PDF.")

    doc = fitz.open(str(path))

    total_pages = len(doc)
    pages_to_parse = total_pages if max_pages is None else min(total_pages, max_pages)

    pages = []
    all_links = []
    all_headings = []

    for page_index in range(pages_to_parse):
        page = doc.load_page(page_index)
        page_number = page_index + 1

        text = page.get_text("text") or ""
        words = text.split()

        links = []
        for link in page.get_links():
            uri = link.get("uri")
            if uri:
                link_record = {
                    "page": page_number,
                    "url": uri
                }
                links.append(link_record)
                all_links.append(link_record)

        images = page.get_images(full=True)
        headings = extract_candidate_headings(text)

        for heading in headings:
            all_headings.append({
                "page": page_number,
                "heading": heading
            })

        pages.append({
            "page_number": page_number,
            "text": text,
            "word_count": len(words),
            "character_count": len(text),
            "links": links,
            "image_count": len(images),
            "candidate_headings": headings
        })

    metadata = doc.metadata or {}
    doc.close()

    file_size_mb = path.stat().st_size / (1024 ** 2)

    return {
        "file_name": path.name,
        "file_path": str(path),
        "file_size_mb": round(file_size_mb, 2),
        "total_pages": total_pages,
        "pages_parsed": pages_to_parse,
        "metadata": metadata,
        "pages": pages,
        "links": all_links,
        "candidate_headings": all_headings,
        "analysis_limit_note": (
            "Only part of the PDF was parsed because a page limit was selected."
            if pages_to_parse < total_pages
            else ""
        )
    }
