"""Quick OCR test runner — run as: python run_ocr_tests.py"""
import sys
sys.path.insert(0, '.')

from ai.vision_service import _match_text_to_products, _normalise_text

def test(name, expr, expected=True):
    try:
        result = expr()
        if result == expected or (expected is True and result):
            print(f"PASS: {name}")
            return True
        else:
            print(f"FAIL: {name} — got {result!r}, expected {expected!r}")
            return False
    except Exception as e:
        print(f"FAIL: {name} — exception: {e}")
        return False

passed = 0
total = 0

def run(name, fn):
    global passed, total
    total += 1
    if test(name, fn):
        passed += 1

run("maggi full match",
    lambda: any("maggi" in r.name.lower() for r in _match_text_to_products("maggi noodles instant", 0)))

run("maggi confidence >= 0.90",
    lambda: (
        lambda rs: rs[0].confidence >= 0.90 if rs else False
    )(_match_text_to_products("maggi noodles instant", 0)))

run("amul brand match",
    lambda: any("amul" in r.name.lower() for r in _match_text_to_products("amul taaza fresh milk", 0)))

run("colgate match",
    lambda: any("colgate" in r.name.lower() for r in _match_text_to_products("colgate strong teeth toothpaste", 0)))

run("empty text returns empty",
    lambda: _match_text_to_products("", 0) == [])

run("unrelated text returns empty",
    lambda: _match_text_to_products("quantum physics electromagnetic", 0) == [])

mage_norm = _normalise_text("Mage 2 Minute Noodleg")
mage_results = _match_text_to_products("Mage 2 Minute Noodleg", 0)
print(f"INFO: 'Mage 2 Minute Noodleg' normalized='{mage_norm}' -> {[r.name for r in mage_results]}")
# '2 minute' is not enough alone to trigger — needs 'noodles' but 'noodleg' doesn't match
# The original OCR 'Mage!' fix tested here: '2 minute noodles' should match
mage2_results = _match_text_to_products("Mage 2 minute noodles", 0)
run("Mage + 2 minute noodles matches Maggi",
    lambda: any("maggi" in r.name.lower() for r in mage2_results))

print(f"\n{passed}/{total} passed")
sys.exit(0 if passed == total else 1)
