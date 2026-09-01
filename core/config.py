import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
RESULT_DIR = os.path.join(BASE_DIR, "static", "results")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

MAX_CONTENT_LENGTH = 25 * 1024 * 1024

COLORS = {
    "glioma": (30, 38, 179),       # red, matches --glioma in style.css
    "meningioma": (168, 95, 59),   # blue, matches --meningioma in style.css
    "pituitary": (156, 75, 126),   # purple, matches --pituitary in style.css
}
