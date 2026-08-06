#!/usr/bin/env python3
"""
Общая логика поиска фотографий по лицу.

Используется GUI-версией (findmyphoto.py) и CLI-версией (search_cli.py),
чтобы логика поиска была в одном месте.
"""

import hashlib
import os
import shutil
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import face_recognition
import numpy as np
from PIL import Image
from tqdm import tqdm

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
RESULT_DIR_NAME = "find_results"


def _encode_photo(photo_path, max_side=600):
    """Загружает фото, уменьшает до max_side и возвращает энкодинги лиц.

    Возвращает None при ошибке чтения или если лиц не найдено.
    """
    try:
        pil = Image.open(photo_path)
        pil = pil.convert("RGB")
        pil.thumbnail((max_side, max_side), Image.LANCZOS)
        img = np.array(pil)
        del pil
        encodings = face_recognition.face_encodings(img, num_jitters=0, model="small")
        del img
        return encodings
    except Exception:
        return None


def _file_md5(path, chunk_size=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk_size), b""):
            h.update(block)
    return h.hexdigest()


def collect_photos(folder, exclude_results=True):
    """Собирает фотографии, исключая собственную папку с результатами."""
    result_dir = os.path.abspath(os.path.join(folder, RESULT_DIR_NAME))
    photos = []
    for f in sorted(Path(folder).rglob("*")):
        if not f.is_file():
            continue
        if f.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if exclude_results and os.path.abspath(str(f)).startswith(result_dir):
            continue
        photos.append(f)
    return photos


def _process_photo(photo_path, ref_encodings, tolerance, max_side):
    """Обрабатывает одно фото. Возвращает (есть_лица, совпадение_или_None)."""
    encodings = _encode_photo(photo_path, max_side)
    if not encodings:
        return False, None

    best = None
    for i, enc in enumerate(encodings):
        distances = face_recognition.face_distance(ref_encodings, enc)
        distance = float(distances.min())
        if best is None or distance < best["distance"]:
            best = {
                "path": str(photo_path),
                "distance": distance,
                "faces_count": len(encodings),
                "face_index": i,
            }

    if best is not None and best["distance"] < tolerance:
        return True, best
    return True, None


def _default_workers():
    return max(1, min(4, os.cpu_count() or 1))


def _scan_serial(photo_files, ref_encodings, tolerance, max_side, progress_callback=None):
    matches = []
    with_faces = 0
    skipped = 0
    iterator = tqdm(photo_files, desc="Scanning") if progress_callback is None else photo_files

    for done, photo_path in enumerate(iterator, 1):
        has_faces, match = _process_photo(str(photo_path), ref_encodings, tolerance, max_side)
        if has_faces:
            with_faces += 1
        else:
            skipped += 1
        if match is not None:
            matches.append(match)
        if progress_callback:
            progress_callback(done, len(photo_files), str(photo_path))

    return matches, with_faces, skipped


def _scan_parallel(photo_files, ref_encodings, tolerance, max_side, workers, progress_callback=None):
    matches = []
    with_faces = 0
    skipped = 0
    done = 0
    pbar = None if progress_callback else tqdm(total=len(photo_files), desc="Scanning")

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_process_photo, str(p), ref_encodings, tolerance, max_side): p
            for p in photo_files
        }
        for future in as_completed(futures):
            try:
                has_faces, match = future.result()
            except Exception:
                has_faces, match = False, None
            done += 1
            if has_faces:
                with_faces += 1
            else:
                skipped += 1
            if match is not None:
                matches.append(match)
            if progress_callback:
                progress_callback(done, len(photo_files), str(futures[future]))
            elif pbar is not None:
                pbar.update(1)

    if pbar is not None:
        pbar.close()
    return matches, with_faces, skipped


def save_results(photos_folder, matches, tolerance, top_n, stats, output_dir=None):
    """Пишет results.txt и копирует топ-совпадения. Возвращает (папка, скопировано)."""
    out_dir = output_dir or os.path.join(os.path.abspath(photos_folder), RESULT_DIR_NAME)
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "results.txt"), "w", encoding="utf-8") as f:
        f.write("SEARCH RESULTS\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total matches: {len(matches)}\n")
        f.write(f"Photos with faces: {stats['with_faces']}\n")
        f.write(f"Skipped (no face / error): {stats['skipped']}\n")
        f.write(f"Tolerance: {tolerance}\n")
        f.write(f"Max side: {stats['max_side']}px, jitters: {stats['num_jitters']}\n")
        f.write(f"Elapsed: {stats['elapsed']:.1f}s\n")
        f.write("=" * 80 + "\n\n")

        for idx, m in enumerate(matches[:top_n]):
            confidence = (1 - m["distance"]) * 100
            f.write(f"{idx+1}. {os.path.basename(m['path'])}\n")
            f.write(f"   Confidence: {confidence:.1f}%\n")
            f.write(f"   Distance: {m['distance']:.4f}\n")
            f.write(f"   Path: {m['path']}\n")
            f.write(f"   Faces on photo: {m['faces_count']}\n\n")

    top_folder = os.path.join(out_dir, "top_matches")
    os.makedirs(top_folder, exist_ok=True)
    copied = 0
    for i, m in enumerate(matches[:top_n]):
        try:
            shutil.copy(m["path"], os.path.join(top_folder, f"{i+1:03d}_{os.path.basename(m['path'])}"))
            copied += 1
        except Exception:
            pass

    return out_dir, copied


def find_photos(photos_folder, reference_photo, tolerance=0.6, max_side=600,
                num_jitters=3, workers=None, top_n=100, output_dir=None,
                dedup=True, progress_callback=None):
    """Основной поиск. Возвращает dict со статистикой или {"error": ...}."""
    photos_folder = os.fspath(photos_folder)
    reference_photo = os.fspath(reference_photo)

    if not os.path.isdir(photos_folder):
        return {"error": "folder_not_found"}

    start = time.time()

    ref_image = face_recognition.load_image_file(reference_photo)
    ref_encodings = face_recognition.face_encodings(ref_image, num_jitters=num_jitters, model="small")
    del ref_image
    if not ref_encodings:
        return {"error": "no_face_in_reference"}

    photo_files = collect_photos(photos_folder)
    total = len(photo_files)
    if total == 0:
        return {"error": "no_photos"}

    # Дедупликация одинаковых фотографий (копий) по md5.
    # На медленных дисках (например /mnt в WSL) полное чтение файлов дорого — можно отключить.
    if dedup:
        seen = set()
        unique = []
        for f in photo_files:
            digest = _file_md5(f)
            if digest in seen:
                continue
            seen.add(digest)
            unique.append(f)
        photo_files = unique
    total_unique = len(photo_files)

    if workers in (None, 1):
        matches, with_faces, skipped = _scan_serial(
            photo_files, ref_encodings, tolerance, max_side, progress_callback
        )
    else:
        try:
            matches, with_faces, skipped = _scan_parallel(
                photo_files, ref_encodings, tolerance, max_side, workers, progress_callback
            )
        except Exception:
            matches, with_faces, skipped = _scan_serial(
                photo_files, ref_encodings, tolerance, max_side, progress_callback
            )

    matches.sort(key=lambda m: m["distance"])

    stats = {
        "with_faces": with_faces,
        "skipped": skipped,
        "max_side": max_side,
        "num_jitters": num_jitters,
        "elapsed": time.time() - start,
    }

    out_dir, copied = save_results(photos_folder, matches, tolerance, top_n, stats, output_dir)

    return {
        "matches": matches,
        "output_folder": out_dir,
        "copied": copied,
        "elapsed": stats["elapsed"],
        "total": total,
        "unique": total_unique,
        "with_faces": with_faces,
        "skipped": skipped,
    }
