from functools import lru_cache
from typing import Iterable, Tuple

import cv2
import easyocr
import numpy as np

ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
WESTERN_DIGITS = "0123456789"


@lru_cache(maxsize=1)
def _get_reader():
    # gpu=False ensures compatibility on servers without GPU support.
    return easyocr.Reader(["ar", "en"], gpu=False)


def _rotate_image(image: np.ndarray, angle: int) -> np.ndarray:
    if angle == 0:
        return image
    if angle == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if angle == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    if angle == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    raise ValueError(f"Unsupported rotation angle: {angle}")


def _score_results(results: Iterable[Tuple]) -> float:
    score = 0.0
    for item in results:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            continue
        _bbox, text, confidence = item
        if isinstance(text, str) and text.strip():
            score += len(text.strip()) * float(confidence)
    return score


def _auto_orient_and_crop(image_path: str, reader, save_path: str | None = None) -> np.ndarray:
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Unable to read image at {image_path}")

    evaluated: list[Tuple[float, np.ndarray, list]] = []
    for angle in (0, 90, 180, 270):
        rotated = _rotate_image(image, angle)
        results = reader.readtext(rotated, detail=1, paragraph=False)
        score = _score_results(results)
        evaluated.append((score, rotated, results))

    # Choose orientation with highest OCR confidence/coverage
    evaluated.sort(key=lambda item: item[0], reverse=True)
    _best_score, best_image, best_results = evaluated[0]

    if best_results:
        points = []
        for bbox, text, confidence in best_results:
            if not text or not text.strip():
                continue
            if float(confidence) < 0.2:
                continue
            points.extend(bbox)

        if points:
            coords = np.array(points)
            min_x = max(int(np.min(coords[:, 0]) - 20), 0)
            max_x = min(int(np.max(coords[:, 0]) + 20), best_image.shape[1])
            min_y = max(int(np.min(coords[:, 1]) - 20), 0)
            max_y = min(int(np.max(coords[:, 1]) + 20), best_image.shape[0])
            if max_x - min_x > 10 and max_y - min_y > 10:
                best_image = best_image[min_y:max_y, min_x:max_x]

    if save_path:
        cv2.imwrite(save_path, best_image)
    return best_image


def extract_text(image_path: str, *, processed_path: str | None = None) -> str:
    reader = _get_reader()
    try:
        processed_image = _auto_orient_and_crop(image_path, reader, processed_path)
    except Exception:
        processed_image = cv2.imread(image_path)
        if processed_image is None:
            return ""

    results = reader.readtext(processed_image, detail=0, paragraph=True)
    if not results:
        results = reader.readtext(processed_image, detail=0, paragraph=False)
    return "\n".join(results)


def normalize_digits(text: str) -> str:
    return text.translate(str.maketrans(ARABIC_DIGITS, WESTERN_DIGITS))
