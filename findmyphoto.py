#!/usr/bin/env python3
"""
🔍 Интерактивный поиск фотографий с face recognition
Все параметры спрашиваются через UI диалоги.
"""

import os
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
import tkinter.font as tkFont
from tkinter import filedialog, messagebox, ttk

REQUIRED_PACKAGES = {
    'face_recognition': 'face-recognition',
    'PIL': 'pillow',
    'cv2': 'opencv-python',
    'tqdm': 'tqdm',
    'numpy': 'numpy',
}


def ensure_dependencies():
    """Возвращает список pip-пакетов, которые нужно установить."""
    missing = []
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)
    return missing


class PhotoFinderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Поиск моих фотографий")
        self.root.geometry("620x480")
        self.root.resizable(False, False)

        self.photos_folder = None
        self.reference_photo = None
        self.search_core = None
        self.is_running = False

        self.create_ui()

    def create_ui(self):
        title_font = tkFont.Font(family="Arial", size=14, weight="bold")
        normal_font = tkFont.Font(family="Arial", size=10)

        title = tk.Label(self.root, text="Поиск фотографий", font=title_font)
        title.pack(pady=15)

        info_frame = tk.Frame(self.root)
        info_frame.pack(pady=5, padx=20, fill=tk.BOTH, expand=True)

        tk.Label(info_frame, text="Папка с фотографиями:", font=normal_font, anchor="w").pack(fill=tk.X, pady=(5, 5))
        self.folder_label = tk.Label(info_frame, text="не выбрана", fg="gray", font=normal_font)
        self.folder_label.pack(fill=tk.X, padx=20)
        tk.Button(info_frame, text="Выбрать папку", command=self.select_photos_folder).pack(pady=3)

        tk.Label(info_frame, text="Опорное фото (на котором ты есть):", font=normal_font, anchor="w").pack(fill=tk.X, pady=(10, 5))
        self.ref_label = tk.Label(info_frame, text="не выбрано", fg="gray", font=normal_font)
        self.ref_label.pack(fill=tk.X, padx=20)
        tk.Button(info_frame, text="Выбрать фото", command=self.select_reference_photo).pack(pady=3)

        tk.Label(info_frame, text="Чувствительность (меньше = строже):", font=normal_font, anchor="w").pack(fill=tk.X, pady=(10, 5))
        self.tolerance_var = tk.DoubleVar(value=0.6)
        tolerance_frame = tk.Frame(info_frame)
        tolerance_frame.pack(fill=tk.X, padx=20)
        tk.Scale(tolerance_frame, from_=0.3, to=1.0, resolution=0.05,
                orient=tk.HORIZONTAL, variable=self.tolerance_var,
                font=normal_font).pack(fill=tk.X)

        # Прогресс
        progress_frame = tk.Frame(self.root)
        progress_frame.pack(fill=tk.X, padx=30, pady=(5, 0))
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X)
        self.status_var = tk.StringVar(value="")
        tk.Label(progress_frame, textvariable=self.status_var, font=normal_font,
                 fg="gray", anchor="w").pack(fill=tk.X, pady=(3, 0))

        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=15)
        self.start_button = tk.Button(button_frame, text="НАЧАТЬ ПОИСК", command=self.start_search,
                 bg="#4CAF50", fg="white", font=tkFont.Font(size=11, weight="bold"),
                 padx=20, pady=10)
        self.start_button.pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="Выход", command=self.root.quit,
                 padx=20, pady=10).pack(side=tk.LEFT, padx=10)

    def select_photos_folder(self):
        folder = filedialog.askdirectory(title="Выбери папку с фотографиями")
        if folder:
            self.photos_folder = folder
            self.folder_label.config(text=folder, fg="black")

    def select_reference_photo(self):
        file = filedialog.askopenfilename(
            title="Выбери опорное фото",
            filetypes=[("Изображения", "*.jpg *.jpeg *.png *.gif *.bmp"), ("Все файлы", "*.*")]
        )
        if file:
            self.reference_photo = file
            self.ref_label.config(text=Path(file).name, fg="black")

    def start_search(self):
        if self.is_running:
            return
        if not self.photos_folder:
            messagebox.showerror("Ошибка", "Выбери папку с фотографиями!")
            return
        if not self.reference_photo:
            messagebox.showerror("Ошибка", "Выбери опорное фото!")
            return

        self.search_core = __import__("search_core")
        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.status_var.set("Загрузка опорного фото...")

        photos_folder = self.photos_folder
        reference_photo = self.reference_photo
        tolerance = self.tolerance_var.get()

        def worker():
            try:
                result = self.search_core.find_photos(
                    photos_folder,
                    reference_photo,
                    tolerance=tolerance,
                    progress_callback=self._on_progress,
                )
                self.root.after(0, self._finish_search, result)
            except Exception as e:
                self.root.after(0, self._show_error, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_progress(self, done, total, current_path):
        self.root.after(0, self._update_progress, done, total)

    def _update_progress(self, done, total):
        if total:
            self.progress_var.set(done * 100 / total)
        self.status_var.set(f"Обработано {done} из {total}")

    def _show_error(self, message):
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        messagebox.showerror("Ошибка", message)

    def _finish_search(self, result):
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)

        if "error" in result:
            errors = {
                "no_face_in_reference": "На опорном фото не найдено лиц!\nПроверь, чтобы человек был хорошо виден.",
                "no_photos": "В выбранной папке не найдено фотографий!",
            }
            self.status_var.set("")
            messagebox.showerror("Ошибка", errors[result["error"]])
            return

        matches = result["matches"]
        self.status_var.set("Готово")
        best = matches[0]["distance"] if matches else 0.0
        best_conf = (1 - best) * 100

        messagebox.showinfo(
            "Успех!",
            f"ПОИСК ЗАВЕРШЕН!\n\n"
            f"Статистика:\n"
            f"  - Найдено совпадений: {len(matches)}\n"
            f"  - Лучший результат: {best:.4f}\n"
            f"  - Уверенность лучшего: {best_conf:.1f}%\n"
            f"  - Время: {result['elapsed']:.1f} сек\n\n"
            f"Результаты сохранены:\n  {result['output_folder']}\n"
            f"Подробный лог: results.txt\n"
            f"Топ фото: top_matches/\n"
        )

        if sys.platform == "win32":
            try:
                os.startfile(result["output_folder"])
            except Exception:
                pass


def main():
    missing = ensure_dependencies()
    if missing:
        answer = messagebox.askyesno(
            "Зависимости",
            f"Не установлены пакеты:\n{', '.join(missing)}\n\nУстановить сейчас?"
        )
        if answer:
            for package in missing:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])
        else:
            print(f"Установи вручную: pip install {' '.join(missing)}")
            return

    root = tk.Tk()
    PhotoFinderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
