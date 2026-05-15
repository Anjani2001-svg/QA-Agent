 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/qa_agent.py b/qa_agent.py
new file mode 100644
index 0000000000000000000000000000000000000000..e14ca57cd91d64518997c50efa517c6929cc2a2b
--- /dev/null
+++ b/qa_agent.py
@@ -0,0 +1,322 @@
+#!/usr/bin/env python3
+"""E-book/PDF QA agent for marketing review (UK English)."""
+from __future__ import annotations
+
+import argparse
+import json
+import re
+import statistics
+from dataclasses import dataclass, asdict
+from difflib import SequenceMatcher
+from pathlib import Path
+from typing import Any, Dict, Iterable, List, Optional, Tuple
+
+try:
+    import pypdf
+except Exception as exc:  # pragma: no cover
+    raise SystemExit("Missing dependency: pypdf. Install with `pip install pypdf`.") from exc
+
+
+CATEGORIES = [
+    "Cover Page Quality", "Topic Relevance", "Target Audience Suitability", "Marketing Purpose Alignment",
+    "Accuracy of AI-Generated Content", "Content Originality", "Headings and Subheadings", "Numbering Accuracy",
+    "Table of Contents", "Page Numbering", "Headers and Footers", "Grammar and Spelling", "Tone and Readability",
+    "Repetition", "Image Relevance", "Image Quality", "Image Placement", "Image Accuracy", "Formatting Consistency",
+    "Spacing and Alignment", "Tables and Charts", "Accessibility", "Branding", "Links and Calls to Action",
+    "Legal and Compliance Risks", "Overall Readability and User Experience",
+]
+
+STATUS_VALUES = ["Pass", "Pass with minor issues", "Needs revision", "High-risk revision required"]
+CATEGORY_STATUS_VALUES = ["Pass", "Minor issues", "Major issues", "Not applicable", "Needs manual review"]
+SEVERITY_WEIGHTS = {"Critical": 15, "Major": 7, "Minor": 3, "Suggestion": 1}
+
+US_TO_UK = {
+    "color": "colour", "organize": "organise", "center": "centre", "analyze": "analyse",
+    "behavior": "behaviour", "favorite": "favourite", "optimization": "optimisation",
+}
+
+CTA_PATTERNS = [r"learn more", r"contact us", r"book (a )?demo", r"sign up", r"get started", r"download now"]
+RISK_PATTERNS = [r"guaranteed", r"risk-free", r"cure", r"100%", r"no side effects", r"financial advice"]
+HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")
+URL_RE = re.compile(r"https?://[^\s)\]>\"]+")
+
+
+@dataclass
+class Issue:
+    page_or_section: str
+    category: str
+    severity: str
+    issue: str
+    explanation: str
+    recommended_fix: str
+    evidence: str = ""
+
+
+@dataclass
+class CategoryReview:
+    category: str
+    status: str
+    notes: str
+    examples: List[str]
+
+
+@dataclass
+class PageData:
+    number: int
+    text: str
+    headings: List[str]
+    urls: List[str]
+    has_image: bool
+
+
+def normalise_ws(text: str) -> str:
+    return re.sub(r"\s+", " ", text).strip()
+
+
+def split_sentences(text: str) -> List[str]:
+    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
+
+
+def extract_pages(pdf_path: Path) -> List[PageData]:
+    reader = pypdf.PdfReader(str(pdf_path))
+    pages: List[PageData] = []
+    for idx, page in enumerate(reader.pages, start=1):
+        raw = page.extract_text() or ""
+        lines = [normalise_ws(l) for l in raw.splitlines() if normalise_ws(l)]
+        headings = [ln for ln in lines if HEADING_RE.match(ln) or (len(ln) < 90 and ln.istitle())]
+        urls = URL_RE.findall(raw)
+        has_image = bool(getattr(page, "images", []))
+        pages.append(PageData(number=idx, text=raw, headings=headings, urls=urls, has_image=has_image))
+    return pages
+
+
+def detect_toc(pages: List[PageData]) -> List[Tuple[str, int]]:
+    toc_entries: List[Tuple[str, int]] = []
+    for page in pages[: min(8, len(pages))]:
+        if "table of contents" in page.text.lower():
+            for line in page.text.splitlines():
+                m = re.search(r"(.+?)\s+\.{2,}\s*(\d+)\s*$", line.strip())
+                if m:
+                    toc_entries.append((normalise_ws(m.group(1)), int(m.group(2))))
+    return toc_entries
+
+
+def fuzzy_find_heading(h: str, pages: List[PageData]) -> Optional[int]:
+    best = (0.0, None)
+    for p in pages:
+        for ph in p.headings:
+            score = SequenceMatcher(None, h.lower(), ph.lower()).ratio()
+            if score > best[0]:
+                best = (score, p.number)
+    return best[1] if best[0] >= 0.74 else None
+
+
+def analyse(pdf_path: Path) -> Dict[str, Any]:
+    pages = extract_pages(pdf_path)
+    issues: List[Issue] = []
+    category_reviews: List[CategoryReview] = []
+
+    if not pages:
+        raise ValueError("No pages detected in PDF")
+
+    # Cover checks
+    cover = pages[0].text.lower()
+    if len(normalise_ws(pages[0].text)) < 80:
+        issues.append(Issue("Page 1", "Cover Page Quality", "Major", "Cover page has very limited text context",
+                           "Cover appears sparse, making title/topic clarity difficult.",
+                           "Ensure clear title, subtitle, brand and author/company are visible on cover."))
+
+    # ToC checks
+    toc = detect_toc(pages)
+    if toc:
+        for title, declared_page in toc:
+            actual = fuzzy_find_heading(title, pages)
+            if actual is None:
+                issues.append(Issue("Table of Contents", "Table of Contents", "Major", f"TOC entry not found: {title}",
+                                   "TOC references a heading not detected in document body.",
+                                   "Update TOC or heading text to match exactly.", evidence=f"TOC entry '{title}'"))
+            elif abs(actual - declared_page) >= 2:
+                issues.append(Issue("Table of Contents", "Table of Contents", "Major", f"TOC page mismatch for '{title}'",
+                                   f"TOC lists page {declared_page}, but closest matching heading appears on page {actual}.",
+                                   "Regenerate TOC page numbers after final layout changes."))
+    else:
+        category_reviews.append(CategoryReview("Table of Contents", "Needs manual review", "No machine-detected TOC entries.", []))
+
+    # Page numbering heuristic
+    if len(pages) > 3:
+        footer_nums = []
+        for p in pages:
+            lines = [normalise_ws(x) for x in p.text.splitlines() if normalise_ws(x)]
+            if lines and re.fullmatch(r"\d{1,4}", lines[-1]):
+                footer_nums.append((p.number, int(lines[-1])))
+        if footer_nums and any((b - a) != 1 for (_, a), (_, b) in zip(footer_nums, footer_nums[1:])):
+            issues.append(Issue("Multiple pages", "Page Numbering", "Major", "Visible page numbering appears non-sequential",
+                               "Detected footer numbers do not increment consistently.",
+                               "Check footer page numbering fields and section breaks."))
+
+    # Repetition + readability + grammar markers
+    paragraphs = []
+    for p in pages:
+        for para in re.split(r"\n\s*\n", p.text):
+            n = normalise_ws(para)
+            if len(n) > 90:
+                paragraphs.append((p.number, n))
+
+        sentences = split_sentences(p.text)
+        long_sentences = [s for s in sentences if len(s.split()) > 38]
+        if long_sentences:
+            issues.append(Issue(f"Page {p.number}", "Tone and Readability", "Minor", "Overly long sentences reduce readability",
+                               "Some sentences are lengthy for general-public marketing material.",
+                               "Split long sentences into shorter statements with clearer signposting.",
+                               evidence=long_sentences[0][:180]))
+
+        for us, uk in US_TO_UK.items():
+            if re.search(rf"\b{re.escape(us)}\b", p.text, re.IGNORECASE):
+                issues.append(Issue(f"Page {p.number}", "Grammar and Spelling", "Minor", f"American spelling detected: '{us}'",
+                                   "Document requires UK English consistency.",
+                                   f"Replace '{us}' with '{uk}' where appropriate."))
+
+        for pat in RISK_PATTERNS:
+            m = re.search(pat, p.text, re.IGNORECASE)
+            if m:
+                issues.append(Issue(f"Page {p.number}", "Legal and Compliance Risks", "Major", "Potentially risky claim language",
+                                   "Absolute or sensitive claim language may need legal/compliance substantiation.",
+                                   "Add evidence, qualification, and disclaimers; route through legal review.", evidence=m.group(0)))
+
+    for i, (p1, t1) in enumerate(paragraphs):
+        for p2, t2 in paragraphs[i + 1 : i + 25]:
+            sim = SequenceMatcher(None, t1[:500].lower(), t2[:500].lower()).ratio()
+            if sim > 0.93:
+                issues.append(Issue(f"Pages {p1} and {p2}", "Repetition", "Minor", "Possible duplicated paragraph",
+                                   "Very high similarity between paragraphs indicates likely duplication/filler.",
+                                   "Deduplicate or rewrite one of the repeated passages.", evidence=t1[:140]))
+                break
+
+    # Link + CTA
+    all_urls = [(p.number, u) for p in pages for u in p.urls]
+    if not all_urls:
+        issues.append(Issue("Document-wide", "Links and Calls to Action", "Major", "No visible URLs detected",
+                           "Marketing e-books usually need at least one clear next-step CTA.",
+                           "Add clear CTA with trackable URL, QR code, or contact channel."))
+    cta_hits = sum(bool(re.search(pat, p.text, re.IGNORECASE)) for p in pages for pat in CTA_PATTERNS)
+    if cta_hits == 0:
+        issues.append(Issue("Document-wide", "Marketing Purpose Alignment", "Major", "No clear call-to-action language detected",
+                           "Content may educate readers but does not guide them to a next step.",
+                           "Add context-aware CTA blocks near key conversion points."))
+
+    # Accessibility manual limitations
+    issues.append(Issue("Document metadata", "Accessibility", "Suggestion", "Alt text/tag tree verification is limited",
+                       "Programmatic extraction cannot fully validate tagged PDF reading order and alt text completeness.",
+                       "Run manual accessibility audit with Adobe Acrobat Accessibility Checker and WCAG review."))
+
+    # Category rollup
+    by_cat: Dict[str, List[Issue]] = {c: [] for c in CATEGORIES}
+    for it in issues:
+        by_cat.setdefault(it.category, []).append(it)
+    for cat in CATEGORIES:
+        items = by_cat.get(cat, [])
+        if not items:
+            status, note = "Pass", "No material issues detected by automated checks."
+        else:
+            worst = "Suggestion"
+            order = ["Suggestion", "Minor", "Major", "Critical"]
+            worst = sorted((i.severity for i in items), key=lambda s: order.index(s))[-1]
+            status = "Major issues" if worst in {"Major", "Critical"} else "Minor issues"
+            note = f"{len(items)} issue(s) flagged."
+        category_reviews.append(CategoryReview(cat, status, note, [i.issue for i in items[:3]]))
+
+    score = max(0, 100 - sum(SEVERITY_WEIGHTS[i.severity] for i in issues))
+    if any(i.severity == "Critical" for i in issues):
+        overall = "High-risk revision required"
+    elif score >= 85:
+        overall = "Pass with minor issues" if issues else "Pass"
+    elif score >= 60:
+        overall = "Needs revision"
+    else:
+        overall = "High-risk revision required"
+
+    top_fixes = [i.recommended_fix for i in sorted(issues, key=lambda x: SEVERITY_WEIGHTS[x.severity], reverse=True)[:5]]
+
+    report = {
+        "overall_status": overall,
+        "quality_score": int(score),
+        "executive_summary": "Automated marketing QA completed with focus on content quality, structure, compliance risk and conversion readiness.",
+        "top_recommendations": top_fixes,
+        "issues": [asdict(i) for i in issues],
+        "category_reviews": [asdict(c) for c in category_reviews],
+        "marketing_effectiveness": {
+            "trust_building": "Moderate; depends on factual substantiation and consistency of claims.",
+            "educational_value": "Assessed from readability and structure; manual subject-matter validation may still be required.",
+            "brand_alignment": "Evaluate consistency of brand mentions, style and voice in flagged branding/category notes.",
+            "cta_quality": "Derived from detected CTA phrases/links and placement indicators.",
+            "lead_generation_suitability": "Higher when CTAs are explicit, specific and repeated at natural decision points.",
+        },
+        "accessibility_review": "Automated checks cover partial indicators only. Manual assistive-technology and tagged-PDF validation is still required.",
+        "final_recommendation": (
+            "Ready to publish" if overall == "Pass" else
+            "Publish after minor edits" if overall == "Pass with minor issues" else
+            "Needs revision before publishing" if overall == "Needs revision" else
+            "Do not publish until major issues are fixed"
+        ),
+    }
+    return report
+
+
+def to_markdown(report: Dict[str, Any]) -> str:
+    lines = []
+    lines.append("# E-book QA Report")
+    lines.append("\n## 1. Executive Summary")
+    lines.append(f"- **Overall QA status:** {report['overall_status']}")
+    lines.append(f"- **Overall quality score:** {report['quality_score']}/100")
+    lines.append(f"- **Summary:** {report['executive_summary']}")
+    lines.append("- **Top 5 recommended fixes:**")
+    for rec in report["top_recommendations"][:5]:
+        lines.append(f"  - {rec}")
+
+    lines.append("\n## 2. Issue Log")
+    lines.append("| Page/Section | Category | Severity | Issue | Explanation | Recommended Fix |")
+    lines.append("|---|---|---|---|---|---|")
+    for i in report["issues"]:
+        lines.append(f"| {i['page_or_section']} | {i['category']} | {i['severity']} | {i['issue']} | {i['explanation']} | {i['recommended_fix']} |")
+
+    lines.append("\n## 3. Category-by-Category Review")
+    for c in report["category_reviews"]:
+        lines.append(f"### {c['category']}")
+        lines.append(f"- **Status:** {c['status']}")
+        lines.append(f"- **Notes:** {c['notes']}")
+        if c["examples"]:
+            lines.append("- **Key examples:**")
+            for e in c["examples"]:
+                lines.append(f"  - {e}")
+
+    lines.append("\n## 4. Marketing Effectiveness Review")
+    m = report["marketing_effectiveness"]
+    lines.append(f"- **Build trust:** {m['trust_building']}")
+    lines.append(f"- **Educates clearly:** {m['educational_value']}")
+    lines.append(f"- **Offer/brand connection:** {m['brand_alignment']}")
+    lines.append(f"- **CTA placement/quality:** {m['cta_quality']}")
+    lines.append(f"- **Lead generation suitability:** {m['lead_generation_suitability']}")
+
+    lines.append("\n## 5. Accessibility Review")
+    lines.append(report["accessibility_review"])
+
+    lines.append("\n## 6. Final Recommendation")
+    lines.append(f"**{report['final_recommendation']}**")
+    return "\n".join(lines) + "\n"
+
+
+def main() -> None:
+    parser = argparse.ArgumentParser(description="QA agent for e-book/PDF marketing review.")
+    parser.add_argument("pdf", type=Path, help="Path to input PDF")
+    parser.add_argument("--json-out", type=Path, default=Path("qa_report.json"))
+    parser.add_argument("--md-out", type=Path, default=Path("qa_report.md"))
+    args = parser.parse_args()
+
+    report = analyse(args.pdf)
+    args.json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
+    args.md_out.write_text(to_markdown(report), encoding="utf-8")
+    print(f"Generated: {args.json_out} and {args.md_out}")
+
+
+if __name__ == "__main__":
+    main()
 
EOF
)
