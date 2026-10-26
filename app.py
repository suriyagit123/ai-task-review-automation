"""
AI-Powered Task Review Automation System.
Streamlit Web Interface.
"""

import os
import sys
from datetime import datetime, date, timedelta
import pandas as pd
import streamlit as st

# Ensure project root is in Python module search path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.models import Task, RequirementItem, CandidateSubmission, ReviewSession, RequirementFinding
from src.database import Database
from src.file_validator import validate_file, extract_safe_preview, sanitize_filename
from src.ai_engine import AIReviewService, LocalRuleReviewEngine, OllamaReviewEngine
from src.followup import (
    validate_next_review_date,
    generate_followup_summary,
    simulate_send_notification,
    send_followup_email,
    get_smtp_config,
    validate_recipient_email,
    load_project_env
)
from src.excel_export import export_review_to_excel

# Ensure .env from project root is loaded into environment immediately
load_project_env()

# --- Page Configuration ---
st.set_page_config(
    page_title="Task Review Automation",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Initialize Database ---
db = Database()
# Seed fictional sample data on first run
db.seed_sample_data()

# --- Custom Styling ---
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 14px 18px;
        border-left: 4px solid #1E88E5;
        margin-bottom: 12px;
    }
    .status-completed {
        background-color: #d4edda;
        color: #155724;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 6px;
        display: inline-block;
    }
    .status-partial {
        background-color: #fff3cd;
        color: #856404;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 6px;
        display: inline-block;
    }
    .status-unverified {
        background-color: #cce5ff;
        color: #004085;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 6px;
        display: inline-block;
    }
    .status-missing {
        background-color: #f8d7da;
        color: #721c24;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 6px;
        display: inline-block;
    }
    .badge-high {
        background-color: #dc3545;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.82em;
    }
    .badge-med {
        background-color: #fd7e14;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.82em;
    }
    .badge-low {
        background-color: #6c757d;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.82em;
    }
</style>
""", unsafe_allow_html=True)


def status_badge_html(status: str) -> str:
    s = (status or "").strip()
    if s == "Completed":
        return '<span class="status-completed">✓ Completed</span>'
    elif s == "Partially Completed":
        return '<span class="status-partial">⚠ Partially Completed</span>'
    elif s == "Needs Verification":
        return '<span class="status-unverified">🔍 Needs Verification</span>'
    elif s == "Missing":
        return '<span class="status-missing">✗ Missing</span>'
    return f'<span>{s}</span>'


def priority_badge_html(priority: str) -> str:
    p = (priority or "Medium").capitalize()
    if p == "High":
        return '<span class="badge-high">HIGH</span>'
    elif p == "Low":
        return '<span class="badge-low">LOW</span>'
    return '<span class="badge-med">MEDIUM</span>'


# --- Sidebar Navigation ---
st.sidebar.title("⚖️ Task Review System")
st.sidebar.caption("AI-Powered Candidate Task Review & Gap Automation")

pages = [
    "📊 Dashboard",
    "📝 Task Requirements (Module 1)",
    "📤 Candidate Submission (Module 2)",
    "🤖 AI Review & Gap Analysis (Module 3)",
    "✍️ Reviewer Approval & Feedback (Module 5)",
    "📜 Review History & Excel Export (Module 6)",
    "📅 Next Review & Follow-Up (Module 7)",
    "⚙️ AI Model & System Settings"
]

selected_page = st.sidebar.radio("Navigate to Module:", pages)

# Sidebar Quick Status
st.sidebar.markdown("---")
st.sidebar.markdown("**System Health & Mode**")
st.sidebar.success("● Database: SQLite Connected")
ollama_check = OllamaReviewEngine().is_available()
if ollama_check[0]:
    st.sidebar.success("● Ollama Server: Online")
else:
    st.sidebar.info("● Local Smart Engine: Active (Offline)")

st.sidebar.markdown("---")
st.sidebar.caption("Human-in-the-Loop Architecture • No API keys required")


# ==============================================================================
# PAGE 1: DASHBOARD
# ==============================================================================
if selected_page == "📊 Dashboard":
    st.title("📊 Task Review & Automation Dashboard")
    st.write(
        "Welcome to the **AI-Powered Task Review Automation System**. "
        "This platform automates technical candidate evaluations, flags requirement gaps, "
        "and guides reviewers through actionable human-in-the-loop sign-offs."
    )

    tasks = db.get_tasks()
    submissions = db.get_all_submissions()
    reviews = db.get_all_reviews()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Defined Tasks", len(tasks))
    with col2:
        st.metric("Total Submissions", len(submissions))
    with col3:
        st.metric("Reviews Completed", len(reviews))
    with col4:
        pending = sum(1 for r in reviews if r.get("status") in ["Draft", "Needs Work"])
        st.metric("Pending Action / Drafts", pending)

    st.markdown("---")

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("Recent Review Activity")
        if reviews:
            rev_df = pd.DataFrame(reviews)[[
                "id", "task_title", "candidate_name", "reviewer_name", "status", "next_review_date", "created_at"
            ]].rename(columns={
                "id": "Review ID",
                "task_title": "Task",
                "candidate_name": "Candidate",
                "reviewer_name": "Reviewer",
                "status": "Status",
                "next_review_date": "Next Review",
                "created_at": "Reviewed On"
            })
            st.dataframe(rev_df, use_container_width=True, hide_index=True)
        else:
            st.info("No reviews conducted yet. Go to **AI Review & Gap Analysis** to start one.")

    with col_right:
        st.subheader("Task Completion Status Distribution")
        if reviews:
            total_c = sum(r.get("completed_count") or 0 for r in reviews)
            total_p = sum(r.get("partial_count") or 0 for r in reviews)
            total_m = sum(r.get("missing_count") or 0 for r in reviews)
            total_u = sum(r.get("unverified_count") or 0 for r in reviews)

            status_summary_df = pd.DataFrame({
                "Status": ["Completed", "Partially Completed", "Needs Verification", "Missing"],
                "Count": [total_c, total_p, total_u, total_m]
            })
            st.bar_chart(status_summary_df.set_index("Status"))
        else:
            st.info("Data chart will appear once reviews are performed.")

    st.markdown("---")
    st.subheader("💡 How This Automation Protects Decision Integrity")
    cols = st.columns(3)
    with cols[0]:
        st.markdown("""
        **1. Verification over Claims**
        The engine strictly checks code and test outputs. Candidate claims in text descriptions without supporting evidence are flagged as **Needs Verification**, not Completed.
        """)
    with cols[1]:
        st.markdown("""
        **2. Safe File Inspection**
        Candidate code is checked via static analysis and text inspection. **Zero code execution** occurs on your machine, eliminating security vulnerabilities.
        """)
    with cols[2]:
        st.markdown("""
        **3. Human-in-the-Loop**
        AI acts purely as an assistive analyst. Final approval, hiring decisions, and requirement overrides remain 100% in reviewer control.
        """)


# ==============================================================================
# PAGE 2: TASK REQUIREMENTS (MODULE 1)
# ==============================================================================
elif selected_page == "📝 Task Requirements (Module 1)":
    st.title("📝 Module 1: Task Requirements (Source of Truth)")
    st.write(
        "Define the exact task requirements, expected modules, and acceptance criteria. "
        "The system strictly preserves these specifications as the immutable standard against which submissions are evaluated."
    )

    tab_create, tab_view = st.tabs(["➕ Define New Task", "📋 View Existing Tasks"])

    with tab_create:
        with st.form("create_task_form"):
            st.subheader("Task Specification Form")
            title = st.text_input("Task Title *", placeholder="e.g. User Authentication & RBAC REST API")
            description = st.text_area(
                "Original Task Description *",
                placeholder="Explain the background, goals, and problem statement...",
                height=100
            )

            col1, col2 = st.columns(2)
            with col1:
                expected_modules = st.text_input(
                    "Expected Modules & Features",
                    placeholder="e.g. auth_service, token_manager, models, routes/api, test_suite"
                )
                expected_output = st.text_input(
                    "Expected Output Deliverables",
                    placeholder="e.g. Working API service, automated test suite, execution log"
                )
            with col2:
                submission_instructions = st.text_area(
                    "Submission Instructions",
                    placeholder="e.g. Submit code files, test logs with pytest, and README...",
                    height=95
                )

            st.markdown("#### Individual Requirements & Acceptance Criteria")
            st.caption("Define specific measurable items that AI will evaluate one by one.")

            req_count = st.number_input("Number of requirements to define", min_value=1, max_value=10, value=3, step=1)
            req_data = []

            for i in range(int(req_count)):
                st.markdown(f"**Requirement #{i+1}**")
                rc1, rc2, rc3 = st.columns([1, 2, 1])
                with rc1:
                    code = st.text_input(f"Code #{i+1}", value=f"REQ-{i+1}", key=f"req_code_{i}")
                with rc2:
                    rtitle = st.text_input(f"Requirement Title #{i+1}", placeholder="e.g. Bcrypt Hashing", key=f"req_title_{i}")
                with rc3:
                    rpriority = st.selectbox(f"Priority #{i+1}", ["High", "Medium", "Low"], index=1, key=f"req_prio_{i}")

                rdesc = st.text_input(f"Requirement Description #{i+1}", placeholder="Detailed expectation...", key=f"req_desc_{i}")
                rcrit = st.text_input(f"Acceptance Criteria #{i+1}", placeholder="Specific condition to satisfy...", key=f"req_crit_{i}")
                req_data.append((code, rtitle, rdesc, rcrit, rpriority))
                st.markdown("---")

            submitted = st.form_submit_button("💾 Save Task to Database", use_container_width=True)
            if submitted:
                if not title.strip() or not description.strip():
                    st.error("Please provide both Task Title and Original Task Description.")
                else:
                    new_task = Task(
                        title=title.strip(),
                        description=description.strip(),
                        expected_modules=expected_modules.strip(),
                        expected_output=expected_output.strip(),
                        submission_instructions=submission_instructions.strip()
                    )
                    items = []
                    for code, rtitle, rdesc, rcrit, rpriority in req_data:
                        if rtitle.strip():
                            items.append(RequirementItem(
                                req_code=code.strip(),
                                title=rtitle.strip(),
                                description=rdesc.strip(),
                                acceptance_criteria=rcrit.strip(),
                                priority=rpriority
                            ))
                    new_task.requirements = items
                    task_id = db.create_task(new_task)
                    st.success(f"✓ Task '{new_task.title}' saved successfully with ID #{task_id} and {len(items)} requirements!")
                    st.rerun()

    with tab_view:
        tasks = db.get_tasks()
        if not tasks:
            st.info("No tasks recorded yet.")
        else:
            for t in tasks:
                with st.expander(f"📌 Task #{t.id}: {t.title} ({len(t.requirements)} requirements)"):
                    st.markdown(f"**Description:** {t.description}")
                    st.markdown(f"**Expected Modules:** `{t.expected_modules or 'Not specified'}`")
                    st.markdown(f"**Expected Output:** `{t.expected_output or 'Not specified'}`")
                    st.markdown(f"**Submission Instructions:** {t.submission_instructions or 'Not specified'}")
                    st.markdown("**Requirements Specification:**")
                    r_df = pd.DataFrame([{
                        "Code": r.req_code,
                        "Title": r.title,
                        "Description": r.description,
                        "Acceptance Criteria": r.acceptance_criteria,
                        "Priority": r.priority
                    } for r in t.requirements])
                    st.dataframe(r_df, use_container_width=True, hide_index=True)


# ==============================================================================
# PAGE 3: CANDIDATE SUBMISSION (MODULE 2)
# ==============================================================================
elif selected_page == "📤 Candidate Submission (Module 2)":
    st.title("📤 Module 2: Candidate Submission")
    st.write(
        "Enter or upload the candidate's submitted work, test results, and implementation artifacts. "
        "Uploaded files are inspected safely for text and code structures without automatic execution."
    )

    tasks = db.get_tasks()
    if not tasks:
        st.warning("Please define at least one Task in Module 1 first.")
    else:
        task_options = {f"Task #{t.id}: {t.title}": t.id for t in tasks}
        selected_task_label = st.selectbox("Select Associated Task *", list(task_options.keys()))
        selected_task_id = task_options[selected_task_label]
        target_task = db.get_task_by_id(selected_task_id)

        st.info(f"Submitting for **{target_task.title}** ({len(target_task.requirements)} requirements to satisfy)")

        with st.form("submission_form"):
            col1, col2 = st.columns(2)
            with col1:
                candidate_id = st.text_input("Candidate ID *", placeholder="e.g. CAND-9102")
                candidate_name = st.text_input("Candidate Name *", placeholder="e.g. Jordan Smith")
            with col2:
                submission_title = st.text_input("Submission Title *", placeholder="e.g. Jordan S - Auth & RBAC API v1")
                repo_url = st.text_input("Repository URL (Optional)", placeholder="e.g. https://github.com/candidate/project-repo")

            description = st.text_area(
                "Description of Completed Work (Candidate Claims) *",
                placeholder="What did the candidate claim was done? (e.g. Implemented auth, added tests, set up tokens...)",
                height=110
            )

            evidence_text = st.text_area(
                "Submission Evidence (Code Excerpts, Test Runs, Logs) *",
                placeholder="Paste code snippets, terminal test output (e.g. pytest log), or text descriptions of test cases...",
                height=180
            )

            st.markdown("#### Safe File Uploads (Optional)")
            st.caption("Upload code, config, logs, or documents (.py, .js, .json, .md, .txt, .pdf, .png). Max 5MB per file. No code is executed.")
            uploaded_files = st.file_uploader(
                "Choose project files",
                accept_multiple_files=True,
                type=["py", "js", "ts", "json", "txt", "md", "csv", "sql", "pdf", "png", "jpg", "xlsx"]
            )

            submitted = st.form_submit_button("📥 Register Candidate Submission", use_container_width=True)

            if submitted:
                if not candidate_id.strip() or not candidate_name.strip() or not submission_title.strip() or not description.strip():
                    st.error("Please fill in Candidate ID, Candidate Name, Submission Title, and Description.")
                else:
                    processed_files = []
                    has_file_errors = False
                    if uploaded_files:
                        for uf in uploaded_files:
                            content = uf.read()
                            is_valid, err = validate_file(uf.name, content)
                            if not is_valid:
                                st.error(f"Error in file '{uf.name}': {err}")
                                has_file_errors = True
                                break
                            preview_info = extract_safe_preview(uf.name, content)
                            processed_files.append(preview_info)

                    if not has_file_errors:
                        sub = CandidateSubmission(
                            task_id=selected_task_id,
                            candidate_id=candidate_id.strip(),
                            candidate_name=candidate_name.strip(),
                            submission_title=submission_title.strip(),
                            description=description.strip(),
                            evidence_text=evidence_text.strip(),
                            repo_url=repo_url.strip(),
                            uploaded_files=processed_files
                        )
                        sub_id = db.create_submission(sub)
                        st.success(f"✓ Submission #{sub_id} for candidate {sub.candidate_name} ({sub.candidate_id}) saved successfully!")
                        st.rerun()

        # Display previous submissions for this task
        st.markdown("---")
        st.subheader("Existing Submissions for Selected Task")
        subs = db.get_submissions_for_task(selected_task_id)
        if not subs:
            st.write("No submissions yet for this task.")
        else:
            for s in subs:
                with st.expander(f"📄 Submission #{s.id}: {s.submission_title} by {s.candidate_name} ({s.candidate_id})"):
                    st.markdown(f"**Submitted At:** {s.submitted_at}")
                    st.markdown(f"**Repository:** `{s.repo_url or 'None provided'}`")
                    st.markdown(f"**Description:** {s.description}")
                    if s.uploaded_files:
                        st.markdown(f"**Uploaded Files ({len(s.uploaded_files)}):** {', '.join([f['filename'] for f in s.uploaded_files])}")
                    if s.evidence_text:
                        st.code(s.evidence_text[:600] + ("..." if len(s.evidence_text) > 600 else ""), language="python")


# ==============================================================================
# PAGE 4: AI REVIEW & GAP ANALYSIS (MODULE 3 & 4)
# ==============================================================================
elif selected_page == "🤖 AI Review & Gap Analysis (Module 3)":
    st.title("🤖 Module 3 & 4: AI Review & Gap Analysis Dashboard")
    st.write(
        "Evaluate candidate submission evidence directly against the original task requirements. "
        "The engine distinguishes **verified evidence** from **unverified claims** and highlights missing or unverified criteria."
    )

    tasks = db.get_tasks()
    if not tasks:
        st.warning("No tasks available. Please create a task first.")
    else:
        col_t, col_s = st.columns(2)
        with col_t:
            task_options = {f"Task #{t.id}: {t.title}": t.id for t in tasks}
            sel_task_label = st.selectbox("Select Task to Review", list(task_options.keys()))
            sel_task_id = task_options[sel_task_label]
            selected_task = db.get_task_by_id(sel_task_id)

        subs = db.get_submissions_for_task(sel_task_id)
        with col_s:
            if not subs:
                st.warning("No submissions found for this task. Submit one in Module 2 first.")
                selected_sub = None
            else:
                sub_options = {f"Sub #{s.id}: {s.candidate_name} ({s.candidate_id}) - {s.submission_title}": s.id for s in subs}
                sel_sub_label = st.selectbox("Select Candidate Submission", list(sub_options.keys()))
                selected_sub_id = sub_options[sel_sub_label]
                selected_sub = db.get_submission_by_id(selected_sub_id)

        if selected_task and selected_sub:
            st.markdown("---")
            col_ai1, col_ai2 = st.columns([2, 1])
            with col_ai1:
                engine_choice = st.selectbox(
                    "Select AI Review Engine",
                    [
                        "Local Smart Analyzer (Default, Built-in, No API key needed)",
                        "Ollama Local LLM (llama3 / mistral)"
                    ]
                )
            with col_ai2:
                st.write("")
                st.write("")
                run_review = st.button("🚀 Run AI Gap Analysis", type="primary", use_container_width=True)

            # Store active analysis in session state
            session_key = f"analysis_{selected_task.id}_{selected_sub.id}"

            if run_review:
                with st.spinner("Analyzing requirements against verified submission evidence..."):
                    engine = AIReviewService.get_engine(engine_choice)
                    findings, summary_text = engine.review(selected_task, selected_sub)
                    st.session_state[session_key] = {
                        "findings": findings,
                        "summary": summary_text,
                        "engine_used": engine_choice,
                        "task_id": selected_task.id,
                        "submission_id": selected_sub.id
                    }
                    st.success("✓ AI Review & Gap Analysis complete!")

            if session_key in st.session_state:
                res = st.session_state[session_key]
                findings: list[RequirementFinding] = res["findings"]
                summary_text = res["summary"]

                st.markdown("### 📊 Review Metrics & Status Breakdown")
                tot = len(findings)
                c_cnt = sum(1 for f in findings if f.status == "Completed")
                p_cnt = sum(1 for f in findings if f.status == "Partially Completed")
                u_cnt = sum(1 for f in findings if f.status == "Needs Verification")
                m_cnt = sum(1 for f in findings if f.status == "Missing")

                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Total Requirements", tot)
                m2.metric("✓ Completed", c_cnt)
                m3.metric("⚠ Partially Done", p_cnt)
                m4.metric("🔍 Needs Verification", u_cnt)
                m5.metric("✗ Missing", m_cnt)

                st.markdown("---")
                st.markdown("### 📋 Requirement-by-Requirement Gap Report")

                for idx, f in enumerate(findings, start=1):
                    with st.expander(f"#{idx} [{f.req_code}] - {f.original_requirement[:50]}... | Status: {f.status}", expanded=True):
                        st.markdown(f"**Original Requirement:** {f.original_requirement}")
                        st.markdown(f"**Expected Result:** `{f.expected_result}`")

                        col_f1, col_f2 = st.columns(2)
                        with col_f1:
                            st.markdown(f"**Status:** {status_badge_html(f.status)}", unsafe_allow_html=True)
                            st.markdown(f"**Priority:** {priority_badge_html(f.priority)}", unsafe_allow_html=True)
                            st.markdown(f"**Evidence Found in Submission:**\n> {f.evidence_found}")
                        with col_f2:
                            st.markdown(f"**Identified Gap:**\n> {f.identified_gap}")
                            st.markdown(f"**Recommended Correction:**\n> {f.recommended_correction}")
                            st.markdown(f"**Suggested Next Action:**\n> {f.suggested_next_action}")

                st.markdown("---")
                st.markdown("### 📝 Overall Review Summary")
                st.markdown(summary_text)

                st.info("👉 Ready to edit findings, add reviewer notes, and approve? Proceed to **Reviewer Approval & Feedback (Module 5)** in the sidebar!")


# ==============================================================================
# PAGE 5: REVIEWER APPROVAL & FEEDBACK (MODULE 5)
# ==============================================================================
elif selected_page == "✍️ Reviewer Approval & Feedback (Module 5)":
    st.title("✍️ Module 5: Reviewer Approval and Feedback")
    st.write(
        "Human-in-the-loop review. Inspect AI findings, edit corrections, approve or reject specific items, "
        "record your final notes, and persist the official review session to SQLite."
    )

    tasks = db.get_tasks()
    if not tasks:
        st.warning("Please create a task first.")
    else:
        task_options = {f"Task #{t.id}: {t.title}": t.id for t in tasks}
        sel_task_label = st.selectbox("Select Task", list(task_options.keys()), key="fb_task")
        sel_task_id = task_options[sel_task_label]
        target_task = db.get_task_by_id(sel_task_id)

        subs = db.get_submissions_for_task(sel_task_id)
        if not subs:
            st.warning("No submissions available for this task.")
        else:
            sub_options = {f"Sub #{s.id}: {s.candidate_name} ({s.candidate_id})": s.id for s in subs}
            sel_sub_label = st.selectbox("Select Candidate Submission", list(sub_options.keys()), key="fb_sub")
            sel_sub_id = sub_options[sel_sub_label]
            target_sub = db.get_submission_by_id(sel_sub_id)

            session_key = f"analysis_{target_task.id}_{target_sub.id}"

            # Auto-run local analysis if not in session state
            if session_key not in st.session_state:
                engine = LocalRuleReviewEngine()
                findings, summary = engine.review(target_task, target_sub)
                st.session_state[session_key] = {
                    "findings": findings,
                    "summary": summary,
                    "engine_used": "Local Smart Analyzer",
                    "task_id": target_task.id,
                    "submission_id": target_sub.id
                }

            analysis_data = st.session_state[session_key]
            current_findings: list[RequirementFinding] = analysis_data["findings"]

            st.markdown("---")
            st.subheader(f"Review Session: {target_task.title} ➔ {target_sub.candidate_name}")

            with st.form("reviewer_approval_form"):
                reviewer_name = st.text_input("Reviewer Name / Title *", value="Lead Technical Reviewer")
                overall_status = st.selectbox(
                    "Overall Submission Decision Status *",
                    ["Needs Work", "Approved", "Draft"],
                    index=0
                )
                overall_notes = st.text_area(
                    "Final Reviewer Feedback & Executive Summary *",
                    value=analysis_data.get("summary", ""),
                    height=140
                )
                outstanding_actions = st.text_area(
                    "Outstanding Actions Required Before Next Milestone",
                    placeholder="List specific code fixes, tests, or documentation candidate must submit...",
                    value="1. Correct JWT expiration to 60 minutes.\n2. Submit concrete RBAC decorator code and 403 test output.\n3. Implement rate limiting on /login endpoint."
                )

                st.markdown("#### Individual Requirement Findings & Approvals")
                st.caption("Inspect and optionally override AI-assigned status for each requirement.")

                overrides = []
                for i, f in enumerate(current_findings):
                    st.markdown(f"##### [{f.req_code}] {f.original_requirement[:60]}")
                    st.markdown(f"**AI Status:** `{f.status}` | **Evidence:** {f.evidence_found[:120]}...")

                    c1, c2, c3 = st.columns([1, 2, 1])
                    with c1:
                        # Allow reviewer override
                        status_choice = st.selectbox(
                            f"Override Status ({f.req_code})",
                            ["(Keep AI Status)", "Completed", "Partially Completed", "Needs Verification", "Missing"],
                            key=f"status_override_{i}"
                        )
                    with c2:
                        notes = st.text_input(
                            f"Reviewer Notes ({f.req_code})",
                            placeholder="Add specific justification or instructions...",
                            key=f"notes_{i}"
                        )
                    with c3:
                        is_app = st.checkbox(
                            f"Approve Finding",
                            value=True,
                            key=f"app_{i}"
                        )

                    c_gap, c_corr = st.columns(2)
                    with c_gap:
                        edit_gap = st.text_input(f"Identified Gap ({f.req_code})", value=f.identified_gap, key=f"gap_{i}")
                    with c_corr:
                        edit_corr = st.text_input(f"Recommended Correction ({f.req_code})", value=f.recommended_correction, key=f"corr_{i}")

                    overrides.append((status_choice, notes, is_app, edit_gap, edit_corr))
                    st.markdown("---")

                save_btn = st.form_submit_button("💾 Save & Commit Official Review to SQLite", use_container_width=True)

                if save_btn:
                    # Apply overrides
                    for idx, (s_choice, notes, is_app, edit_gap, edit_corr) in enumerate(overrides):
                        if s_choice != "(Keep AI Status)":
                            current_findings[idx].reviewer_override_status = s_choice
                        current_findings[idx].reviewer_notes = notes
                        current_findings[idx].is_approved = is_app
                        current_findings[idx].identified_gap = edit_gap
                        current_findings[idx].recommended_correction = edit_corr

                    review_record = ReviewSession(
                        task_id=target_task.id,
                        submission_id=target_sub.id,
                        reviewer_name=reviewer_name.strip(),
                        ai_engine_used=analysis_data.get("engine_used", "Local Smart Analyzer"),
                        overall_summary=overall_notes.strip(),
                        status=overall_status,
                        outstanding_actions=outstanding_actions.strip(),
                        findings=current_findings
                    )

                    review_id = db.create_review(review_record)
                    st.success(f"✓ Official Review Session #{review_id} successfully saved to SQLite!")
                    st.balloons()


# ==============================================================================
# PAGE 6: REVIEW HISTORY & EXCEL EXPORT (MODULE 6)
# ==============================================================================
elif selected_page == "📜 Review History & Excel Export (Module 6)":
    st.title("📜 Module 6: Review History & Excel Export")
    st.write(
        "View historical task reviews stored persistently in SQLite. "
        "Inspect full finding breakdowns and download audit spreadsheets (.xlsx) generated with Pandas and OpenPyXL."
    )

    all_reviews = db.get_all_reviews()
    if not all_reviews:
        st.info("No reviews recorded in SQLite yet. Complete a review in Module 5 first.")
    else:
        st.subheader(f"Stored Review Sessions ({len(all_reviews)})")
        hist_df = pd.DataFrame(all_reviews)[[
            "id", "task_title", "candidate_id", "candidate_name", "reviewer_name",
            "status", "completed_count", "partial_count", "missing_count", "unverified_count", "created_at"
        ]].rename(columns={
            "id": "Review ID",
            "task_title": "Task",
            "candidate_id": "Candidate ID",
            "candidate_name": "Candidate Name",
            "reviewer_name": "Reviewer",
            "status": "Review Status",
            "completed_count": "✓ Done",
            "partial_count": "⚠ Partial",
            "missing_count": "✗ Missing",
            "unverified_count": "🔍 Unverified",
            "created_at": "Recorded At"
        })
        st.dataframe(hist_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("🔍 Inspect & Export Specific Review")

        review_options = {f"Review #{r['id']} - {r['candidate_name']} ({r['candidate_id']}) - {r['task_title']}": r["id"] for r in all_reviews}
        sel_rev_label = st.selectbox("Select Review Record to Inspect", list(review_options.keys()))
        sel_rev_id = review_options[sel_rev_label]

        selected_review = db.get_review_by_id(sel_rev_id)
        parent_task = db.get_task_by_id(selected_review.task_id)
        parent_sub = db.get_submission_by_id(selected_review.submission_id)

        if selected_review and parent_task and parent_sub:
            col_d1, col_d2 = st.columns([3, 1])
            with col_d1:
                st.markdown(f"**Task:** {parent_task.title}")
                st.markdown(f"**Candidate:** {parent_sub.candidate_name} (`{parent_sub.candidate_id}`)")
                st.markdown(f"**Reviewer:** {selected_review.reviewer_name} | **Status:** `{selected_review.status}`")
                st.markdown(f"**Next Review Scheduled:** `{selected_review.next_review_date or 'Not Set'}`")
            with col_d2:
                # Excel Export Button
                excel_data = export_review_to_excel(selected_review, parent_task, parent_sub)
                st.download_button(
                    label="📥 Export Report to Excel (.xlsx)",
                    data=excel_data,
                    file_name=f"Review_{selected_review.id}_{parent_sub.candidate_id}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

            st.markdown("#### Requirement Findings Table")
            findings_rows = []
            for f in selected_review.findings:
                findings_rows.append({
                    "Code": f.req_code,
                    "Requirement": f.original_requirement,
                    "Expected": f.expected_result,
                    "AI Status": f.status,
                    "Final Status": f.final_status,
                    "Gap": f.identified_gap,
                    "Recommended Correction": f.recommended_correction,
                    "Priority": f.priority,
                    "Reviewer Notes": f.reviewer_notes or "—"
                })
            st.dataframe(pd.DataFrame(findings_rows), use_container_width=True, hide_index=True)

            if selected_review.overall_summary:
                st.markdown("#### Reviewer Feedback & Overall Summary")
                st.info(selected_review.overall_summary)

            if selected_review.outstanding_actions:
                st.markdown("#### Outstanding Action Items")
                st.warning(selected_review.outstanding_actions)


# ==============================================================================
# PAGE 7: NEXT REVIEW SCHEDULING & FOLLOW-UP (MODULE 7)
# ==============================================================================
elif selected_page == "📅 Next Review & Follow-Up (Module 7)":
    st.title("📅 Module 7: Next Review Scheduling & Follow-Up Automation")
    st.write(
        "Schedule milestone review dates, generate follow-up action checklists for candidates, "
        "and prepare formatted email reminders without accidental unverified dispatch."
    )

    all_reviews = db.get_all_reviews()
    if not all_reviews:
        st.warning("No reviews recorded yet. Please complete a review in Module 5 first.")
    else:
        review_options = {f"Review #{r['id']} - {r['candidate_name']} ({r['candidate_id']}) - {r['task_title']}": r["id"] for r in all_reviews}
        sel_rev_label = st.selectbox("Select Review Session to Schedule Follow-Up", list(review_options.keys()))
        sel_rev_id = review_options[sel_rev_label]

        review_session = db.get_review_by_id(sel_rev_id)
        task = db.get_task_by_id(review_session.task_id)
        submission = db.get_submission_by_id(review_session.submission_id)

        st.markdown("---")
        st.subheader("1. Schedule Next Milestone Review Date")

        today = date.today()
        default_next = today + timedelta(days=7)

        col_date, col_btn = st.columns([2, 1])
        with col_date:
            chosen_date = st.date_input(
                "Select Next Review Date (Must be in the future) *",
                value=default_next,
                min_value=today + timedelta(days=1)
            )
            date_str = chosen_date.strftime("%Y-%m-%d")

        with col_btn:
            st.write("")
            st.write("")
            save_date_btn = st.button("📅 Confirm & Save Review Date", use_container_width=True)

        if save_date_btn:
            is_valid, msg = validate_next_review_date(date_str)
            if not is_valid:
                st.error(msg)
            else:
                review_session.next_review_date = date_str
                review_session.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db.update_review(review_session)
                st.success(f"✓ Next review date successfully scheduled for {date_str}!")

        # Generate structured follow-up summary
        active_date = review_session.next_review_date if review_session.next_review_date else date_str
        followup_data = generate_followup_summary(task, submission, review_session.findings, active_date)

        st.markdown("---")
        st.subheader("2. Automated Follow-Up Checklist")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Candidate:** {submission.candidate_name} (`{submission.candidate_id}`)")
            st.markdown(f"**Task:** {task.title}")
            st.markdown(f"**Target Milestone Date:** `{active_date}`")
            st.metric("Outstanding Requirements", followup_data["total_outstanding"])

        with c2:
            st.markdown("**Outstanding Items Requiring Attention:**")
            for item in followup_data["outstanding_items"]:
                st.markdown(f"- **[{item['req_code']}]** ({item['status']}): {item['gap']}")

        st.markdown("#### Evidence Candidate Must Provide Before Next Review")
        for ev in followup_data["evidence_needed"]:
            st.markdown(f"- 🔍 {ev}")

        st.markdown("---")
        st.subheader("3. Candidate Email Notification Dispatch")
        st.caption("Review the email draft below. Real emails are sent via Gmail SMTP when configured.")

        # Show SMTP configuration status
        smtp_cfg = get_smtp_config()
        if smtp_cfg["is_configured"]:
            st.success(f"● Gmail SMTP Ready: Sender configured as **{smtp_cfg['sender_email']}** (via environment)")
        else:
            st.info("ℹ️ Gmail SMTP is not yet configured. To send real emails, set the `GMAIL_SENDER_EMAIL` and `GMAIL_APP_PASSWORD` environment variables (or create a `.env` file).")

        email_draft = followup_data["email_reminder_draft"]
        st.text_area("Email Content Preview", value=email_draft, height=250)

        st.markdown("#### Candidate Recipient & Dispatch Confirmation")
        send_col1, send_col2 = st.columns([1, 1])
        with send_col1:
            recipient_email = st.text_input(
                "Candidate Real Email Address *",
                value="",
                placeholder="e.g. candidate@gmail.com",
                help="Must be a real email address. Placeholder domains like @example.com will be rejected."
            )
            st.caption("⚠️ Placeholder addresses (such as `cand-1001@example.com`) are automatically rejected.")
        with send_col2:
            st.write("")
            st.write("")
            confirm_send = st.checkbox("✅ I confirm that I have reviewed the draft and approve sending this email.")

        send_btn = st.button("📤 Send Automated Reminder Notification", type="primary", use_container_width=True)

        if send_btn:
            email_subject = f"Action Required: Task Review Follow-Up - {task.title}"
            with st.spinner("Connecting to SMTP server and dispatching email..."):
                res = send_followup_email(
                    recipient=recipient_email,
                    subject=email_subject,
                    body=email_draft,
                    confirmed_by_reviewer=confirm_send
                )

            if res["success"]:
                st.success(f"✓ {res['message']}")
                st.balloons()
            else:
                st.error(f"❌ {res['message']}")
                if res.get("status") == "NOT_CONFIGURED":
                    st.info(
                        "**How to configure Gmail SMTP:**\n\n"
                        "1. Generate a 16-character App Password at [Google Account Security](https://myaccount.google.com/apppasswords).\n"
                        "2. Set the environment variables in PowerShell:\n"
                        "   `$env:GMAIL_SENDER_EMAIL=\"your_email@gmail.com\"`\n"
                        "   `$env:GMAIL_APP_PASSWORD=\"your_16_char_app_password\"`\n"
                        "   *(or create a `.env` file in the project folder with these variables).*"
                    )


# ==============================================================================
# PAGE 8: SETTINGS & SYSTEM STATUS
# ==============================================================================
elif selected_page == "⚙️ AI Model & System Settings":
    st.title("⚙️ AI Model & System Settings")
    st.write("Configure local AI engines, check database status, and inspect system environment.")

    st.subheader("AI Engine Configuration")
    ollama_host = st.text_input("Ollama Host URL", value="http://localhost:11434")
    ollama_model = st.text_input("Ollama Model Name", value="llama3")

    if st.button("Test Ollama Connection"):
        engine = OllamaReviewEngine(host=ollama_host, model=ollama_model)
        avail, msg = engine.is_available()
        if avail:
            st.success(f"✓ {msg}")
        else:
            st.info(f"ℹ️ {msg}\n\nNote: The system seamlessly uses the built-in **Local Smart Analyzer** when Ollama is offline.")

    st.markdown("---")
    st.subheader("Email (SMTP) Configuration Status")
    smtp_status = get_smtp_config()
    env_file = smtp_status.get("env_file_path", os.path.join(PROJECT_ROOT, ".env"))
    env_exists = smtp_status.get("env_file_exists", os.path.exists(env_file))

    st.write(f"- **Project Root:** `{PROJECT_ROOT}`")
    st.write(f"- **Target `.env` Path:** `{env_file}`")
    st.write(f"- **`.env` File Status:** {'✅ Found' if env_exists else '❌ Not found in project root'}")

    if smtp_status["is_configured"]:
        st.success(f"● Gmail SMTP is configured. Sender: `{smtp_status['sender_email']}` (Host: `{smtp_status['server']}:{smtp_status['port']}`)")
        st.caption("Password is safely loaded from environment variables and never displayed.")
    else:
        st.warning("⚠️ Gmail SMTP is not configured. Set `GMAIL_SENDER_EMAIL` and `GMAIL_APP_PASSWORD` environment variables to enable real email dispatch.")
        if env_exists:
            st.info(
                "💡 A `.env` file was detected, but either `GMAIL_SENDER_EMAIL` or `GMAIL_APP_PASSWORD` is empty or missing.\n\n"
                "Please verify that the keys inside `.env` are named exactly:\n"
                "- `GMAIL_SENDER_EMAIL=your_email@gmail.com`\n"
                "- `GMAIL_APP_PASSWORD=your_16_char_app_password`"
            )

    st.markdown("---")
    st.subheader("Database & Environment")
    st.write(f"- **Database Path:** `{db.db_path}`")
    st.write(f"- **Python Version:** `{sys.version}`")
    st.write(f"- **Uploads Folder:** `{os.path.join(PROJECT_ROOT, 'uploads')}`")
    st.write(f"- **Allowed Extensions:** `.py, .js, .ts, .txt, .md, .json, .csv, .sql, .pdf, .png, .jpg, .xlsx`")
    st.write(f"- **Max File Size:** 5 MB")
