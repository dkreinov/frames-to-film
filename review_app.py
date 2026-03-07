from __future__ import annotations

from pathlib import Path

import streamlit as st

from review_models import DECISIONS, ISSUE_TAGS, RedoRequest, ReviewRecord
from review_store import (
    DEFAULT_RUN_ID,
    discover_clip_pairs,
    ensure_review_files,
    frame_image_path,
    load_redo_queue,
    load_reviews,
    load_winners,
    queue_redo,
    remove_redo_request,
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

STATUS_FILTERS = [
    "All clips",
    "Needs review",
    "Redo queue",
    "Approved",
    "Needs discussion",
]


def main() -> None:
    st.set_page_config(
        page_title="Olga Movie Review",
        page_icon="M",
        layout="wide",
    )
    inject_styles()

    st.title("Olga Movie Review")
    st.caption("Review clips, pick the winning version, and queue retries for weak segments.")

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
    redo_lookup = {(item.pair_id, item.source_version): item for item in redo_requests}
    pair_rows = build_pair_rows(pairs, review_lookup, redo_lookup, winners)

    selected_pair = select_pair(pairs, pair_rows, status_filter)

    review_tab, queue_tab = st.tabs(["Review", "Redo queue"])
    with review_tab:
        left_col, right_col = st.columns([1.05, 1.95], gap="large")
        with left_col:
            render_inbox(pair_rows, status_filter, selected_pair.pair_id)
        with right_col:
            render_review_panel(selected_pair, review_lookup, redo_lookup, winners, run_id)

    with queue_tab:
        render_redo_queue(redo_requests, review_lookup, winners)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .review-guide {
            border: 1px solid #d9dde7;
            border-radius: 12px;
            padding: 0.9rem 1rem;
            background: #f8fafc;
            margin-bottom: 1rem;
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

    st.sidebar.header("Inbox Filter")
    status_filter = st.sidebar.selectbox("Show", options=STATUS_FILTERS, index=0)

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

    if not visible_pair_ids:
        visible_pair_ids = pair_ids

    if "selected_pair_id" not in st.session_state:
        st.session_state.selected_pair_id = visible_pair_ids[0]

    if st.session_state.selected_pair_id not in visible_pair_ids:
        st.session_state.selected_pair_id = visible_pair_ids[0]

    button_cols = st.sidebar.columns(2)
    current_index = visible_pair_ids.index(st.session_state.selected_pair_id)
    if button_cols[0].button("Previous", use_container_width=True, disabled=current_index == 0):
        st.session_state.selected_pair_id = visible_pair_ids[current_index - 1]
    if button_cols[1].button(
        "Next",
        use_container_width=True,
        disabled=current_index == len(visible_pair_ids) - 1,
    ):
        st.session_state.selected_pair_id = visible_pair_ids[current_index + 1]

    next_review_pair = next_pair_needing_review(filtered_pair_ids)
    if st.sidebar.button(
        "Jump to next needs review",
        use_container_width=True,
        disabled=next_review_pair is None,
    ) and next_review_pair is not None:
        st.session_state.selected_pair_id = next_review_pair

    selected_pair_id = st.sidebar.selectbox(
        "Clip",
        options=visible_pair_ids,
        index=visible_pair_ids.index(st.session_state.selected_pair_id),
        format_func=pair_label,
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
    metric_cols[0].metric("Needs review", unreviewed)
    metric_cols[1].metric("Approved", approved)
    metric_cols[2].metric("Redo queue", redo)
    metric_cols[3].metric("Discuss", discussion)

    rows = []
    for item in visible_rows:
        rows.append(
            {
                "selected": "*" if item["pair_id"] == selected_pair_id else "",
                "pair": item["pair_id"],
                "latest": f"v{item['latest_version']}",
                "winner": f"v{item['winner_version']}" if item["winner_version"] else "-",
                "versions": item["version_count"],
                "status": item["status"],
                "rating": item["rating"],
            }
        )

    st.caption(f"Showing {len(visible_rows)} of {len(pair_rows)} clips.")
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_review_panel(selected_pair, review_lookup, redo_lookup, winners, run_id: str) -> None:
    st.subheader(pair_label(selected_pair.pair_id))

    version_numbers = [item.version for item in selected_pair.versions]
    version_labels = {item.version: f"v{item.version} - {item.filename}" for item in selected_pair.versions}
    default_version = selected_pair.latest_version().version
    if "selected_version_by_pair" not in st.session_state:
        st.session_state.selected_version_by_pair = {}

    selected_version = st.session_state.selected_version_by_pair.get(selected_pair.pair_id, default_version)
    if selected_version not in version_numbers:
        selected_version = default_version

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
    current_status = pair_status(selected_pair.pair_id, current_clip.version, review_lookup, redo_lookup)

    render_status_banner(current_status, winner_version, current_clip.version)

    meta_cols = st.columns(4)
    meta_cols[0].metric("Selected version", f"v{current_clip.version}")
    meta_cols[1].metric("Start frame", selected_pair.start_frame_id)
    meta_cols[2].metric("End frame", selected_pair.end_frame_id)
    meta_cols[3].metric("Winner", f"v{winner_version}" if winner_version else "Not set")

    st.markdown(
        """
        <div class="review-guide">
        Approve the clip if it is ready for the final cut.
        Choose Redo if the clip should be regenerated, then tag the problem so the next pass knows what to fix.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.video(str(Path(current_clip.video_path)))

    image_cols = st.columns(2, gap="large")
    start_path = frame_image_path(selected_pair.start_frame_id)
    end_path = frame_image_path(selected_pair.end_frame_id)
    image_cols[0].image(str(start_path), caption=f"Start frame: {selected_pair.start_frame_id}", use_container_width=True)
    image_cols[1].image(str(end_path), caption=f"End frame: {selected_pair.end_frame_id}", use_container_width=True)

    compare_tab, review_tab = st.tabs(["Compare versions", "Review this version"])

    with compare_tab:
        if len(selected_pair.versions) == 1:
            st.info("Only one version exists for this pair right now. You can still mark it as the winner.")
        else:
            compare_versions(selected_pair)

        if st.button("Mark selected version as winner", use_container_width=True):
            save_winner(selected_pair.pair_id, current_clip.version, run_id=run_id)
            st.success(f"Saved v{current_clip.version} as the winner for {selected_pair.pair_id}.")
            st.rerun()

    with review_tab:
        if review is not None:
            st.info(
                f"Last review: {DECISION_LABELS.get(review.decision, review.decision)}"
                f" | Rating: {review.rating if review.rating is not None else '-'}"
                f" | Reviewed at: {review.reviewed_at}"
            )
        if queued_redo is not None:
            st.warning("This version is currently in the redo queue.")

        with st.expander("Current clip details", expanded=False):
            st.write(f"File: `{current_clip.filename}`")
            st.write(f"Path: `{current_clip.video_path}`")

        with st.form(key=f"review-form-{selected_pair.pair_id}-{current_clip.version}"):
            decision = st.radio(
                "Decision",
                options=DECISIONS,
                index=DECISIONS.index(review.decision) if review else 0,
                format_func=lambda item: DECISION_LABELS[item],
                horizontal=True,
            )

            rating_options = ["-"] + [str(number) for number in range(1, 6)]
            saved_rating = str(review.rating) if review and review.rating is not None else "-"
            rating_value = st.select_slider("Quality rating", options=rating_options, value=saved_rating)

            issue_defaults = review.issues if review else []
            issues = st.multiselect(
                "What went wrong?",
                options=list(ISSUE_TAGS),
                default=issue_defaults,
                format_func=lambda item: ISSUE_LABELS[item],
                placeholder="Choose one or more issue tags",
            )

            note = st.text_area(
                "Optional note",
                value=review.note if review else "",
                placeholder="Example: face morphs in the middle, transition is too dramatic.",
                height=120,
            )

            reviewed_by = st.text_input("Reviewer", value=review.reviewed_by if review else "local-user")
            submitted = st.form_submit_button("Save review", type="primary", use_container_width=True)

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

                st.success("Review saved.")
                st.rerun()


def render_status_banner(status: str, winner_version: int | None, selected_version: int) -> None:
    classes = {
        "Needs review": "status-pill status-unreviewed",
        "Approved": "status-pill status-approved",
        "Redo queued": "status-pill status-redo",
        "Needs discussion": "status-pill status-discussion",
    }
    badge = f'<span class="{classes[status]}">{status}</span>'
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
        "Left version",
        options=version_numbers,
        index=0,
        format_func=lambda version: f"v{version}",
        key=f"left-version-{selected_pair.pair_id}",
    )
    right_version = compare_cols[1].selectbox(
        "Right version",
        options=version_numbers,
        index=min(1, len(version_numbers) - 1),
        format_func=lambda version: f"v{version}",
        key=f"right-version-{selected_pair.pair_id}",
    )

    version_map = {item.version: item for item in selected_pair.versions}
    compare_cols[0].video(str(Path(version_map[left_version].video_path)))
    compare_cols[1].video(str(Path(version_map[right_version].video_path)))


def render_redo_queue(redo_requests, review_lookup, winners) -> None:
    st.subheader("Redo queue")
    if not redo_requests:
        st.info("No clips are queued for redo.")
        return

    rows: list[dict[str, str | int]] = []
    for item in redo_requests:
        review = review_lookup.get((item.pair_id, item.source_version))
        rows.append(
            {
                "pair": item.pair_id,
                "version": f"v{item.source_version}",
                "status": item.status,
                "issues": ", ".join(ISSUE_LABELS[tag] for tag in item.issues) if item.issues else "-",
                "note": item.note or "-",
                "winner": f"v{winners[item.pair_id]}" if item.pair_id in winners else "-",
                "decision": DECISION_LABELS.get(review.decision, "-") if review else "-",
            }
        )

    metric_cols = st.columns(3)
    metric_cols[0].metric("Queued clips", len(rows))
    metric_cols[1].metric("Pairs with winners", sum(1 for item in rows if item["winner"] != "-"))
    metric_cols[2].metric("Notes added", sum(1 for item in rows if item["note"] != "-"))

    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption("This queue is the handoff for the next regeneration pass.")


def filtered_rows(pair_rows, status_filter: str):
    if status_filter == "All clips":
        return pair_rows
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


def next_pair_needing_review(pair_rows):
    for item in pair_rows:
        if item["status"] == "Needs review":
            return item["pair_id"]
    return None


def pair_label(pair_id: str) -> str:
    start_frame, end_frame = pair_id.split("_to_", 1)
    return f"{pair_id} | {start_frame} to {end_frame}"


if __name__ == "__main__":
    main()
