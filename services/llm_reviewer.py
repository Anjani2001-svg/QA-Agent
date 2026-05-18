import json
import os
from openai import OpenAI
from dotenv import load_dotenv


try:
    import streamlit as st
except Exception:
    st = None


load_dotenv()


QA_CATEGORIES = [
    "Cover Page Quality",
    "Topic Relevance",
    "Target Audience Suitability",
    "Marketing Purpose Alignment",
    "Accuracy of AI-Generated Content",
    "Content Originality",
    "Headings and Subheadings",
    "Numbering Accuracy",
    "Table of Contents",
    "Page Numbering",
    "Headers and Footers",
    "Grammar and Spelling",
    "Tone and Readability",
    "Repetition",
    "Image Relevance",
    "Image Quality",
    "Image Placement",
    "Image Accuracy",
    "Formatting Consistency",
    "Spacing and Alignment",
    "Tables and Charts",
    "Accessibility",
    "Branding",
    "Links and Calls to Action",
    "Legal and Compliance Risks",
    "Overall Readability and User Experience"
]


VISUAL_REVIEW_CATEGORIES = [
    "Image Relevance",
    "Image Quality",
    "Image Placement",
    "Image Accuracy",
    "Formatting Consistency",
    "Spacing and Alignment",
    "Tables and Charts",
    "Accessibility"
]


def get_secret(name: str, default: str = "") -> str:
    value = os.getenv(name, "")

    if value:
        return value

    if st is not None:
        try:
            return st.secrets.get(name, default)
        except Exception:
            return default

    return default


def get_client_and_model():
    """
    Supports both OpenRouter and direct OpenAI.

    For Streamlit Cloud Secrets, use:

    LLM_PROVIDER = "openrouter"
    OPENROUTER_API_KEY = "your_key_here"
    OPENROUTER_MODEL = "openai/gpt-4o-mini"

    Or:

    LLM_PROVIDER = "openrouter"
    OPENROUTER_API_KEY = "your_key_here"
    OPENROUTER_MODEL = "deepseek/deepseek-chat"
    """

    provider = get_secret("LLM_PROVIDER", "").strip().lower()

    openrouter_key = get_secret("OPENROUTER_API_KEY", "").strip()
    openai_key = get_secret("OPENAI_API_KEY", "").strip()

    if not provider:
        if openrouter_key or openai_key.startswith("sk-or-"):
            provider = "openrouter"
        else:
            provider = "openai"

    if provider == "openrouter":
        api_key = openrouter_key or openai_key

        if not api_key:
            raise RuntimeError(
                "OpenRouter key missing. Add OPENROUTER_API_KEY in Streamlit Secrets or .env."
            )

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )

        model = get_secret("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        return client, model

    if provider == "openai":
        if not openai_key:
            raise RuntimeError(
                "OpenAI key missing. Add OPENAI_API_KEY in Streamlit Secrets or .env."
            )

        client = OpenAI(api_key=openai_key)
        model = get_secret("OPENAI_MODEL", "gpt-4o-mini")
        return client, model

    raise RuntimeError("Invalid LLM_PROVIDER. Use 'openrouter' or 'openai'.")


def extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1:
            raise ValueError("The model did not return valid JSON.")

        return json.loads(text[start:end + 1])


def get_document_image_summary(document_profile: dict) -> dict:
    pages = document_profile.get("pages", [])
    pages_with_images = [
        page.get("page_number")
        for page in pages
        if page.get("image_count", 0) > 0
    ]

    image_heavy_pages = [
        page.get("page_number")
        for page in pages
        if page.get("image_count", 0) >= 2
    ]

    image_with_low_text_pages = [
        page.get("page_number")
        for page in pages
        if page.get("image_count", 0) > 0 and page.get("word_count", 0) < 40
    ]

    return {
        "total_pages_with_images": len(pages_with_images),
        "pages_with_images": pages_with_images[:100],
        "image_heavy_pages": image_heavy_pages[:100],
        "image_with_low_text_pages": image_with_low_text_pages[:100],
        "note": (
            "Version 1 checks image relevance using image counts, page text, headings and context. "
            "It does not fully inspect the image pixels unless a vision model/page screenshot workflow is added."
        )
    }


def compact_page(page: dict) -> dict:
    image_count = page.get("image_count", 0)
    word_count = page.get("word_count", 0)

    if image_count > 0 and word_count < 40:
        image_review_hint = (
            "This page contains image(s) but very little text. "
            "Check whether the image is clearly explained, relevant and accessible."
        )
    elif image_count > 0:
        image_review_hint = (
            "This page contains image(s). Review whether the image appears to support the surrounding text and heading."
        )
    else:
        image_review_hint = "No image detected on this page."

    return {
        "page_number": page.get("page_number"),
        "word_count": word_count,
        "image_count": image_count,
        "image_review_hint": image_review_hint,
        "links": page.get("links", []),
        "candidate_headings": page.get("candidate_headings", []),
        "text_excerpt": page.get("text", "")[:3500]
    }


def build_review_prompt(document_profile: dict, rule_issues: list[dict]) -> str:
    compact_pages = [compact_page(page) for page in document_profile.get("pages", [])]
    image_summary = get_document_image_summary(document_profile)

    return f"""
You are a QA reviewer for public-facing marketing e-books and PDFs.

Use UK English.

Review the supplied PDF content as marketing material for the general public.

Check the document against these QA categories:
{json.dumps(QA_CATEGORIES, indent=2)}

For every issue, include:
- page_or_section
- category
- severity: Critical, Major, Minor, or Suggestion
- issue
- explanation
- recommended_fix
- evidence, where useful

Important rules:
- Do not invent page numbers.
- Use only the supplied page numbers.
- Do not claim a fact is false unless it can be verified from the supplied content.
- Use "Needs verification" for unsupported claims, statistics, dates, guarantees or factual statements requiring evidence.
- Use "Needs legal/compliance review" for legal, medical, financial, privacy, copyright, guarantee or testimonial risks.
- Do not make definitive plagiarism claims. Use "possible duplicate/copy concern" where appropriate.
- Be specific and practical.
- Focus on publishing quality, credibility, marketing effectiveness, accessibility and reader trust.

Image Relevance check:
- If a page contains images, assess whether the image appears to support the surrounding content using the page heading, nearby text and context.
- Flag images that appear random, misleading, purely decorative without purpose, off-topic, unexplained, or not clearly connected to the section.
- If a page has images but very little text, flag this as a possible Image Relevance or Accessibility concern.
- Do not pretend to inspect image pixels. If visual inspection is needed, mark the category as "Needs manual review".
- The Image Relevance category must appear in category_reviews with a clear status.

Image Quality, Image Placement and Image Accuracy:
- If visual inspection is not available, mark these as "Needs manual review" when images are present.
- Do not claim an image is low-resolution, stretched or misleading unless the supplied evidence supports it.

Known rule-based issues:
{json.dumps(rule_issues, indent=2, ensure_ascii=False)}

Document image summary:
{json.dumps(image_summary, indent=2, ensure_ascii=False)}

Document profile:
{json.dumps({
    "file_name": document_profile.get("file_name"),
    "total_pages": document_profile.get("total_pages", document_profile.get("page_count")),
    "pages_parsed": document_profile.get("pages_parsed", len(document_profile.get("pages", []))),
    "metadata": document_profile.get("metadata", {}),
    "pages": compact_pages
}, indent=2, ensure_ascii=False)}

Return only valid JSON using this schema:
{{
  "overall_status": "Pass | Pass with minor issues | Needs revision | High-risk revision required",
  "quality_score": 0,
  "executive_summary": "",
  "top_recommendations": [],
  "issues": [
    {{
      "page_or_section": "",
      "category": "",
      "severity": "Critical | Major | Minor | Suggestion",
      "issue": "",
      "explanation": "",
      "recommended_fix": "",
      "evidence": ""
    }}
  ],
  "category_reviews": [
    {{
      "category": "",
      "status": "Pass | Minor issues | Major issues | Not applicable | Needs manual review",
      "notes": "",
      "examples": []
    }}
  ],
  "marketing_effectiveness": {{
    "trust_building": "",
    "educational_value": "",
    "brand_alignment": "",
    "cta_quality": "",
    "lead_generation_suitability": ""
  }},
  "accessibility_review": "",
  "final_recommendation": ""
}}
"""


def normalise_severity(severity: str) -> str:
    allowed = ["Critical", "Major", "Minor", "Suggestion"]
    severity = str(severity or "").strip()

    if severity in allowed:
        return severity

    return "Minor"


def normalise_issue(issue: dict) -> dict:
    return {
        "page_or_section": str(issue.get("page_or_section", "")).strip(),
        "category": str(issue.get("category", "")).strip(),
        "severity": normalise_severity(issue.get("severity", "Minor")),
        "issue": str(issue.get("issue", "")).strip(),
        "explanation": str(issue.get("explanation", "")).strip(),
        "recommended_fix": str(issue.get("recommended_fix", "")).strip(),
        "evidence": str(issue.get("evidence", "")).strip()
    }


def dedupe_issues(issues: list[dict]) -> list[dict]:
    seen = set()
    cleaned = []

    for issue in issues:
        item = normalise_issue(issue)

        if not item["issue"]:
            continue

        key = (
            item["page_or_section"].lower(),
            item["category"].lower(),
            item["issue"].lower()
        )

        if key not in seen:
            seen.add(key)
            cleaned.append(item)

    return cleaned


def calculate_score(issues: list[dict]) -> int:
    score = 100

    penalties = {
        "Critical": 12,
        "Major": 6,
        "Minor": 2,
        "Suggestion": 0.5
    }

    for issue in issues:
        score -= penalties.get(issue.get("severity", "Minor"), 2)

    return max(0, min(100, round(score)))


def status_from_score(score: int, issues: list[dict]) -> str:
    critical_count = sum(1 for issue in issues if issue.get("severity") == "Critical")
    major_count = sum(1 for issue in issues if issue.get("severity") == "Major")

    if critical_count >= 2:
        return "High-risk revision required"

    if critical_count == 1 or major_count >= 5:
        return "Needs revision"

    if score >= 90:
        return "Pass"

    if score >= 80:
        return "Pass with minor issues"

    if score >= 50:
        return "Needs revision"

    return "High-risk revision required"


def get_category_status(category: str, issues: list[dict], document_profile: dict) -> str:
    category_issues = [
        issue for issue in issues
        if issue.get("category", "").lower() == category.lower()
    ]

    has_images = any(
        page.get("image_count", 0) > 0
        for page in document_profile.get("pages", [])
    )

    if not category_issues:
        if category in ["Image Relevance", "Image Quality", "Image Placement", "Image Accuracy"]:
            return "Needs manual review" if has_images else "Not applicable"

        if category in ["Tables and Charts"]:
            return "Needs manual review"

        if category in ["Accessibility", "Formatting Consistency", "Spacing and Alignment"]:
            return "Needs manual review"

        return "Pass"

    if any(issue.get("severity") in ["Critical", "Major"] for issue in category_issues):
        return "Major issues"

    return "Minor issues"


def build_category_reviews(report: dict, document_profile: dict) -> list[dict]:
    issues = report.get("issues", [])
    existing_reviews = report.get("category_reviews", [])

    review_map = {}

    for review in existing_reviews:
        category = review.get("category", "")
        if category:
            review_map[category] = review

    final_reviews = []

    for category in QA_CATEGORIES:
        category_issues = [
            issue for issue in issues
            if issue.get("category", "").lower() == category.lower()
        ]

        examples = [
            f"{issue.get('page_or_section')}: {issue.get('issue')}"
            for issue in category_issues
        ][:5]

        status = get_category_status(category, issues, document_profile)

        if category in review_map:
            review = review_map[category]
            review["status"] = review.get("status") or status
            review["notes"] = review.get("notes") or default_category_notes(category, status, document_profile)
            review["examples"] = review.get("examples") or examples
        else:
            review = {
                "category": category,
                "status": status,
                "notes": default_category_notes(category, status, document_profile),
                "examples": examples
            }

        if category == "Image Relevance":
            review["notes"] = build_image_relevance_notes(status, document_profile, category_issues)

        final_reviews.append(review)

    return final_reviews


def default_category_notes(category: str, status: str, document_profile: dict) -> str:
    if status == "Pass":
        return "No significant issue detected in the parsed content."

    if status == "Not applicable":
        return "This category does not appear to apply to the parsed content."

    if status == "Needs manual review":
        return (
            "This category may require manual or visual review because Version 1 uses extracted text, "
            "page metadata and image counts rather than full visual inspection."
        )

    return "Issues were detected in this category. See the issue log for details."


def build_image_relevance_notes(status: str, document_profile: dict, image_issues: list[dict]) -> str:
    image_summary = get_document_image_summary(document_profile)
    total_pages_with_images = image_summary["total_pages_with_images"]

    if total_pages_with_images == 0:
        return "No images were detected in the parsed pages, so Image Relevance is not applicable."

    if image_issues:
        return (
            f"Images were detected on {total_pages_with_images} parsed page(s). "
            "Potential Image Relevance issues were found. Review the issue log and check the images manually before publishing."
        )

    return (
        f"Images were detected on {total_pages_with_images} parsed page(s). "
        "No clear Image Relevance issue was found from the surrounding text, but Version 1 cannot fully inspect image pixels. "
        "Manual visual review is recommended."
    )


def ensure_report_complete(report: dict, document_profile: dict, rule_issues: list[dict]) -> dict:
    report = report or {}

    model_issues = report.get("issues", [])
    all_issues = dedupe_issues(rule_issues + model_issues)

    score = calculate_score(all_issues)
    status = status_from_score(score, all_issues)

    report["issues"] = all_issues
    report["quality_score"] = score
    report["overall_status"] = status

    if not report.get("executive_summary"):
        report["executive_summary"] = (
            f"The QA review analysed {document_profile.get('pages_parsed', len(document_profile.get('pages', [])))} "
            f"page(s). {len(all_issues)} issue(s) were identified. "
            "Items marked as needing verification or manual review should be checked before publication."
        )

    if not report.get("top_recommendations"):
        fixes = []
        for issue in all_issues:
            fix = issue.get("recommended_fix", "")
            if fix and fix not in fixes:
                fixes.append(fix)
            if len(fixes) == 5:
                break

        report["top_recommendations"] = fixes or [
            "Carry out a final manual proofread before publishing.",
            "Manually review image relevance, image quality and layout before publishing.",
            "Verify factual claims and legal/compliance-sensitive statements.",
            "Check links and calls to action.",
            "Review accessibility, including alt text, contrast and reading order."
        ]

    report["category_reviews"] = build_category_reviews(report, document_profile)

    if not report.get("marketing_effectiveness"):
        report["marketing_effectiveness"] = {
            "trust_building": "Assess trust-building based on accuracy, clarity, evidence and professionalism.",
            "educational_value": "Review whether the content clearly educates the reader without unnecessary jargon.",
            "brand_alignment": "Check that brand messaging, tone, visual style and CTAs are consistent.",
            "cta_quality": "Review whether CTAs are clear, useful and placed at appropriate points.",
            "lead_generation_suitability": "The document should guide readers towards a relevant next step without being overly sales-focused."
        }

    if not report.get("accessibility_review"):
        report["accessibility_review"] = (
            "Accessibility was reviewed using extractable text, image counts, headings and rule-based checks. "
            "Alt text, tagged PDF structure, reading order and colour contrast may require manual review."
        )

    if not report.get("final_recommendation"):
        if status in ["Pass", "Pass with minor issues"]:
            report["final_recommendation"] = "Publish after minor edits"
        elif status == "Needs revision":
            report["final_recommendation"] = "Needs revision before publishing"
        else:
            report["final_recommendation"] = "Do not publish until major issues are fixed"

    return report


def review_document(document_profile: dict, rule_issues: list[dict], pages_per_batch: int = 5) -> dict:
    client, model = get_client_and_model()
    prompt = build_review_prompt(document_profile, rule_issues)

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a strict JSON API. Return only valid JSON. Do not use markdown."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2
    )

    content = completion.choices[0].message.content or ""
    report = extract_json(content)

    return ensure_report_complete(report, document_profile, rule_issues)
