"""
Debug script: find exactly where the false 4th product comes from.
Run: python _debug_pipeline.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from ai.vision_service import (
    _TERM_INDEX, _BRAND_NAMES, _match_text_to_products,
    _fuse_results, _normalise_text, _GROCERY_KB,
)
from ai.visual_recognizer import (
    _COLOUR_PROFILES, _COLOUR_GROUPS, _NAME_TO_GROUP,
    _dedup_by_colour_group, VisualRecognizer,
)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: Short/common terms in _TERM_INDEX that cause false-positive OCR hits
# ─────────────────────────────────────────────────────────────────────────────
print("=== TEST 1: Dangerous short terms in _TERM_INDEX ===")
dangerous = [(t, c) for t, (c, _) in _TERM_INDEX.items() if len(t) <= 5]
print(f"Terms with <=5 chars ({len(dangerous)} total):")
for t, c in sorted(dangerous):
    print(f"  '{t}' -> {c}")
print()

# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: Simulate OCR on typical mixed-product image
# Random printed words that might appear in a shopping photo
# ─────────────────────────────────────────────────────────────────────────────
print("=== TEST 2: OCR false-positive scenarios ===")

test_texts = [
    # Background grocery bag with various text
    ("Grocery bag text", "Fresh Vegetables Daily Use Sugar Salt Oil Net Weight 500g"),
    # Store shelf label
    ("Shelf price tag", "PRICE Rs 45 per kg FRESH DAILY"),
    # Image with Maggi + Tomato + Onion - but OCR reads side text
    ("Maggi label side", "NET WT 70g CONTAINS MAIDA CONTAINS WHEAT"),
    # Plastic wrap with nutritional info
    ("Nutrition label", "ENERGY 250 kcal PROTEIN 5g CARBOHYDRATE 45g FAT 2g"),
    # The KEY scenario: image with 3 products, OCR misreads background
    ("Scene with 3 products", "Tomato Fresh Maggi noodles 70g Amul milk 1L best before"),
]

for label, text in test_texts:
    results = _match_text_to_products(text, 0)
    print(f"  '{label}'")
    print(f"    OCR text: '{text[:60]}...' " if len(text) > 60 else f"    OCR text: '{text}'")
    print(f"    Detected: {[(r.name, r.confidence) for r in results]}")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: The actual multi-group colour problem
# Image: Tomato (red) + Carrot (orange) + Broccoli (green)
# All 3 should fire their group, and all 3 SHOULD stay after dedup
# But what else might fire?
# ─────────────────────────────────────────────────────────────────────────────
print("=== TEST 3: Colour group firing for 3-product image ===")

# Simulate what classify() returns for 3-product image
# If we have: Tomato (red), Carrot (orange), Broccoli (green)
# After dedup: 3 groups fire → 3 products -- correct!
# 
# BUT: if the image also has any neutral/background that triggers a 4th group,
# OR if the OCR fires and adds a 4th product, we get 4.

# Let's test _fuse_results with the exact thresholds
print("Scenario: 3 visual products + 0 OCR")
r = _fuse_results({"Tomato": 0.82, "Carrot": 0.82, "Broccoli": 0.72}, {}, 0)
print(f"  Result: {[(p.name, p.confidence) for p in r]}")
assert len(r) == 3

print("Scenario: 3 visual products + 1 OCR product (different product)")
r = _fuse_results({"Tomato": 0.82, "Carrot": 0.82, "Broccoli": 0.72},
                  {"Maggi 2-Minute Noodles 70g": 0.90}, 0)
print(f"  Result: {[(p.name, p.confidence) for p in r]}")
print(f"  Count: {len(r)}  <-- THIS IS THE BUG if image only has 3 products!")
print()

# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: Cross-group boundary: Orange group vs Yellow group
# Mango hue=22-42 overlaps with Banana hue=30-50
# If an orange-toned image has pixels in hue 30-42 with sat>=130, val=150-255,
# BOTH Mango (orange group) and Banana (yellow group) may fire
# ─────────────────────────────────────────────────────────────────────────────
print("=== TEST 4: Cross-group HSV boundary analysis ===")
print("Checking if any profiles from DIFFERENT groups share HSV pixels...")
print()

# Build a map of (h, s, v) pixel → which profiles fire
# For a pixel at hue=35, sat=145, val=180
# Does it fire Mango (orange grp) AND Banana (yellow grp)?
test_pixels = [
    (35, 145, 180, "yellow-orange pixel"),   # could be Mango AND Banana
    (30, 140, 200, "orange-yellow pixel"),   # Carrot/Banana boundary
    (22, 155, 180, "orange pixel"),           # Carrot and Mango
    (60, 90, 100, "dark green pixel"),        # Broccoli AND Spinach AND Cabbage
    (80, 100, 80, "dark green saturated"),    # Spinach and Broccoli
]

for h, s, v, label in test_pixels:
    firing = []
    for name, h_lo, h_hi, s_lo, v_lo, v_hi, base_conf in _COLOUR_PROFILES:
        if h_hi >= h_lo:
            hue_ok = h_lo <= h <= h_hi
        else:
            hue_ok = h >= h_lo or h <= h_hi
        if hue_ok and s >= s_lo and v_lo <= v <= v_hi:
            gi = _NAME_TO_GROUP.get(name, -1)
            firing.append((name, base_conf, gi))
    # Unique groups
    groups = set(gi for _, _, gi in firing)
    print(f"  Pixel H={h} S={s} V={v} ({label}):")
    for name, conf, gi in firing:
        grp = _COLOUR_GROUPS[gi] if gi >= 0 else "none"
        print(f"    fires: {name} (group {gi}) conf={conf}")
    if len(groups) > 1:
        print(f"  *** CROSS-GROUP! Groups {groups} both fire on this pixel ***")
    print()

# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: THE KEY BUG — _image_likely_has_text() false positive
# This is the most likely source of the 4th product.
# If the heuristic says "has text" on a vegetable image, OCR runs and
# may find a match from background label/packaging.
# ─────────────────────────────────────────────────────────────────────────────
print("=== TEST 5: The OCR false-positive pipeline ===")
print()
print("When OCR runs on a vegetable-only image:")
print("  - Produces garbled text from texture/background")
print("  - _match_text_to_products Pass 1 scans ALL terms in _TERM_INDEX")
print("  - If ANY single-word term appears in garbled text -> match scored 0.90")
print("  - That match enters ocr_hits")
print("  - _fuse_results adds it if o_conf >= 0.65")
print("  - RESULT: false 4th product from background noise")
print()

# What common English words appear in _TERM_INDEX that could match OCR noise?
common_words_that_are_terms = []
common_english = [
    "the", "a", "is", "in", "on", "of", "to", "and", "or", "for",
    "oil", "salt", "sugar", "milk", "rice", "dal", "tea", "bru",
    "vim", "rin", "lax", "amul", "tide", "dove", "lux",
]
for w in common_english:
    if w in _TERM_INDEX:
        common_words_that_are_terms.append((w, _TERM_INDEX[w]))

print("Common words that are _TERM_INDEX entries (OCR false-positive risk):")
for w, (canonical, cat) in sorted(common_words_that_are_terms):
    print(f"  '{w}' -> {canonical}")
print()

# ─────────────────────────────────────────────────────────────────────────────
# TEST 6: Diagnose the EXACT multi-image dedup issue
# When user uploads 1 image with 3 products → only 1 image in images_b64
# But in _sync_hybrid_pipeline, each image runs _process_single_image_hybrid
# The seen_names set prevents duplicates ACROSS images
# But duplicates WITHIN ONE image are already handled by _fuse_results
# Is there a path where one image produces 4 results when only 3 exist?
# ─────────────────────────────────────────────────────────────────────────────
print("=== TEST 6: Multi-crop accumulation path ===")
print()
print("In VisualRecognizer.classify():")
print("  1. Full image processed -> up to 4 per crop")
print("  2. 4 quadrant crops processed -> up to 4 each")
print("  3. All results accumulated into 'accumulated' dict (best conf per name)")
print("  4. _dedup_by_colour_group() applied ONCE after ALL crops")
print("  5. Filter by MIN_CONF, sort, cap at MAX_PRODUCTS=6")
print()
print("Key question: can the accumulation BEFORE step 4 produce cross-group hits?")
print()
print("Example: Full image has Tomato(red) - fires group 0")
print("         Top-left quadrant also has Carrot(orange) - fires group 1")
print("         Bottom-right quadrant has dark background that fires Onion(purple)")
print("         OCR adds Maggi(snacks, no colour group)")
print()
print("After final dedup: Tomato + Carrot + Onion + Maggi = 4 products")
print("BUT only 3 physical products existed!")
print()
print("THE ROOT CAUSE: Quadrant crops analyze PARTS of the image independently.")
print("A background/shadow that covers one quadrant can trigger a colour hit")
print("that did NOT correspond to any real product.")

print()
print("=" * 60)
print("CONCLUSION")
print("=" * 60)
print()
print("The false 4th product enters via ONE of these paths:")
print()
print("PATH A (most common): OCR fires on background text/texture")
print("  -> Pass 1 finds a term in garbled OCR output")
print("  -> Scores 0.90 (full term match)")
print("  -> Passes OCR-only threshold 0.65")
print("  -> Adds a 4th product NOT in the image")
print()
print("PATH B: A quadrant crop matches a 4th colour group from background")
print("  -> Background colour triggers a colour profile")
print("  -> Confidence may meet the 0.55 MIN_CONF + 0.60 fusion threshold")
print("  -> After cross-crop dedup: 4th group fires -> 4th product")
print()
print("PATH C: Carrot (orange, hue 15-30) + Banana (yellow, hue 30-50)")
print("  overlap at hue 30. If image has a pixel at hue=30, sat>=130, val=150-255,")
print("  it fires BOTH Carrot (group 1) and Banana (group 2) = 2 groups.")
print("  So an image with Tomato+Carrot (2 products) can produce 3 hits!")
print()
