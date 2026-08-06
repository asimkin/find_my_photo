#!/bin/sh
# Запуск консольной версии (при первом запуске сам выполнит setup.sh)
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ] || ! .venv/bin/python -c "import face_recognition" >/dev/null 2>&1; then
    echo "==> Первый запуск: настраиваю окружение..."
    ./setup.sh || exit 1
fi
exec .venv/bin/python search_cli.py "$@"
