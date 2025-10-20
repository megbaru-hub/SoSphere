# core/utils.py
import os
from django.conf import settings
import random
import string
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

def generate_random_signature(length=16):
    """Generates a random alphanumeric string for the signature hash."""
    characters = string.ascii_letters + string.digits
    signature_parts = [
        ''.join(random.choice(characters) for i in range(4)),
        ''.join(random.choice(characters) for i in range(4)),
        ''.join(random.choice(characters) for i in range(4)),
        ''.join(random.choice(characters) for i in range(4)),
    ]
    return '-'.join(signature_parts)

# /home/megbaru/Documents/SoSphere/core/utils.py

def create_grand_seller_stamp():
    """
    Reads the stamp image, converts it to a Base64 string, and returns
    the data URI part for direct embedding in HTML.
    """
    # Define the path to your stamp image
    # Adjust this path if 'stamp.jpg' is located elsewhere in your static files
    stamp_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'stamp.png')

    # Fallback/Debug check (optional but helpful)
    if not os.path.exists(stamp_path):
        print(f"WARNING: Stamp image not found at {stamp_path}")
        return None 

    try:
        with open(stamp_path, "rb") as image_file:
            # Encode the image data to Base64
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Return the full data URI for embedding
            return f"data:image/jpeg;base64,{encoded_string}"
    except Exception as e:
        print(f"Error processing stamp image: {e}")
        return None
