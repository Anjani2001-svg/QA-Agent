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


def get_client_and_models():
    provider = get_secret("LLM_PROVIDER", "openrouter").strip().lower()

    openrouter_key = get_secret("OPENROUTER_API_KEY", "").strip()
    openai_key = get_secret("OPENAI_API_KEY", "").strip()

    if provider == "openrouter":
        api_key = openrouter_key or openai_key

        if not api_key:
            raise RuntimeError(
                "OpenRouter key missing. Add OPENROUTER_API_KEY in Streamlit Secrets."
            )

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )

        text_model = get_secret("OPENROUTER_MODEL", "deepseek/deepseek-v3.2")
        vision_model = get_secret("OPENROUTER_VISION_MODEL", "openai/gpt-4o-mini")

        return client, text_model, vision_model

    if provider == "openai":
        if not openai_key:
            raise RuntimeError(
                "OpenAI key missing. Add OPENAI_API_KEY in Streamlit Secrets."
            )

        client = OpenAI(api_key=openai_key)
        text_model = get_secret("OPENAI_MODEL", "gpt-4o-mini")
        vision_model = get_secret("OPENAI_VISION_MODEL", "gpt-4o-mini")

        return client, text_model, vision_model

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


def call_json_model(client, model: str, messages: list[dict]) -> dict:
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
            response_format={"type": "json_object"}
        )
    except Exception:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2
        )

    content = completion.choices[0].message.content or ""
    return extract_json(content)


def compact_page(page: dict) -> dict:
    return {
        "page_number": page.get("page_number"),
        "word_count": page.get("word_count", 0),
        "image_count": page.get("image_count", 0),
        "links": page.get("links", []),
        "candidate_headings": page.get("candidate_headings", []),
        "text_excerpt": page.get("text", "")[:3500]
    }


def build_text_review_prompt(
    document_profile: dict,
    rule_issues: list[dict],
    visual_issues: list[dict]
) -> str:
    compact_pages = [
        compact_page(page)
        for page in document_profile.get("pages", [])
    ]

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
- Do not duplicate issues already listed in rule-based or visual findings unless you add useful context.

Rule-based issues:
{json.dumps(rule_issues, indent=2, ensure_ascii=False)}

Visual/image review issues:
{json.dumps(visual_issues, indent=2, ensure_ascii=False)}

Document profile:
{json.dumps({
    "file_name": document_profile.get("file_name"),
    "total_pages": document_profile.get("total_pages"),
    "pages_parsed": document_profile.get("pages_parsed"),
    "visual_pages_reviewed": document_profile.get("visual_pages_reviewed", 0),
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


def build_visual_prompt(visual_page: dict) -> str:
    return f"""
You are visually reviewing one PDF page from an e-book or marketing document.

Use UK English.

Inspect the page screenshot and check:
- Image Relevance: whether images visually support the surrounding topic/content.
- Image Quality: whether images appear sharp, cropped correctly, not stretched, and professional.
- Image Placement: whether images are placed near relevant text and do not disrupt reading flow.
- Image Accuracy: whether images could mislead readers about people, settings, services, products, processes or cultural context.
- Branding: whether visuals fit the document brand/style.
- Spacing and Alignment: whether visual layout appears clean and professional.
- Accessibility: whether image-heavy content may need alt text, captions or OCR text.

Do not flag a cover image as irrelevant just because it has little text. Judge whether the visual appears relevant to the title/topic.

Page information:
{json.dumps({
    "page_number": visual_page.get("page_number"),
    "image_count": visual_page.get("image_count"),
    "word_count": visual_page.get("word_count"),
    "candidate_headings": visual_page.get("candidate_headings", []),
    "text_excerpt": visual_page.get("text_excerpt", "")
}, indent=2, ensure_ascii=False)}

Return only valid JSON:
{{
  "issues": [
    {{
      "page_or_section": "Page {visual_page.get("page_number")}",
      "category": "Image Relevance | Image Quality | Image Placement | Image Accuracy | Branding | Spacing and Alignment | Accessibility",
      "severity": "Critical | Major | Minor | Suggestion",
      "issue": "",
      "explanation": "",
      "recommended_fix": "",
      "evidence": ""
    }}
  ]
}}
"""


def review_visual_pages(client, vision_model: str, document_profile: dict) -> list[dict]:
    visual_pages = document_profile.get("visual_pages", [])

    if not visual_pages:
        document_profile["visual_review_completed"] = False
        document_profile["visual_pages_reviewed"] = 0
        return []

    visual_issues = []
    reviewed_count = 0

    for visual_page in visual_pages:
        prompt = build_visual_prompt(visual_page)
        image_data_url = visual_page.get("image_data_url")

        if not image_data_url:
            continue

        messages = [
            {
                "role": "system",
                "content": "You are a strict JSON API. Return only valid JSON. Do not use markdown."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url
                        }
                    }
                ]
            }
        ]

        try:
            result = call_json_model(client, vision_model, messages)
            issues = result.get("issues", [])

            for issue in issues:
                if issue.get("issue"):
                    visual_issues.append(issue)

            reviewed_count += 1

        except Exception as exc:
            visual_issues.append({
                "page_or_section": f"Page {visual_page.get('page_number')}",
                "category": "Image Relevance",
                "severity": "Suggestion",
                "issue": "Visual image review could not be completed",
                "explanation": (
                    "The app attempted to visually inspect this page, but the selected vision model did not complete the request."
                ),
                "recommended_fix": (
                    "Check that OPENROUTER_VISION_MODEL is set to a vision-capable model, then rerun the review."
                ),
                "evidence": str(exc)[:250]
            })

    document_profile["visual_review_completed"] = reviewed_count > 0
    document_profile["visual_pages_reviewed"] = reviewed_count

    return visual_issues


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

    base_penalties = {
        "Critical": 12,
        "Major": 6,
        "Minor": 2,
        "Suggestion": 0.5
    }

    extra_issue_penalties = {
        "Broken table of contents bookmark/reference": 4,
        "Document appears to be learner/course content rather than marketing material": 4,
        "No clear call to action detected": 3,
        "Image-only or scanned page detected": 4,
        "Broken link detected": 3,
        "Image appears unrelated to surrounding content": 4,
        "Visual image review could not be completed": 1
    }

    for issue in issues:
        severity = issue.get("severity", "Minor")
        issue_name = issue.get("issue", "")

        score -= base_penalties.get(severity, 2)
        score -= extra_issue_penalties.get(issue_name, 0)

    return max(0, min(100, round(score)))


def status_from_score(score: int, issues: list[dict]) -> str:
    critical_count = sum(
        1 for issue in issues
        if issue.get("severity") == "Critical"
    )

    major_count = sum(
        1 for issue in issues
        if issue.get("severity") == "Major"
    )

    issue_names = [
        issue.get("issue", "")
        for issue in issues
    ]

    if critical_count >= 2:
        return "High-risk revision required"

    if "Broken table of contents bookmark/reference" in issue_names and major_count >= 2:
        return "Needs revision"

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

    visual_done = document_profile.get("visual_review_completed", False)

    if not category_issues:
        if category in ["Image Relevance", "Image Quality", "Image Placement", "Image Accuracy"]:
            if not has_images:
                return "Not applicable"
            return "Pass" if visual_done else "Needs manual review"

        if category in ["Tables and Charts"]:
            return "Not applicable"

        if category in ["Accessibility", "Formatting Consistency", "Spacing and Alignment"]:
            return "Needs manual review"

        return "Pass"

    if any(issue.get("severity") in ["Critical", "Major"] for issue in category_issues):
        return "Major issues"

    return "Minor issues"


def default_category_notes(category: str, status: str, document_profile: dict) -> str:
    if status == "Pass":
        return "No significant issue detected in the parsed and visual review."

    if status == "Not applicable":
        return "This category does not appear to apply to the parsed content."

    if status == "Needs manual review":
        return (
            "This category may require manual review because not all visual or accessibility metadata can be fully inspected automatically."
        )

    return "Issues were detected in this category. See the issue log for details."


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

        review = review_map.get(category, {
            "category": category,
            "status": status,
            "notes": default_category_notes(category, status, document_profile),
            "examples": examples
        })

        review["category"] = category
        review["status"] = status
        review["examples"] = examples
        review["notes"] = review.get("notes") or default_category_notes(category, status, document_profile)

        if category == "Image Relevance":
            if document_profile.get("visual_review_completed"):
                review["notes"] = (
                    f"Visual page review completed for {document_profile.get('visual_pages_reviewed', 0)} page(s). "
                    "Image relevance was assessed using rendered page screenshots."
                )
            else:
                review["notes"] = (
                    "Image relevance could not be fully visually reviewed. Check the image manually or set a valid vision model."
                )

        final_reviews.append(review)

    return final_reviews


def ensure_report_complete(report: dict, document_profile: dict, all_input_issues: list[dict]) -> dict:
    report = report or {}

    model_issues = report.get("issues", [])
    all_issues = dedupe_issues(all_input_issues + model_issues)

    score = calculate_score(all_issues)
    status = status_from_score(score, all_issues)

    report["issues"] = all_issues
    report["quality_score"] = score
    report["overall_status"] = status

    if not report.get("executive_summary"):
        report["executive_summary"] = (
            f"The QA review analysed {document_profile.get('pages_parsed', len(document_profile.get('pages', [])))} "
            f"page(s), including visual review for {document_profile.get('visual_pages_reviewed', 0)} page(s). "
            f"{len(all_issues)} issue(s) were identified. "
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
            "Review image relevance, image quality and layout before publishing.",
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
            "Accessibility was reviewed using extractable text, image counts, rendered page screenshots and rule-based checks. "
            "Alt text, tagged PDF structure, reading order and colour contrast may still require manual review."
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
    client, text_model, vision_model = get_client_and_models()

    visual_issues = review_visual_pages(
        client=client,
        vision_model=vision_model,
        document_profile=document_profile
    )

    prompt = build_text_review_prompt(
        document_profile=document_profile,
        rule_issues=rule_issues,
        visual_issues=visual_issues
    )

    text_report = call_json_model(
        client=client,
        model=text_model,
        messages=[
            {
                "role": "system",
                "content": "You are a strict JSON API. Return only valid JSON. Do not use markdown."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return ensure_report_complete(
        report=text_report,
        document_profile=document_profile,
        all_input_issues=rule_issues + visual_issues
    )
