#!/usr/bin/env python3
"""Поиск фотографий по лицу из командной строки."""
import argparse
import os
import sys

from search_core import find_photos

ERROR_MESSAGES = {
    "no_face_in_reference": "На опорном фото не найдено лиц. Проверь, чтобы человек был хорошо виден.",
    "no_photos": "В указанной папке не найдено фотографий.",
}

DEFAULT_PHOTOS = "photos_to_search"
DEFAULT_REFERENCE = "my_reference_photo.jpg"


def _pick_photos_folder(args):
    """Определяет папку с фото: флаг > позиционный аргумент > интерактивный ввод > дефолт."""
    folder = args.photos_opt or args.photos_pos
    if folder:
        return folder

    # В неинтерактивном режиме (скрипты/тесты) не блокируемся на input()
    if not sys.stdin.isatty():
        return DEFAULT_PHOTOS

    while True:
        answer = input(f"Путь к папке с фото (Enter = {DEFAULT_PHOTOS}): ").strip()
        if not answer:
            return DEFAULT_PHOTOS
        if os.path.isdir(answer):
            return answer
        print(f"Папка не найдена: {answer}")


def main():
    parser = argparse.ArgumentParser(
        description="Находит все фотографии, на которых есть человек с опорного фото."
    )
    parser.add_argument("photos_pos", nargs="?", default=None, metavar="photos",
                        help=f"Папка с фотографиями для поиска (по умолчанию {DEFAULT_PHOTOS})")
    parser.add_argument("--photos", "-p", dest="photos_opt", default=None,
                        help="Папка с фотографиями для поиска (аналог позиционного аргумента)")
    parser.add_argument("--reference", "-r", default=DEFAULT_REFERENCE,
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
    parser.add_argument("--output", dest="output_dir", default=None,
                        help="Куда сохранить результаты (по умолчанию find_results/ внутри папки поиска)")
    parser.add_argument("--no-dedup", action="store_true",
                        help="Не проверять копии фото по md5 (быстрее на медленных дисках, напр. /mnt)")
    args = parser.parse_args()

    if args.photos_opt and args.photos_pos:
        parser.error("Задай путь только один раз: либо позиционным аргументом, либо через --photos")
    photos_folder = _pick_photos_folder(args)

    result = find_photos(
        photos_folder,
        args.reference,
        tolerance=args.tolerance,
        max_side=args.max_side,
        num_jitters=args.jitters,
        workers=args.workers,
        top_n=args.top,
        output_dir=args.output_dir,
        dedup=not args.no_dedup,
    )

    if "error" in result:
        if result["error"] == "folder_not_found":
            print(f"Папка не найдена: {photos_folder}")
        else:
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
