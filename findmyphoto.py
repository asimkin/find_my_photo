#!/usr/bin/env python3
"""
🔍 Интерактивный поиск фотографий с face recognition
Все параметры спрашиваются через UI диалоги
"""

import os
import sys
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import threading

# === УСТАНОВКА ЗАВИСИМОСТЕЙ ===
def check_and_install_dependencies():
    """Проверяет и устанавливает нужные пакеты"""
    required_packages = {
        'face_recognition': 'face-recognition',
        'PIL': 'pillow',
        'cv2': 'opencv-python',
        'tqdm': 'tqdm',
        'numpy': 'numpy'
    }
    
    missing = []
    for import_name, pip_name in required_packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)
    
    if missing:
        print(f"Installing missing packages: {', '.join(missing)}")
        for package in missing:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package, '-q'])
        print("Packages installed!")
    else:
        print("All dependencies installed")

# Проверяем зависимости в самом начале
try:
    check_and_install_dependencies()
except Exception as e:
    print(f"Error installing dependencies: {e}")
    print("Try running manually:")
    print("pip install face-recognition pillow opencv-python tqdm numpy")
    input("Press Enter after installation...")

# Теперь импортируем всё остальное
import face_recognition
from PIL import Image
import numpy as np
from tqdm import tqdm
import shutil

class PhotoFinderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Поиск моих фотографий")
        self.root.geometry("600x400")
        self.root.resizable(False, False)
        
        self.photos_folder = None
        self.reference_photo = None
        self.tolerance = 0.6
        
        self.create_ui()
    
    def create_ui(self):
        """Создает интерфейс"""
        import tkinter.font as tkFont
        
        title_font = tkFont.Font(family="Arial", size=14, weight="bold")
        normal_font = tkFont.Font(family="Arial", size=10)
        
        # Заголовок
        title = tk.Label(self.root, text="Поиск фотографий", font=title_font)
        title.pack(pady=20)
        
        # Фрейм для информации
        info_frame = tk.Frame(self.root)
        info_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        # Папка с фото
        tk.Label(info_frame, text="Папка с фотографиями:", font=normal_font, anchor="w").pack(fill=tk.X, pady=(10, 5))
        self.folder_label = tk.Label(info_frame, text="не выбрана", fg="gray", font=normal_font)
        self.folder_label.pack(fill=tk.X, padx=20)
        tk.Button(info_frame, text="Выбрать папку", command=self.select_photos_folder).pack(pady=5)
        
        # Опорное фото
        tk.Label(info_frame, text="Опорное фото (на котором ты есть):", font=normal_font, anchor="w").pack(fill=tk.X, pady=(15, 5))
        self.ref_label = tk.Label(info_frame, text="не выбрано", fg="gray", font=normal_font)
        self.ref_label.pack(fill=tk.X, padx=20)
        tk.Button(info_frame, text="Выбрать фото", command=self.select_reference_photo).pack(pady=5)
        
        # Чувствительность
        tk.Label(info_frame, text="Чувствительность (меньше = строже):", font=normal_font, anchor="w").pack(fill=tk.X, pady=(15, 5))
        self.tolerance_var = tk.DoubleVar(value=0.6)
        tolerance_frame = tk.Frame(info_frame)
        tolerance_frame.pack(fill=tk.X, padx=20)
        tk.Scale(tolerance_frame, from_=0.3, to=1.0, resolution=0.05, 
                orient=tk.HORIZONTAL, variable=self.tolerance_var, 
                font=normal_font).pack(fill=tk.X)
        
        # Кнопки управления
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=20)
        tk.Button(button_frame, text="НАЧАТЬ ПОИСК", command=self.start_search, 
                 bg="#4CAF50", fg="white", font=tkFont.Font(size=11, weight="bold"), 
                 padx=20, pady=10).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="Выход", command=self.root.quit, 
                 padx=20, pady=10).pack(side=tk.LEFT, padx=10)
    
    def select_photos_folder(self):
        folder = filedialog.askdirectory(title="Выбери папку с 1000 фотографиями")
        if folder:
            self.photos_folder = folder
            self.folder_label.config(text=folder, fg="black")
    
    def select_reference_photo(self):
        file = filedialog.askopenfilename(
            title="Выбери опорное фото",
            filetypes=[("Изображения", "*.jpg *.jpeg *.png"), ("Все файлы", "*.*")]
        )
        if file:
            self.reference_photo = file
            self.ref_label.config(text=Path(file).name, fg="black")
    
    def start_search(self):
        """Запускает поиск в отдельном потоке"""
        if not self.photos_folder:
            messagebox.showerror("Ошибка", "Выбери папку с фотографиями!")
            return
        
        if not self.reference_photo:
            messagebox.showerror("Ошибка", "Выбери опорное фото!")
            return
        
        # Запускаем в отдельном потоке, чтобы UI не зависал
        thread = threading.Thread(target=self.run_search)
        thread.start()
    
    def run_search(self):
        """Основной поиск"""
        try:
            self.root.after(0, lambda: messagebox.showinfo("Статус", "Поиск начался...\n(это может занять несколько минут)"))

            tolerance = self.tolerance_var.get()
            output_folder = os.path.join(self.photos_folder, "find_results")
            os.makedirs(output_folder, exist_ok=True)

            # === ЗАГРУЗКА ОПОРНОГО ФОТО ===
            print("\nЗагружаю опорное фото...")
            ref_image = face_recognition.load_image_file(self.reference_photo)
            ref_encodings = face_recognition.face_encodings(ref_image, num_jitters=10, model="small")

            if not ref_encodings:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", "На опорном фото не найдено лица!\nПроверь, чтобы ты был хорошо виден."))
                return

            target_encoding = ref_encodings[0]
            print(f"Опорное фото загружено. Найдено {len(ref_encodings)} лиц(о).")

            # === СБОР ФОТОГРАФИЙ ===
            photo_files = list(Path(self.photos_folder).glob("**/*.*"))
            photo_files = [f for f in photo_files if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']]
            print(f"Найдено {len(photo_files)} фотографий\n")

            matches = []
            MAX_SIDE = 600

            print("Ищу совпадения...\n")
            for photo_path in tqdm(photo_files, desc="Сканирование"):
                try:
                    pil = Image.open(photo_path)
                    pil.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
                    current_image = np.array(pil)
                    del pil

                    current_encodings = face_recognition.face_encodings(current_image, num_jitters=0, model="small")

                    if not current_encodings:
                        continue

                    for i, encoding in enumerate(current_encodings):
                        distance = face_recognition.face_distance([target_encoding], encoding)[0]

                        if distance < tolerance:
                            matches.append({
                                'path': photo_path,
                                'distance': distance,
                                'faces_count': len(current_encodings),
                                'face_index': i
                            })
                            break

                except Exception as e:
                    pass
                try:
                    del current_image
                except Exception:
                    pass
            
            # === СОРТИРОВКА ===
            matches.sort(key=lambda x: x['distance'])
            
            print(f"\n✅ Найдено совпадений: {len(matches)}")
            if matches:
                print(f"Лучший результат: distance = {matches[0]['distance']:.4f}")
            
            # === СОХРАНЕНИЕ РЕЗУЛЬТАТОВ ===
            with open(os.path.join(output_folder, "results.txt"), "w", encoding='utf-8') as f:
                f.write("🔍 РЕЗУЛЬТАТЫ ПОИСКА\n")
                f.write("=" * 80 + "\n\n")
                f.write(f"Всего найдено совпадений: {len(matches)}\n")
                f.write(f"Параметр чувствительности (tolerance): {tolerance}\n")
                f.write("(чем меньше distance, тем точнее совпадение)\n")
                f.write("=" * 80 + "\n\n")
                
                for idx, match in enumerate(matches[:100]):
                    f.write(f"{idx+1}. {match['path'].name}\n")
                    confidence = (1 - match['distance']) * 100
                    f.write(f"   Уверенность: {confidence:.1f}%\n")
                    f.write(f"   Distance: {match['distance']:.4f}\n")
                    f.write(f"   Путь: {match['path']}\n")
                    f.write(f"   Лиц на фото: {match['faces_count']}\n\n")
            
            # === КОПИРОВАНИЕ ТОП ФОТО ===
            if len(matches) > 0:
                top_folder = os.path.join(output_folder, "top_matches")
                os.makedirs(top_folder, exist_ok=True)
                
                for i, match in enumerate(matches[:100]):
                    try:
                        shutil.copy(match['path'], os.path.join(top_folder, f"{i+1:03d}_{match['path'].name}"))
                    except:
                        pass
                
                print(f"📁 Скопировано {min(100, len(matches))} фото в папку")
            
            # === ПОКАЗЫВАЕМ РЕЗУЛЬТАТ ===
            if matches:
                best_distance = matches[0]['distance']
                best_confidence = (1 - best_distance) * 100
            else:
                best_distance = 0
                best_confidence = 0
            
            result_msg = f"""ПОИСК ЗАВЕРШЕН!

Статистика:
  - Найдено совпадений: {len(matches)}
  - Лучший результат: {best_distance:.4f}
  - Уверенность лучшего: {best_confidence:.1f}%

Результаты сохранены:
  {output_folder}

Подробный лог: results.txt
Топ фото: top_matches/
"""
            self.root.after(0, lambda: messagebox.showinfo("Успех!", result_msg))
            self.root.after(0, lambda: os.startfile(output_folder) if sys.platform == 'win32' else None)
            
        except Exception as e:
            error_msg = f"Ошибка: {str(e)}"
            print(error_msg)
            self.root.after(0, lambda: messagebox.showerror("Ошибка", error_msg))

if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoFinderApp(root)
    root.mainloop()