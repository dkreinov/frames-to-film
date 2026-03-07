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
    save_review,
    queue_redo,
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


def main() -> None:
    st.set_page_config(
        page_title="Olga Movie Review",
        page_icon="🎬",
        layout="wide",
    )

    st.title("Olga Movie Review")
    st.caption("Review generated clips, mark what went wrong, and build a redo queue.")

    run_id = sidebar_controls()
    ensure_review_files(run_id)

    pairs = discover_clip_pairs()
    reviews = load_reviews(run_id)
    redo_requests = load_redo_queue(run_id)

    if not pairs:
        st.error("No generated clips were found in kling_test/videos.")
        return

    review_lookup = {(item.pair_id, item.version): item for item in reviews}
    redo_lookup = {(item.pair_id, item.source_version): item for item in redo_requests}

    selected_pair = select_pair(pairs, review_lookup)

    left_col, right_col = st.columns([1.15, 1.85], gap="large")

    with left_col:
        render_inbox(pairs, review_lookup, redo_lookup, selected_pair.pair_id)

    with right_col:
        render_review_panel(selected_pair, review_lookup, redo_lookup, run_id)


def sidebar_controls() -> str:
    st.sidebar.header("Review Run")
    return st.sidebar.text_input("Run ID", value=DEFAULT_RUN_ID).strip() or DEFAULT_RUN_ID


def select_pair(pairs, review_lookup):
    pair_ids = [pair.pair_id for pair in pairs]
    unreviewed_pair_ids = [
        pair.pair_id
        for pair in pairs
        if (pair.pair_id, pair.latest_version().version) not in review_lookup
    ]

    if "selected_pair_id" not in st.session_state:
        st.session_state.selected_pair_id = unreviewed_pair_ids[0] if unreviewed_pair_ids else pair_ids[0]

    selected_pair_id = st.sidebar.selectbox(
        "Clip",
        options=pair_ids,
        index=pair_ids.index(st.session_state.selected_pair_id),
        format_func=lambda pair_id: pair_label(pair_id),
    )
    st.session_state.selected_pair_id = selected_pair_id

    return next(pair for pair in pairs if pair.pair_id == selected_pair_id)


def render_inbox(pairs, review_lookup, redo_lookup, selected_pair_id: str) -> None:
    st.subheader("Inbox")

    total_pairs = len(pairs)
    approved = 0
    redo = 0
    discussion = 0
    unreviewed = 0

    rows: list[dict[str, str | int]] = []
    for pair in pairs:
        latest = pair.latest_version()
        if latest is None:
            continue

        review = review_lookup.get((pair.pair_id, latest.version))
        if review is None:
            status = "Unreviewed"
            unreviewed += 1
        elif review.decision == "approve":
            status = "Approved"
            approved += 1
        elif review.decision == "redo":
            status = "Redo requested"
            redo += 1
        else:
            status = "Needs discussion"
            discussion += 1

        if (pair.pair_id, latest.version) in redo_lookup and status != "Redo requested":
            status = "Redo queued"

        rows.append(
            {
                "pair": pair.pair_id,
                "version": f"v{latest.version}",
                "status": status,
                "rating": review.rating if review and review.rating is not None else "-",
                "selected": "●" if pair.pair_id == selected_pair_id else "",
            }
        )

    metric_cols = st.columns(4)
    metric_cols[0].metric("Unreviewed", unreviewed)
    metric_cols[1].metric("Approved", approved)
    metric_cols[2].metric("Redo", redo)
    metric_cols[3].metric("Discuss", discussion)

    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption(f"{total_pairs} total pairs discovered from kling_test/videos.")


def render_review_panel(selected_pair, review_lookup, redo_lookup, run_id: str) -> None:
    latest = selected_pair.latest_version()
    if latest is None:
        st.warning("This pair has no clip versions.")
        return

    review = review_lookup.get((selected_pair.pair_id, latest.version))
    queued_redo = redo_lookup.get((selected_pair.pair_id, latest.version))

    st.subheader(pair_label(selected_pair.pair_id))
    meta_cols = st.columns(4)
    meta_cols[0].metric("Current version", f"v{latest.version}")
    meta_cols[1].metric("Start frame", selected_pair.start_frame_id)
    meta_cols[2].metric("End frame", selected_pair.end_frame_id)
    meta_cols[3].metric("Redo queue", "Queued" if queued_redo else "Not queued")

    st.video(str(Path(latest.video_path)))

    image_cols = st.columns(2, gap="large")
    start_path = frame_image_path(selected_pair.start_frame_id)
    end_path = frame_image_path(selected_pair.end_frame_id)
    image_cols[0].image(str(start_path), caption=f"Start frame: {selected_pair.start_frame_id}", use_container_width=True)
    image_cols[1].image(str(end_path), caption=f"End frame: {selected_pair.end_frame_id}", use_container_width=True)

    if review is not None:
        st.info(
            f"Last review: {DECISION_LABELS.get(review.decision, review.decision)}"
            f" | Rating: {review.rating if review.rating is not None else '-'}"
            f" | Reviewed at: {review.reviewed_at}"
        )

    with st.expander("Current clip details", expanded=False):
        st.write(f"File: `{latest.filename}`")
        st.write(f"Path: `{latest.video_path}`")

    with st.form(key=f"review-form-{selected_pair.pair_id}-{latest.version}"):
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
                version=latest.version,
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
                        source_version=latest.version,
                        issues=issues,
                        note=note.strip(),
                    ),
                    run_id=run_id,
                )

            st.success("Review saved.")
            st.rerun()


def pair_label(pair_id: str) -> str:
    start_frame, end_frame = pair_id.split("_to_", 1)
    return f"{pair_id}  |  {start_frame} → {end_frame}"


if __name__ == "__main__":
    main()
