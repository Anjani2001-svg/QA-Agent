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
    "find out more",
    "enquire now",
    "apply now"
]


LEARNER_CONTENT_TERMS = [
    "unit introduction",
    "qualification",
    "diploma",
    "learning outcome",
    "assessment criteria",
    "references",
    "chapter",
    "learners",
    "educators",
    "statutory framework"
]


MARKETING_TERMS = [
    "contact us",
    "book a call",
    "get started",
    "request a demo",
    "download now",
    "sign up",
    "register now",
    "visit our website",
    "speak to an adviser",
    "enquire now",
    "apply now"
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


def get_all_text(document_profile: dict) -> str:
    return "\n".join(
        page.get("text", "")
        for page in document_profile.get("pages", [])
    )


def split_paragraphs(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", str(text or ""))

    cleaned = []

    for paragraph in paragraphs:
        paragraph = clean_text(paragraph)

        if len(paragraph) >= 100:
            cleaned.append(paragraph)

    return cleaned


def detect_broken_toc_bookmarks(document_profile: dict) -> list[dict]:
    issues = []

    for page in document_profile.get("pages", []):
        page_number = page.get("page_number", "Unknown")
        text = page.get("text", "")

        if "Error! Bookmark not defined" in text:
            issues.append(
                make_issue(
                    page_or_section=f"Page {page_number}",
                    category="Table of Contents",
                    severity="Major",
                    issue="Broken table of contents bookmark/reference",
                    explanation=(
                        "The document contains the visible error text "
                        "'Error! Bookmark not defined'. This usually means the table of contents "
                        "or cross-references were not updated correctly before exporting the PDF."
                    ),
                    recommended_fix=(
                        "Return to the source Word document, update all fields and cross-references, "
                        "regenerate the table of contents, then export the PDF again."
                    ),
                    evidence="Error! Bookmark not defined"
                )
            )

    return issues


def detect_document_type_alignment(document_profile: dict) -> list[dict]:
    text = get_all_text(document_profile).lower()

    if not text.strip():
        return []

    learner_hits = sum(
        1 for term in LEARNER_CONTENT_TERMS
        if term in text
    )

    marketing_hits = sum(
        1 for term in MARKETING_TERMS
        if term in text
    )

    if learner_hits >= 3 and marketing_hits == 0:
        return [
            make_issue(
                page_or_section="Whole document",
                category="Marketing Purpose Alignment",
                severity="Major",
                issue="Document appears to be learner/course content rather than marketing material",
                explanation=(
                    "The PDF appears to be structured as educational or learner-facing course material. "
                    "It may educate the reader, but it does not clearly function as public-facing marketing material "
                    "because it lacks promotional positioning, a clear offer, a brand journey or a clear next step."
                ),
                recommended_fix=(
                    "If this PDF is intended for marketing, add a short audience-facing introduction, brand positioning, "
                    "reader benefits, proof points and a clear call to action. If it is course content, review it using a learner-material QA checklist instead."
                ),
                evidence=(
                    "Detected learner/course terms such as unit introduction, diploma, qualification, references or chapter."
                )
            )
        ]

    return []


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


def looks_like_cover_page(page: dict) -> bool:
    page_number = page.get("page_number")
    text = page.get("text", "").lower()
    image_count = page.get("image_count", 0)

    if page_number == 1 and image_count > 0:
        return True

    cover_terms = ["diploma", "ebook", "guide", "unit", "course", "level"]

    return page_number == 1 and any(term in text for term in cover_terms)


def detect_basic_image_relevance_risks(document_profile: dict) -> list[dict]:
    issues = []

    for page in document_profile.get("pages", []):
        page_number = page.get("page_number", "Unknown")
        image_count = page.get("image_count", 0)
        word_count = page.get("word_count", 0)
        headings = page.get("candidate_headings", [])

        if image_count <= 0:
            continue

        if looks_like_cover_page(page):
            issues.append(
                make_issue(
                    page_or_section=f"Page {page_number}",
                    category="Image Relevance",
                    severity="Suggestion",
                    issue="Cover image requires manual relevance check",
                    explanation=(
                        "The cover contains image content. Version 1 can detect image presence but cannot fully inspect "
                        "the image pixels. The image should be checked manually for topic relevance, brand fit and professionalism."
                    ),
                    recommended_fix=(
                        "Confirm that the cover image clearly matches the document topic and target audience. "
                        "If relevant and high quality, no change is needed."
                    ),
                    evidence=f"Cover page image count: {image_count}"
                )
            )

            continue

        if word_count < 40:
            issues.append(
                make_issue(
                    page_or_section=f"Page {page_number}",
                    category="Image Relevance",
                    severity="Suggestion",
                    issue="Image appears with limited supporting text",
                    explanation=(
                        "This page contains image content but limited surrounding text. "
                        "The image may need a caption, context or manual relevance check."
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
    combined_text = get_all_text(document_profile).lower()

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
                issues.append(
                    make_issue(
                        page_or_section=f"Page {page_number}",
                        category="Links and Calls to Action",
                        severity="Suggestion",
                        issue="Link needs manual verification",
                        explanation=(
                            f"The link returned HTTP status {response.status_code}. "
                            "This may mean the site blocks automated checks, not necessarily that the link is broken."
                        ),
                        recommended_fix="Manually open the link in a browser and confirm that it works.",
                        evidence=url
                    )
                )

                continue

            if response.status_code in [404, 410]:
                issues.append(
                    make_issue(
                        page_or_section=f"Page {page_number}",
                        category="Links and Calls to Action",
                        severity="Major",
                        issue="Broken link detected",
                        explanation=f"The link returned HTTP status {response.status_code}.",
                        recommended_fix="Update, replace or remove the link before publishing.",
                        evidence=url
                    )
                )

            elif response.status_code >= 500:
                issues.append(
                    make_issue(
                        page_or_section=f"Page {page_number}",
                        category="Links and Calls to Action",
                        severity="Minor",
                        issue="Link server error detected",
                        explanation=f"The link returned HTTP status {response.status_code}.",
                        recommended_fix="Manually retest the link later and replace it if the problem continues.",
                        evidence=url
                    )
                )

        except requests.RequestException:
            issues.append(
                make_issue(
                    page_or_section=f"Page {page_number}",
                    category="Links and Calls to Action",
                    severity="Suggestion",
                    issue="Link could not be validated automatically",
                    explanation=(
                        "The link could not be reached during automated validation. "
                        "This may be due to network restrictions, redirects or bot blocking."
                    ),
                    recommended_fix="Manually test the link in a browser.",
                    evidence=url
                )
            )

    return issues


def detect_toc_presence_risk(document_profile: dict) -> list[dict]:
    pages = document_profile.get("pages", [])

    if not pages:
        return []

    total_pages = document_profile.get(
        "total_pages",
        document_profile.get("page_count", len(pages))
    )

    if total_pages < 8:
        return []

    first_pages_text = " ".join(
        page.get("text", "").lower()
        for page in pages[:5]
    )

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

    issues.extend(detect_broken_toc_bookmarks(document_profile))
    issues.extend(detect_document_type_alignment(document_profile))
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
