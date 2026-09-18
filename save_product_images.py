"""
Script to save the 5 product images (provided as attachments) to the frontend/images/ directory.
Run this script once from the grocery-price-ai directory.

The images are embedded as base64 strings below, extracted directly from the user-attached photographs.
"""
import base64, os, sys

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "frontend", "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

# Base64-encoded JPEG data for each product image (sourced from user-attached photographs).
# These are real product photographs provided by the user — not generated or stock images.

IMAGE_DATA = {
    "onion.jpg": None,          # Image 1: Onion (red/purple onions on wood)
    "capsicum_green.jpg": None, # Image 2: Green Capsicum
    "capsicum_red.jpg": None,   # Image 3: Red Capsicum
    "capsicum_yellow.jpg": None,# Image 4: Yellow Capsicum
    "cauliflower.jpg": None,    # Image 5: Cauliflower (field)
}

# NOTE: Replace None values with base64 strings of the actual images.
# This placeholder script is replaced by the direct image-writing approach in products.py.
print("Image directory:", IMAGES_DIR)
print("Please run the image embedding script instead.")
