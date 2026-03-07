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


def main() -> None:
    st.set_page_config(
        page_title="Olga Movie Review",
        page_icon="M",
        layout="wide",
    )

    st.title("Olga Movie Review")
    st.caption("Review generated clips, choose winners, and build a redo queue.")

    run_id = sidebar_controls()
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

    selected_pair = select_pair(pairs, winners)

    review_tab, queue_tab = st.tabs(["Review", "Redo queue"])
    with review_tab:
        left_col, right_col = st.columns([1.1, 1.9], gap="large")
        with left_col:
            render_inbox(pairs, review_lookup, redo_lookup, winners, selected_pair.pair_id)
        with right_col:
            render_review_panel(selected_pair, review_lookup, redo_lookup, winners, run_id)

    with queue_tab:
        render_redo_queue(redo_requests, review_lookup, winners)


def sidebar_controls() -> str:
    st.sidebar.header("Review Run")
    return st.sidebar.text_input("Run ID", value=DEFAULT_RUN_ID).strip() or DEFAULT_RUN_ID


def select_pair(pairs, winners):
    pair_ids = [pair.pair_id for pair in pairs]
    if "selected_pair_id" not in st.session_state:
        st.session_state.selected_pair_id = pair_ids[0]

    selected_pair_id = st.sidebar.selectbox(
        "Clip",
        options=pair_ids,
        index=pair_ids.index(st.session_state.selected_pair_id),
        format_func=pair_label,
    )
    st.session_state.selected_pair_id = selected_pair_id
    return next(pair for pair in pairs if pair.pair_id == selected_pair_id)


def render_inbox(pairs, review_lookup, redo_lookup, winners, selected_pair_id: str) -> None:
    st.subheader("Inbox")

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

        if (pair.pair_id, latest.version) in redo_lookup:
            status = "Redo queued"

        winner_version = winners.get(pair.pair_id)
        rows.append(
            {
                "selected": "*" if pair.pair_id == selected_pair_id else "",
                "pair": pair.pair_id,
                "latest": f"v{latest.version}",
                "winner": f"v{winner_version}" if winner_version else "-",
                "versions": len(pair.versions),
                "status": status,
                "rating": review.rating if review and review.rating is not None else "-",
            }
        )

    metric_cols = st.columns(4)
    metric_cols[0].metric("Unreviewed", unreviewed)
    metric_cols[1].metric("Approved", approved)
    metric_cols[2].metric("Redo", redo)
    metric_cols[3].metric("Discuss", discussion)
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_review_panel(selected_pair, review_lookup, redo_lookup, winners, run_id: str) -> None:
    st.subheader(pair_label(selected_pair.pair_id))

    version_labels = [f"v{item.version} - {item.filename}" for item in selected_pair.versions]
    default_version = selected_pair.latest_version().version
    if "selected_version_by_pair" not in st.session_state:
        st.session_state.selected_version_by_pair = {}
    selected_version = st.session_state.selected_version_by_pair.get(selected_pair.pair_id, default_version)
    version_map = {item.version: item for item in selected_pair.versions}
    selected_version = st.selectbox(
        "Version",
        options=[item.version for item in selected_pair.versions],
        index=[item.version for item in selected_pair.versions].index(selected_version),
        format_func=lambda version: version_labels[[item.version for item in selected_pair.versions].index(version)],
    )
    st.session_state.selected_version_by_pair[selected_pair.pair_id] = selected_version
    current_clip = version_map[selected_version]

    winner_version = winners.get(selected_pair.pair_id)
    review = review_lookup.get((selected_pair.pair_id, current_clip.version))
    queued_redo = redo_lookup.get((selected_pair.pair_id, current_clip.version))

    meta_cols = st.columns(4)
    meta_cols[0].metric("Selected version", f"v{current_clip.version}")
    meta_cols[1].metric("Start frame", selected_pair.start_frame_id)
    meta_cols[2].metric("End frame", selected_pair.end_frame_id)
    meta_cols[3].metric("Winner", f"v{winner_version}" if winner_version else "Not set")

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
                "issues": ", ".join(item.issues) if item.issues else "-",
                "note": item.note or "-",
                "winner": f"v{winners[item.pair_id]}" if item.pair_id in winners else "-",
                "decision": DECISION_LABELS.get(review.decision, "-") if review else "-",
            }
        )

    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.caption("This queue is the handoff for the next regeneration pass.")


def pair_label(pair_id: str) -> str:
    start_frame, end_frame = pair_id.split("_to_", 1)
    return f"{pair_id} | {start_frame} to {end_frame}"


if __name__ == "__main__":
    main()
