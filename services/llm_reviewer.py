import json
import os
from openai import OpenAI
from dotenv import load_dotenv


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


def get_client_and_model():
    """
    Supports both OpenRouter and direct OpenAI.

    For OpenRouter, use:
    LLM_PROVIDER=openrouter
    OPENROUTER_API_KEY=your_key_here
    OPENROUTER_MODEL=openai/gpt-4o-mini

    For OpenAI, use:
    LLM_PROVIDER=openai
    OPENAI_API_KEY=your_key_here
    OPENAI_MODEL=gpt-4o-mini
    """

    provider = os.getenv("LLM_PROVIDER", "").strip().lower()

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    # Auto-detect OpenRouter if the key starts with sk-or-
    if not provider:
        if openrouter_key or openai_key.startswith("sk-or-"):
            provider = "openrouter"
        else:
            provider = "openai"

    if provider == "openrouter":
        api_key = openrouter_key or openai_key

        if not api_key:
            raise RuntimeError(
                "OpenRouter key missing. Add OPENROUTER_API_KEY to your .env file."
            )

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )

        model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        return client, model

    if provider == "openai":
        if not openai_key:
            raise RuntimeError(
                "OpenAI key missing. Add OPENAI_API_KEY to your .env file."
            )

        client = OpenAI(api_key=openai_key)
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
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


def build_review_prompt(document_profile: dict, rule_issues: list[dict]) -> str:
    compact_pages = []

    for page in document_profile["pages"]:
        compact_pages.append({
            "page_number": page.get("page_number"),
            "word_count": page.get("word_count"),
            "image_count": page.get("image_count"),
            "links": page.get("links", []),
            "candidate_headings": page.get("candidate_headings", []),
            "text_excerpt": page.get("text", "")[:3500]
        })

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

Known rule-based issues:
{json.dumps(rule_issues, indent=2, ensure_ascii=False)}

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
    return extract_json(content)