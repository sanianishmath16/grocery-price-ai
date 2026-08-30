"""
vision_service.py — Free image-based grocery product identification.

HOW IT WORKS (completely free, no API credits needed)
------------------------------------------------------
1. Pillow + pytesseract OCR extracts text from food packaging labels.
2. A comprehensive grocery keyword index matches extracted text to known
   brands/products (Amul, Maggi, Tata, Britannia, etc.).
3. Results are ranked by confidence and deduplicated.

This runs entirely locally inside the container — no external API calls,
no credits, no rate limits.

QUALITY
-------
• Works well on: clear product packaging, grocery labels, receipts, shelf photos.
• May struggle with: blurry photos, very small text, artistic packaging.
• When text is ambiguous, returns the best guess rather than nothing.

OPTIONAL UPGRADE
----------------
If you later add OpenAI credits, set OPENAI_API_KEY and the service
automatically upgrades to GPT-4o Vision for much higher accuracy.
The free local path remains as fallback.
"""

import base64
import io
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

class VisionStatus(str, Enum):
    OK               = "ok"                # Products detected successfully
    NO_PRODUCTS      = "no_products"       # Image processed but nothing identified
    LOW_CONFIDENCE   = "low_confidence"    # Detected but confidence too low
    NOT_CONFIGURED   = "not_configured"    # Vision API key/service not set up
    QUOTA_EXHAUSTED  = "quota_exhausted"   # OpenAI credits exhausted
    RATE_LIMITED     = "rate_limited"      # OpenAI temporary rate limit
    AUTH_ERROR       = "auth_error"        # Invalid/revoked API key
    ERROR            = "error"             # Unexpected error during analysis


@dataclass
class DetectedProduct:
    """A single grocery product identified from one image."""
    name: str                        # e.g. "Amul Milk 1L"
    confidence: float = 1.0          # 0.0 – 1.0
    from_image_index: int = 0


@dataclass
class VisionResult:
    """Full result for one image analysis call."""
    status: VisionStatus
    products: List[DetectedProduct] = field(default_factory=list)
    error_message: str = ""
    image_count_processed: int = 0


# ---------------------------------------------------------------------------
# Grocery knowledge base — brand + product keyword index
# ---------------------------------------------------------------------------
# Each entry: (search_terms_list, canonical_product_name, category)
# search_terms are lowercase; any match triggers the canonical name.

_GROCERY_KB: List[Tuple[List[str], str, str]] = [
    # ── Dairy ──────────────────────────────────────────────────────────────
    (["amul milk", "amul taaza", "amul gold"], "Amul Milk 1L", "dairy"),
    (["amul butter", "amul salted butter"], "Amul Butter 500g", "dairy"),
    (["amul paneer", "amul tofu"], "Amul Paneer 200g", "dairy"),
    (["amul ghee", "amul pure ghee"], "Amul Pure Ghee 500g", "dairy"),
    (["amul curd", "amul dahi"], "Amul Dahi 400g", "dairy"),
    (["mother dairy milk", "mother dairy toned"], "Mother Dairy Toned Milk 1L", "dairy"),
    (["nandini milk", "nandini toned"], "Nandini Toned Milk 1L", "dairy"),
    (["heritage milk", "heritage toned"], "Heritage Toned Milk 1L", "dairy"),
    (["britannia cheese", "britannia processed cheese"], "Britannia Cheese Slice 200g", "dairy"),
    # ── Noodles & instant food ─────────────────────────────────────────────
    (["maggi", "maggi noodles", "maggi 2-minute", "2 minute noodles"], "Maggi 2-Minute Noodles 70g", "snacks"),
    (["yippee noodles", "sunfeast yippee"], "Sunfeast YiPPee Noodles 70g", "snacks"),
    (["knorr soup", "knorr"], "Knorr Soup 44g", "snacks"),
    (["patanjali noodles", "atta noodles"], "Patanjali Atta Noodles 60g", "snacks"),
    # ── Biscuits ───────────────────────────────────────────────────────────
    (["parle-g", "parle g biscuit", "parle g"], "Parle-G Biscuits 100g", "snacks"),
    (["britannia good day", "good day biscuit"], "Britannia Good Day Biscuits 100g", "snacks"),
    (["britannia marie", "marie gold", "marie biscuit"], "Britannia Marie Gold 200g", "snacks"),
    (["oreo", "oreo biscuit", "cadbury oreo"], "Cadbury Oreo Biscuits 120g", "snacks"),
    (["mcvities", "mc vities digestive"], "McVities Digestive Biscuits 250g", "snacks"),
    (["hide & seek", "hide and seek"], "Parle Hide & Seek 200g", "snacks"),
    (["sunfeast dark fantasy", "dark fantasy"], "Sunfeast Dark Fantasy 150g", "snacks"),
    # ── Chips & snacks ─────────────────────────────────────────────────────
    (["lay's", "lays chips", "lays classic", "lays"], "Lay's Chips 26g", "snacks"),
    (["uncle chipps", "uncle chips"], "Uncle Chipps 30g", "snacks"),
    (["kurkure", "kurkure masala"], "Kurkure Masala Munch 90g", "snacks"),
    (["bingo", "bingo chips", "bingo mad angles"], "Bingo Mad Angles 70g", "snacks"),
    (["doritos", "doritos nacho"], "Doritos Nacho Cheese 45g", "snacks"),
    (["haldiram", "haldiram's", "haldirams bhujiaa"], "Haldiram's Bhujia 200g", "snacks"),
    (["bikaji", "bikaji bhujia"], "Bikaji Bhujia 200g", "snacks"),
    # ── Chocolate & candy ─────────────────────────────────────────────────
    (["dairy milk", "cadbury dairy milk", "cdm"], "Cadbury Dairy Milk 36g", "snacks"),
    (["kit kat", "kitkat", "nestle kitkat"], "KitKat 36.5g", "snacks"),
    (["munch", "nestle munch"], "Munch Chocolate 28g", "snacks"),
    (["5 star", "cadbury 5 star"], "Cadbury 5 Star 42g", "snacks"),
    (["twix", "mars", "snickers"], "Snickers 50g", "snacks"),
    (["ferrero rocher", "ferrero"], "Ferrero Rocher T3 37.5g", "snacks"),
    # ── Beverages ─────────────────────────────────────────────────────────
    (["coca cola", "coke", "coca-cola"], "Coca-Cola 500ml", "beverages"),
    (["pepsi", "pepsi cola"], "Pepsi 500ml", "beverages"),
    (["sprite", "sprite lemon"], "Sprite 500ml", "beverages"),
    (["7up", "7 up"], "7Up 500ml", "beverages"),
    (["frooti", "parle agro frooti"], "Frooti Mango Drink 200ml", "beverages"),
    (["real juice", "dabur real"], "Dabur Real Juice 1L", "beverages"),
    (["tropicana", "tropicana juice"], "Tropicana Juice 1L", "beverages"),
    (["bournvita", "cadbury bournvita"], "Cadbury Bournvita 500g", "beverages"),
    (["horlicks", "horlicks original"], "Horlicks 500g", "beverages"),
    (["complan", "complan nutrition"], "Complan 200g", "beverages"),
    (["nescafe", "nescafe classic", "nescafe coffee"], "Nescafé Classic 50g", "beverages"),
    (["bru coffee", "bru instant coffee"], "Bru Instant Coffee 50g", "beverages"),
    (["tata tea", "tata gold tea"], "Tata Tea Gold 250g", "beverages"),
    (["red label", "brooke bond red label"], "Brooke Bond Red Label 250g", "beverages"),
    (["lipton tea", "lipton green"], "Lipton Green Tea 25 bags", "beverages"),
    # ── Staples ────────────────────────────────────────────────────────────
    (["aashirvaad atta", "aashirvaad wheat", "aashirvaad flour"], "Aashirvaad Atta 5kg", "staples"),
    (["pillsbury atta", "pillsbury chakki fresh"], "Pillsbury Atta 5kg", "staples"),
    (["fortune atta", "fortune chakki", "fortune wheat"], "Fortune Chakki Atta 5kg", "staples"),
    (["tata salt", "tata iodized salt"], "Tata Salt 1kg", "staples"),
    (["aashirvaad salt", "captain cook salt"], "Captain Cook Salt 1kg", "staples"),
    (["india gate basmati", "india gate rice"], "India Gate Basmati Rice 1kg", "staples"),
    (["kohinoor basmati", "kohinoor rice"], "Kohinoor Basmati Rice 1kg", "staples"),
    (["daawat basmati", "daawat rice"], "Daawat Basmati Rice 1kg", "staples"),
    (["fortune soya", "fortune soyabean oil"], "Fortune Soyabean Oil 1L", "staples"),
    (["saffola gold", "saffola oil"], "Saffola Gold Oil 1L", "staples"),
    (["dalda vanaspati", "dalda"], "Dalda Vanaspati 1kg", "staples"),
    (["mdh masala", "mdh spices", "mdh"], "MDH Masala 100g", "staples"),
    (["everest masala", "everest spices", "everest"], "Everest Masala 100g", "staples"),
    (["catch masala", "catch spices"], "Catch Masala 100g", "staples"),
    (["tata sampann dal", "tata dal"], "Tata Sampann Tur Dal 500g", "staples"),
    (["sugar", "tata sugar", "white sugar"], "Sugar 1kg", "staples"),
    # ── Personal care ─────────────────────────────────────────────────────
    (["dettol soap", "dettol original"], "Dettol Original Soap 75g", "personal_care"),
    (["lifebuoy", "lifebuoy soap", "lifebuoy total"], "Lifebuoy Total Soap 125g", "personal_care"),
    (["dove soap", "dove beauty"], "Dove Beauty Bar 75g", "personal_care"),
    (["lux soap", "lux soft glow"], "Lux Soft Glow Soap 80g", "personal_care"),
    (["pears soap", "pears pure gentle"], "Pears Soap 75g", "personal_care"),
    (["colgate", "colgate strong teeth", "colgate toothpaste"], "Colgate Strong Teeth 200g", "personal_care"),
    (["pepsodent", "pepsodent 2in1"], "Pepsodent Germicheck 200g", "personal_care"),
    (["closeup", "close-up toothpaste"], "Closeup Red Toothpaste 200g", "personal_care"),
    (["oral-b", "oral b toothbrush"], "Oral-B Toothbrush 1pc", "personal_care"),
    (["head & shoulders", "head and shoulders"], "Head & Shoulders Anti-Dandruff Shampoo 340ml", "personal_care"),
    (["dove shampoo", "dove damage therapy"], "Dove Damage Therapy Shampoo 340ml", "personal_care"),
    (["pantene", "pantene shampoo"], "Pantene Shampoo 340ml", "personal_care"),
    (["sunsilk", "sunsilk shampoo"], "Sunsilk Shampoo 340ml", "personal_care"),
    (["clinic plus", "clinic plus shampoo"], "Clinic Plus Shampoo 175ml", "personal_care"),
    (["dettol handwash", "dettol liquid wash"], "Dettol Liquid Handwash 200ml", "personal_care"),
    (["lifebuoy handwash", "lifebuoy liquid"], "Lifebuoy Handwash 200ml", "personal_care"),
    (["savlon", "savlon antiseptic"], "Savlon Antiseptic 200ml", "personal_care"),
    (["nivea", "nivea cream", "nivea moisturiser"], "Nivea Soft Cream 200ml", "personal_care"),
    (["vaseline", "vaseline petroleum jelly"], "Vaseline Petroleum Jelly 100ml", "personal_care"),
    (["himalaya face wash", "himalaya neem"], "Himalaya Neem Face Wash 150ml", "personal_care"),
    (["garnier face wash", "garnier men"], "Garnier Men Face Wash 100ml", "personal_care"),
    # ── Home care ─────────────────────────────────────────────────────────
    (["surf excel", "surf excel matic"], "Surf Excel Matic 2kg", "home_care"),
    (["ariel", "ariel matic", "ariel detergent"], "Ariel Matic 2kg", "home_care"),
    (["tide", "tide detergent", "tide plus"], "Tide Plus Detergent 1kg", "home_care"),
    (["rin", "rin detergent", "rin advanced"], "Rin Detergent 1kg", "home_care"),
    (["nirma", "nirma washing powder"], "Nirma Washing Powder 1kg", "home_care"),
    (["vim", "vim dishwash", "vim dish bar"], "Vim Dishwash Bar 300g", "home_care"),
    (["pril", "pril dishwash", "pril liquid"], "Pril Dishwash Liquid 250ml", "home_care"),
    (["harpic", "harpic toilet cleaner"], "Harpic Toilet Cleaner 500ml", "home_care"),
    (["lizol", "lizol floor cleaner"], "Lizol Floor Cleaner 500ml", "home_care"),
    (["colin", "colin glass cleaner"], "Colin Glass Cleaner 500ml", "home_care"),
    (["scotch-brite", "scotch brite scrub"], "Scotch-Brite Scrub Pad 2pcs", "home_care"),
]

# Build a flattened index: lowercase_term → canonical_name
_TERM_INDEX: dict = {}
for terms, canonical, cat in _GROCERY_KB:
    for t in terms:
        _TERM_INDEX[t.lower()] = (canonical, cat)

# Brand-only terms for partial matching
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
    2. Free local OCR-based recognition (pytesseract + Pillow) — always available
    """
    if not images_b64:
        return VisionResult(status=VisionStatus.NO_PRODUCTS, error_message="No images provided.")

    # Try OpenAI first only if key is set
    if os.getenv("OPENAI_API_KEY", ""):
        result = await _identify_via_openai(images_b64)
        if result.status == VisionStatus.OK:
            return result
        if result.status in (VisionStatus.QUOTA_EXHAUSTED, VisionStatus.AUTH_ERROR):
            # Credits exhausted or bad key — fall through to free OCR
            logger.info(
                "OpenAI unavailable (%s) — falling back to free local OCR.", result.status
            )
        elif result.status == VisionStatus.RATE_LIMITED:
            logger.info("OpenAI rate limited — falling back to free local OCR.")
        # For all non-OK OpenAI results, fall through to free OCR

    # Free local OCR-based recognition
    return await _identify_via_local_ocr(images_b64)


# ---------------------------------------------------------------------------
# Free local OCR implementation (Pillow + pytesseract)
# ---------------------------------------------------------------------------

async def _identify_via_local_ocr(images_b64: List[str]) -> VisionResult:
    """
    Extract text from images using OCR, then match against the grocery KB.

    This is fully free — no API calls, no credits needed.
    Runs synchronously in an executor to avoid blocking the event loop.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_ocr_pipeline, images_b64)


def _sync_ocr_pipeline(images_b64: List[str]) -> VisionResult:
    """
    Synchronous OCR + keyword matching pipeline.
    Processes all images and merges results.
    """
    all_products: List[DetectedProduct] = []
    seen_names: set = set()

    for img_idx, b64 in enumerate(images_b64):
        try:
            raw = base64.b64decode(b64)
            products = _process_single_image(raw, img_idx)
            for p in products:
                if p.name not in seen_names:
                    seen_names.add(p.name)
                    all_products.append(p)
        except Exception as exc:
            logger.warning("OCR failed for image %d: %s", img_idx, exc)

    if not all_products:
        return VisionResult(
            status=VisionStatus.NO_PRODUCTS,
            image_count_processed=len(images_b64),
            error_message=(
                "No grocery products could be identified in the uploaded images. "
                "Try a clearer, well-lit photo of the product label or packaging, "
                "or enter the product name manually using text search."
            ),
        )

    logger.info(
        "Local OCR identified %d products from %d images: %s",
        len(all_products), len(images_b64),
        [p.name for p in all_products[:5]],
    )
    return VisionResult(
        status=VisionStatus.OK,
        products=all_products,
        image_count_processed=len(images_b64),
    )


def _process_single_image(image_bytes: bytes, img_idx: int) -> List[DetectedProduct]:
    """
    Run OCR on one image and return matched DetectedProduct list.
    Falls back gracefully if pytesseract is not installed.
    """
    from PIL import Image, ImageEnhance, ImageFilter

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # ── Preprocessing ────────────────────────────────────────────────────────
    # 1. Upscale if image is small — OCR needs text to be at least ~20px tall
    w, h = img.size
    if max(w, h) < 800:
        scale = 800 / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # 2. Convert to grayscale, boost contrast and sharpness
    img = img.convert("L")
    img = ImageEnhance.Contrast(img).enhance(2.2)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    img = img.filter(ImageFilter.SHARPEN)

    # ── OCR ──────────────────────────────────────────────────────────────────
    extracted_text = ""
    try:
        import pytesseract
        # Try multiple page segmentation modes; use the first that yields text.
        # psm 3  = automatic page segmentation (good for full product labels)
        # psm 11 = sparse text, no OSD (good for packaging with scattered text)
        # psm 6  = uniform block (good for single-block labels)
        for psm in (3, 11, 6):
            text = pytesseract.image_to_string(
                img,
                config=f"--psm {psm} --oem 3 -l eng",
            )
            if len(text.strip()) > 8:
                extracted_text = text
                break
        logger.debug("OCR raw text (first 300 chars): %s", extracted_text[:300])
    except ImportError:
        logger.warning("pytesseract not installed — keyword matching only")
    except Exception as exc:
        logger.warning("pytesseract OCR error: %s", exc)

    return _match_text_to_products(extracted_text, img_idx)


def _normalise_text(text: str) -> str:
    """Normalise unicode, lowercase, remove non-alphanumeric chars.
    Hyphens/underscores → spaces so "2-minute" matches "2 minute" in the KB.
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.lower()
    text = re.sub(r"[-_]", " ", text)           # "2-minute" → "2 minute"
    text = re.sub(r"[^a-z0-9 &.']", " ", text)  # strip other special chars
    return re.sub(r"\s+", " ", text).strip()


def _match_text_to_products(raw_text: str, img_idx: int) -> List[DetectedProduct]:
    """
    Match extracted OCR text against the grocery knowledge base.

    Scoring:
    - Full term match → confidence 0.90
    - Brand-only match → confidence 0.65
    - Partial term match (60%+ of words) → confidence 0.55
    """
    norm_text = _normalise_text(raw_text)
    if not norm_text:
        return []

    found: dict = {}  # canonical_name → max_confidence

    # ── Pass 1: exact/substring term match ────────────────────────────────
    for term, (canonical, _cat) in _TERM_INDEX.items():
        if term in norm_text:
            score = 0.90
            found[canonical] = max(found.get(canonical, 0.0), score)

    # ── Pass 2: brand-only match (lower confidence) ────────────────────────
    if not found:
        for brand in _BRAND_NAMES:
            if brand in norm_text:
                # Find the canonical name that best matches this brand
                canonical = _brand_to_canonical(brand, norm_text)
                if canonical:
                    score = 0.65
                    found[canonical] = max(found.get(canonical, 0.0), score)

    # ── Pass 3: token overlap for partial matches ─────────────────────────
    if not found:
        text_tokens = set(norm_text.split())
        for term, (canonical, _cat) in _TERM_INDEX.items():
            term_tokens = set(term.split())
            if len(term_tokens) == 0:
                continue
            overlap = len(term_tokens & text_tokens) / len(term_tokens)
            if overlap >= 0.6:
                score = 0.55 * overlap
                found[canonical] = max(found.get(canonical, 0.0), score)

    # ── Build products, filter by minimum confidence ──────────────────────
    MIN_CONF = 0.50
    products = [
        DetectedProduct(name=name, confidence=round(conf, 2), from_image_index=img_idx)
        for name, conf in found.items()
        if conf >= MIN_CONF
    ]

    # Sort by confidence descending, max 5 per image
    products.sort(key=lambda p: p.confidence, reverse=True)
    return products[:5]


def _brand_to_canonical(brand: str, text: str) -> Optional[str]:
    """Given a matched brand and the full text, find the best canonical name."""
    # Find all knowledge base entries that contain this brand
    candidates = [
        (canonical, terms)
        for terms, canonical, _ in _GROCERY_KB
        if any(brand in t for t in terms)
    ]
    if not candidates:
        return None
    # Pick the candidate whose terms have the most overlap with the text
    best_name = None
    best_score = 0.0
    text_tokens = set(text.split())
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
    """
    Send images to OpenAI GPT-4o with vision and parse the grocery product list.
    Requires OPENAI_API_KEY and credits on the account.
    """
    try:
        import openai  # type: ignore
        import json

        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

        content = [
            {
                "type": "text",
                "text": (
                    "You are a grocery product identification assistant. "
                    "Look at the provided image(s) and list every distinct grocery product you can see. "
                    "For each product, give its common name as a shopper would search for it "
                    "(e.g. 'Amul Milk 1L', 'Britannia Good Day Biscuits 100g', 'Tata Salt 1kg'). "
                    "Include brand names and pack sizes where visible. "
                    "Return ONLY a JSON array of strings. "
                    'Example: ["Amul Milk 1L", "Maggi Noodles 70g", "Tata Salt 1kg"]'
                ),
            }
        ]

        for b64 in images_b64:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}",
                    "detail": "low",
                },
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
            DetectedProduct(name=p.strip(), confidence=0.92, from_image_index=0)
            for p in products_raw if p.strip()
        ]
        logger.info("OpenAI identified %d products from %d images.", len(products), len(images_b64))
        return VisionResult(status=VisionStatus.OK, products=products, image_count_processed=len(images_b64))

    except ImportError:
        return VisionResult(
            status=VisionStatus.NOT_CONFIGURED,
            error_message="OpenAI package not installed.",
            image_count_processed=len(images_b64),
        )
    except Exception as exc:
        status, user_msg = _classify_openai_exception(exc)
        logger.error("OpenAI vision call failed [%s]: %s", status, exc)
        return VisionResult(status=status, error_message=user_msg, image_count_processed=len(images_b64))


def _classify_openai_exception(exc: Exception):
    try:
        import openai  # type: ignore
        if isinstance(exc, openai.RateLimitError):
            body = getattr(exc, "body", None) or {}
            if not isinstance(body, dict):
                body = {}
            error_obj = body.get("error") or body
            code = error_obj.get("code", "") or ""
            err_type = error_obj.get("type", "") or ""
            if code in ("credit_balance_exhausted", "insufficient_quota") or err_type == "insufficient_quota":
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
    return (
        VisionStatus.ERROR,
        "OpenAI error — using free local recognition.",
    )
