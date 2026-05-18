import re
from collections import Counter

import requests


US_TO_UK = {
    "color": "colour",
    "colors": "colours",
    "colored": "coloured",
    "organize": "organise",
    "organized": "organised",
    "organizing": "organising",
    "organization": "organisation",
    "organizations": "organisations",
    "center": "centre",
    "centers": "centres",
    "behavior": "behaviour",
    "behaviors": "behaviours",
    "analyze": "analyse",
    "analyzed": "analysed",
    "analyzing": "analysing",
    "customize": "customise",
    "customized": "customised",
    "customizing": "customising",
    "favorite": "favourite",
    "favorites": "favourites",
    "prioritize": "prioritise",
    "prioritized": "prioritised",
    "realize": "realise",
    "realized": "realised",
    "recognize": "recognise",
    "recognized": "recognised",
    "specialize": "specialise",
    "specialized": "specialised"
}


CTA_TERMS = [
    "contact us",
    "book a call",
    "get started",
    "download",
    "sign up",
    "register",
    "learn more",
    "visit",
    "call us",
    "email us",
    "request a demo",
    "speak to us",
    "get in touch",
    "find out more"
]


def make_issue(
    page_or_section: str,
    category: str,
    severity: str,
    issue: str,
    explanation: str,
    recommended_fix: str,
    evidence: str = ""
) -> dict:
    return {
        "page_or_section": page_or_section,
        "category": category,
        "severity": severity,
        "issue": issue,
        "explanation": explanation,
        "recommended_fix": recommended_fix,
        "evidence": evidence
    }


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def split_paragraphs(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", str(text or ""))

    cleaned = []
    for paragraph in paragraphs:
        paragraph = clean_text(paragraph)
        if len(paragraph) >= 100:
            cleaned.append(paragraph)

    return cleaned


def detect_repeated_paragraphs(document_profile: dict) -> list[dict]:
    paragraph_locations = []

    for page in document_profile.get("pages", []):
        page_number = page.get("page_number", "Unknown")

        for paragraph in split_paragraphs(page.get("text", "")):
            normalised = paragraph.lower().strip()
            paragraph_locations.append((normalised, page_number, paragraph))

    counts = Counter(item[0] for item in paragraph_locations)

    issues = []
    seen = set()

    for normalised, page_number, original in paragraph_locations:
        if counts[normalised] > 1 and normalised not in seen:
            seen.add(normalised)

            issues.append(
                make_issue(
                    page_or_section=f"Page {page_number}",
                    category="Repetition",
                    severity="Major",
                    issue="Repeated paragraph detected",
                    explanation=(
                        "The same or very similar paragraph appears more than once. "
                        "This can make the e-book feel repetitive, generic or AI-generated."
                    ),
                    recommended_fix=(
                        "Remove the duplicate paragraph or rewrite the repeated section so each part adds distinct value."
                    ),
                    evidence=original[:300]
                )
            )

    return issues


def detect_us_spellings(document_profile: dict) -> list[dict]:
    issues = []
    seen = set()

    for page in document_profile.get("pages", []):
        page_number = page.get("page_number", "Unknown")
        text = page.get("text", "")

        for us_word, uk_word in US_TO_UK.items():
            pattern = rf"\b{re.escape(us_word)}\b"

            if re.search(pattern, text, flags=re.IGNORECASE):
                key = (page_number, us_word)

                if key in seen:
                    continue

                seen.add(key)

                issues.append(
                    make_issue(
                        page_or_section=f"Page {page_number}",
                        category="Grammar and Spelling",
                        severity="Minor",
                        issue=f"American English spelling used: '{us_word}'",
                        explanation="The e-book should use UK English standards.",
                        recommended_fix=(
                            f"Replace '{us_word}' with '{uk_word}', unless it appears in a proper noun, URL or quoted source."
                        ),
                        evidence=us_word
                    )
                )

    return issues


def detect_empty_or_scanned_pages(document_profile: dict) -> list[dict]:
    issues = []

    for page in document_profile.get("pages", []):
        page_number = page.get("page_number", "Unknown")
        word_count = page.get("word_count", 0)
        image_count = page.get("image_count", 0)

        if word_count == 0 and image_count > 0:
            issues.append(
                make_issue(
                    page_or_section=f"Page {page_number}",
                    category="Accessibility",
                    severity="Major",
                    issue="Image-only or scanned page detected",
                    explanation=(
                        "No extractable text was found, but the page contains image content. "
                        "This may indicate a scanned page or text embedded inside an image, which can reduce accessibility."
                    ),
                    recommended_fix=(
                        "Add OCR text or provide an accessible text layer so screen readers and search tools can read the content."
                    )
                )
            )

        elif word_count == 0:
            issues.append(
                make_issue(
                    page_or_section=f"Page {page_number}",
                    category="Overall Readability and User Experience",
                    severity="Minor",
                    issue="No extractable text found on page",
                    explanation="The page appears blank or contains content that could not be extracted.",
                    recommended_fix="Check the page manually and remove it if it is unnecessary."
                )
            )

    return issues


def detect_long_sentences(document_profile: dict) -> list[dict]:
    issues = []

    for page in document_profile.get("pages", []):
        page_number = page.get("page_number", "Unknown")
        text = clean_text(page.get("text", ""))

        if not text:
            continue

        sentences = re.split(r"(?<=[.!?])\s+", text)

        for sentence in sentences:
            words = sentence.split()

            if len(words) > 45:
                issues.append(
                    make_issue(
                        page_or_section=f"Page {page_number}",
                        category="Tone and Readability",
                        severity="Suggestion",
                        issue="Long sentence may reduce readability",
                        explanation=(
                            "The sentence is quite long for a general public marketing e-book. "
                            "Long sentences can make the content harder to follow."
                        ),
                        recommended_fix="Split the sentence into two shorter sentences or simplify the structure.",
                        evidence=sentence[:300]
                    )
                )

                break

    return issues


def detect_basic_image_relevance_risks(document_profile: dict) -> list[dict]:
    issues = []

    for page in document_profile.get("pages", []):
        page_number = page.get("page_number", "Unknown")
        image_count = page.get("image_count", 0)
        word_count = page.get("word_count", 0)
        headings = page.get("candidate_headings", [])

        if image_count <= 0:
            continue

        if word_count < 40:
            issues.append(
                make_issue(
                    page_or_section=f"Page {page_number}",
                    category="Image Relevance",
                    severity="Suggestion",
                    issue="Image appears with very little supporting text",
                    explanation=(
                        "This page contains image content but very little surrounding text. "
                        "The image may be decorative, unclear, insufficiently explained or difficult to understand without context."
                    ),
                    recommended_fix=(
                        "Check whether the image clearly supports the section. "
                        "Add a caption, short explanation or replace the image if it does not support the content."
                    ),
                    evidence=f"Image count: {image_count}; word count: {word_count}"
                )
            )

        if image_count >= 3 and word_count < 120:
            issues.append(
                make_issue(
                    page_or_section=f"Page {page_number}",
                    category="Image Placement",
                    severity="Suggestion",
                    issue="Image-heavy page may need manual layout review",
                    explanation=(
                        "The page contains several images but limited text. "
                        "This may affect reading flow, image relevance or visual balance."
                    ),
                    recommended_fix=(
                        "Manually review the page layout and confirm that each image supports the message and appears near relevant text."
                    ),
                    evidence=f"Image count: {image_count}; word count: {word_count}; headings: {headings[:3]}"
                )
            )

    return issues


def detect_image_manual_review_need(document_profile: dict) -> list[dict]:
    pages_with_images = [
        page.get("page_number")
        for page in document_profile.get("pages", [])
        if page.get("image_count", 0) > 0
    ]

    if not pages_with_images:
        return []

    return [
        make_issue(
            page_or_section="Pages with images",
            category="Image Quality",
            severity="Suggestion",
            issue="Image quality requires manual visual review",
            explanation=(
                "The parser detected images, but Version 1 does not fully inspect image pixels, resolution, cropping or distortion."
            ),
            recommended_fix=(
                "Manually check image sharpness, cropping, stretching, brand fit and visual consistency before publishing."
            ),
            evidence=f"Pages with detected images: {pages_with_images[:30]}"
        )
    ]


def detect_missing_cta(document_profile: dict) -> list[dict]:
    combined_text = " ".join(
        page.get("text", "").lower()
        for page in document_profile.get("pages", [])
    )

    if not combined_text.strip():
        return []

    if not any(term in combined_text for term in CTA_TERMS):
        return [
            make_issue(
                page_or_section="Whole document",
                category="Links and Calls to Action",
                severity="Major",
                issue="No clear call to action detected",
                explanation=(
                    "The e-book appears to lack a clear next step for readers. "
                    "This weakens its usefulness as marketing or lead-generation material."
                ),
                recommended_fix=(
                    "Add a clear, helpful CTA near the end of the e-book and, where relevant, after key sections."
                )
            )
        ]

    return []


def check_links(document_profile: dict, max_links: int = 50) -> list[dict]:
    issues = []

    links = document_profile.get("links", [])[:max_links]

    for link in links:
        url = link.get("url", "")
        page_number = link.get("page", "Unknown")

        if not url.startswith(("http://", "https://")):
            continue

        try:
            response = requests.head(
                url,
                timeout=8,
                allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            if response.status_code in [403, 405]:
                response = requests.get(
                    url,
                    timeout=8,
                    allow_redirects=True,
                    stream=True,
                    headers={"User-Agent": "Mozilla/5.0"}
                )

            if response.status_code >= 400:
                issues.append(
                    make_issue(
                        page_or_section=f"Page {page_number}",
                        category="Links and Calls to Action",
                        severity="Major",
                        issue="Potential broken link",
                        explanation=f"The link returned HTTP status {response.status_code}.",
                        recommended_fix="Update, replace or remove the link before publishing.",
                        evidence=url
                    )
                )

        except requests.RequestException:
            issues.append(
                make_issue(
                    page_or_section=f"Page {page_number}",
                    category="Links and Calls to Action",
                    severity="Major",
                    issue="Link could not be validated",
                    explanation="The link could not be reached during validation.",
                    recommended_fix="Manually test the link and replace it if it is broken.",
                    evidence=url
                )
            )

    return issues


def detect_toc_presence_risk(document_profile: dict) -> list[dict]:
    pages = document_profile.get("pages", [])

    if not pages:
        return []

    total_pages = document_profile.get("total_pages", document_profile.get("page_count", len(pages)))

    if total_pages < 8:
        return []

    first_pages_text = " ".join(
        page.get("text", "").lower()
        for page in pages[:5]
    )

    toc_terms = [
        "table of contents",
        "contents",
        "chapter",
        "page"
    ]

    if "table of contents" not in first_pages_text and "contents" not in first_pages_text:
        return [
            make_issue(
                page_or_section="Front matter",
                category="Table of Contents",
                severity="Suggestion",
                issue="Table of contents not clearly detected",
                explanation=(
                    "A table of contents was not clearly detected in the first few parsed pages. "
                    "Longer e-books usually benefit from a contents page for navigation."
                ),
                recommended_fix=(
                    "Add or check the table of contents if the e-book has multiple sections or chapters."
                )
            )
        ]

    return []


def run_rule_checks(
    document_profile: dict,
    validate_links: bool = True,
    max_links: int = 50
) -> list[dict]:
    issues = []

    issues.extend(detect_empty_or_scanned_pages(document_profile))
    issues.extend(detect_repeated_paragraphs(document_profile))
    issues.extend(detect_us_spellings(document_profile))
    issues.extend(detect_long_sentences(document_profile))
    issues.extend(detect_basic_image_relevance_risks(document_profile))
    issues.extend(detect_image_manual_review_need(document_profile))
    issues.extend(detect_missing_cta(document_profile))
    issues.extend(detect_toc_presence_risk(document_profile))

    if validate_links:
        issues.extend(check_links(document_profile, max_links=max_links))

    return issues
