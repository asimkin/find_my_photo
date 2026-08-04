#!/usr/bin/env python3
"""Поиск фотографий по лицу из командной строки."""
import argparse
import sys

from search_core import find_photos

ERROR_MESSAGES = {
    "no_face_in_reference": "На опорном фото не найдено лиц. Проверь, чтобы человек был хорошо виден.",
    "no_photos": "В указанной папке не найдено фотографий.",
}


def main():
    parser = argparse.ArgumentParser(
        description="Находит все фотографии, на которых есть человек с опорного фото."
    )
    parser.add_argument("photos", nargs="?", default="photos_to_search",
                        help="Папка с фотографиями для поиска")
    parser.add_argument("--reference", "-r", default="my_reference_photo.jpg",
                        help="Опорное фото с лицом")
    parser.add_argument("--tolerance", "-t", type=float, default=0.6,
                        help="Чувствительность поиска (меньше = строже)")
    parser.add_argument("--top", type=int, default=100,
                        help="Сколько лучших совпадений сохранить")
    parser.add_argument("--workers", "-w", type=int, default=None,
                        help="Кол-во процессов (по умолчанию авт., 1 = без параллелизма)")
    parser.add_argument("--jitters", "-j", type=int, default=3,
                        help="Точность энкодинга опорного фото (0-10, больше = медленнее)")
    parser.add_argument("--max-side", type=int, default=600,
                        help="Максимальная сторона фото при обработке, px")
    args = parser.parse_args()

    result = find_photos(
        args.photos,
        args.reference,
        tolerance=args.tolerance,
        max_side=args.max_side,
        num_jitters=args.jitters,
        workers=args.workers,
        top_n=args.top,
    )

    if "error" in result:
        print(ERROR_MESSAGES[result["error"]])
        return 1

    matches = result["matches"]
    print(f"\nMatches found: {len(matches)}")
    if matches:
        print(f"Best distance: {matches[0]['distance']:.4f}")
    print(f"Photos scanned: {result['unique']} unique (of {result['total']})")
    print(f"Elapsed: {result['elapsed']:.1f}s")
    print(f"Top matches copied: {result['copied']}")
    print(f"Results saved to: {result['output_folder']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
