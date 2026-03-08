from __future__ import annotations

from pathlib import Path

import streamlit as st

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

    st.title("Olga Movie Review")
    st.caption("Review clips, pick the winning version, and queue retries for weak segments.")
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
        .block-container {
            max-width: 100%;
            padding-top: 1rem;
            padding-right: 1.25rem;
            padding-bottom: 1rem;
            padding-left: 1.25rem;
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
        [data-testid="stMetric"] {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 0.55rem 0.8rem;
        }
        [data-testid="stMetric"] label,
        [data-testid="stMetric"] p {
            margin-bottom: 0;
        }
        .review-guide {
            border: 1px solid #d9dde7;
            border-radius: 12px;
            padding: 0.75rem 0.9rem;
            background: #f8fafc;
            margin-bottom: 0.8rem;
        }
        .review-summary {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin: 0.45rem 0 0.8rem;
        }
        .review-chip {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 999px;
            color: #334155;
            font-size: 0.88rem;
            padding: 0.3rem 0.65rem;
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
            background: #edf2f7;
            color: #334155;
        }
        .status-approved {
            background: #dcfce7;
            color: #166534;
        }
        .status-redo {
            background: #fef3c7;
            color: #92400e;
        }
        .status-discussion {
            background: #dbeafe;
            color: #1d4ed8;
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

    st.sidebar.header("How to use")
    st.sidebar.markdown(
        "1. Pick a clip.\n"
        "2. Watch it and compare it to the start and end frames.\n"
        "3. Approve it or request a redo.\n"
        "4. Use the redo queue as the handoff for the next generation pass."
    )
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
    if "selected_version_by_pair" not in st.session_state:
        st.session_state.selected_version_by_pair = {}

    selected_version = st.session_state.selected_version_by_pair.get(selected_pair.pair_id, default_version)
    if selected_version not in version_numbers:
        selected_version = default_version

    main_cols = st.columns([1.35, 1], gap="large")

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
            st.info("This pair has multiple versions. Compare them, then accept the best one.")
            with st.expander("Compare versions side by side", expanded=True):
                compare_versions(selected_pair)

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


def compare_versions(selected_pair) -> None:
    version_numbers = [item.version for item in selected_pair.versions]
    compare_cols = st.columns(2, gap="large")
    left_version = compare_cols[0].selectbox(
        "Compare from",
        options=version_numbers,
        index=0,
        format_func=lambda version: f"v{version}",
        key=f"left-version-{selected_pair.pair_id}",
    )
    right_version = compare_cols[1].selectbox(
        "Compare to",
        options=version_numbers,
        index=min(1, len(version_numbers) - 1),
        format_func=lambda version: f"v{version}",
        key=f"right-version-{selected_pair.pair_id}",
    )

    version_map = {item.version: item for item in selected_pair.versions}
    compare_cols[0].caption(f"v{left_version} - {version_map[left_version].filename}")
    compare_cols[0].video(str(Path(version_map[left_version].video_path)))
    compare_cols[1].caption(f"v{right_version} - {version_map[right_version].filename}")
    compare_cols[1].video(str(Path(version_map[right_version].video_path)))


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
