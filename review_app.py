from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from redo_runner import preview_redo_queue, redo_request_key, run_redo_queue
from review_models import DECISIONS, ISSUE_TAGS, RedoRequest, ReviewRecord
from review_store import (
    accept_review_version,
    DEFAULT_RUN_ID,
    discover_clip_pairs,
    ensure_review_files,
    frame_image_path,
    load_redo_queue,
    load_reviews,
    load_winners,
    queue_redo,
    remove_redo_request,
    remove_redo_waiting_review,
    save_review,
    save_winner,
)


DECISION_LABELS = {
    "approve": "Approve",
    "redo": "Redo",
    "needs_discussion": "Needs discussion",
}

ISSUE_LABELS = {
    "face_bad": "Face looks bad",
    "identity_drift": "Identity drift",
    "hands_body_bad": "Hands or body look wrong",
    "transition_bad": "Transition is bad",
    "scenario_wrong": "Scenario is wrong",
    "background_wrong": "Background is wrong",
    "style_mismatch": "Style mismatch",
    "too_fast": "Too fast",
    "too_slow": "Too slow",
    "artifacts": "Artifacts",
    "emotion_wrong": "Emotion is wrong",
    "prompt_ignored": "Prompt ignored",
}

ISSUE_GROUPS = [
    ("Face and identity", ["face_bad", "identity_drift", "hands_body_bad", "emotion_wrong"]),
    ("Transition and motion", ["transition_bad", "too_fast", "too_slow"]),
    ("Scene and style", ["scenario_wrong", "background_wrong", "style_mismatch", "prompt_ignored", "artifacts"]),
]

STATUS_LABELS = {
    "Needs review": "Unreviewed",
    "Redo queued": "Needs redo",
    "Approved": "Approved",
    "Needs discussion": "Needs discussion",
    "waiting_review": "New version ready",
    "queued": "Queued to rerun",
    "failed": "Retry failed",
}

STATUS_FILTERS = [
    "All clips",
    "Rebuilt clips",
    "Needs review",
    "Redo queue",
    "Approved",
    "Needs discussion",
]

FILTER_LABELS = {
    "All clips": "All clips",
    "Rebuilt clips": "Rebuilt clips",
    "Needs review": "Unreviewed",
    "Redo queue": "Needs redo",
    "Approved": "Approved",
    "Needs discussion": "Needs discussion",
}

STATUS_SHORT_LABELS = {
    "Needs review": "[ ]",
    "Redo queued": "[R]",
    "Approved": "[OK]",
    "Needs discussion": "[?]",
}


def main() -> None:
    st.set_page_config(
        page_title="Olga Movie Review",
        page_icon="M",
        layout="wide",
    )
    inject_styles()

    st.markdown(
        """
        <div class="hero-banner">
            <div class="hero-kicker">AI film review desk</div>
            <h1>Olga Movie Review</h1>
            <p>Review clips, compare rebuilt versions, and queue smarter retries without losing story continuity.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    review_notice = st.session_state.pop("review_notice", "")
    if review_notice:
        st.success(review_notice)

    run_id, status_filter = sidebar_controls()
    ensure_review_files(run_id)

    pairs = discover_clip_pairs()
    reviews = load_reviews(run_id)
    redo_requests = load_redo_queue(run_id)
    winners = load_winners(run_id)

    if not pairs:
        st.error("No generated clips were found in kling_test/videos.")
        return

    review_lookup = {(item.pair_id, item.version): item for item in reviews}
    queued_redo_lookup = {
        (item.pair_id, item.source_version): item
        for item in redo_requests
        if item.status == "queued"
    }
    waiting_review_lookup = {
        (item.pair_id, item.target_version): item
        for item in redo_requests
        if item.status == "waiting_review" and item.target_version is not None
    }
    pair_rows = build_pair_rows(pairs, review_lookup, queued_redo_lookup, winners)

    selected_pair = select_pair(pairs, pair_rows, status_filter)

    review_tab, queue_tab = st.tabs(["Review", "Redo queue"])
    with review_tab:
        render_review_panel(
            selected_pair,
            review_lookup,
            queued_redo_lookup,
            waiting_review_lookup,
            winners,
            run_id,
            pair_rows,
            progress_counts(pair_rows),
            status_filter,
        )
        with st.expander("Inbox overview", expanded=False):
            render_inbox(pair_rows, status_filter, selected_pair.pair_id)

    with queue_tab:
        render_redo_queue(redo_requests, review_lookup, winners, run_id)

    error_message = st.session_state.pop("redo_run_error", "")
    if error_message:
        st.error(error_message)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(255, 237, 213, 0.75), transparent 28%),
                radial-gradient(circle at top right, rgba(254, 226, 226, 0.65), transparent 24%),
                linear-gradient(180deg, #fffdf8 0%, #fff8f1 100%);
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #fff8ec 0%, #fffaf3 100%);
            border-right: 1px solid #f1ddc6;
        }
        .block-container {
            max-width: 100%;
            padding-top: 1rem;
            padding-right: 1.25rem;
            padding-bottom: 1rem;
            padding-left: 1.25rem;
        }
        .hero-banner {
            background: linear-gradient(135deg, rgba(255, 248, 236, 0.98) 0%, rgba(255, 255, 255, 0.98) 56%, rgba(255, 238, 230, 0.98) 100%);
            border: 1px solid #edd5bd;
            border-radius: 24px;
            box-shadow: 0 18px 45px rgba(127, 29, 29, 0.08);
            margin-bottom: 1rem;
            padding: 1.2rem 1.4rem 1rem;
        }
        .hero-banner h1 {
            color: #1f2937;
            letter-spacing: -0.03em;
            margin: 0.1rem 0 0.25rem;
        }
        .hero-banner p {
            color: #6b7280;
            font-size: 1rem;
            margin: 0;
            max-width: 58rem;
        }
        .hero-kicker {
            color: #9a3412;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.16em;
            text-transform: uppercase;
        }
        h1 {
            margin-top: 0;
            margin-bottom: 0.25rem;
        }
        h3 {
            margin-top: 0.35rem;
            margin-bottom: 0.75rem;
        }
        [data-testid="stTabs"] {
            margin-top: 0.35rem;
        }
        [data-baseweb="tab-list"] {
            gap: 0.4rem;
        }
        [data-baseweb="tab"] {
            background: rgba(255, 250, 243, 0.9);
            border: 1px solid #efd9c6;
            border-radius: 999px 999px 0 0;
            padding: 0.35rem 0.9rem;
        }
        [aria-selected="true"][data-baseweb="tab"] {
            background: linear-gradient(180deg, #fff2e2 0%, #fff8f0 100%);
            border-color: #e6b17e;
            color: #9a3412;
        }
        [data-testid="stMetric"] {
            background: rgba(255, 251, 245, 0.92);
            border: 1px solid #edd5bd;
            border-radius: 14px;
            box-shadow: 0 8px 24px rgba(120, 53, 15, 0.06);
            padding: 0.55rem 0.8rem;
        }
        [data-testid="stMetric"] label,
        [data-testid="stMetric"] p {
            margin-bottom: 0;
        }
        [data-testid="stButton"] > button,
        [data-testid="stFormSubmitButton"] > button {
            background: linear-gradient(180deg, #fffaf4 0%, #fff3e6 100%);
            border: 1px solid #e7c8a9;
            border-radius: 14px;
            box-shadow: 0 8px 18px rgba(154, 52, 18, 0.08);
            color: #7c2d12;
            font-weight: 600;
        }
        [data-testid="stButton"] > button:hover,
        [data-testid="stFormSubmitButton"] > button:hover {
            border-color: #dd9d67;
            color: #9a3412;
        }
        button[kind="primary"] {
            background: linear-gradient(180deg, #ef6c3d 0%, #dc5a30 100%) !important;
            border-color: #cf4c23 !important;
            color: #fffaf5 !important;
        }
        button[kind="primary"]:hover {
            background: linear-gradient(180deg, #f07a4f 0%, #df6138 100%) !important;
            color: #ffffff !important;
        }
        [data-testid="stExpander"] {
            background: rgba(255, 252, 248, 0.9);
            border: 1px solid #efd9c6;
            border-radius: 18px;
            overflow: hidden;
        }
        [data-testid="stExpander"] details summary {
            background: rgba(255, 248, 239, 0.92);
        }
        [data-testid="stForm"] {
            background: rgba(255, 252, 248, 0.88);
            border: 1px solid #efd9c6;
            border-radius: 18px;
            padding: 0.85rem 0.95rem 0.4rem;
        }
        .review-guide {
            border: 1px solid #efd9c6;
            border-radius: 14px;
            padding: 0.75rem 0.9rem;
            background: linear-gradient(180deg, #fff8f0 0%, #fffdf8 100%);
            margin-bottom: 0.8rem;
        }
        .review-summary {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin: 0.45rem 0 0.8rem;
        }
        .review-chip {
            background: rgba(255, 251, 245, 0.96);
            border: 1px solid #edd5bd;
            border-radius: 999px;
            color: #7c2d12;
            font-size: 0.88rem;
            font-weight: 600;
            padding: 0.32rem 0.72rem;
            white-space: nowrap;
        }
        .status-pill {
            display: inline-block;
            padding: 0.2rem 0.65rem;
            border-radius: 999px;
            font-size: 0.85rem;
            font-weight: 600;
            margin-right: 0.5rem;
            margin-bottom: 0.5rem;
        }
        .status-unreviewed {
            background: #f3f4f6;
            color: #374151;
        }
        .status-approved {
            background: #d7f7df;
            color: #166534;
        }
        .status-redo {
            background: #ffe5bf;
            color: #9a3412;
        }
        .status-discussion {
            background: #e4ebff;
            color: #1d4ed8;
        }
        .compare-focus-shell {
            border: 1px solid #efd9c6;
            border-radius: 20px;
            box-shadow: 0 18px 40px rgba(120, 53, 15, 0.08);
            padding: 0.85rem 1rem;
            background: linear-gradient(180deg, rgba(255, 251, 245, 0.98) 0%, rgba(255, 255, 255, 0.98) 100%);
            margin: 0.25rem 0 0.8rem;
        }
        .compare-card-label {
            color: #7c2d12;
            font-size: 0.9rem;
            font-weight: 600;
            margin-bottom: 0.35rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sidebar_controls() -> tuple[str, str]:
    st.sidebar.header("Review Run")
    run_id = st.sidebar.text_input("Run ID", value=DEFAULT_RUN_ID).strip() or DEFAULT_RUN_ID

    st.sidebar.header("Quick view")
    status_filter = st.sidebar.radio(
        "Show",
        options=STATUS_FILTERS,
        index=STATUS_FILTERS.index("Needs review"),
        format_func=lambda item: FILTER_LABELS[item],
        label_visibility="collapsed",
    )

    st.sidebar.caption("Pick a clip, review it, then save or queue a redo.")
    return run_id, status_filter


def select_pair(pairs, pair_rows, status_filter: str):
    filtered_pair_ids = filtered_rows(pair_rows, status_filter)
    pair_ids = [pair.pair_id for pair in pairs]
    visible_pair_ids = [row["pair_id"] for row in filtered_pair_ids]
    pair_row_lookup = {item["pair_id"]: item for item in pair_rows}

    if not visible_pair_ids:
        visible_pair_ids = pair_ids

    pending_pair_id = st.session_state.pop("pending_selected_pair_choice", None)
    if pending_pair_id in visible_pair_ids:
        st.session_state.selected_pair_id = pending_pair_id
        st.session_state.selected_pair_choice = pending_pair_id

    if "selected_pair_id" not in st.session_state:
        st.session_state.selected_pair_id = visible_pair_ids[0]

    if st.session_state.selected_pair_id not in visible_pair_ids:
        st.session_state.selected_pair_id = visible_pair_ids[0]
    if "selected_pair_choice" not in st.session_state:
        st.session_state.selected_pair_choice = st.session_state.selected_pair_id
    if st.session_state.selected_pair_choice not in visible_pair_ids:
        st.session_state.selected_pair_choice = st.session_state.selected_pair_id

    current_index = visible_pair_ids.index(st.session_state.selected_pair_id)
    render_sidebar_queue_summary(pair_rows, visible_pair_ids, current_index)

    button_cols = st.sidebar.columns(2)
    if button_cols[0].button("Previous", use_container_width=True, disabled=current_index == 0):
        set_selected_pair(visible_pair_ids[current_index - 1])
        st.rerun()
    if button_cols[1].button(
        "Next",
        use_container_width=True,
        disabled=current_index == len(visible_pair_ids) - 1,
    ):
        set_selected_pair(visible_pair_ids[current_index + 1])
        st.rerun()

    next_review_pair = next_pair_needing_review(filtered_pair_ids, st.session_state.selected_pair_id)
    if st.sidebar.button(
        "Jump to next unreviewed",
        use_container_width=True,
        disabled=next_review_pair is None,
    ) and next_review_pair is not None:
        set_selected_pair(next_review_pair)
        st.rerun()

    current_row = pair_row_lookup[st.session_state.selected_pair_id]
    st.sidebar.markdown("**Current clip**")
    st.sidebar.caption(
        f"{st.session_state.selected_pair_id} | {display_status(current_row['status'])} | "
        f"{version_summary(current_row)}"
    )
    st.sidebar.caption("[ ] Unreviewed  [R] Needs redo  [OK] Approved  [?] Discussion")

    selected_pair_id = st.sidebar.radio(
        "Queue",
        options=visible_pair_ids,
        key="selected_pair_choice",
        format_func=lambda pair_id: queue_option_label(pair_id, pair_row_lookup[pair_id]),
        label_visibility="collapsed",
    )
    st.session_state.selected_pair_id = selected_pair_id
    return next(pair for pair in pairs if pair.pair_id == selected_pair_id)


def build_pair_rows(pairs, review_lookup, redo_lookup, winners):
    rows = []
    for pair in pairs:
        latest = pair.latest_version()
        if latest is None:
            continue

        status = pair_status(pair.pair_id, latest.version, review_lookup, redo_lookup)
        review = review_lookup.get((pair.pair_id, latest.version))
        winner_version = winners.get(pair.pair_id)
        rows.append(
            {
                "pair_id": pair.pair_id,
                "latest_version": latest.version,
                "winner_version": winner_version,
                "version_count": len(pair.versions),
                "rebuilt": len(pair.versions) > 1,
                "status": status,
                "rating": str(review.rating) if review and review.rating is not None else "-",
            }
        )
    return rows


def render_inbox(pair_rows, status_filter: str, selected_pair_id: str) -> None:
    st.subheader("Inbox")

    visible_rows = filtered_rows(pair_rows, status_filter)
    if not visible_rows:
        st.info("No clips match this filter.")
        visible_rows = pair_rows

    approved = count_rows(pair_rows, "Approved")
    redo = count_rows(pair_rows, "Redo queued")
    discussion = count_rows(pair_rows, "Needs discussion")
    unreviewed = count_rows(pair_rows, "Needs review")

    metric_cols = st.columns(4)
    metric_cols[0].metric("Unreviewed", unreviewed)
    metric_cols[1].metric("Approved", approved)
    metric_cols[2].metric("Needs redo", redo)
    metric_cols[3].metric("Needs discussion", discussion)

    rows = []
    for item in visible_rows:
        rows.append(
            {
                "selected": "*" if item["pair_id"] == selected_pair_id else "",
                "pair": item["pair_id"],
                "latest": f"v{item['latest_version']}",
                "winner": f"v{item['winner_version']}" if item["winner_version"] else "-",
                "versions": item["version_count"],
                "rebuilt": "Yes" if item["rebuilt"] else "-",
                "status": display_status(item["status"]),
                "rating": item["rating"],
            }
        )

    st.caption(f"Showing {len(visible_rows)} of {len(pair_rows)} clips.")
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_review_panel(
    selected_pair,
    review_lookup,
    redo_lookup,
    waiting_review_lookup,
    winners,
    run_id: str,
    pair_rows,
    progress,
    status_filter: str,
) -> None:
    st.subheader(pair_label(selected_pair.pair_id))

    version_numbers = [item.version for item in selected_pair.versions]
    version_labels = {item.version: f"v{item.version} - {item.filename}" for item in selected_pair.versions}
    default_version = selected_pair.latest_version().version
    compare_focus_pair_id = st.session_state.get("compare_focus_pair_id")
    if compare_focus_pair_id == selected_pair.pair_id:
        render_compare_focus_mode(selected_pair, version_labels)
        return
    if "selected_version_by_pair" not in st.session_state:
        st.session_state.selected_version_by_pair = {}

    selected_version = st.session_state.selected_version_by_pair.get(selected_pair.pair_id, default_version)
    if selected_version not in version_numbers:
        selected_version = default_version

    main_cols = st.columns([1.55, 0.9], gap="large")

    with main_cols[1]:
        selected_version = st.selectbox(
            "Version",
            options=version_numbers,
            index=version_numbers.index(selected_version),
            format_func=lambda version: version_labels[version],
        )
        st.session_state.selected_version_by_pair[selected_pair.pair_id] = selected_version

    version_map = {item.version: item for item in selected_pair.versions}
    current_clip = version_map[selected_version]
    winner_version = winners.get(selected_pair.pair_id)
    review = review_lookup.get((selected_pair.pair_id, current_clip.version))
    queued_redo = redo_lookup.get((selected_pair.pair_id, current_clip.version))
    waiting_review = waiting_review_lookup.get((selected_pair.pair_id, current_clip.version))
    current_status = pair_status(selected_pair.pair_id, current_clip.version, review_lookup, redo_lookup)

    with main_cols[0]:
        st.video(str(Path(current_clip.video_path)))
        image_cols = st.columns(2, gap="medium")
        start_path = frame_image_path(selected_pair.start_frame_id)
        end_path = frame_image_path(selected_pair.end_frame_id)
        image_cols[0].image(
            str(start_path),
            caption=f"Start: {selected_pair.start_frame_id}",
            use_container_width=True,
        )
        image_cols[1].image(
            str(end_path),
            caption=f"End: {selected_pair.end_frame_id}",
            use_container_width=True,
        )

    with main_cols[1]:
        render_status_banner(current_status, winner_version, current_clip.version)

        st.markdown(
            (
                '<div class="review-summary">'
                f'<span class="review-chip">Reviewed {progress["reviewed"]}/{progress["total"]}</span>'
                f'<span class="review-chip">Unreviewed {progress["unreviewed"]}</span>'
                f'<span class="review-chip">Needs redo {progress["redo"]}</span>'
                f'<span class="review-chip">Selected v{current_clip.version}</span>'
                f'<span class="review-chip">Winner {f"v{winner_version}" if winner_version else "not set"}</span>'
                f'<span class="review-chip">Frames {selected_pair.start_frame_id} -> {selected_pair.end_frame_id}</span>'
                "</div>"
            ),
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="review-guide">
            Decide if this version is good enough, needs another try, or should be discussed.
            </div>
            """,
            unsafe_allow_html=True,
        )

        if len(selected_pair.versions) == 1:
            st.caption("Only one version exists for this pair right now.")
        else:
            st.caption("Multiple versions available. Compare them if you need to choose a winner.")
            with st.expander("Compare versions side by side", expanded=waiting_review is not None):
                compare_versions(selected_pair, selected_version, version_labels)

        winner_button_label = "Mark selected version as winner"
        if waiting_review is not None:
            winner_button_label = f"Accept v{current_clip.version} and clear new-version-ready state"
        elif len(selected_pair.versions) > 1:
            winner_button_label = f"Accept v{current_clip.version} as the winner"

        if st.button(winner_button_label, use_container_width=True):
            save_winner(selected_pair.pair_id, current_clip.version, run_id=run_id)
            if waiting_review is not None:
                accept_review_version(selected_pair.pair_id, current_clip.version, run_id=run_id)
                st.success(
                    f"Accepted v{current_clip.version} as the winner for {selected_pair.pair_id} and cleared the waiting-review entry."
                )
            else:
                st.success(f"Saved v{current_clip.version} as the winner for {selected_pair.pair_id}.")
            st.rerun()

        if review is not None:
            st.info(
                f"Last review: {DECISION_LABELS.get(review.decision, review.decision)}"
                f" | Rating: {review.rating if review.rating is not None else '-'}"
                f" | Reviewed at: {review.reviewed_at}"
            )
        if queued_redo is not None:
            st.warning("This version is currently in the redo queue.")
        if waiting_review is not None:
            st.info("This retried version is back. Approve it here or accept it as the winner above.")

        decision = st.radio(
            "Decision",
            options=DECISIONS,
            index=DECISIONS.index(review.decision) if review else 0,
            format_func=lambda item: DECISION_LABELS[item],
            horizontal=True,
            key=f"decision-{selected_pair.pair_id}-{current_clip.version}",
        )

        with st.form(key=f"review-form-{selected_pair.pair_id}-{current_clip.version}"):

            rating_options = ["-"] + [str(number) for number in range(1, 6)]
            saved_rating = str(review.rating) if review and review.rating is not None else "5"
            rating_value = st.select_slider("Quality rating", options=rating_options, value=saved_rating)

            issue_defaults = review.issues if review else []
            note_default = review.note if review else ""
            issues: list[str] = issue_defaults
            note = note_default
            if decision != "approve":
                st.caption("What needs fixing?")
                issues = render_issue_group_inputs(selected_pair.pair_id, current_clip.version, issue_defaults)

                note = st.text_area(
                    "Optional note",
                    value=note_default,
                    placeholder="Example: face morphs in the middle, transition is too dramatic.",
                    height=90,
                )
            else:
                st.caption("Approved clips do not need issue tags or notes.")
                issues = []
                note = ""

            with st.expander("Advanced review options", expanded=False):
                reviewed_by = st.text_input("Reviewer", value=review.reviewed_by if review else "local-user")
                st.write(f"File: `{current_clip.filename}`")
                st.write(f"Path: `{current_clip.video_path}`")

            submit_cols = st.columns(2, gap="medium")
            save_only = submit_cols[0].form_submit_button("Save only", use_container_width=True)
            approve_and_next = submit_cols[1].form_submit_button(
                "Approve and next",
                type="primary",
                use_container_width=True,
                disabled=decision != "approve",
            )
            submitted = save_only or approve_and_next

            if submitted:
                record = ReviewRecord(
                    pair_id=selected_pair.pair_id,
                    version=current_clip.version,
                    decision=decision,
                    rating=None if rating_value == "-" else int(rating_value),
                    issues=issues,
                    note=note.strip(),
                    reviewed_by=reviewed_by.strip() or "local-user",
                )
                save_review(record, run_id=run_id)
                remove_redo_waiting_review(selected_pair.pair_id, current_clip.version, run_id=run_id)

                if decision == "redo":
                    queue_redo(
                        RedoRequest(
                            pair_id=selected_pair.pair_id,
                            source_version=current_clip.version,
                            issues=issues,
                            note=note.strip(),
                        ),
                        run_id=run_id,
                    )
                else:
                    remove_redo_request(selected_pair.pair_id, current_clip.version, run_id=run_id)

                if decision == "approve" and approve_and_next:
                    remaining_unreviewed = remaining_unreviewed_after_save(pair_rows, selected_pair.pair_id)
                    next_pair_id = next_pair_to_review(pair_rows, selected_pair.pair_id)
                    if next_pair_id is not None:
                        set_selected_pair(next_pair_id)
                        st.session_state.review_notice = (
                            f"Approved {selected_pair.pair_id}. {remaining_unreviewed} clips still unreviewed. Moved to {next_pair_id}."
                        )
                    else:
                        st.session_state.review_notice = (
                            f"Approved {selected_pair.pair_id}. {remaining_unreviewed} clips still unreviewed."
                        )
                elif decision == "approve":
                    target_pair_id = next_pair_for_filter(pair_rows, selected_pair.pair_id, "Approved", status_filter)
                    set_selected_pair(target_pair_id)
                    if target_pair_id == selected_pair.pair_id:
                        st.session_state.review_notice = f"Approved {selected_pair.pair_id}. Stayed on this clip."
                    else:
                        st.session_state.review_notice = (
                            f"Approved {selected_pair.pair_id}. It no longer matches this filter, so the queue moved to {target_pair_id}."
                        )
                elif decision == "redo":
                    target_pair_id = next_pair_for_filter(pair_rows, selected_pair.pair_id, "Redo queued", status_filter)
                    set_selected_pair(target_pair_id)
                    st.session_state.review_notice = (
                        f"Queued redo for {selected_pair.pair_id}. {progress['redo'] + 1} clips now need another pass."
                    )
                elif decision == "needs_discussion":
                    target_pair_id = next_pair_for_filter(pair_rows, selected_pair.pair_id, "Needs discussion", status_filter)
                    set_selected_pair(target_pair_id)
                    st.session_state.review_notice = f"Saved discussion note for {selected_pair.pair_id}."
                else:
                    set_selected_pair(selected_pair.pair_id)
                    st.session_state.review_notice = "Review saved."
                st.rerun()


def render_status_banner(status: str, winner_version: int | None, selected_version: int) -> None:
    classes = {
        "Needs review": "status-pill status-unreviewed",
        "Approved": "status-pill status-approved",
        "Redo queued": "status-pill status-redo",
        "Needs discussion": "status-pill status-discussion",
    }
    badge = f'<span class="{classes[status]}">{display_status(status)}</span>'
    winner_text = "This version is not marked as the winner yet."
    if winner_version == selected_version:
        winner_text = "This version is currently marked as the winner."
    elif winner_version is not None:
        winner_text = f"Winner is v{winner_version}."
    st.markdown(f"{badge} {winner_text}", unsafe_allow_html=True)

def render_compare_focus_mode(selected_pair, version_labels) -> None:
    st.markdown('<div class="compare-focus-shell">', unsafe_allow_html=True)
    header_cols = st.columns([1, 1], gap="medium")
    header_cols[0].markdown("**Focused compare mode**")
    if header_cols[1].button("Back to review details", use_container_width=True):
        st.session_state.compare_focus_pair_id = None
        st.rerun()
    st.caption("Review controls are hidden here so the compare videos can use more of the page.")
    compare_versions(selected_pair, selected_pair.latest_version().version, version_labels, focused=True)
    st.markdown("</div>", unsafe_allow_html=True)


def compare_versions(selected_pair, selected_version: int, version_labels, focused: bool = False) -> None:
    version_numbers = [item.version for item in selected_pair.versions]
    version_map = {item.version: item for item in selected_pair.versions}
    selected_versions = compare_version_selection(selected_pair.pair_id, version_numbers, selected_version)

    control_cols = st.columns([2.2, 1, 1], gap="medium")
    selected_versions = control_cols[0].multiselect(
        "Compare versions",
        options=version_numbers,
        default=selected_versions,
        format_func=lambda version: version_labels[version],
        max_selections=4,
        key=f"compare-versions-{selected_pair.pair_id}",
        help="Choose up to four versions to compare side by side.",
    )
    selected_versions = normalized_compare_selection(selected_versions, version_numbers, selected_version)
    st.session_state.compare_versions_by_pair[selected_pair.pair_id] = selected_versions

    if focused:
        if control_cols[1].button("Exit large compare view", use_container_width=True):
            st.session_state.compare_focus_pair_id = None
            st.rerun()
    else:
        if control_cols[1].button("Open large compare view", use_container_width=True):
            st.session_state.compare_focus_pair_id = selected_pair.pair_id
            st.rerun()

    control_cols[2].caption(f"{len(selected_versions)} selected")
    marker_id = compare_marker_id(selected_pair.pair_id, focused)
    render_compare_sync_controls(marker_id, focused)
    render_compare_videos(marker_id, [version_map[version] for version in selected_versions])


def compare_version_selection(pair_id: str, version_numbers: list[int], selected_version: int) -> list[int]:
    if "compare_versions_by_pair" not in st.session_state:
        st.session_state.compare_versions_by_pair = {}
    saved_versions = st.session_state.compare_versions_by_pair.get(pair_id)
    if saved_versions:
        return normalized_compare_selection(saved_versions, version_numbers, selected_version)
    return default_compare_versions(version_numbers, selected_version)


def default_compare_versions(version_numbers: list[int], selected_version: int) -> list[int]:
    if len(version_numbers) == 1:
        return [version_numbers[0]]
    if selected_version not in version_numbers:
        return version_numbers[-2:]
    selected_index = version_numbers.index(selected_version)
    if selected_index == 0:
        return version_numbers[:2]
    return [version_numbers[selected_index - 1], selected_version]


def normalized_compare_selection(selected_versions: list[int], version_numbers: list[int], selected_version: int) -> list[int]:
    valid_versions = [version for version in version_numbers if version in selected_versions]
    if not valid_versions:
        return default_compare_versions(version_numbers, selected_version)
    return valid_versions[:4]


def compare_marker_id(pair_id: str, focused: bool) -> str:
    suffix = "focus" if focused else "inline"
    return f"compare-{pair_id.replace('_', '-')}-{suffix}"


def render_compare_sync_controls(marker_id: str, focused: bool) -> None:
    height = 78 if focused else 72
    mode_label = "focused compare" if focused else "compare"
    script = f"""
    <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:0 0 0.5rem 0;">
      <button onclick="controlCompare('play')" style="padding:0.4rem 0.8rem;border-radius:999px;border:1px solid #d9dde7;background:#ffffff;cursor:pointer;">Play all</button>
      <button onclick="controlCompare('pause')" style="padding:0.4rem 0.8rem;border-radius:999px;border:1px solid #d9dde7;background:#ffffff;cursor:pointer;">Pause all</button>
      <button onclick="controlCompare('restart')" style="padding:0.4rem 0.8rem;border-radius:999px;border:1px solid #d9dde7;background:#ffffff;cursor:pointer;">Restart all</button>
      <button onclick="controlCompare('fullscreen')" style="padding:0.4rem 0.8rem;border-radius:999px;border:1px solid #d9dde7;background:#ffffff;cursor:pointer;">Fullscreen compare</button>
      <span id="compare-status" style="font-size:0.82rem;color:#475569;">Use the buttons above or each player's native controls.</span>
    </div>
    <script>
    const markerId = {json.dumps(marker_id)};
    const modeLabel = {json.dumps(mode_label)};
    function getCompareNodes() {{
      try {{
        const doc = window.parent.document;
        const frame = window.frameElement;
        const frameContainer = frame?.parentElement?.parentElement;
        if (frameContainer) {{
          const scopedVideos = Array.from(frameContainer.querySelectorAll('video'));
          if (scopedVideos.length) {{
            return {{
              start: null,
              end: null,
              videos: scopedVideos,
              container: frameContainer
            }};
          }}
        }}
        const start = doc.getElementById(`${{markerId}}-start`);
        const end = doc.getElementById(`${{markerId}}-end`);
        if (!start || !end) {{
          return {{start: null, end: null, videos: [], container: null}};
        }}
        const videos = [];
        let node = start.nextElementSibling;
        while (node && node !== end) {{
          videos.push(...node.querySelectorAll('video'));
          node = node.nextElementSibling;
        }}
        return {{
          start,
          end,
          videos,
          container: start.closest('[data-testid="stVerticalBlock"]')
        }};
      }} catch (error) {{
        return {{start: null, end: null, videos: [], container: null, error}};
      }}
    }}
    function setStatus(message) {{
      const label = document.getElementById('compare-status');
      if (label) {{
        label.textContent = message;
      }}
    }}
    async function controlCompare(action) {{
      const {{videos, container, error}} = getCompareNodes();
      if (error) {{
        setStatus(`Shared controls are unavailable in this browser. Use each player's controls instead.`);
        return;
      }}
      if (!videos.length) {{
        setStatus(`No videos found in this ${{modeLabel}} view yet.`);
        return;
      }}
      if (action === 'pause') {{
        videos.forEach((video) => video.pause());
        setStatus(`Paused ${{videos.length}} video(s).`);
        return;
      }}
      if (action === 'restart') {{
        videos.forEach((video) => {{
          video.pause();
          video.currentTime = 0;
        }});
        const results = await Promise.allSettled(videos.map((video) => video.play()));
        const failed = results.filter((result) => result.status === 'rejected').length;
        setStatus(failed ? `Restarted ${{videos.length - failed}} video(s). Some browsers blocked autoplay.` : `Restarted ${{videos.length}} video(s) from the beginning.`);
        return;
      }}
      if (action === 'play') {{
        videos.forEach((video) => {{
          if (video.currentTime < 0.05) {{
            video.currentTime = 0;
          }}
        }});
        const results = await Promise.allSettled(videos.map((video) => video.play()));
        const failed = results.filter((result) => result.status === 'rejected').length;
        setStatus(failed ? `Played ${{videos.length - failed}} video(s). Some browsers blocked autoplay.` : `Playing ${{videos.length}} video(s) together.`);
        return;
      }}
      if (action === 'fullscreen') {{
        if (container && container.requestFullscreen) {{
          await container.requestFullscreen();
          setStatus(`Opened the ${{modeLabel}} in fullscreen.`);
        }} else {{
          setStatus(`Fullscreen is unavailable here. Use each player's native fullscreen button.`);
        }}
      }}
    }}
    </script>
    """
    components.html(script, height=height)


def render_compare_videos(marker_id: str, selected_versions) -> None:
    st.markdown(f"<div id='{marker_id}-start'></div>", unsafe_allow_html=True)
    total_versions = len(selected_versions)

    if total_versions == 1:
        render_compare_card(selected_versions[0], full_width=True)
    elif total_versions == 2:
        compare_cols = st.columns(2, gap="large")
        for column, clip in zip(compare_cols, selected_versions, strict=False):
            with column:
                render_compare_card(clip)
    else:
        for row_start in range(0, total_versions, 2):
            row_clips = selected_versions[row_start : row_start + 2]
            compare_cols = st.columns(2, gap="large")
            for index, clip in enumerate(row_clips):
                with compare_cols[index]:
                    render_compare_card(clip)
    st.markdown(f"<div id='{marker_id}-end'></div>", unsafe_allow_html=True)


def render_compare_card(clip, full_width: bool = False) -> None:
    st.markdown(
        f"<div class='compare-card-label'>v{clip.version} - {clip.filename}</div>",
        unsafe_allow_html=True,
    )
    st.video(str(Path(clip.video_path)))
    if full_width:
        st.caption("Use the player's native fullscreen button for the largest single-video view.")


def render_redo_queue(redo_requests, review_lookup, winners, run_id: str) -> None:
    st.subheader("Redo queue")
    if not redo_requests:
        st.info("No clips are queued for redo.")
        return

    queued_requests = [item for item in redo_requests if item.status == "queued"]
    waiting_review_requests = [item for item in redo_requests if item.status == "waiting_review"]
    failed_requests = [item for item in redo_requests if item.status == "failed"]

    metric_cols = st.columns(3)
    metric_cols[0].metric("Queued to rerun", len(queued_requests))
    metric_cols[1].metric("New version ready", len(waiting_review_requests))
    metric_cols[2].metric("Retry failed", len(failed_requests))

    st.caption("Queued items can be sent to Kling. New version ready items already produced a retry and are waiting for review.")

    selected_queue_keys = []
    if queued_requests:
        options = [redo_request_key(item.pair_id, item.source_version) for item in queued_requests]
        labels = {
            redo_request_key(item.pair_id, item.source_version): (
                f"{item.pair_id} from v{item.source_version}"
            )
            for item in queued_requests
        }
        selected_queue_keys = st.multiselect(
            "Queued items to run",
            options=options,
            default=options,
            format_func=lambda key: labels[key],
            help="Choose exactly which queued retries to preview or run.",
        )

    control_cols = st.columns([1, 1, 1.2], gap="large")
    if control_cols[0].button("Preview queued retries", use_container_width=True):
        if not selected_queue_keys:
            st.warning("Select at least one queued retry to preview.")
        else:
            st.session_state.redo_preview = preview_redo_queue(run_id, set(selected_queue_keys))

    run_confirmed = control_cols[1].checkbox("Use Kling credits", value=False)
    if control_cols[2].button(
        "Run queued retries",
        use_container_width=True,
        disabled=not queued_requests or not selected_queue_keys,
        type="primary",
    ):
        if not run_confirmed:
            st.warning("Tick 'Use Kling credits' before running queued retries.")
        elif not selected_queue_keys:
            st.warning("Select at least one queued retry to run.")
        else:
            try:
                with st.spinner("Submitting queued retries to Kling..."):
                    st.session_state.redo_results = run_redo_queue(run_id, set(selected_queue_keys))
                    st.session_state.redo_preview = []
            except Exception as error:
                st.session_state.redo_run_error = f"Retry run failed: {error}"
            st.rerun()

    preview_rows = st.session_state.get("redo_preview", [])
    if preview_rows:
        st.markdown("**Queued retry preview**")
        st.dataframe(
            [
                {
                    "pair": item["pair_id"],
                    "from": f"v{item['source_version']}",
                    "to": f"v{item['target_version']}",
                    "output_file": item["output_file"],
                    "prompt_mode": item["prompt_mode"],
                    "issues": item["issues"],
                }
                for item in preview_rows
            ],
            use_container_width=True,
            hide_index=True,
        )
        for item in preview_rows:
            with st.expander(f"{item['pair_id']} retry prompt", expanded=False):
                st.write(item["retry_prompt"])

    result_rows = st.session_state.get("redo_results", [])
    if result_rows:
        st.markdown("**Last retry run**")
        st.dataframe(result_rows, use_container_width=True, hide_index=True)

    st.markdown("**Queued to rerun**")
    render_redo_request_table(queued_requests, review_lookup, winners)

    if waiting_review_requests:
        st.markdown("**New version ready**")
        render_redo_request_table(waiting_review_requests, review_lookup, winners)

    if failed_requests:
        st.markdown("**Retry failed**")
        render_redo_request_table(failed_requests, review_lookup, winners)


def render_redo_request_table(redo_requests, review_lookup, winners) -> None:
    rows: list[dict[str, str | int]] = []
    for item in redo_requests:
        review = review_lookup.get((item.pair_id, item.source_version))
        rows.append(
            {
                "pair": item.pair_id,
                "source_version": f"v{item.source_version}",
                "target_version": f"v{item.target_version}" if item.target_version else "-",
                "status": display_status(item.status),
                "issues": ", ".join(ISSUE_LABELS[tag] for tag in item.issues) if item.issues else "-",
                "note": item.note or "-",
                "winner": f"v{winners[item.pair_id]}" if item.pair_id in winners else "-",
                "decision": DECISION_LABELS.get(review.decision, "-") if review else "-",
                "output_file": item.output_file or "-",
                "error": item.error or "-",
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def filtered_rows(pair_rows, status_filter: str):
    if status_filter == "All clips":
        return pair_rows
    if status_filter == "Rebuilt clips":
        return [item for item in pair_rows if item["rebuilt"]]
    if status_filter == "Needs review":
        return [item for item in pair_rows if item["status"] == "Needs review"]
    if status_filter == "Redo queue":
        return [item for item in pair_rows if item["status"] == "Redo queued"]
    if status_filter == "Approved":
        return [item for item in pair_rows if item["status"] == "Approved"]
    return [item for item in pair_rows if item["status"] == "Needs discussion"]


def pair_status(pair_id: str, version: int, review_lookup, redo_lookup) -> str:
    if (pair_id, version) in redo_lookup:
        return "Redo queued"

    review = review_lookup.get((pair_id, version))
    if review is None:
        return "Needs review"
    if review.decision == "approve":
        return "Approved"
    if review.decision == "redo":
        return "Redo queued"
    return "Needs discussion"


def count_rows(pair_rows, status: str) -> int:
    return sum(1 for item in pair_rows if item["status"] == status)


def progress_counts(pair_rows) -> dict[str, int]:
    total = len(pair_rows)
    unreviewed = count_rows(pair_rows, "Needs review")
    approved = count_rows(pair_rows, "Approved")
    redo = count_rows(pair_rows, "Redo queued")
    discussion = count_rows(pair_rows, "Needs discussion")
    reviewed = total - unreviewed
    return {
        "total": total,
        "reviewed": reviewed,
        "unreviewed": unreviewed,
        "approved": approved,
        "redo": redo,
        "discussion": discussion,
    }


def next_pair_for_filter(pair_rows, current_pair_id: str, new_status: str, status_filter: str) -> str:
    updated_rows = []
    for item in pair_rows:
        if item["pair_id"] == current_pair_id:
            updated = dict(item)
            updated["status"] = new_status
            updated_rows.append(updated)
        else:
            updated_rows.append(item)

    visible_rows = filtered_rows(updated_rows, status_filter)
    visible_pair_ids = [item["pair_id"] for item in visible_rows]
    if not visible_pair_ids:
        return current_pair_id
    if current_pair_id in visible_pair_ids:
        return current_pair_id

    pair_ids = [item["pair_id"] for item in updated_rows]
    current_index = pair_ids.index(current_pair_id) if current_pair_id in pair_ids else -1
    ordered_rows = updated_rows[current_index + 1 :] + updated_rows[:current_index]
    for item in ordered_rows:
        if item["pair_id"] in visible_pair_ids:
            return item["pair_id"]
    return visible_pair_ids[0]


def remaining_unreviewed_after_save(pair_rows, current_pair_id: str) -> int:
    remaining = count_rows(pair_rows, "Needs review")
    current_row = next((item for item in pair_rows if item["pair_id"] == current_pair_id), None)
    if current_row is not None and current_row["status"] == "Needs review":
        return max(0, remaining - 1)
    return remaining


def display_status(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def queue_option_label(pair_id: str, row: dict[str, str | int | bool | None]) -> str:
    return f"{status_short(str(row['status']))} {pair_id} {version_summary(row)}"


def render_issue_group_inputs(pair_id: str, version: int, issue_defaults: list[str]) -> list[str]:
    selected: list[str] = []
    for group_name, group_issues in ISSUE_GROUPS:
        defaults = [item for item in issue_defaults if item in group_issues]
        group_selected = st.multiselect(
            group_name,
            options=group_issues,
            default=defaults,
            format_func=lambda item: ISSUE_LABELS[item],
            key=f"issues-{pair_id}-{version}-{group_name}",
            placeholder="Choose any that apply",
        )
        selected.extend(group_selected)
    return selected


def status_short(status: str) -> str:
    return STATUS_SHORT_LABELS.get(status, "[ ]")


def version_summary(row: dict[str, str | int | bool | None]) -> str:
    if row["winner_version"]:
        return f"w:v{row['winner_version']}"
    return f"v{row['latest_version']}"


def render_sidebar_queue_summary(pair_rows, visible_pair_ids, current_index: int) -> None:
    unreviewed = count_rows(pair_rows, "Needs review")
    redo = count_rows(pair_rows, "Redo queued")
    rebuilt = sum(1 for item in pair_rows if item["rebuilt"])

    st.sidebar.markdown("**Queue summary**")
    summary_cols = st.sidebar.columns(2)
    summary_cols[0].metric("Left", unreviewed)
    summary_cols[1].metric("Needs redo", redo)
    st.sidebar.caption(f"Rebuilt clips: {rebuilt}")
    st.sidebar.caption(f"Showing clip {current_index + 1} of {len(visible_pair_ids)} in this filter.")


def next_pair_needing_review(pair_rows, current_pair_id: str):
    pair_ids = [item["pair_id"] for item in pair_rows]
    if current_pair_id not in pair_ids:
        current_index = -1
    else:
        current_index = pair_ids.index(current_pair_id)

    ordered_rows = pair_rows[current_index + 1 :] + pair_rows[: current_index + 1]
    for item in ordered_rows:
        if item["status"] == "Needs review":
            return item["pair_id"]
    return None


def next_pair_to_review(pair_rows, current_pair_id: str):
    pair_ids = [item["pair_id"] for item in pair_rows]
    if current_pair_id not in pair_ids:
        ordered_rows = pair_rows
    else:
        current_index = pair_ids.index(current_pair_id)
        ordered_rows = pair_rows[current_index + 1 :] + pair_rows[:current_index]

    for item in ordered_rows:
        if item["status"] == "Needs review":
            return item["pair_id"]
    return None


def set_selected_pair(pair_id: str) -> None:
    st.session_state.pending_selected_pair_choice = pair_id


def pair_label(pair_id: str) -> str:
    start_frame, end_frame = pair_id.split("_to_", 1)
    return f"{pair_id} | {start_frame} to {end_frame}"


if __name__ == "__main__":
    main()
