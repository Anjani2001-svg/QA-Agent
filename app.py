import json
import shutil
import tempfile

import streamlit as st

from services.pdf_parser import parse_pdf
from services.rule_checks import run_rule_checks
from services.llm_reviewer import review_document
from services.report_builder import build_markdown_report
from services.word_report_builder import build_word_report


st.set_page_config(
    page_title="E-book / PDF Marketing QA Agent",
    page_icon="📘",
    layout="wide"
)

st.title("E-book / PDF Marketing QA Agent")
st.write("Upload an e-book or PDF and get a QA report.")

uploaded_file = st.file_uploader(
    "Upload PDF",
    type=["pdf"],
    accept_multiple_files=False
)

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        uploaded_file.seek(0)
        shutil.copyfileobj(uploaded_file, tmp)
        pdf_path = tmp.name

    st.success(f"Uploaded: {uploaded_file.name}")

    validate_links = st.checkbox(
        "Validate links",
        value=False,
        help="Turn this on only if you want the app to test links. It may slow down the review."
    )

    if st.button("Run QA Review", type="primary"):
        try:
            with st.spinner("Parsing PDF..."):
                document_profile = parse_pdf(pdf_path)

            with st.spinner("Running rule-based checks..."):
                rule_issues = run_rule_checks(
                    document_profile,
                    validate_links=validate_links
                )

            with st.spinner("Running QA reviewer with DeepSeek V3.2..."):
                qa_json = review_document(document_profile, rule_issues)

            markdown_report = build_markdown_report(qa_json)
            word_report = build_word_report(qa_json)

            st.subheader("QA Report")
            st.markdown(markdown_report)

            st.download_button(
                label="Download Markdown Report",
                data=markdown_report,
                file_name="qa_report.md",
                mime="text/markdown"
            )

            st.download_button(
                label="Download JSON Report",
                data=json.dumps(qa_json, indent=2, ensure_ascii=False),
                file_name="qa_report.json",
                mime="application/json"
            )

            st.download_button(
                label="Download Word Report",
                data=word_report,
                file_name="qa_report.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

        except Exception as exc:
            st.error("The QA review failed.")
            st.exception(exc)
