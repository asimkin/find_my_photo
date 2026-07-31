#!/usr/bin/env python3
"""Optimized face search: resize 600px + small model => ~4x faster."""
import os, sys, shutil, time
from pathlib import Path
import face_recognition
import numpy as np
from PIL import Image
from tqdm import tqdm

PHOTOS_FOLDER = r"photos_to_search"
REFERENCE_PHOTO = r"my_reference_photo.jpg"
TOLERANCE = 0.6
OUTPUT_FOLDER = os.path.join("photos_to_search", "find_results")
MAX_SIDE = 600

print("Loading reference photo...")
ref_image = face_recognition.load_image_file(REFERENCE_PHOTO)
ref_encodings = face_recognition.face_encodings(ref_image, num_jitters=10, model="small")
if not ref_encodings:
    print("ERROR: no face found in reference photo")
    sys.exit(1)
target_encoding = ref_encodings[0]
print(f"Reference loaded. Model: small, num_jitters=10")

photo_files = [
    f for f in Path(PHOTOS_FOLDER).rglob("*.*")
    if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif", ".bmp"]
    and "find_results" not in str(f)
]
print(f"Photos to scan: {len(photo_files)}")

matches = []
start_time = time.time()

for photo_path in tqdm(photo_files, desc="Scanning"):
    try:
        pil = Image.open(photo_path)
        pil.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        img = np.array(pil)
        del pil

        encodings = face_recognition.face_encodings(img, num_jitters=0, model="small")
        if not encodings:
            continue

        for i, enc in enumerate(encodings):
            distance = face_recognition.face_distance([target_encoding], enc)[0]
            if distance < TOLERANCE:
                matches.append({
                    "path": photo_path,
                    "distance": float(distance),
                    "faces_count": len(encodings),
                    "face_index": i,
                })
                break
    except Exception:
        pass
    del img

elapsed = time.time() - start_time
matches.sort(key=lambda x: x["distance"])

print(f"\nScan complete in {elapsed/60:.1f} min ({elapsed/len(photo_files)*1000:.0f}ms/photo)")
print(f"Matches found: {len(matches)}")
if matches:
    print(f"Best distance: {matches[0]['distance']:.4f}")

os.makedirs(OUTPUT_FOLDER, exist_ok=True)
with open(os.path.join(OUTPUT_FOLDER, "results.txt"), "w", encoding="utf-8") as f:
    f.write("SEARCH RESULTS\n")
    f.write("=" * 80 + "\n\n")
    f.write(f"Total matches: {len(matches)}\n")
    f.write(f"Tolerance: {TOLERANCE}\n\n")
    for idx, m in enumerate(matches[:100]):
        confidence = (1 - m["distance"]) * 100
        f.write(f"{idx+1}. {m['path'].name}\n")
        f.write(f"   Confidence: {confidence:.1f}%\n")
        f.write(f"   Distance: {m['distance']:.4f}\n")
        f.write(f"   Path: {m['path']}\n\n")

if matches:
    top_folder = os.path.join(OUTPUT_FOLDER, "top_matches")
    os.makedirs(top_folder, exist_ok=True)
    for i, m in enumerate(matches[:100]):
        try:
            shutil.copy(m["path"], os.path.join(top_folder, f"{i+1:03d}_{m['path'].name}"))
        except Exception:
            pass
    print(f"Top {min(100, len(matches))} photos copied to {top_folder}")

print(f"Results saved to {OUTPUT_FOLDER}")
print("SEARCH COMPLETE")
