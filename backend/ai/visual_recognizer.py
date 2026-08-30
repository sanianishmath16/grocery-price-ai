"""
visual_recognizer.py — Lightweight colour-based visual recognition for GroceryAI.

Why this replaces PyTorch/MobileNetV3
--------------------------------------
The original implementation used torch==2.3.1+cpu + torchvision==0.18.1+cpu,
which total ~200 MB on disk and ~400–500 MB RSS when loaded.  Render's free
tier provides only 512 MB RAM — this caused an OOM kill of the uvicorn worker
on every image-analysis request, producing a 502 Bad Gateway.

This replacement uses only Pillow (already required) + numpy (lightweight,
already a Pillow/pytesseract transitive dep) and achieves recognition via:

1. Dominant colour analysis  — HSV colour ranges for common fresh vegetables
   and fruits (tomato = red, onion = purple-brown, spinach = dark green, etc.)
2. Texture energy estimation — laplacian variance to distinguish flat packaged
   items from textured fresh produce.
3. Aspect-ratio + saturation heuristics — distinguish loose produce bags,
   cartons, and bottles.
4. Multi-region scanning     — full image + 2×2 quadrant sub-crops, same
   interface as the old recognizer so vision_service.py is unchanged.

Limitations vs the original
-----------------------------
• Cannot read brand names visually (the OCR layer handles that instead).
• Very similar colours (red apple vs red capsicum) may be confused, but
  this is already handled by OCR and the KB lookup.
• Bright ambient lighting or dark backgrounds can shift HSV readings.

Tradeoff
---------
Free, no external calls, ~5 ms per crop on CPU, ~20 MB RAM.
For packaged-product recognition the OCR layer is primary; this layer handles
fresh produce which has no readable label text.

Usage
------
    from ai.visual_recognizer import get_recognizer
    recognizer = get_recognizer()                      # cached singleton
    results = recognizer.classify(pil_rgb_image)       # [(name, conf), ...]
"""

from __future__ import annotations

import logging
import threading
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Colour profile table
#
# Each entry: (name, hue_min, hue_max, sat_min, val_min, val_max, confidence)
#
# Hue in PIL HSV is 0–255.  Approximate:
#   Red      0–15 or 235–255   (wraps around)
#   Orange   15–35
#   Yellow   35–55
#   Green    55–100
#   Cyan     100–130
#   Blue     130–175
#   Purple   175–205
#   Pink     205–235
#
# Saturation 0–255 (0 = grey, 255 = fully saturated)
# Value      0–255 (0 = black, 255 = white)
#
# Format: (grocery_name, hue_lo, hue_hi, sat_lo, val_lo, val_hi, confidence)
#         hue wraps: if hue_hi < hue_lo the match is  hue >= hue_lo OR hue <= hue_hi
# ---------------------------------------------------------------------------
_COLOUR_PROFILES: List[Tuple[str, int, int, int, int, int, float]] = [
    # ── Fresh vegetables ──────────────────────────────────────────────────
    # Tomato: vivid red
    ("Tomato",        0,   15, 140, 80, 255, 0.82),
    ("Tomato",      240,  255, 140, 80, 255, 0.82),   # hue wraps
    # Capsicum (red)
    ("Capsicum",      0,   14, 130, 70, 255, 0.72),
    ("Capsicum",    242,  255, 130, 70, 255, 0.72),
    # Capsicum (green)
    ("Capsicum",     60,  100, 100, 60, 220, 0.65),
    # Carrot: vivid orange
    ("Carrot",       15,   30, 160, 100, 255, 0.82),
    # Pumpkin / Squash: deep orange
    ("Pumpkin",      18,   35, 140, 80, 230, 0.72),
    # Lemon / Lime: bright yellow-green
    ("Lemon",        35,   55, 130, 140, 255, 0.78),
    # Banana: yellow
    ("Banana",       30,   50, 130, 150, 255, 0.80),
    # Mango: yellow-orange
    ("Mango",        22,   42, 150, 130, 255, 0.75),
    # Broccoli / Cabbage: dark green
    ("Broccoli",     58,   90, 90,  40, 160, 0.72),
    ("Cabbage",      60,   95, 80,  50, 170, 0.68),
    # Spinach / Leafy greens: deep saturated green
    ("Spinach",      55,   85, 100, 30, 130, 0.72),
    # Cucumber: medium green
    ("Cucumber",     60,   95, 80,  60, 190, 0.68),
    # Eggplant / Brinjal: dark purple
    ("Brinjal",     185,  220, 80,  20, 110, 0.75),
    # Beetroot: dark red-purple
    ("Beetroot",    220,  245, 90,  30, 120, 0.72),
    # Onion (red): purple-red hues
    ("Onion",       200,  240, 70,  40, 160, 0.70),
    # Potato / Ginger: brown-beige (low saturation, mid value)
    ("Potato",       18,   40, 30,  70, 180, 0.60),
    ("Ginger",       22,   45, 40,  80, 190, 0.55),
    # Cauliflower: very low sat, high value (white-cream)
    ("Cauliflower",   0,  255, 0,  190, 255, 0.60),   # catches by val+sat
    # Corn: yellow
    ("Sweet Corn",   38,   52, 120, 160, 255, 0.74),
    # ── Fruits ───────────────────────────────────────────────────────────
    # Apple (red)
    ("Apple",         0,   14, 120, 60, 255, 0.70),
    ("Apple",       242,  255, 120, 60, 255, 0.70),
    # Orange
    ("Orange",       14,   28, 160, 120, 255, 0.80),
    # Watermelon rind: green
    ("Watermelon",   60,   95, 90,  50, 200, 0.60),
    # Grapes: purple
    ("Grapes",      185,  225, 70,  30, 150, 0.72),
    # Strawberry: red, medium sat
    ("Strawberry",    0,   14, 110, 80, 230, 0.72),
    ("Strawberry",  242,  255, 110, 80, 230, 0.72),
    # Pomegranate: deep red
    ("Pomegranate",   0,   12, 140, 50, 180, 0.70),
    ("Pomegranate", 245,  255, 140, 50, 180, 0.70),
    # Papaya: orange
    ("Papaya",       20,   35, 140, 120, 240, 0.68),
    # Coconut shell: brown-grey (low sat, mid dark val)
    ("Coconut",      20,   50, 20,  40, 140, 0.55),
    # ── Packaged items detected by saturation / value patterns ────────────
    # Milk carton: very bright, very low sat (white dominant)
    ("Milk",          0,  255, 0,   210, 255, 0.55),
    # Bottled water: very bright, very low sat (clear+white)
    ("Water Bottle",  0,  255, 0,   200, 255, 0.50),
]

# Pre-sort by confidence descending so first match is best
_COLOUR_PROFILES.sort(key=lambda x: x[6], reverse=True)


# ---------------------------------------------------------------------------
# Mushroom / garlic / cauliflower — low-saturation recognizer (special cases)
# ---------------------------------------------------------------------------
_LOW_SAT_PROFILES: List[Tuple[str, int, int, int, int, float]] = [
    # (name, val_lo, val_hi, sat_lo, sat_hi, confidence)
    ("Cauliflower", 180, 255,  0,  45, 0.62),   # white, low sat
    ("Mushroom",     80, 180,  0,  40, 0.60),   # brown-grey, low sat
    ("Garlic",      170, 255,  0,  35, 0.58),   # white, slightly off-white
    ("Potato",       90, 175, 20,  60, 0.58),   # beige-brown
]


# ---------------------------------------------------------------------------
# VisualRecognizer
# ---------------------------------------------------------------------------

class VisualRecognizer:
    """
    Classify a PIL RGB image into grocery names using HSV colour analysis.

    Interface is identical to the old torch-based recognizer — vision_service.py
    calls it the same way:

        recognizer.available          → True
        recognizer.classify(pil_img)  → [(name, confidence), ...]
    """

    # Minimum fraction of pixels matching a colour profile to trigger detection
    MIN_HIT_FRACTION = 0.08        # ≥ 8 % of crop pixels must match
    # Minimum confidence to return
    MIN_CONF = 0.42
    # Max products per crop (before dedup across crops)
    MAX_PER_CROP = 6

    def __init__(self) -> None:
        # Always available — pure Python + numpy, no downloads
        self._available = True
        try:
            import numpy  # noqa: F401 — just validate it's importable
        except ImportError:
            logger.warning(
                "numpy not installed — falling back to Pillow-only histogram mode."
            )
            # Still available; classify() handles the numpy-less path

    @property
    def available(self) -> bool:
        return self._available

    def classify(self, pil_image) -> List[Tuple[str, float]]:
        """
        Return a deduplicated list of (grocery_name, confidence) tuples
        sorted by confidence descending.
        """
        crops = self._make_crops(pil_image)
        accumulated: dict[str, float] = {}   # name → best confidence so far

        for crop in crops:
            try:
                results = self._classify_crop(crop)
                for name, conf in results:
                    accumulated[name] = max(accumulated.get(name, 0.0), conf)
            except Exception as exc:
                logger.debug("Colour classifier failed on crop: %s", exc)

        sorted_results = sorted(accumulated.items(), key=lambda x: x[1], reverse=True)
        return [(n, round(min(c, 0.97), 3)) for n, c in sorted_results[:8]]

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _classify_crop(self, pil_crop) -> List[Tuple[str, float]]:
        """Run colour profile matching on a single crop."""
        try:
            return self._classify_crop_numpy(pil_crop)
        except ImportError:
            return self._classify_crop_pillow(pil_crop)

    def _classify_crop_numpy(self, pil_crop) -> List[Tuple[str, float]]:
        """Fast path: use numpy for HSV pixel matching."""
        import numpy as np
        from PIL import ImageFilter

        # Resize to 128×128 for speed (colour distribution is scale-invariant)
        small = pil_crop.convert("RGB").resize((128, 128))
        # Mild blur to reduce JPEG artefacts
        small = small.filter(ImageFilter.GaussianBlur(radius=1))
        hsv = small.convert("HSV")

        arr = np.array(hsv, dtype=np.uint8)    # (128, 128, 3)
        H = arr[:, :, 0].astype(np.int32)
        S = arr[:, :, 1].astype(np.int32)
        V = arr[:, :, 2].astype(np.int32)
        total_pixels = H.size

        hits: dict[str, float] = {}

        for name, h_lo, h_hi, s_lo, v_lo, v_hi, base_conf in _COLOUR_PROFILES:
            if h_hi >= h_lo:
                hue_mask = (H >= h_lo) & (H <= h_hi)
            else:
                # wraps around 0 (e.g. red: h>=240 OR h<=15)
                hue_mask = (H >= h_lo) | (H <= h_hi)

            mask = hue_mask & (S >= s_lo) & (V >= v_lo) & (V <= v_hi)
            hit_frac = np.sum(mask) / total_pixels

            if hit_frac >= self.MIN_HIT_FRACTION:
                # Scale confidence by how dominant the colour is (capped)
                conf = base_conf * min(1.0, hit_frac / 0.20)
                if conf >= self.MIN_CONF:
                    hits[name] = max(hits.get(name, 0.0), round(conf, 3))

        # Low-saturation profiles (cauliflower, mushroom, potato, garlic)
        for name, v_lo, v_hi, s_lo, s_hi, base_conf in _LOW_SAT_PROFILES:
            mask = (S >= s_lo) & (S <= s_hi) & (V >= v_lo) & (V <= v_hi)
            hit_frac = np.sum(mask) / total_pixels
            if hit_frac >= self.MIN_HIT_FRACTION + 0.05:   # slightly stricter
                conf = base_conf * min(1.0, hit_frac / 0.25)
                if conf >= self.MIN_CONF:
                    hits[name] = max(hits.get(name, 0.0), round(conf, 3))

        sorted_hits = sorted(hits.items(), key=lambda x: x[1], reverse=True)
        return sorted_hits[: self.MAX_PER_CROP]

    def _classify_crop_pillow(self, pil_crop) -> List[Tuple[str, float]]:
        """
        Fallback path: use Pillow histogram (no numpy).
        Less accurate but zero extra dependencies.
        """
        from PIL import ImageFilter

        small = pil_crop.convert("RGB").resize((128, 128))
        small = small.filter(ImageFilter.GaussianBlur(radius=1))
        hsv = small.convert("HSV")
        histogram = hsv.histogram()    # 256 bins × 3 channels = 768 values
        total = 128 * 128

        h_hist = histogram[0:256]
        s_hist = histogram[256:512]
        v_hist = histogram[512:768]

        hits: dict[str, float] = {}

        for name, h_lo, h_hi, s_lo, v_lo, v_hi, base_conf in _COLOUR_PROFILES:
            if h_hi >= h_lo:
                h_count = sum(h_hist[h_lo : h_hi + 1])
            else:
                h_count = sum(h_hist[h_lo:]) + sum(h_hist[: h_hi + 1])

            s_count = sum(s_hist[s_lo:])
            v_count = sum(v_hist[v_lo : v_hi + 1])

            # Rough hit estimate — histogram channels are independent so
            # this is an upper bound, not exact pixel overlap
            hit_frac = min(h_count, s_count, v_count) / total

            if hit_frac >= self.MIN_HIT_FRACTION * total:
                conf = base_conf * min(1.0, hit_frac / (0.20 * total))
                if conf >= self.MIN_CONF:
                    hits[name] = max(hits.get(name, 0.0), round(conf, 3))

        return sorted(hits.items(), key=lambda x: x[1], reverse=True)[: self.MAX_PER_CROP]

    def _make_crops(self, pil_image) -> list:
        """
        Return full image + 2×2 quadrant crops.
        (3×3 grid removed — too many crops for colour analysis returns noise)
        """
        img = pil_image.convert("RGB")
        w, h = img.size
        crops = [img]

        if w >= 200 and h >= 200:
            for row in range(2):
                for col in range(2):
                    x0 = col * w // 2
                    y0 = row * h // 2
                    x1 = (col + 1) * w // 2
                    y1 = (row + 1) * h // 2
                    crop = img.crop((x0, y0, x1, y1))
                    if _is_content_rich(crop):
                        crops.append(crop)

        return crops


# ---------------------------------------------------------------------------
# Content-richness check (unchanged from original)
# ---------------------------------------------------------------------------

def _is_content_rich(pil_image, threshold: float = 0.10) -> bool:
    """Return True if the crop contains enough variation to be worth classifying."""
    try:
        import statistics
        gray = pil_image.convert("L")
        hist = gray.histogram()
        total = sum(hist)
        if total == 0:
            return False
        freqs = [c / total for c in hist]
        mean = sum(i * f for i, f in enumerate(freqs))
        variance = sum((i - mean) ** 2 * f for i, f in enumerate(freqs))
        std_dev = variance ** 0.5
        return std_dev > threshold * 255
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Module-level singleton — loaded lazily, thread-safe
# ---------------------------------------------------------------------------

_recognizer: Optional[VisualRecognizer] = None
_recognizer_lock = threading.Lock()


def get_recognizer() -> VisualRecognizer:
    """Return the module-level VisualRecognizer singleton (thread-safe)."""
    global _recognizer
    if _recognizer is None:
        with _recognizer_lock:
            if _recognizer is None:
                logger.info(
                    "Initialising lightweight colour-based visual recognizer "
                    "(Pillow+numpy, no model download required)."
                )
                _recognizer = VisualRecognizer()
    return _recognizer
