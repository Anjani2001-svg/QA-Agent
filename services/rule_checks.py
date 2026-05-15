import re
from collections import Counter

import requests


US_TO_UK = {
    "color": "colour",
    "colors": "colours",
    "organize": "organise",
    "organized": "organised",
    "organizing": "organising",
    "center": "centre",
    "behavior": "behaviour",
    "analyze": "analyse",
    "analyzed": "analysed",
    "customize": "customise",
    "customized": "customised"
}


def split_paragraphs(text: str) -> list[str]:
    return [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if len(paragraph.strip()) > 80
    ]


def detect_repeated_paragraphs(document_profile: dict) -> list[dict]:
    paragraph_locations = []

    for page in document_profile["pages"]:
        for paragraph in split_paragraphs(page["text"]):
            normalised = re.sub(r"\s+", " ", paragraph.lower()).strip()
            paragraph_locations.append((normalised, page["page_number"], paragraph))

    counts = Counter(item[0] for item in paragraph_locations)

    issues = []
    seen = set()

    for normalised, page_number, original in paragraph_locations:
        if counts[normalised] > 1 and normalised not in seen:
            seen.add(normalised)
            issues.append({
                "page_or_section": f"Page {page_number}",
                "category": "Repetition",
                "severity": "Major",
                "issue": "Repeated paragraph detected",
                "explanation": "The same or very similar paragraph appears more than once, which may make the e-book feel repetitive or AI-generated.",
                "recommended_fix": "Remove the duplicate paragraph or rewrite it so each section adds distinct value.",
                "evidence": original[:250]
            })

    return issues


def detect_us_spellings(document_profile: dict) -> list[dict]:
    issues = []

    for page in document_profile["pages"]:
        text_lower = page["text"].lower()

        for us_word, uk_word in US_TO_UK.items():
            pattern = rf"\b{re.escape(us_word)}\b"
            if re.search(pattern, text_lower):
                issues.append({
                    "page_or_section": f"Page {page['page_number']}",
                    "category": "Grammar and Spelling",
                    "severity": "Minor",
                    "issue": f"American English spelling used: '{us_word}'",
                    "explanation": "The document should use UK English standards.",
                    "recommended_fix": f"Replace '{us_word}' with '{uk_word}', unless it appears in a proper noun or quoted source.",
                    "evidence": us_word
                })

    return issues


def check_links(document_profile: dict) -> list[dict]:
    issues = []

    for link in document_profile.get("links", []):
        url = link["url"]

        if not url.startswith(("http://", "https://")):
            continue

        try:
            response = requests.head(url, timeout=8, allow_redirects=True)
            if response.status_code >= 400:
                issues.append({
                    "page_or_section": f"Page {link['page']}",
                    "category": "Links and Calls to Action",
                    "severity": "Major",
                    "issue": "Potential broken link",
                    "explanation": f"The link returned HTTP status {response.status_code}.",
                    "recommended_fix": "Update or replace the link before publishing.",
                    "evidence": url
                })
        except requests.RequestException:
            issues.append({
                "page_or_section": f"Page {link['page']}",
                "category": "Links and Calls to Action",
                "severity": "Major",
                "issue": "Link could not be validated",
                "explanation": "The link could not be reached during validation.",
                "recommended_fix": "Manually test the link and replace it if it is broken.",
                "evidence": url
            })

    return issues


def detect_empty_pages(document_profile: dict) -> list[dict]:
    issues = []

    for page in document_profile["pages"]:
        if page["word_count"] == 0:
            issues.append({
                "page_or_section": f"Page {page['page_number']}",
                "category": "Overall Readability and User Experience",
                "severity": "Major",
                "issue": "No extractable text found on page",
                "explanation": "The page may be blank, image-only, scanned, or inaccessible to text extraction.",
                "recommended_fix": "Check the page manually. If it is scanned, add OCR text or provide an accessible text layer.",
                "evidence": ""
            })

    return issues


def run_rule_checks(document_profile: dict) -> list[dict]:
    issues = []
    issues.extend(detect_repeated_paragraphs(document_profile))
    issues.extend(detect_us_spellings(document_profile))
    issues.extend(check_links(document_profile))
    issues.extend(detect_empty_pages(document_profile))
    return issues