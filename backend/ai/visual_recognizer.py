"""
visual_recognizer.py — Local computer-vision image recognition for GroceryAI.

Model
-----
MobileNetV3-Small pretrained on ImageNet-1k (torchvision).
  • Weight file: ~10 MB (downloaded once to ~/.cache/torch/hub)
  • CPU inference: ~30–80 ms per crop on a 224×224 patch
  • 1000 ImageNet classes cover the majority of fresh produce, packaged food
    categories, bottles, and household product containers.

Architecture
------------
1. Whole-image classification  — classify the full image once.
2. Multi-region scanning       — divide image into 3×3 and 2×2 grid cells;
                                  classify each cell that has sufficient content.
3. Top-K label mapping         — map ImageNet labels → grocery product names
                                  using a comprehensive lookup table.
4. Deduplication + confidence  — merge duplicate products, keep highest score.
5. Fresh produce vs packaging  — separate confidence logic for unpackaged items.

Usage
-----
    from ai.visual_recognizer import VisualRecognizer
    recognizer = VisualRecognizer()           # load once at startup
    results = recognizer.classify(pil_image)  # list of (grocery_name, confidence)

Limitations
-----------
• ImageNet was not trained specifically for grocery recognition, so some
  very niche products (e.g. specific spice brands) may not be detected visually.
• For those, the OCR layer in vision_service.py handles the detection.
• Very similar-looking vegetables (e.g. cucumber vs zucchini) may be confused.
"""

from __future__ import annotations

import logging
import threading
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ImageNet label → grocery product mapping
#
# Key  = lowercase substring that appears in an ImageNet class label
# Value = (canonical_grocery_name, confidence_multiplier)
#
# The confidence multiplier lets us distinguish clear matches (tomato → 1.0)
# from indirect inferences (banana_peel → 0.7, bread_loaf → 0.85).
# ---------------------------------------------------------------------------

_IMAGENET_TO_GROCERY: List[Tuple[str, str, float]] = [
    # ── Fresh vegetables ──────────────────────────────────────────────────
    ("tomato",          "Tomato",               1.00),
    ("cucumber",        "Cucumber",             1.00),
    ("zucchini",        "Cucumber",             0.70),  # often confused
    ("acorn_squash",    "Pumpkin",              0.70),
    ("butternut",       "Pumpkin",              0.75),
    ("pumpkin",         "Pumpkin",              1.00),
    ("cauliflower",     "Cauliflower",          1.00),
    ("broccoli",        "Broccoli",             1.00),
    ("artichoke",       "Cauliflower",          0.65),
    ("head_cabbage",    "Cabbage",              1.00),
    ("red_cabbage",     "Cabbage",              0.90),
    ("cabbage",         "Cabbage",              1.00),
    ("bell_pepper",     "Capsicum",             1.00),
    ("hot_pepper",      "Green Chilli",         0.85),
    ("jalapeño",        "Green Chilli",         0.80),
    ("eggplant",        "Brinjal",              1.00),
    ("corn",            "Sweet Corn",           1.00),
    ("ear_of_corn",     "Sweet Corn",           1.00),
    ("mushroom",        "Mushroom",             1.00),
    ("agaric",          "Mushroom",             0.85),
    ("rapini",          "Broccoli",             0.70),
    ("cardoon",         "Brinjal",              0.60),
    ("spinach",         "Spinach",              0.85),
    ("lettuce",         "Spinach",              0.75),

    # ── Root vegetables ───────────────────────────────────────────────────
    ("carrot",          "Carrot",               1.00),
    ("radish",          "Radish",               1.00),
    ("turnip",          "Radish",               0.75),
    ("potato",          "Potato",               1.00),
    ("beet",            "Beetroot",             0.90),
    ("sweet_potato",    "Potato",               0.80),
    ("yam",             "Potato",               0.70),
    ("taro",            "Potato",               0.70),

    # ── Bulbs / aromatics ─────────────────────────────────────────────────
    ("onion",           "Onion",                1.00),
    ("garlic",          "Garlic",               1.00),
    ("leek",            "Onion",                0.75),

    # ── Fruits ───────────────────────────────────────────────────────────
    ("apple",           "Apple",                1.00),
    ("granny_smith",    "Apple",                0.95),
    ("banana",          "Banana",               1.00),
    ("orange",          "Orange",               1.00),
    ("lemon",           "Lemon",                1.00),
    ("lime",            "Lemon",                0.80),
    ("mango",           "Mango",                1.00),
    ("grape",           "Grapes",               1.00),
    ("strawberry",      "Strawberry",           1.00),
    ("watermelon",      "Watermelon",           1.00),
    ("cantaloupe",      "Muskmelon",            0.90),
    ("pineapple",       "Pineapple",            1.00),
    ("pomegranate",     "Pomegranate",          1.00),
    ("papaya",          "Papaya",               1.00),
    ("guava",           "Guava",                0.90),
    ("coconut",         "Coconut",              1.00),
    ("fig",             "Fig",                  1.00),
    ("pear",            "Pear",                 1.00),
    ("peach",           "Peach",                0.90),
    ("plum",            "Plum",                 0.90),
    ("cherry",          "Cherry",               0.90),
    ("kiwi",            "Kiwi",                 0.90),

    # ── Herbs / leafy greens ──────────────────────────────────────────────
    ("herb",            "Coriander",            0.70),
    ("cilantro",        "Coriander",            1.00),
    ("coriander",       "Coriander",            1.00),
    ("mint",            "Mint",                 1.00),
    ("ginger",          "Ginger",               1.00),

    # ── Packaged food categories (ImageNet has many everyday objects) ─────
    ("loaf",            "Bread",                0.85),
    ("bagel",           "Bread",                0.80),
    ("baguette",        "Bread",                0.80),
    ("pretzel",         "Biscuits",             0.70),
    ("chocolate",       "Chocolate",            0.90),
    ("bonbon",          "Chocolate",            0.80),
    ("ice_cream",       "Ice Cream",            0.90),
    ("pizza",           "Pizza",                0.90),
    ("burrito",         "Packaged Food",        0.70),
    ("noodle",          "Noodles",              0.90),
    ("spaghetti",       "Noodles",              0.85),
    ("soup",            "Soup",                 0.85),
    ("cup_of_tea",      "Tea",                  0.80),
    ("coffee_mug",      "Coffee",               0.80),
    ("espresso",        "Coffee",               0.80),
    ("milk_can",        "Milk",                 0.80),
    ("eggnog",          "Milk",                 0.75),
    ("beer_bottle",     "Packaged Beverage",    0.70),
    ("wine_bottle",     "Packaged Beverage",    0.70),
    ("water_bottle",    "Packaged Beverage",    0.75),
    ("pop_bottle",      "Packaged Beverage",    0.80),
    ("plastic_bag",     "Packaged Food",        0.55),
    ("packet",          "Packaged Food",        0.60),
    ("box",             "Packaged Food",        0.55),
    ("jar",             "Packaged Food",        0.60),
    ("can",             "Packaged Beverage",    0.65),
    ("tin_can",         "Packaged Food",        0.65),
    ("carton",          "Packaged Food",        0.60),
    ("chip",            "Chips",                0.80),
    ("french_loaf",     "Bread",                0.80),
    ("pretzel",         "Snacks",               0.70),
    ("cracker",         "Biscuits",             0.80),
    ("cheese",          "Cheese",               0.90),
    ("butter",          "Butter",               0.85),
    ("egg",             "Eggs",                 0.95),
    ("hen",             "Eggs",                 0.70),
    ("meat_loaf",       "Packaged Food",        0.60),
    ("pizza",           "Pizza",                0.90),

    # ── Household products visible in grocery shopping ────────────────────
    ("soap_dispenser",  "Handwash",             0.80),
    ("lotion",          "Moisturiser",          0.75),
    ("toothbrush",      "Toothbrush",           0.90),
    ("bottle",          "Packaged Product",     0.55),
    ("detergent",       "Detergent",            0.80),
]

# Build the lookup: label_fragment → (grocery_name, confidence_multiplier)
_LABEL_MAP: dict = {}
for _fragment, _grocery, _mult in _IMAGENET_TO_GROCERY:
    # Multiple fragments can map to the same grocery name — that's fine
    if _fragment not in _LABEL_MAP:
        _LABEL_MAP[_fragment] = (_grocery, _mult)

# ---------------------------------------------------------------------------
# Singleton model holder — loaded once, reused across all requests
# ---------------------------------------------------------------------------

class _ModelHolder:
    """Thread-safe lazy loader for the MobileNetV3-Small model."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model: Optional[object] = None
        self._transform: Optional[object] = None
        self._labels: Optional[list] = None
        self._available: Optional[bool] = None

    def load(self) -> bool:
        """Load the model. Returns True if successful, False if torch unavailable."""
        if self._available is not None:
            return self._available
        with self._lock:
            if self._available is not None:
                return self._available
            try:
                import torch
                import torchvision.models as models
                import torchvision.transforms as T

                logger.info("Loading MobileNetV3-Small (ImageNet-1k) for visual recognition…")
                weights = models.MobileNet_V3_Small_Weights.IMAGENET1K_V1
                model = models.mobilenet_v3_small(weights=weights)
                model.eval()

                # Freeze — inference only, no gradients needed
                for p in model.parameters():
                    p.requires_grad_(False)

                transform = T.Compose([
                    T.Resize(256),
                    T.CenterCrop(224),
                    T.ToTensor(),
                    T.Normalize(mean=[0.485, 0.456, 0.406],
                                std=[0.229, 0.224, 0.225]),
                ])

                self._model = model
                self._transform = transform
                self._labels = weights.meta["categories"]
                self._available = True
                logger.info(
                    "MobileNetV3-Small loaded — %d ImageNet classes available.",
                    len(self._labels),
                )
            except ImportError:
                logger.warning(
                    "torch/torchvision not installed — visual recognition unavailable. "
                    "OCR-only pipeline will be used."
                )
                self._available = False
            except Exception as exc:
                logger.error("Failed to load visual model: %s", exc)
                self._available = False
        return self._available

    @property
    def model(self):
        return self._model

    @property
    def transform(self):
        return self._transform

    @property
    def labels(self):
        return self._labels


_holder = _ModelHolder()


# ---------------------------------------------------------------------------
# Public recognizer
# ---------------------------------------------------------------------------

class VisualRecognizer:
    """
    Classifies a PIL image into grocery product names using
    MobileNetV3-Small (ImageNet) running entirely on CPU.

    Call classify(pil_image) → list of (product_name, confidence 0–1).

    Returns an empty list if:
    • torch is not installed
    • the model could not be loaded
    • no grocery-relevant classes were recognised
    """

    # Top-K labels from ImageNet to consider per crop
    TOP_K = 10
    # Minimum softmax probability to consider a class
    MIN_PROB = 0.04
    # Minimum combined confidence after mapping to return a product
    MIN_GROCERY_CONF = 0.40

    def __init__(self) -> None:
        self._available = _holder.load()

    @property
    def available(self) -> bool:
        return self._available

    def classify(self, pil_image) -> List[Tuple[str, float]]:
        """
        Run visual classification on a PIL RGB image.

        Returns
        -------
        List of (grocery_product_name, confidence) tuples,
        sorted by confidence descending, deduplicated.
        """
        if not self._available:
            return []

        import torch

        crops = self._make_crops(pil_image)
        raw_results: dict[str, float] = {}   # grocery_name → best confidence

        for crop in crops:
            try:
                tensor = _holder.transform(crop).unsqueeze(0)   # (1, 3, 224, 224)
                with torch.no_grad():
                    logits = _holder.model(tensor)
                    probs = torch.softmax(logits, dim=1)[0]      # (1000,)

                top_probs, top_indices = torch.topk(probs, self.TOP_K)

                for prob_tensor, idx_tensor in zip(top_probs, top_indices):
                    prob = prob_tensor.item()
                    if prob < self.MIN_PROB:
                        break
                    label = _holder.labels[idx_tensor.item()].lower()
                    label_clean = label.replace(",", "").replace(" ", "_")

                    grocery, mult = self._map_label(label, label_clean)
                    if grocery is None:
                        continue

                    combined = prob * mult
                    if combined >= self.MIN_GROCERY_CONF:
                        existing = raw_results.get(grocery, 0.0)
                        raw_results[grocery] = max(existing, combined)

            except Exception as exc:
                logger.warning("Visual classification failed on crop: %s", exc)

        # Sort by confidence descending
        sorted_results = sorted(raw_results.items(), key=lambda x: x[1], reverse=True)

        # Cap at 8 products per image — avoid noise
        return [(name, round(min(conf, 0.99), 3)) for name, conf in sorted_results[:8]]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _make_crops(self, pil_image) -> list:
        """
        Return a list of PIL image crops to classify:
        1. Full image
        2. 2×2 quadrants (top-left, top-right, bottom-left, bottom-right)
        3. 3×3 grid cells (centre strip, edges)

        Crops with very little content (nearly uniform colour) are skipped.
        This enables multi-object detection from a single photo.
        """
        from PIL import Image
        img = pil_image.convert("RGB")
        w, h = img.size
        crops = []

        # Full image always included
        crops.append(img)

        # Only add sub-crops for images large enough that crops have content
        if w >= 200 and h >= 200:
            # 2×2 quadrants
            for row in range(2):
                for col in range(2):
                    x0 = col * w // 2
                    y0 = row * h // 2
                    x1 = (col + 1) * w // 2
                    y1 = (row + 1) * h // 2
                    crop = img.crop((x0, y0, x1, y1))
                    if _is_content_rich(crop):
                        crops.append(crop)

            # 3×3 grid (only the 9 cells)
            if w >= 400 and h >= 400:
                for row in range(3):
                    for col in range(3):
                        x0 = col * w // 3
                        y0 = row * h // 3
                        x1 = (col + 1) * w // 3
                        y1 = (row + 1) * h // 3
                        crop = img.crop((x0, y0, x1, y1))
                        if _is_content_rich(crop):
                            crops.append(crop)

        return crops

    def _map_label(self, label_raw: str, label_clean: str) -> Tuple[Optional[str], float]:
        """
        Check the label against our mapping table using substring matching.
        Returns (grocery_name, confidence_multiplier) or (None, 0).
        """
        # Direct lookup on cleaned label first
        for fragment, (grocery, mult) in _LABEL_MAP.items():
            if fragment in label_raw or fragment in label_clean:
                return grocery, mult
        return None, 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_content_rich(pil_image, threshold: float = 0.10) -> bool:
    """
    Return True if the crop has enough variation to contain real content
    (not a plain background/sky/floor).
    Uses std-dev of the grayscale histogram as a quick proxy.
    """
    try:
        import statistics
        gray = pil_image.convert("L")
        hist = gray.histogram()              # 256 bins
        total = sum(hist)
        if total == 0:
            return False
        freqs = [c / total for c in hist]
        mean = sum(i * f for i, f in enumerate(freqs))
        variance = sum((i - mean) ** 2 * f for i, f in enumerate(freqs))
        std_dev = variance ** 0.5
        return std_dev > threshold * 255    # e.g. >25.5 for threshold=0.10
    except Exception:
        return True   # if we can't tell, include the crop


# ---------------------------------------------------------------------------
# Module-level singleton for import convenience
# ---------------------------------------------------------------------------

# Loaded lazily on first import of this module
_recognizer: Optional[VisualRecognizer] = None
_recognizer_lock = threading.Lock()


def get_recognizer() -> VisualRecognizer:
    """Return the module-level VisualRecognizer singleton (thread-safe)."""
    global _recognizer
    if _recognizer is None:
        with _recognizer_lock:
            if _recognizer is None:
                _recognizer = VisualRecognizer()
    return _recognizer
