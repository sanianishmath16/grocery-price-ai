"""
vision_service.py — Hybrid grocery image recognition pipeline for GroceryAI.

PIPELINE (all free, no API credits required)
--------------------------------------------
1. Visual Recognition (MobileNetV3-Small, ImageNet-1k)
   • Runs on every image/crop without needing text
   • Detects fresh produce, fruits, packaged food shapes
   • Multi-region scanning: full image + 2×2 + 3×3 grid crops

2. OCR (Tesseract via pytesseract + Pillow)
   • Extracts text from packaged product labels
   • Fuzzy-matches against comprehensive grocery brand KB

3. Fusion
   • Results from both paths are merged and deduplicated
   • Visual detections get visual_confidence; OCR detections get ocr_confidence
   • Where both detect the same product, confidence is boosted
   • Minimum threshold filters noise

OPTIONAL UPGRADE
----------------
Set OPENAI_API_KEY to use GPT-4o Vision as the primary path.
All open/free paths remain as automatic fallbacks.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types (unchanged schema so main.py stays the same)
# ---------------------------------------------------------------------------

class VisionStatus(str, Enum):
    OK               = "ok"
    NO_PRODUCTS      = "no_products"
    LOW_CONFIDENCE   = "low_confidence"
    NOT_CONFIGURED   = "not_configured"
    QUOTA_EXHAUSTED  = "quota_exhausted"
    RATE_LIMITED     = "rate_limited"
    AUTH_ERROR       = "auth_error"
    ERROR            = "error"


@dataclass
class DetectedProduct:
    """A single grocery product identified from one image."""
    name: str
    confidence: float = 1.0
    from_image_index: int = 0
    source: str = "hybrid"      # "visual" | "ocr" | "hybrid" | "openai"


@dataclass
class VisionResult:
    """Full result for one image analysis call."""
    status: VisionStatus
    products: List[DetectedProduct] = field(default_factory=list)
    error_message: str = ""
    image_count_processed: int = 0


# ---------------------------------------------------------------------------
# Grocery OCR knowledge base — brand + product keyword index
# (unchanged from original — OCR still handles packaged products)
# ---------------------------------------------------------------------------
_GROCERY_KB: List[Tuple[List[str], str, str]] = [
    # ── Dairy ──────────────────────────────────────────────────────────────
    (["amul milk", "amul taaza", "amul gold"],     "Amul Milk 1L",              "dairy"),
    (["amul butter", "amul salted butter"],         "Amul Butter 500g",          "dairy"),
    (["amul paneer", "amul tofu"],                  "Amul Paneer 200g",          "dairy"),
    (["amul ghee", "amul pure ghee"],               "Amul Pure Ghee 500g",       "dairy"),
    (["amul curd", "amul dahi"],                    "Amul Dahi 400g",            "dairy"),
    (["amul cream", "amul fresh cream"],            "Amul Fresh Cream 200ml",    "dairy"),
    (["mother dairy milk", "mother dairy toned"],   "Mother Dairy Toned Milk 1L","dairy"),
    (["nandini milk", "nandini toned"],             "Nandini Toned Milk 1L",     "dairy"),
    (["heritage milk", "heritage toned"],           "Heritage Toned Milk 1L",    "dairy"),
    (["britannia cheese", "britannia processed"],   "Britannia Cheese Slice 200g","dairy"),
    # ── Noodles & instant food ─────────────────────────────────────────────
    (["maggi", "maggi noodles", "2 minute noodles", "2-minute"],
                                                    "Maggi 2-Minute Noodles 70g","snacks"),
    (["yippee noodles", "sunfeast yippee"],         "Sunfeast YiPPee Noodles 70g","snacks"),
    (["knorr soup", "knorr"],                       "Knorr Soup 44g",            "snacks"),
    (["patanjali noodles", "atta noodles"],         "Patanjali Atta Noodles 60g","snacks"),
    # ── Biscuits ───────────────────────────────────────────────────────────
    (["parle-g", "parle g biscuit", "parle g"],     "Parle-G Biscuits 100g",     "snacks"),
    (["britannia good day", "good day biscuit"],    "Britannia Good Day 100g",   "snacks"),
    (["britannia marie", "marie gold"],             "Britannia Marie Gold 200g", "snacks"),
    (["oreo", "cadbury oreo"],                      "Cadbury Oreo Biscuits 120g","snacks"),
    (["mcvities", "mc vities digestive"],           "McVities Digestive 250g",   "snacks"),
    (["hide & seek", "hide and seek"],              "Parle Hide & Seek 200g",    "snacks"),
    (["sunfeast dark fantasy", "dark fantasy"],     "Sunfeast Dark Fantasy 150g","snacks"),
    # ── Chips & snacks ─────────────────────────────────────────────────────
    (["lays", "lay's", "lays classic"],             "Lay's Chips 26g",           "snacks"),
    (["uncle chipps", "uncle chips"],               "Uncle Chipps 30g",          "snacks"),
    (["kurkure", "kurkure masala"],                 "Kurkure Masala Munch 90g",  "snacks"),
    (["bingo", "bingo chips", "bingo mad angles"],  "Bingo Mad Angles 70g",      "snacks"),
    (["doritos", "doritos nacho"],                  "Doritos Nacho Cheese 45g",  "snacks"),
    (["haldiram", "haldiram's"],                    "Haldiram's Bhujia 200g",    "snacks"),
    (["bikaji", "bikaji bhujia"],                   "Bikaji Bhujia 200g",        "snacks"),
    # ── Chocolate & candy ─────────────────────────────────────────────────
    (["dairy milk", "cadbury dairy milk", "cdm"],   "Cadbury Dairy Milk 36g",    "snacks"),
    (["kit kat", "kitkat", "nestle kitkat"],        "KitKat 36.5g",              "snacks"),
    (["munch", "nestle munch"],                     "Munch Chocolate 28g",       "snacks"),
    (["5 star", "cadbury 5 star"],                  "Cadbury 5 Star 42g",        "snacks"),
    (["snickers", "mars"],                          "Snickers 50g",              "snacks"),
    (["ferrero rocher", "ferrero"],                 "Ferrero Rocher T3 37.5g",   "snacks"),
    (["twix"],                                      "Twix 50g",                  "snacks"),
    # ── Beverages ─────────────────────────────────────────────────────────
    (["coca cola", "coke", "coca-cola"],            "Coca-Cola 500ml",           "beverages"),
    (["pepsi", "pepsi cola"],                       "Pepsi 500ml",               "beverages"),
    (["sprite", "sprite lemon"],                    "Sprite 500ml",              "beverages"),
    (["7up", "7 up"],                               "7Up 500ml",                 "beverages"),
    (["frooti", "parle agro frooti"],               "Frooti Mango Drink 200ml",  "beverages"),
    (["real juice", "dabur real"],                  "Dabur Real Juice 1L",       "beverages"),
    (["tropicana", "tropicana juice"],              "Tropicana Juice 1L",        "beverages"),
    (["bournvita", "cadbury bournvita"],            "Cadbury Bournvita 500g",    "beverages"),
    (["horlicks", "horlicks original"],             "Horlicks 500g",             "beverages"),
    (["complan", "complan nutrition"],              "Complan 200g",              "beverages"),
    (["nescafe", "nescafe classic", "nescafe coffee"], "Nescafé Classic 50g",    "beverages"),
    (["bru coffee", "bru instant"],                "Bru Instant Coffee 50g",    "beverages"),
    (["tata tea", "tata gold tea"],                "Tata Tea Gold 250g",        "beverages"),
    (["red label", "brooke bond red label"],        "Brooke Bond Red Label 250g","beverages"),
    (["lipton tea", "lipton green"],               "Lipton Green Tea 25 bags",  "beverages"),
    # ── Staples ────────────────────────────────────────────────────────────
    (["aashirvaad atta", "aashirvaad wheat"],       "Aashirvaad Atta 5kg",       "staples"),
    (["pillsbury atta", "pillsbury chakki"],        "Pillsbury Atta 5kg",        "staples"),
    (["fortune atta", "fortune chakki"],            "Fortune Chakki Atta 5kg",   "staples"),
    (["tata salt", "tata iodized salt"],            "Tata Salt 1kg",             "staples"),
    (["captain cook salt"],                         "Captain Cook Salt 1kg",     "staples"),
    (["india gate basmati", "india gate rice"],     "India Gate Basmati Rice 1kg","staples"),
    (["kohinoor basmati", "kohinoor rice"],         "Kohinoor Basmati Rice 1kg", "staples"),
    (["daawat basmati", "daawat rice"],             "Daawat Basmati Rice 1kg",   "staples"),
    (["fortune soya", "fortune soyabean oil"],      "Fortune Soyabean Oil 1L",   "staples"),
    (["saffola gold", "saffola oil"],               "Saffola Gold Oil 1L",       "staples"),
    (["dalda vanaspati", "dalda"],                  "Dalda Vanaspati 1kg",       "staples"),
    (["mdh masala", "mdh spices", "mdh"],           "MDH Masala 100g",           "staples"),
    (["everest masala", "everest spices"],          "Everest Masala 100g",       "staples"),
    (["catch masala", "catch spices"],              "Catch Masala 100g",         "staples"),
    (["tata sampann dal", "tata dal"],              "Tata Sampann Tur Dal 500g", "staples"),
    (["sugar", "tata sugar", "white sugar"],        "Sugar 1kg",                 "staples"),
    # ── Personal care ─────────────────────────────────────────────────────
    (["dettol soap", "dettol original"],            "Dettol Original Soap 75g",  "personal_care"),
    (["lifebuoy", "lifebuoy soap"],                "Lifebuoy Total Soap 125g",  "personal_care"),
    (["dove soap", "dove beauty"],                  "Dove Beauty Bar 75g",       "personal_care"),
    (["lux soap", "lux soft glow"],                "Lux Soft Glow Soap 80g",    "personal_care"),
    (["pears soap", "pears pure gentle"],           "Pears Soap 75g",            "personal_care"),
    (["colgate", "colgate strong teeth"],           "Colgate Strong Teeth 200g", "personal_care"),
    (["pepsodent", "pepsodent 2in1"],               "Pepsodent Germicheck 200g", "personal_care"),
    (["closeup", "close-up toothpaste"],            "Closeup Red Toothpaste 200g","personal_care"),
    (["oral-b", "oral b toothbrush"],               "Oral-B Toothbrush 1pc",     "personal_care"),
    (["head & shoulders", "head and shoulders"],    "Head & Shoulders Shampoo 340ml","personal_care"),
    (["dove shampoo", "dove damage therapy"],       "Dove Damage Therapy Shampoo 340ml","personal_care"),
    (["pantene", "pantene shampoo"],                "Pantene Shampoo 340ml",     "personal_care"),
    (["sunsilk", "sunsilk shampoo"],                "Sunsilk Shampoo 340ml",     "personal_care"),
    (["clinic plus", "clinic plus shampoo"],        "Clinic Plus Shampoo 175ml", "personal_care"),
    (["dettol handwash", "dettol liquid wash"],     "Dettol Liquid Handwash 200ml","personal_care"),
    (["lifebuoy handwash", "lifebuoy liquid"],      "Lifebuoy Handwash 200ml",   "personal_care"),
    (["savlon", "savlon antiseptic"],               "Savlon Antiseptic 200ml",   "personal_care"),
    (["nivea", "nivea cream"],                      "Nivea Soft Cream 200ml",    "personal_care"),
    (["vaseline", "vaseline petroleum jelly"],      "Vaseline Petroleum Jelly 100ml","personal_care"),
    (["himalaya face wash", "himalaya neem"],       "Himalaya Neem Face Wash 150ml","personal_care"),
    (["garnier face wash", "garnier men"],          "Garnier Men Face Wash 100ml","personal_care"),
    # ── Home care ─────────────────────────────────────────────────────────
    (["surf excel", "surf excel matic"],            "Surf Excel Matic 2kg",      "home_care"),
    (["ariel", "ariel matic"],                      "Ariel Matic 2kg",           "home_care"),
    (["tide", "tide detergent", "tide plus"],       "Tide Plus Detergent 1kg",   "home_care"),
    (["rin", "rin detergent"],                      "Rin Detergent 1kg",         "home_care"),
    (["nirma", "nirma washing powder"],             "Nirma Washing Powder 1kg",  "home_care"),
    (["vim", "vim dishwash"],                       "Vim Dishwash Bar 300g",     "home_care"),
    (["pril", "pril dishwash"],                     "Pril Dishwash Liquid 250ml","home_care"),
    (["harpic", "harpic toilet cleaner"],           "Harpic Toilet Cleaner 500ml","home_care"),
    (["lizol", "lizol floor cleaner"],              "Lizol Floor Cleaner 500ml", "home_care"),
    (["colin", "colin glass cleaner"],              "Colin Glass Cleaner 500ml", "home_care"),
    (["scotch-brite", "scotch brite"],              "Scotch-Brite Scrub Pad 2pcs","home_care"),
]

# Build flat index: lowercase_term → (canonical_name, category)
_TERM_INDEX: Dict[str, Tuple[str, str]] = {}
for _terms, _canonical, _cat in _GROCERY_KB:
    for _t in _terms:
        _TERM_INDEX[_t.lower()] = (_canonical, _cat)

_BRAND_NAMES = [
    "amul", "nestle", "britannia", "parle", "haldiram", "maggi", "lays",
    "kurkure", "bingo", "cadbury", "dairy milk", "kitkat", "kit kat", "5 star",
    "aashirvaad", "fortune", "saffola", "dabur", "patanjali", "himalaya",
    "dettol", "lifebuoy", "dove", "head shoulders", "colgate", "pepsodent",
    "closeup", "surf excel", "ariel", "tide", "rin", "nirma", "vim", "harpic",
    "tata", "mdh", "everest", "india gate", "kohinoor", "daawat", "frooti",
    "tropicana", "bournvita", "horlicks", "nescafe", "bru", "lipton",
    "yippee", "sunfeast", "oreo", "mcvities", "doritos", "bikaji", "ferrero",
    "coca cola", "coke", "pepsi", "sprite", "7up", "nivea", "vaseline",
    "garnier", "pantene", "sunsilk", "clinic plus", "savlon", "pril",
    "lizol", "colin", "scotch brite",
]
_BRAND_NAMES.sort(key=len, reverse=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def identify_products(images_b64: List[str]) -> VisionResult:
    """
    Identify grocery products from base64-encoded images.

    Priority order:
    1. OpenAI GPT-4o Vision (if OPENAI_API_KEY is set and credits available)
    2. Free hybrid pipeline: visual recognition + OCR (always available)
    """
    if not images_b64:
        return VisionResult(status=VisionStatus.NO_PRODUCTS,
                            error_message="No images provided.")

    # Try OpenAI first only if key is set
    if os.getenv("OPENAI_API_KEY", ""):
        result = await _identify_via_openai(images_b64)
        if result.status == VisionStatus.OK:
            return result
        if result.status in (VisionStatus.QUOTA_EXHAUSTED,
                              VisionStatus.AUTH_ERROR,
                              VisionStatus.RATE_LIMITED):
            logger.info(
                "OpenAI unavailable (%s) — falling back to free hybrid pipeline.",
                result.status,
            )

    # Free hybrid pipeline (visual + OCR)
    return await _identify_via_hybrid(images_b64)


# ---------------------------------------------------------------------------
# Noop recognizer — used when visual_recognizer fails to import
# ---------------------------------------------------------------------------

class _NoopRecognizer:
    """Stub recognizer that always returns empty results (OCR-only mode)."""
    available = False

    def classify(self, _pil_image):
        return []


# ---------------------------------------------------------------------------
# Free hybrid pipeline
# ---------------------------------------------------------------------------

async def _identify_via_hybrid(images_b64: List[str]) -> VisionResult:
    """Run the visual+OCR hybrid pipeline in a thread executor."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_hybrid_pipeline, images_b64)


def _resize_image_bytes(image_bytes: bytes, max_px: int = 800) -> bytes:
    """
    Resize image so its longest edge is at most max_px, preserving aspect ratio.
    Returns original bytes if resize is not needed or fails.
    This prevents processing huge phone photos and reduces memory usage.
    """
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        if max(w, h) <= max_px:
            return image_bytes   # already small enough
        scale = max_px / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        resized = buf.getvalue()
        logger.debug(
            "Resized image from %dx%d to %dx%d (%.1f KB → %.1f KB)",
            w, h, new_w, new_h,
            len(image_bytes) / 1024,
            len(resized) / 1024,
        )
        return resized
    except Exception as exc:
        logger.warning("Image resize failed, using original: %s", exc)
        return image_bytes


def _sync_hybrid_pipeline(images_b64: List[str]) -> VisionResult:
    """
    Synchronous hybrid pipeline.
    For each image:
      1. Resize to max 800px (prevents OOM on large phone photos)
      2. Run visual recognizer (colour-based, multi-crop)
      3. Run OCR matcher (Tesseract + keyword KB)
      4. Fuse results: prefer visual for fresh produce, OCR for branded items
      5. Deduplicate across images
    """
    try:
        from ai.visual_recognizer import get_recognizer
        recognizer = get_recognizer()
    except Exception as exc:
        logger.error("Failed to initialise visual recognizer: %s", exc)
        # Still continue — OCR-only pipeline will handle packaged products
        recognizer = _NoopRecognizer()

    all_products: List[DetectedProduct] = []
    seen_names: set = set()

    for img_idx, b64 in enumerate(images_b64):
        try:
            raw = base64.b64decode(b64)
            raw = _resize_image_bytes(raw, max_px=800)
            products = _process_single_image_hybrid(raw, img_idx, recognizer)
            for p in products:
                key = p.name.lower()
                if key not in seen_names:
                    seen_names.add(key)
                    all_products.append(p)
        except Exception as exc:
            logger.warning("Hybrid pipeline failed for image %d: %s", img_idx, exc)

    if not all_products:
        return VisionResult(
            status=VisionStatus.NO_PRODUCTS,
            image_count_processed=len(images_b64),
            error_message=(
                "We couldn't identify any grocery products in the uploaded images. "
                "Try a clearer, well-lit photo — or type the product name directly "
                "using Text Search."
            ),
        )

    logger.info(
        "Hybrid pipeline identified %d products from %d image(s): %s",
        len(all_products),
        len(images_b64),
        [p.name for p in all_products[:8]],
    )
    return VisionResult(
        status=VisionStatus.OK,
        products=all_products,
        image_count_processed=len(images_b64),
    )


def _image_likely_has_text(pil_img) -> bool:
    """
    Fast heuristic: returns True if the image likely contains printed text
    (e.g. a product label), False if it is likely raw produce with no text.

    Method: compute the Laplacian variance of the grayscale image.
    Printed text creates sharp high-contrast edges that yield a high Laplacian
    variance.  A bowl of tomatoes has soft colour gradients → low variance.

    Threshold is tuned conservatively so that product labels always pass and
    pure-vegetable photos usually skip (saving 1–2 Tesseract passes each).
    """
    try:
        import numpy as np
        gray = pil_img.convert("L").resize((256, 256))
        arr = np.array(gray, dtype=np.float32)
        # Laplacian approximation: difference of each pixel and its 4 neighbours
        lap = (
            np.roll(arr, 1, axis=0) + np.roll(arr, -1, axis=0)
            + np.roll(arr, 1, axis=1) + np.roll(arr, -1, axis=1)
            - 4 * arr
        )
        variance = float(np.var(lap))
        # Empirically: text-heavy labels → variance ≥ 400; plain produce → < 200
        result = variance >= 250
        logger.debug("Image text-likelihood: Laplacian variance=%.1f → %s", variance, result)
        return result
    except Exception:
        return True   # if check fails, run OCR anyway (safe default)


def _process_single_image_hybrid(
    image_bytes: bytes,
    img_idx: int,
    recognizer,
) -> List[DetectedProduct]:
    """
    Run both visual recognition and OCR on one image, then fuse results.
    """
    from PIL import Image, ImageEnhance, ImageFilter

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    # Image is already resized to ≤800px by _resize_image_bytes before this call.

    # ── STEP 1: Visual recognition (no text needed) ───────────────────────
    visual_hits: Dict[str, float] = {}
    if recognizer.available:
        vis_results = recognizer.classify(img)
        for name, conf in vis_results:
            existing = visual_hits.get(name, 0.0)
            visual_hits[name] = max(existing, conf)
        if visual_hits:
            logger.debug(
                "Image %d visual detections: %s",
                img_idx,
                [(n, round(c, 2)) for n, c in list(visual_hits.items())[:5]],
            )

    # ── STEP 2: OCR extraction (skip if image has no text-like regions) ───
    # Heuristic: check whether the image has high-contrast, sharp horizontal
    # or vertical edges typical of printed text.  This avoids running 3 full
    # Tesseract passes on raw vegetable photos (which contain no useful text).
    ocr_hits: Dict[str, float] = {}
    if _image_likely_has_text(img):
        img_gray = img.convert("L")
        img_gray = ImageEnhance.Contrast(img_gray).enhance(2.2)
        img_gray = ImageEnhance.Sharpness(img_gray).enhance(2.0)
        img_gray = img_gray.filter(ImageFilter.SHARPEN)

        extracted_text = ""
        try:
            import pytesseract
            # Single PSM pass: PSM 3 (auto) — sufficient for product labels.
            # Only fall through to PSM 6 if the first pass returns nothing useful.
            for psm in (3, 6):
                text = pytesseract.image_to_string(
                    img_gray, config=f"--psm {psm} --oem 3 -l eng"
                )
                if len(text.strip()) > 8:
                    extracted_text = text
                    break
            logger.debug("Image %d OCR text (first 200): %s", img_idx, extracted_text[:200])
        except ImportError:
            logger.warning("pytesseract not installed — OCR unavailable for image %d", img_idx)
        except Exception as exc:
            logger.warning("OCR error on image %d: %s", img_idx, exc)

        if extracted_text.strip():
            ocr_results = _match_text_to_products(extracted_text, img_idx)
            for p in ocr_results:
                existing = ocr_hits.get(p.name, 0.0)
                ocr_hits[p.name] = max(existing, p.confidence)
    else:
        logger.debug("Image %d: no text regions detected — skipping OCR", img_idx)

    # ── STEP 3: Fusion ────────────────────────────────────────────────────
    return _fuse_results(visual_hits, ocr_hits, img_idx)


# Maximum products returned per single image — a real basket photo rarely
# has more than this many DISTINCT visually dominant objects.
_MAX_PRODUCTS_PER_IMAGE = 8


def _fuse_results(
    visual_hits: Dict[str, float],
    ocr_hits: Dict[str, float],
    img_idx: int,
) -> List[DetectedProduct]:
    """
    Merge visual and OCR detections into a single ranked list.

    Strict anti-hallucination fusion rules:
    - Both visual AND OCR agree  → strongest evidence; confidence boost (+10%)
    - OCR only (packaged labels) → direct text match; use OCR confidence (≥0.65)
    - Visual only (fresh produce)→ colour-based; use visual confidence (≥0.60)

    Thresholds are intentionally strict:
    - Visual-only minimum raised to 0.60 (was 0.40) to cut colour noise.
    - OCR-only minimum raised to 0.65 (was 0.50) — short brand matches are
      common OCR false positives (e.g. "MAG" → Maggi).
    - Per-image cap of _MAX_PRODUCTS_PER_IMAGE prevents accumulated noise
      from producing unbounded result lists.
    """
    combined: Dict[str, Tuple[float, str]] = {}   # name → (conf, source)

    # Products confirmed by both visual colour AND OCR text
    for name, v_conf in visual_hits.items():
        if name in ocr_hits:
            boosted = min(0.97, max(v_conf, ocr_hits[name]) + 0.10)
            combined[name] = (boosted, "hybrid")

    # Products detected only by visual colour (fresh produce, no label)
    for name, v_conf in visual_hits.items():
        if name not in combined and v_conf >= 0.60:
            combined[name] = (v_conf, "visual")

    # Products detected only by OCR (packaged products with clear text)
    for name, o_conf in ocr_hits.items():
        if name not in combined and o_conf >= 0.65:
            combined[name] = (o_conf, "ocr")

    products = [
        DetectedProduct(
            name=name,
            confidence=round(conf, 3),
            from_image_index=img_idx,
            source=source,
        )
        for name, (conf, source) in combined.items()
    ]
    products.sort(key=lambda p: p.confidence, reverse=True)
    return products[:_MAX_PRODUCTS_PER_IMAGE]


# ---------------------------------------------------------------------------
# OCR matching helpers (unchanged logic, same as original)
# ---------------------------------------------------------------------------

def _normalise_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.lower()
    text = re.sub(r"[-_]", " ", text)
    text = re.sub(r"[^a-z0-9 &.']", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _match_text_to_products(raw_text: str, img_idx: int) -> List[DetectedProduct]:
    """Match OCR text against the grocery KB. Returns up to 5 matches."""
    norm_text = _normalise_text(raw_text)
    if not norm_text:
        return []

    found: Dict[str, float] = {}

    # Pass 1: full term match
    for term, (canonical, _) in _TERM_INDEX.items():
        if term in norm_text:
            found[canonical] = max(found.get(canonical, 0.0), 0.90)

    # Pass 2: brand-only match
    if not found:
        for brand in _BRAND_NAMES:
            if brand in norm_text:
                canonical = _brand_to_canonical(brand, norm_text)
                if canonical:
                    found[canonical] = max(found.get(canonical, 0.0), 0.65)

    # Pass 3: token overlap
    if not found:
        text_tokens = set(norm_text.split())
        for term, (canonical, _) in _TERM_INDEX.items():
            term_tokens = set(term.split())
            if not term_tokens:
                continue
            overlap = len(term_tokens & text_tokens) / len(term_tokens)
            if overlap >= 0.6:
                score = 0.55 * overlap
                found[canonical] = max(found.get(canonical, 0.0), score)

    products = [
        DetectedProduct(name=name, confidence=round(conf, 2),
                        from_image_index=img_idx, source="ocr")
        for name, conf in found.items()
        if conf >= 0.50
    ]
    products.sort(key=lambda p: p.confidence, reverse=True)
    return products[:5]


def _brand_to_canonical(brand: str, text: str) -> Optional[str]:
    candidates = [
        (canonical, terms)
        for terms, canonical, _ in _GROCERY_KB
        if any(brand in t for t in terms)
    ]
    if not candidates:
        return None
    text_tokens = set(text.split())
    best_name, best_score = None, 0.0
    for canonical, terms in candidates:
        for t in terms:
            t_tokens = set(t.split())
            overlap = len(t_tokens & text_tokens) / max(len(t_tokens), 1)
            if overlap > best_score:
                best_score = overlap
                best_name = canonical
    return best_name


# ---------------------------------------------------------------------------
# OpenAI GPT-4o Vision (optional upgrade — requires credits)
# ---------------------------------------------------------------------------

async def _identify_via_openai(images_b64: List[str]) -> VisionResult:
    """Send images to OpenAI GPT-4o; requires OPENAI_API_KEY + credits."""
    try:
        import openai
        import json

        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

        content = [
            {
                "type": "text",
                "text": (
                    "You are a grocery product identification assistant. "
                    "Look at the provided image(s) and list every distinct grocery "
                    "product you can see — including fresh vegetables, fruits, and "
                    "packaged products. "
                    "For packaged products include brand names and sizes where visible. "
                    "For fresh produce use common names (e.g. 'Tomato', 'Onion', 'Potato'). "
                    "Return ONLY a JSON array of strings. "
                    'Example: ["Tomato", "Onion", "Amul Milk 1L", "Maggi 2-Minute Noodles 70g"]'
                ),
            }
        ]
        for b64 in images_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"},
            })

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            max_tokens=512,
            temperature=0.2,
        )

        raw_text = response.choices[0].message.content.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

        products_raw: List[str] = json.loads(raw_text)
        if not products_raw:
            return VisionResult(
                status=VisionStatus.NO_PRODUCTS,
                image_count_processed=len(images_b64),
                error_message="No grocery products could be identified.",
            )

        products = [
            DetectedProduct(
                name=p.strip(), confidence=0.92,
                from_image_index=0, source="openai",
            )
            for p in products_raw if p.strip()
        ]
        logger.info(
            "OpenAI identified %d products from %d images.",
            len(products), len(images_b64),
        )
        return VisionResult(
            status=VisionStatus.OK,
            products=products,
            image_count_processed=len(images_b64),
        )

    except ImportError:
        return VisionResult(
            status=VisionStatus.NOT_CONFIGURED,
            error_message="OpenAI package not installed.",
            image_count_processed=len(images_b64),
        )
    except Exception as exc:
        status, user_msg = _classify_openai_exception(exc)
        logger.error("OpenAI vision call failed [%s]: %s", status, exc)
        return VisionResult(
            status=status, error_message=user_msg,
            image_count_processed=len(images_b64),
        )


def _classify_openai_exception(exc: Exception):
    try:
        import openai
        if isinstance(exc, openai.RateLimitError):
            body = getattr(exc, "body", None) or {}
            if not isinstance(body, dict):
                body = {}
            error_obj = body.get("error") or body
            code = error_obj.get("code", "") or ""
            err_type = error_obj.get("type", "") or ""
            if code in ("credit_balance_exhausted", "insufficient_quota") \
                    or err_type == "insufficient_quota":
                return (
                    VisionStatus.QUOTA_EXHAUSTED,
                    "OpenAI quota exhausted — using free local recognition.",
                )
            return (
                VisionStatus.RATE_LIMITED,
                "OpenAI rate limited — using free local recognition.",
            )
        if isinstance(exc, openai.AuthenticationError):
            return (
                VisionStatus.AUTH_ERROR,
                "OpenAI auth error — using free local recognition.",
            )
    except ImportError:
        pass
    return (VisionStatus.ERROR, "OpenAI error — using free local recognition.")
