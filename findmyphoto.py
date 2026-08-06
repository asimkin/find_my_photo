#!/usr/bin/env python3
"""
🔍 Интерактивный поиск фотографий с face recognition
Все параметры спрашиваются через UI диалоги.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

try:
    import tkinter as tk
    import tkinter.font as tkFont
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    print("Для графической версии (findmyphoto.py) нужен модуль tkinter.")
    print("Установи его в системе и запусти через venv:")
    print("    sudo apt install python3-tk")
    print("    .venv/bin/python findmyphoto.py")
    sys.exit(1)

REQUIRED_PACKAGES = {
    'face_recognition': 'face-recognition',
    'PIL': 'pillow',
    'cv2': 'opencv-python',
    'tqdm': 'tqdm',
    'numpy': 'numpy',
}

CONFIG_NAME = "find_my_photo/config.json"


def ensure_dependencies():
    """Возвращает список pip-пакетов, которые нужно установить."""
    missing = []
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)
    return missing


def config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(Path.home(), ".config")
    return os.path.join(base, CONFIG_NAME)


def load_config():
    try:
        with open(config_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(photos_folder, reference_photo, output_folder=""):
    try:
        path = config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "photos_folder": photos_folder,
                "reference_photo": reference_photo,
                "output_folder": output_folder,
            }, f, indent=2)
    except Exception:
        pass


def open_folder(path):
    """Открывает папку в системном файловом менеджере. Возвращает True/False."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
            return True

        # WSL: открываем через Windows Explorer (файловый менеджер Windows).
        # xdg-open в WSL обычно не установлен и без него ничего не открывается.
        if os.environ.get("WSL_DISTRO_NAME") or os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop"):
            try:
                win_path = subprocess.check_output(["wslpath", "-w", path], text=True).strip()
                subprocess.Popen(["explorer.exe", win_path])
                return True
            except Exception:
                pass

        # Обычный Linux
        if shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", path])
            return True
        if shutil.which("gio"):
            subprocess.Popen(["gio", "open", path])
            return True
    except Exception:
        pass
    return False


class PhotoFinderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Поиск моих фотографий")
        self.root.geometry("680x600")
        self.root.resizable(False, False)

        config = load_config()
        self.photos_folder = config.get("photos_folder", "")
        self.reference_photo = config.get("reference_photo", "")
        self.output_folder = config.get("output_folder", "")
        self.folder_var = tk.StringVar(value=self.photos_folder)
        self.reference_var = tk.StringVar(value=self.reference_photo)
        self.output_var = tk.StringVar(value=self.output_folder)
        self.search_core = None
        self.is_running = False
        self.results_folder = None

        self.create_ui()

    def create_ui(self):
        title_font = tkFont.Font(family="Arial", size=14, weight="bold")
        normal_font = tkFont.Font(family="Arial", size=10)

        title = tk.Label(self.root, text="Поиск фотографий", font=title_font)
        title.pack(pady=15)

        info_frame = tk.Frame(self.root)
        info_frame.pack(pady=5, padx=20, fill=tk.BOTH, expand=True)

        tk.Label(info_frame, text="Папка с фотографиями:", font=normal_font, anchor="w").pack(fill=tk.X, pady=(5, 5))
        folder_row = tk.Frame(info_frame)
        folder_row.pack(fill=tk.X, padx=20)
        self.folder_entry = tk.Entry(folder_row, textvariable=self.folder_var, font=normal_font)
        self.folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(folder_row, text="Выбрать…", command=self.select_photos_folder).pack(side=tk.LEFT, padx=(5, 0))

        tk.Label(info_frame, text="Опорное фото (на котором ты есть):", font=normal_font, anchor="w").pack(fill=tk.X, pady=(10, 5))
        ref_row = tk.Frame(info_frame)
        ref_row.pack(fill=tk.X, padx=20)
        self.ref_entry = tk.Entry(ref_row, textvariable=self.reference_var, font=normal_font)
        self.ref_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(ref_row, text="Выбрать фото", command=self.select_reference_photo).pack(side=tk.LEFT, padx=(5, 0))

        tk.Label(info_frame, text="Папка для результатов (пусто = find_results/ в папке поиска):",
                 font=normal_font, anchor="w").pack(fill=tk.X, pady=(10, 5))
        output_row = tk.Frame(info_frame)
        output_row.pack(fill=tk.X, padx=20)
        self.output_entry = tk.Entry(output_row, textvariable=self.output_var, font=normal_font)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(output_row, text="Выбрать…", command=self.select_output_folder).pack(side=tk.LEFT, padx=(5, 0))

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

        self.results_frame = tk.Frame(self.root)
        self.results_path_var = tk.StringVar(value="")
        self.results_path_label = tk.Label(self.results_frame, textvariable=self.results_path_var,
                 font=normal_font, fg="#1a5fb4", anchor="w", cursor="hand2")
        self.results_path_label.pack(fill=tk.X)
        self.results_path_label.bind("<Button-1>", lambda e: self._open_results())
        self.open_button = tk.Button(
            self.results_frame, text="Открыть папку с найденными фото",
            command=self._open_results, state=tk.DISABLED, font=normal_font, padx=10, pady=4)
        self.open_button.pack(pady=(4, 0))

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
            self.folder_var.set(folder)

    def select_reference_photo(self):
        file = filedialog.askopenfilename(
            title="Выбери опорное фото",
            filetypes=[("Изображения", "*.jpg *.jpeg *.png *.gif *.bmp"), ("Все файлы", "*.*")]
        )
        if file:
            self.reference_var.set(file)

    def select_output_folder(self):
        folder = filedialog.askdirectory(title="Выбери папку для результатов (пусто — по умолчанию)")
        if folder:
            self.output_var.set(folder)

    def _open_results(self):
        if self.results_folder:
            if not open_folder(self.results_folder):
                messagebox.showerror(
                    "Не удалось открыть папку",
                    f"Не найден файловый менеджер.\n"
                    f"Путь к результатам:\n{self.results_folder}",
                )

    def _show_results(self, path):
        self.results_folder = path
        self.results_path_var.set(f"Результаты: {path}")
        self.open_button.config(state=tk.NORMAL)
        self.results_frame.pack(fill=tk.X, padx=30, pady=(8, 0))

    def _hide_results(self):
        self.results_folder = None
        self.results_path_var.set("")
        self.open_button.config(state=tk.DISABLED)
        self.results_frame.pack_forget()

    def start_search(self):
        if self.is_running:
            return

        photos_folder = self.folder_var.get().strip()
        if not photos_folder:
            messagebox.showerror("Ошибка", "Укажи папку с фотографиями: вставь путь или выбери через «Выбрать…»!")
            return
        if not os.path.isdir(photos_folder):
            messagebox.showerror("Ошибка", f"Папка не существует:\n{photos_folder}")
            return

        reference_photo = self.reference_var.get().strip()
        if not reference_photo:
            messagebox.showerror("Ошибка", "Укажи опорное фото: вставь путь или выбери через «Выбрать фото»!")
            return
        if not os.path.isfile(reference_photo):
            messagebox.showerror("Ошибка", f"Опорное фото не найдено:\n{reference_photo}")
            return

        output_folder = self.output_var.get().strip()
        if output_folder and not os.path.isdir(output_folder):
            try:
                os.makedirs(output_folder, exist_ok=True)
            except Exception:
                messagebox.showerror("Ошибка", f"Не удалось создать папку для результатов:\n{output_folder}")
                return

        save_config(photos_folder, reference_photo, output_folder)

        self.search_core = __import__("search_core")
        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.status_var.set("Загрузка опорного фото...")
        self._hide_results()

        tolerance = self.tolerance_var.get()

        def worker():
            try:
                result = self.search_core.find_photos(
                    photos_folder,
                    reference_photo,
                    tolerance=tolerance,
                    output_dir=output_folder or None,
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
                "folder_not_found": "Папка с фотографиями не найдена!",
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

        self._show_results(result["output_folder"])

        if sys.platform == "win32":
            open_folder(result["output_folder"])


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
