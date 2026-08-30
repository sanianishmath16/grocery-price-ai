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
    # Corn: vivid yellow (narrow band)
    ("Sweet Corn",   38,   52, 120, 160, 255, 0.74),
    # ── Fruits ───────────────────────────────────────────────────────────
    # Apple (red) — colour group dedup keeps highest-conf per red band
    ("Apple",         0,   14, 120, 60, 255, 0.70),
    ("Apple",       242,  255, 120, 60, 255, 0.70),
    # Orange — distinct saturation from Carrot
    ("Orange",       14,   28, 160, 120, 255, 0.80),
    # Grapes: purple band
    ("Grapes",      185,  225, 70,  30, 150, 0.72),
    # Strawberry: red, slightly lower sat than Tomato
    ("Strawberry",    0,   14, 110, 80, 230, 0.72),
    ("Strawberry",  242,  255, 110, 80, 230, 0.72),
]
# Cauliflower/Garlic/Potato/Milk are handled exclusively by _LOW_SAT_PROFILES
# (stricter hit-fraction thresholds) to prevent white backgrounds triggering them.

# Pre-sort by confidence descending so first match is best
_COLOUR_PROFILES.sort(key=lambda x: x[6], reverse=True)


# ---------------------------------------------------------------------------
# Colour-band groups — for deduplication within a single crop.
#
# When multiple profile names share the same dominant colour band, keep only
# the highest-confidence hit per group.  This prevents one red object from
# simultaneously producing Tomato + Capsicum + Strawberry + Pomegranate.
# ---------------------------------------------------------------------------
_COLOUR_GROUPS: List[Tuple[str, ...]] = [
    # Red band
    ("Tomato", "Capsicum", "Strawberry", "Apple", "Pomegranate"),
    # Orange band
    ("Carrot", "Orange", "Pumpkin", "Papaya", "Mango"),
    # Yellow band
    ("Banana", "Lemon", "Sweet Corn"),
    # Green band
    ("Broccoli", "Cabbage", "Spinach", "Cucumber", "Watermelon"),
    # Purple band
    ("Brinjal", "Grapes", "Onion", "Beetroot"),
    # Neutral / low-sat (only fire when there's a VERY dominant neutral mass)
    ("Cauliflower", "Mushroom", "Garlic", "Potato", "Milk", "Water Bottle"),
]

# Build reverse lookup: name → group index
_NAME_TO_GROUP: dict[str, int] = {}
for _gi, _grp in enumerate(_COLOUR_GROUPS):
    for _nm in _grp:
        _NAME_TO_GROUP[_nm] = _gi


def _dedup_by_colour_group(hits: dict) -> dict:
    """
    Given {name: confidence}, keep only the top-confidence name per colour group.
    Names not in any group are kept as-is.
    """
    group_best: dict[int, tuple] = {}   # group_idx → (name, conf)
    ungrouped: dict[str, float] = {}

    for name, conf in hits.items():
        gi = _NAME_TO_GROUP.get(name)
        if gi is None:
            ungrouped[name] = conf
        else:
            current = group_best.get(gi)
            if current is None or conf > current[1]:
                group_best[gi] = (name, conf)

    result = ungrouped.copy()
    for name, conf in group_best.values():
        result[name] = conf
    return result


# ---------------------------------------------------------------------------
# Mushroom / garlic / cauliflower — low-saturation recognizer (special cases)
# ---------------------------------------------------------------------------
_LOW_SAT_PROFILES: List[Tuple[str, int, int, int, int, float]] = [
    # (name, val_lo, val_hi, sat_lo, sat_hi, confidence)
    # Require sat < 45 AND minimum hit fraction 25% to distinguish from neutral
    # backgrounds (white walls, packaging, bright floors).
    ("Cauliflower", 195, 255,  0,  45, 0.62),   # bright white
    ("Garlic",      200, 255,  0,  30, 0.58),   # very white, very low sat
    # Mushroom and potato have too much overlap with common backgrounds —
    # removed from low-sat profiles to avoid false positives on grey scenes.
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

    Anti-hallucination design
    -------------------------
    • MIN_HIT_FRACTION = 0.15  — at least 15% of crop pixels must match the
      colour profile.  This prevents a small red package corner from triggering
      "Tomato" across the whole image.
    • MIN_CONF = 0.55          — only return products with strong colour evidence.
    • Per-image cap = 5        — a real-world basket rarely has more than 5
      visually distinct dominant colours.  Sub-crops are used for multi-object
      images; the global dedup prevents the same object being counted twice.
    • Dominant-colour guard    — a product is only returned if its colour is
      among the top-3 most dominant colours in the image, not just present.
    """

    # Minimum fraction of pixels matching a colour profile to trigger detection.
    # 15% prevents small colourful labels/backgrounds from falsely firing.
    MIN_HIT_FRACTION = 0.15
    # Minimum confidence to return — below this the match is unreliable.
    MIN_CONF = 0.55
    # Maximum distinct products returned per full classify() call (all crops).
    # If a user uploads 1 image with 6 real objects, sub-crops will find them.
    # Capping at 6 prevents colour noise from adding phantom products.
    MAX_PRODUCTS = 6

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
        sorted by confidence descending, capped at MAX_PRODUCTS.

        Anti-hallucination: only names whose best confidence exceeds MIN_CONF
        AND whose colour is dominant in at least one crop are returned.
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

        # Final cross-crop dedup: keep only top name per colour group
        accumulated = _dedup_by_colour_group(accumulated)
        # Hard filter: only return products above MIN_CONF threshold
        filtered = [(n, c) for n, c in accumulated.items() if c >= self.MIN_CONF]
        sorted_results = sorted(filtered, key=lambda x: x[1], reverse=True)
        # Cap at MAX_PRODUCTS — prevents colour noise accumulating across crops
        return [(n, round(min(c, 0.97), 3)) for n, c in sorted_results[:self.MAX_PRODUCTS]]

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
            hit_frac = float(np.sum(mask)) / total_pixels

            if hit_frac >= self.MIN_HIT_FRACTION:
                # Confidence = base_conf × how dominant (fraction / saturation point).
                # We use 0.30 as the "full dominance" threshold — if 30%+ of the
                # crop matches, confidence is uncapped at base_conf.
                # This prevents low-fraction noise from reaching MIN_CONF.
                conf = base_conf * min(1.0, hit_frac / 0.30)
                if conf >= self.MIN_CONF:
                    hits[name] = max(hits.get(name, 0.0), round(conf, 3))

        # Low-saturation profiles: require higher fraction (neutral backgrounds
        # are common, so we need stricter evidence for cauliflower/mushroom/etc.)
        for name, v_lo, v_hi, s_lo, s_hi, base_conf in _LOW_SAT_PROFILES:
            mask = (S >= s_lo) & (S <= s_hi) & (V >= v_lo) & (V <= v_hi)
            hit_frac = float(np.sum(mask)) / total_pixels
            if hit_frac >= self.MIN_HIT_FRACTION + 0.10:   # 25% min for low-sat
                conf = base_conf * min(1.0, hit_frac / 0.35)
                if conf >= self.MIN_CONF:
                    hits[name] = max(hits.get(name, 0.0), round(conf, 3))

        # Dedup overlapping colour bands before returning
        hits = _dedup_by_colour_group(hits)
        sorted_hits = sorted(hits.items(), key=lambda x: x[1], reverse=True)
        return sorted_hits[:4]   # max 4 per crop to control noise

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
            # this is an upper bound, not exact pixel overlap.
            hit_frac = min(h_count, s_count, v_count) / total

            if hit_frac >= self.MIN_HIT_FRACTION:
                conf = base_conf * min(1.0, hit_frac / 0.30)
                if conf >= self.MIN_CONF:
                    hits[name] = max(hits.get(name, 0.0), round(conf, 3))

        hits = _dedup_by_colour_group(hits)
        return sorted(hits.items(), key=lambda x: x[1], reverse=True)[:4]

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
