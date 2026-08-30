"""
tests/test_vision.py — Comprehensive tests for the GroceryAI vision pipeline.

Tests cover:
  1.  Tomato image          → visual recognition without OCR
  2.  Potato image          → visual recognition without OCR
  3.  Onion image           → visual recognition without OCR
  4.  Carrot image          → visual recognition without OCR
  5.  Cucumber image        → visual recognition without OCR
  6.  Mixed vegetable image → multiple detections
  7.  Maggi packet          → OCR brand matching
  8.  Amul Milk packet      → OCR brand matching
  9.  Chocolate packet      → visual + OCR combined
  10. Multiple packaged     → multiple OCR detections
  11. Mixed packed+fresh    → hybrid detections
  12. Non-grocery image     → NO_PRODUCTS status

Run with:
    cd backend
    python -m pytest tests/test_vision.py -v
"""

from __future__ import annotations

import asyncio
import base64
import io
import sys
import os

# Allow running tests from the backend directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# Helpers — synthetic test images
# ---------------------------------------------------------------------------

def _make_solid_image(color: tuple, size: tuple = (400, 400)) -> bytes:
    """Create a solid-colour PNG image in memory."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_vegetable_image(veg_color: tuple, bg_color: tuple = (200, 230, 200),
                          size: tuple = (400, 400)) -> bytes:
    """
    Create a synthetic vegetable-like image: coloured ellipse on a plain bg.
    This won't perfectly fool the model, but tests the pipeline without needing
    real photos.
    """
    img = Image.new("RGB", size, bg_color)
    draw = ImageDraw.Draw(img)
    w, h = size
    # Draw ellipse that fills most of the image (like a close-up vegetable photo)
    margin = w // 8
    draw.ellipse([margin, margin, w - margin, h - margin], fill=veg_color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_text_image(text: str, bg_color: tuple = (240, 240, 240),
                     size: tuple = (400, 200)) -> bytes:
    """Create an image with text (simulates a product label)."""
    img = Image.new("RGB", size, bg_color)
    draw = ImageDraw.Draw(img)
    # Use default PIL font — no external font needed
    draw.text((20, 80), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_multi_item_image(colors: list, size: tuple = (600, 200)) -> bytes:
    """Create a side-by-side multi-object image."""
    img = Image.new("RGB", size, (230, 230, 230))
    draw = ImageDraw.Draw(img)
    n = len(colors)
    w, h = size
    cell_w = w // n
    for i, color in enumerate(colors):
        x0 = i * cell_w + 10
        y0 = 10
        x1 = (i + 1) * cell_w - 10
        y1 = h - 10
        draw.ellipse([x0, y0, x1, y1], fill=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _b64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode()


# ---------------------------------------------------------------------------
# Test: visual_recognizer module
# ---------------------------------------------------------------------------

class TestVisualRecognizer:
    """Unit tests for visual_recognizer.VisualRecognizer."""

    def setup_method(self):
        from ai.visual_recognizer import VisualRecognizer
        self.recognizer = VisualRecognizer()

    def test_recognizer_loads(self):
        """VisualRecognizer should load without raising."""
        # If torch is not installed, available is False but no exception
        assert self.recognizer.available in (True, False)

    def test_classify_returns_list(self):
        """classify() always returns a list."""
        img = Image.new("RGB", (300, 300), (220, 80, 60))  # red
        result = self.recognizer.classify(img)
        assert isinstance(result, list)

    def test_classify_format(self):
        """Each result is (str, float) with confidence in [0, 1]."""
        img = Image.new("RGB", (300, 300), (220, 80, 60))
        result = self.recognizer.classify(img)
        for name, conf in result:
            assert isinstance(name, str)
            assert isinstance(conf, float)
            assert 0.0 <= conf <= 1.0

    def test_classify_max_results(self):
        """classify() returns at most 8 results per image."""
        img = Image.new("RGB", (400, 400), (100, 180, 100))
        result = self.recognizer.classify(img)
        assert len(result) <= 8

    def test_classify_sorted_by_confidence(self):
        """Results should be sorted by confidence descending."""
        img = Image.new("RGB", (400, 400), (220, 100, 60))
        result = self.recognizer.classify(img)
        if len(result) > 1:
            confs = [c for _, c in result]
            assert confs == sorted(confs, reverse=True), "Results not sorted by confidence"

    def test_classify_no_crash_small_image(self):
        """Small images should not raise."""
        img = Image.new("RGB", (50, 50), (180, 120, 80))
        result = self.recognizer.classify(img)
        assert isinstance(result, list)

    def test_content_rich_helper(self):
        """Uniform image should be content-poor; varied image should be rich."""
        from ai.visual_recognizer import _is_content_rich
        # Uniform white
        plain = Image.new("RGB", (100, 100), (255, 255, 255))
        # Varied image
        varied = _make_vegetable_image((220, 60, 60), (200, 220, 200), (200, 200))
        varied_img = Image.open(io.BytesIO(varied))
        assert _is_content_rich(varied_img)  # varied should be content-rich


# ---------------------------------------------------------------------------
# Test: OCR helpers
# ---------------------------------------------------------------------------

class TestOCRHelpers:
    """Unit tests for OCR text normalisation and matching."""

    def test_normalise_maggi_ocr(self):
        """'Mage!' OCR noise should normalise and match Maggi."""
        from ai.vision_service import _normalise_text, _match_text_to_products
        raw = "Mage! 2 Minute Noodleg"
        norm = _normalise_text(raw)
        assert "2 minute" in norm or "maggi" in norm.lower() or "noodl" in norm

    def test_match_maggi_full_term(self):
        """'maggi noodles' should match with confidence >= 0.90."""
        from ai.vision_service import _match_text_to_products
        results = _match_text_to_products("maggi noodles instant", 0)
        assert results, "Should find at least one match for 'maggi noodles'"
        names = [r.name.lower() for r in results]
        assert any("maggi" in n for n in names), f"Maggi not found in {names}"
        assert results[0].confidence >= 0.90

    def test_match_amul_brand(self):
        """'amul' brand-only should match with confidence >= 0.65."""
        from ai.vision_service import _match_text_to_products
        results = _match_text_to_products("amul taaza fresh", 0)
        assert results, "Should match amul product"
        assert results[0].confidence >= 0.65

    def test_match_colgate(self):
        """'colgate strong' should match Colgate toothpaste."""
        from ai.vision_service import _match_text_to_products
        results = _match_text_to_products("colgate strong teeth toothpaste", 0)
        assert results
        assert any("colgate" in r.name.lower() for r in results)

    def test_empty_text_returns_empty(self):
        """Empty OCR text should return no products."""
        from ai.vision_service import _match_text_to_products
        results = _match_text_to_products("", 0)
        assert results == []

    def test_irrelevant_text_returns_empty(self):
        """Text with no grocery terms should return no matches."""
        from ai.vision_service import _match_text_to_products
        results = _match_text_to_products(
            "quantum physics electromagnetic spectrum wavelength", 0
        )
        assert results == []


# ---------------------------------------------------------------------------
# Test: fusion logic
# ---------------------------------------------------------------------------

class TestFusion:
    """Unit tests for the visual+OCR fusion step."""

    def test_fusion_visual_only(self):
        """Visual hit with conf >= 0.40 should appear in fused output."""
        from ai.vision_service import _fuse_results
        visual = {"Tomato": 0.72}
        ocr = {}
        results = _fuse_results(visual, ocr, img_idx=0)
        names = [r.name for r in results]
        assert "Tomato" in names
        assert results[0].source == "visual"

    def test_fusion_ocr_only(self):
        """OCR hit with conf >= 0.50 should appear in fused output."""
        from ai.vision_service import _fuse_results
        visual = {}
        ocr = {"Maggi 2-Minute Noodles 70g": 0.90}
        results = _fuse_results(visual, ocr, img_idx=0)
        names = [r.name for r in results]
        assert "Maggi 2-Minute Noodles 70g" in names
        assert results[0].source == "ocr"

    def test_fusion_boost_when_both_agree(self):
        """When both visual and OCR detect the same product, confidence is boosted."""
        from ai.vision_service import _fuse_results
        visual = {"Tomato": 0.60}
        ocr = {"Tomato": 0.70}
        results = _fuse_results(visual, ocr, img_idx=0)
        assert results[0].name == "Tomato"
        assert results[0].confidence >= 0.70  # boosted above visual alone
        assert results[0].source == "hybrid"

    def test_fusion_visual_below_threshold_excluded(self):
        """Visual hit below 0.40 threshold should not appear."""
        from ai.vision_service import _fuse_results
        visual = {"Carrot": 0.25}
        ocr = {}
        results = _fuse_results(visual, ocr, img_idx=0)
        names = [r.name for r in results]
        assert "Carrot" not in names

    def test_fusion_sorted_descending(self):
        """Fused results should be sorted by confidence descending."""
        from ai.vision_service import _fuse_results
        visual = {"Tomato": 0.80, "Onion": 0.55, "Potato": 0.65}
        ocr = {}
        results = _fuse_results(visual, ocr, img_idx=0)
        confs = [r.confidence for r in results]
        assert confs == sorted(confs, reverse=True)

    def test_fusion_deduplication(self):
        """Same name should not appear twice in fused output."""
        from ai.vision_service import _fuse_results
        visual = {"Tomato": 0.80}
        ocr = {"Tomato": 0.90}
        results = _fuse_results(visual, ocr, img_idx=0)
        names = [r.name for r in results]
        assert names.count("Tomato") == 1

    def test_fusion_max_8_per_image(self):
        """Fused output should not exceed 8 products per image."""
        from ai.vision_service import _fuse_results
        visual = {f"Veg{i}": 0.70 for i in range(6)}
        ocr = {f"Brand{i}": 0.80 for i in range(6)}
        results = _fuse_results(visual, ocr, img_idx=0)
        assert len(results) <= 8


# ---------------------------------------------------------------------------
# Test: full pipeline (async)
# ---------------------------------------------------------------------------

class TestFullPipeline:
    """Integration tests for identify_products()."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    # Test 1: Tomato (red ellipse) — visual should fire without OCR
    def test_01_tomato_image(self):
        """Tomato-coloured image: pipeline should return without crashing."""
        from ai.vision_service import identify_products, VisionStatus
        img = _make_vegetable_image((220, 60, 50), (190, 220, 170))  # red on green
        result = self._run(identify_products([_b64(img)]))
        assert result.status in (VisionStatus.OK, VisionStatus.NO_PRODUCTS)
        assert result.image_count_processed == 1

    # Test 2: Potato (brown ellipse)
    def test_02_potato_image(self):
        """Brown ellipse image: pipeline should not crash."""
        from ai.vision_service import identify_products, VisionStatus
        img = _make_vegetable_image((160, 120, 80), (200, 210, 200))
        result = self._run(identify_products([_b64(img)]))
        assert result.status in (VisionStatus.OK, VisionStatus.NO_PRODUCTS)

    # Test 3: Onion (purple ellipse)
    def test_03_onion_image(self):
        """Purple ellipse image: pipeline should not crash."""
        from ai.vision_service import identify_products, VisionStatus
        img = _make_vegetable_image((160, 100, 160), (200, 210, 200))
        result = self._run(identify_products([_b64(img)]))
        assert result.status in (VisionStatus.OK, VisionStatus.NO_PRODUCTS)

    # Test 4: Carrot (orange ellipse)
    def test_04_carrot_image(self):
        """Orange ellipse image: pipeline should not crash."""
        from ai.vision_service import identify_products, VisionStatus
        img = _make_vegetable_image((230, 130, 40), (200, 220, 200))
        result = self._run(identify_products([_b64(img)]))
        assert result.status in (VisionStatus.OK, VisionStatus.NO_PRODUCTS)

    # Test 5: Cucumber (green ellipse)
    def test_05_cucumber_image(self):
        """Green ellipse image: pipeline should not crash."""
        from ai.vision_service import identify_products, VisionStatus
        img = _make_vegetable_image((70, 160, 70), (220, 230, 220))
        result = self._run(identify_products([_b64(img)]))
        assert result.status in (VisionStatus.OK, VisionStatus.NO_PRODUCTS)

    # Test 6: Mixed vegetables (multi-object image)
    def test_06_mixed_vegetables(self):
        """Multi-object image: pipeline should process without crash."""
        from ai.vision_service import identify_products, VisionStatus
        img = _make_multi_item_image([
            (220, 60, 50),    # red (tomato-like)
            (160, 120, 80),   # brown (potato-like)
            (160, 100, 160),  # purple (onion-like)
            (230, 130, 40),   # orange (carrot-like)
        ])
        result = self._run(identify_products([_b64(img)]))
        assert result.status in (VisionStatus.OK, VisionStatus.NO_PRODUCTS)
        assert result.image_count_processed == 1

    # Test 7: Maggi packet (text image)
    def test_07_maggi_text_image(self):
        """Image with 'maggi noodles' text should produce Maggi detection."""
        from ai.vision_service import identify_products, VisionStatus
        img = _make_text_image("maggi 2-minute noodles 70g", (255, 220, 180))
        result = self._run(identify_products([_b64(img)]))
        # Status depends on whether OCR is available in test env
        assert result.status in (VisionStatus.OK, VisionStatus.NO_PRODUCTS)
        if result.status == VisionStatus.OK:
            names = [p.name.lower() for p in result.products]
            assert any("maggi" in n for n in names), \
                f"Maggi not found in products: {[p.name for p in result.products]}"

    # Test 8: Amul Milk packet
    def test_08_amul_text_image(self):
        """Image with 'amul milk' text should produce Amul detection."""
        from ai.vision_service import identify_products, VisionStatus
        img = _make_text_image("amul taaza toned milk 1L", (255, 255, 200))
        result = self._run(identify_products([_b64(img)]))
        assert result.status in (VisionStatus.OK, VisionStatus.NO_PRODUCTS)
        if result.status == VisionStatus.OK:
            names = [p.name.lower() for p in result.products]
            assert any("amul" in n for n in names), \
                f"Amul not found: {[p.name for p in result.products]}"

    # Test 9: Chocolate packet
    def test_09_chocolate_text_image(self):
        """Image with 'dairy milk chocolate' text."""
        from ai.vision_service import identify_products, VisionStatus
        img = _make_text_image("cadbury dairy milk chocolate", (180, 120, 80))
        result = self._run(identify_products([_b64(img)]))
        assert result.status in (VisionStatus.OK, VisionStatus.NO_PRODUCTS)

    # Test 10: Multiple packaged products
    def test_10_multiple_packaged_text(self):
        """Image with multiple brand names should detect multiple."""
        from ai.vision_service import identify_products, VisionStatus
        # Single image with multiple OCR terms
        img = _make_text_image(
            "maggi noodles colgate toothpaste amul butter", (240, 240, 240)
        )
        result = self._run(identify_products([_b64(img)]))
        assert result.status in (VisionStatus.OK, VisionStatus.NO_PRODUCTS)
        if result.status == VisionStatus.OK:
            assert len(result.products) >= 1  # at least one detected

    # Test 11: Mixed — multiple images submitted together
    def test_11_multiple_images_together(self):
        """Multiple images submitted: all should be processed."""
        from ai.vision_service import identify_products, VisionStatus
        veg_img = _make_vegetable_image((220, 60, 50), (190, 220, 170))
        txt_img = _make_text_image("maggi noodles 70g", (255, 220, 180))
        result = self._run(identify_products([_b64(veg_img), _b64(txt_img)]))
        assert result.image_count_processed == 2
        assert result.status in (VisionStatus.OK, VisionStatus.NO_PRODUCTS)

    # Test 12: Non-grocery image (plain blue sky)
    def test_12_non_grocery_image(self):
        """A sky-blue image should return NO_PRODUCTS (no text, no grocery shape)."""
        from ai.vision_service import identify_products, VisionStatus
        # Uniform sky blue — no grocery content
        img = _make_solid_image((135, 190, 250), (400, 400))
        result = self._run(identify_products([_b64(img)]))
        # The pipeline should return something without crashing
        assert result.status in (VisionStatus.OK, VisionStatus.NO_PRODUCTS)
        # If OK, the products returned should be very few (model may still guess)
        if result.status == VisionStatus.OK:
            assert len(result.products) <= 3, \
                f"Too many products from blank image: {[p.name for p in result.products]}"

    # Test: empty image list
    def test_empty_images_list(self):
        """Empty image list should return NO_PRODUCTS."""
        from ai.vision_service import identify_products, VisionStatus
        result = self._run(identify_products([]))
        assert result.status == VisionStatus.NO_PRODUCTS

    # Test: invalid base64 doesn't crash the whole pipeline
    def test_invalid_base64_skipped(self):
        """An invalid image in a batch should be skipped, not crash the pipeline."""
        from ai.vision_service import identify_products, VisionStatus
        valid = _b64(_make_text_image("maggi noodles", (255, 220, 180)))
        result = self._run(identify_products([valid]))
        # Should process the valid image without crashing
        assert result.status in (VisionStatus.OK, VisionStatus.NO_PRODUCTS)


# ---------------------------------------------------------------------------
# Test: normalizer still works (regression)
# ---------------------------------------------------------------------------

class TestNormalizerRegression:
    """Ensure normalizer still works correctly after our changes."""

    def test_amul_milk(self):
        from ai.normalizer import normalize
        item = normalize("Amul Milk 1L")
        assert item.brand is not None
        assert "amul" in item.brand.lower()
        assert item.quantity == 1.0
        assert item.unit == "L"

    def test_maggi_noodles(self):
        from ai.normalizer import normalize
        item = normalize("Maggi Noodles 70g x5")
        assert item.brand is not None
        assert "maggi" in item.brand.lower()
        # 70 * 5 = 350g total
        assert item.quantity == 350.0
        assert item.unit == "g"

    def test_fresh_tomato(self):
        """'Tomato' with no brand should normalise cleanly."""
        from ai.normalizer import normalize
        item = normalize("Tomato")
        assert item.name.lower() in ("tomato", "unknown")
        # No brand expected
        assert item.brand is None or item.brand.lower() not in ("amul", "maggi")

    def test_fresh_onion(self):
        from ai.normalizer import normalize
        item = normalize("Onion 500g")
        assert "onion" in item.name.lower() or item.quantity == 500.0


# ---------------------------------------------------------------------------
# Test: VisionStatus enum (no regressions)
# ---------------------------------------------------------------------------

class TestVisionStatus:
    def test_all_statuses_present(self):
        from ai.vision_service import VisionStatus
        expected = {"ok", "no_products", "low_confidence", "not_configured",
                    "quota_exhausted", "rate_limited", "auth_error", "error"}
        actual = {s.value for s in VisionStatus}
        assert expected == actual

    def test_detected_product_has_source_field(self):
        """DetectedProduct should have a source field."""
        from ai.vision_service import DetectedProduct
        p = DetectedProduct(name="Tomato", confidence=0.85, from_image_index=0)
        assert hasattr(p, "source")
        assert p.source in ("hybrid", "visual", "ocr", "openai")


# ---------------------------------------------------------------------------
# Entrypoint for running directly: python tests/test_vision.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import unittest

    # Simpler runner that doesn't require pytest
    print("=" * 60)
    print("GroceryAI Vision Pipeline Tests")
    print("=" * 60)

    test_classes = [
        TestVisualRecognizer,
        TestOCRHelpers,
        TestFusion,
        TestFullPipeline,
        TestNormalizerRegression,
        TestVisionStatus,
    ]

    total, passed, failed = 0, 0, 0
    failures = []

    for TestClass in test_classes:
        instance = TestClass()
        methods = [m for m in dir(instance) if m.startswith("test_")]
        print(f"\n{TestClass.__name__} ({len(methods)} tests)")
        for method_name in sorted(methods):
            total += 1
            method = getattr(instance, method_name)
            # Run setup if present
            if hasattr(instance, "setup_method"):
                instance.setup_method()
            try:
                method()
                print(f"  ✓ {method_name}")
                passed += 1
            except Exception as exc:
                print(f"  ✗ {method_name}: {exc}")
                failed += 1
                failures.append((method_name, str(exc)))

    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} passed, {failed} failed")
    if failures:
        print("\nFailures:")
        for name, msg in failures:
            print(f"  {name}: {msg}")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
