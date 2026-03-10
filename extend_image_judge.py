from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


def judge_extension(source_path: str | Path, result_path: str | Path) -> dict[str, float | str | bool]:
    available, reason = judge_available()
    if not available:
        return {
            "enabled": False,
            "face_count_score": 0.0,
            "face_identity_score": 0.0,
            "person_count_score": 0.0,
            "edge_duplication_risk": 0.0,
            "overall_score": 0.0,
            "label": "Unavailable",
            "reason": reason,
        }

    try:
        source_image = _open_rgb(source_path)
        result_image = _open_rgb(result_path)
        source_aligned, result_center, center_left = _align_images(source_image, result_image)

        source_faces = _detect_faces(source_aligned)
        result_center_faces = _detect_faces(result_center)
        result_full_faces = _detect_faces(result_image)

        source_people = _detect_people(source_aligned)
        result_center_people = _detect_people(result_center)
        result_full_people = _detect_people(result_image)

        face_count_score = _count_score(len(source_faces), len(result_center_faces))
        person_count_score = _count_score(len(source_people), len(result_center_people))
        face_identity_score = _face_identity_score(source_faces, result_center_faces)
        edge_duplication_risk = _edge_duplication_risk(
            result_image.width,
            center_left,
            result_center.width,
            result_full_faces,
            result_center_faces,
            result_full_people,
            result_center_people,
        )

        overall_score = (
            face_count_score * 0.24
            + face_identity_score * 0.46
            + person_count_score * 0.20
            + (1.0 - edge_duplication_risk) * 0.10
        )
        overall_score = max(0.0, min(1.0, overall_score))
        label = _label_for_score(overall_score, edge_duplication_risk)
        reason = _reason_for_result(
            face_count_score,
            face_identity_score,
            person_count_score,
            edge_duplication_risk,
            len(source_faces),
            len(result_center_faces),
            len(source_people),
            len(result_center_people),
            len(result_full_people),
        )

        return {
            "enabled": True,
            "face_count_score": round(face_count_score, 3),
            "face_identity_score": round(face_identity_score, 3),
            "person_count_score": round(person_count_score, 3),
            "edge_duplication_risk": round(edge_duplication_risk, 3),
            "overall_score": round(overall_score, 3),
            "label": label,
            "reason": reason,
        }
    except Exception as exc:
        return {
            "enabled": False,
            "face_count_score": 0.0,
            "face_identity_score": 0.0,
            "person_count_score": 0.0,
            "edge_duplication_risk": 0.0,
            "overall_score": 0.0,
            "label": "Unavailable",
            "reason": f"Judge failed to run: {exc}",
        }


def judge_available() -> tuple[bool, str]:
    try:
        import insightface  # noqa: F401
        import onnxruntime  # noqa: F401
        import ultralytics  # noqa: F401
    except ImportError as exc:
        return False, f"Missing local judge dependency: {exc.name}"

    try:
        _face_model()
        _person_model()
    except Exception as exc:
        return False, str(exc)

    return True, "Local NN judge ready"


@lru_cache(maxsize=1)
def _face_model():
    try:
        from insightface.app import FaceAnalysis
    except ImportError as exc:
        raise RuntimeError(f"Face model is unavailable: {exc}") from exc

    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    return app


@lru_cache(maxsize=1)
def _person_model():
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError(f"Person model is unavailable: {exc}") from exc

    return YOLO("yolov8n.pt")


def _open_rgb(path: str | Path) -> Image.Image:
    image = Image.open(path)
    image = ImageOps.exif_transpose(image)
    if image.mode != "RGB":
        image = image.convert("RGB")
    return image


def _align_images(source_image: Image.Image, result_image: Image.Image) -> tuple[Image.Image, Image.Image, int]:
    target_height = result_image.height
    resized_width = max(1, round(source_image.width * target_height / source_image.height))
    source_resized = source_image.resize((resized_width, target_height), Image.LANCZOS)

    if resized_width >= result_image.width:
        crop_top = max(0, (source_resized.height - result_image.height) // 2)
        source_resized = source_resized.crop((0, crop_top, result_image.width, crop_top + result_image.height))
        return source_resized, result_image.copy(), 0

    center_left = (result_image.width - resized_width) // 2
    center_right = center_left + resized_width
    result_center = result_image.crop((center_left, 0, center_right, target_height))
    return source_resized, result_center, center_left


def _detect_faces(image: Image.Image) -> list[dict[str, np.ndarray | tuple[float, float, float, float]]]:
    face_app = _face_model()
    bgr = np.asarray(image)[:, :, ::-1]
    faces = []
    for face in face_app.get(bgr):
        embedding = np.asarray(face.normed_embedding, dtype=np.float32)
        faces.append(
            {
                "bbox": tuple(float(value) for value in face.bbox),
                "embedding": embedding,
            }
        )
    return faces


def _detect_people(image: Image.Image) -> list[tuple[float, float, float, float]]:
    model = _person_model()
    results = model.predict(np.asarray(image), classes=[0], verbose=False, conf=0.25)
    people: list[tuple[float, float, float, float]] = []
    for result in results:
        if result.boxes is None:
            continue
        for box in result.boxes.xyxy.cpu().tolist():
            people.append(tuple(float(value) for value in box))
    return people


def _count_score(source_count: int, result_count: int) -> float:
    if source_count == 0 and result_count == 0:
        return 1.0
    baseline = max(1, source_count)
    return max(0.0, 1.0 - abs(source_count - result_count) / baseline)


def _face_identity_score(
    source_faces: list[dict[str, np.ndarray | tuple[float, float, float, float]]],
    result_faces: list[dict[str, np.ndarray | tuple[float, float, float, float]]],
) -> float:
    if not source_faces and not result_faces:
        return 1.0
    if not source_faces or not result_faces:
        return 0.0

    remaining = [face["embedding"] for face in result_faces]
    scores: list[float] = []
    for source_face in source_faces:
        if not remaining:
            scores.append(0.0)
            continue
        source_embedding = source_face["embedding"]
        similarities = [float(np.dot(source_embedding, result_embedding)) for result_embedding in remaining]
        best_index = max(range(len(similarities)), key=similarities.__getitem__)
        scores.append(max(0.0, min(1.0, (similarities[best_index] + 1.0) / 2.0)))
        remaining.pop(best_index)
    return sum(scores) / len(scores)


def _edge_duplication_risk(
    result_width: int,
    center_left: int,
    center_width: int,
    result_full_faces: list[dict[str, np.ndarray | tuple[float, float, float, float]]],
    result_center_faces: list[dict[str, np.ndarray | tuple[float, float, float, float]]],
    result_full_people: list[tuple[float, float, float, float]],
    result_center_people: list[tuple[float, float, float, float]],
) -> float:
    center_right = center_left + center_width
    extra_faces = max(0, len(result_full_faces) - len(result_center_faces))
    extra_people = max(0, len(result_full_people) - len(result_center_people))
    edge_faces = sum(1 for face in result_full_faces if _bbox_center_x(face["bbox"]) < center_left or _bbox_center_x(face["bbox"]) > center_right)
    edge_people = sum(1 for box in result_full_people if _bbox_center_x(box) < center_left or _bbox_center_x(box) > center_right)
    edge_band = max(1, round(result_width * 0.16))
    edge_face_band = sum(
        1
        for face in result_full_faces
        if _bbox_center_x(face["bbox"]) <= edge_band or _bbox_center_x(face["bbox"]) >= result_width - edge_band
    )
    edge_person_band = sum(
        1
        for box in result_full_people
        if _bbox_center_x(box) <= edge_band or _bbox_center_x(box) >= result_width - edge_band
    )
    raw_risk = extra_faces * 0.9 + extra_people * 0.7 + edge_faces * 0.8 + edge_people * 0.5 + edge_face_band * 0.4 + edge_person_band * 0.2
    baseline = max(1.0, len(result_center_faces) + len(result_center_people))
    return max(0.0, min(1.0, raw_risk / baseline))


def _bbox_center_x(bbox: tuple[float, float, float, float]) -> float:
    return (bbox[0] + bbox[2]) / 2


def _label_for_score(overall_score: float, edge_duplication_risk: float) -> str:
    if edge_duplication_risk >= 0.45 or overall_score < 0.5:
        return "Bad"
    if overall_score < 0.75:
        return "Review"
    return "Good"


def _reason_for_result(
    face_count_score: float,
    face_identity_score: float,
    person_count_score: float,
    edge_duplication_risk: float,
    source_faces: int,
    result_faces: int,
    source_people: int,
    result_people: int,
    result_people_full: int,
) -> str:
    if edge_duplication_risk >= 0.45:
        return "Likely invented or duplicated people near the image edges."
    if face_identity_score < 0.55:
        return "Faces no longer match the original strongly enough."
    if face_count_score < 0.7:
        return f"Face count drifted from {source_faces} to {result_faces} in the preserved center."
    if person_count_score < 0.7:
        return f"Person count drifted from {source_people} to {result_people} in the preserved center."
    if result_people_full > result_people:
        return "Preserved center looks acceptable, but extra edge people were detected."
    return "Faces and people look consistent with the original."
