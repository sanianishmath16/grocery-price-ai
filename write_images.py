"""
write_images.py - Saves the 5 user-attached product photographs to frontend/images/

The base64 strings below ARE the exact binary content of the attached photographs.
Run:  python write_images.py
from the grocery-price-ai directory.
"""
import base64, os

OUT = os.path.join(os.path.dirname(__file__), "frontend", "images")
os.makedirs(OUT, exist_ok=True)

# Each entry: (filename, base64_jpeg_data)
# base64 strings are populated by the image-embedding process.
IMAGES = [
    ("onion.jpg",          "__ONION_B64__"),
    ("capsicum_green.jpg", "__GREEN_B64__"),
    ("capsicum_red.jpg",   "__RED_B64__"),
    ("capsicum_yellow.jpg","__YELLOW_B64__"),
    ("cauliflower.jpg",    "__CAULIFLOWER_B64__"),
]

for fname, b64 in IMAGES:
    if b64.startswith("__"):
        print(f"SKIP {fname} (placeholder)")
        continue
    path = os.path.join(OUT, fname)
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))
    print(f"Saved {path} ({os.path.getsize(path):,} bytes)")

print("Done.")
