def clean_cell(value) -> str:
    text = str(value or "")
    text = text.replace("|", "\\|")
    text = text.replace("\n", " ")
    return text.strip()


def build_markdown_report(report: dict) -> str:
    lines = []

    lines.append("# E-book / PDF Marketing QA Report\n")

    lines.append("## 1. Executive Summary\n")
    lines.append(f"**Overall QA status:** {report.get('overall_status', '')}  ")
    lines.append(f"**Overall quality score:** {report.get('quality_score', '')}/100\n")
    lines.append(report.get("executive_summary", ""))

    lines.append("\n### Top 5 Recommended Fixes\n")

    recommendations = report.get("top_recommendations", [])
    if recommendations:
        for item in recommendations[:5]:
            lines.append(f"- {item}")
    else:
        lines.append("- No major recommendations were generated.")

    lines.append("\n## 2. Issue Log\n")
    lines.append("| Page/Section | Category | Severity | Issue | Explanation | Recommended Fix |")
    lines.append("|---|---|---|---|---|---|")

    issues = report.get("issues", [])

    if issues:
        for issue in issues:
            lines.append(
                "| {page} | {category} | {severity} | {issue} | {explanation} | {fix} |".format(
                    page=clean_cell(issue.get("page_or_section")),
                    category=clean_cell(issue.get("category")),
                    severity=clean_cell(issue.get("severity")),
                    issue=clean_cell(issue.get("issue")),
                    explanation=clean_cell(issue.get("explanation")),
                    fix=clean_cell(issue.get("recommended_fix"))
                )
            )
    else:
        lines.append("| Whole document | General | Pass | No issues found | No significant issues were identified. | No action required. |")

    lines.append("\n## 3. Category-by-Category Review\n")

    for category in report.get("category_reviews", []):
        lines.append(f"### {category.get('category', '')}\n")
        lines.append(f"**Status:** {category.get('status', '')}\n")
        lines.append(f"**Notes:** {category.get('notes', '')}\n")

        examples = category.get("examples", [])

        if examples:
            lines.append("**Key examples:**")
            for example in examples:
                lines.append(f"- {example}")

        lines.append("")

    lines.append("\n## 4. Marketing Effectiveness Review\n")

    marketing = report.get("marketing_effectiveness", {})

    lines.append(f"**Trust-building:** {marketing.get('trust_building', '')}  ")
    lines.append(f"**Educational value:** {marketing.get('educational_value', '')}  ")
    lines.append(f"**Brand alignment:** {marketing.get('brand_alignment', '')}  ")
    lines.append(f"**CTA quality:** {marketing.get('cta_quality', '')}  ")
    lines.append(f"**Lead-generation suitability:** {marketing.get('lead_generation_suitability', '')}")

    lines.append("\n## 5. Accessibility Review\n")
    lines.append(report.get("accessibility_review", ""))

    lines.append("\n## 6. Final Recommendation\n")
    lines.append(f"**{report.get('final_recommendation', '')}**")

    return "\n".join(lines)
