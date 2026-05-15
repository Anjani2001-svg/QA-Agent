try:
    import fitz  # type: ignore[import]
except ImportError as exc:
    raise ImportError("PyMuPDF is required to parse PDFs. Install it with 'pip install PyMuPDF'.") from exc


def parse_pdf(pdf_path: str) -> dict:
    doc = fitz.open(pdf_path)

    pages = []
    all_links = []

    for page_index, page in enumerate(doc):
        page_number = page_index + 1
        text = page.get_text("text") or ""

        links = []
        for link in page.get_links():
            uri = link.get("uri")
            if uri:
                links.append({
                    "page": page_number,
                    "url": uri
                })
                all_links.append({
                    "page": page_number,
                    "url": uri
                })

        images = page.get_images(full=True)

        pages.append({
            "page_number": page_number,
            "text": text,
            "word_count": len(text.split()),
            "links": links,
            "image_count": len(images)
        })

    metadata = doc.metadata or {}

    return {
        "file_path": pdf_path,
        "page_count": len(doc),
        "metadata": metadata,
        "pages": pages,
        "links": all_links
    }