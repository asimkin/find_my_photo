#!/bin/bash
# Полная настройка проекта: системные пакеты (Ubuntu/Debian), виртуальное окружение, зависимости.
# Выполняется один раз (или автоматически при первом запуске run_gui.sh/run_cli.sh).
set -e
cd "$(dirname "$0")"

PYTHON=${PYTHON:-python3}

echo "==> Настройка $(basename "$PWD")"

# 1. Системные пакеты для Ubuntu/Debian:
#    - python3-venv  — без него `python3 -m venv` падает («ensurepip is not available»)
#    - python3-tk    — модуль tkinter для GUI (через pip на Linux не ставится)
#    - git           — для клонирования проекта
need_sudo=""
if ! grep -qEi "debian|ubuntu" /etc/os-release 2>/dev/null; then
    echo "[1/3] Не Ubuntu/Debian — системные пакеты поставь вручную: python3-venv, python3-tk (если нужен GUI)"
elif ! "$PYTHON" -c "import ensurepip" >/dev/null 2>&1; then
    echo "[1/3] python3-venv не найден"
    need_sudo="$need_sudo python3-venv"
fi
if ! "$PYTHON" -c "import tkinter" >/dev/null 2>&1; then
    echo "[1/3] tkinter не найден"
    need_sudo="$need_sudo python3-tk"
fi
if ! command -v git >/dev/null 2>&1; then
    echo "[1/3] git не найден"
    need_sudo="$need_sudo git"
fi
if [ -n "$need_sudo" ]; then
    echo "[1/3] Устанавливаю системные пакеты (потребуется пароль sudo):$need_sudo"
    if ! sudo apt-get update && sudo apt-get install -y $need_sudo; then
        echo
        echo "Не удалось установить системные пакеты автоматически."
        echo "Выполни вручную: sudo apt-get install$need_sudo"
        exit 1
    fi
else
    echo "[1/3] Системные пакеты уже установлены"
fi

# 2. Виртуальное окружение
if [ ! -x .venv/bin/python ]; then
    echo "[2/3] Создаю виртуальное окружение..."
    "$PYTHON" -m venv .venv
else
    echo "[2/3] Виртуальное окружение уже есть"
fi

# 3. Зависимости (--no-deps: все нужные пакеты перечислены в requirements.txt,
#    чтобы face-recognition не тянул старую версию моделей)
echo "[3/3] Устанавливаю зависимости..."
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet --no-deps -r requirements.txt

echo
echo "Готово! Запуск:"
echo "  GUI: ./run_gui.sh"
echo "  CLI: ./run_cli.sh"
