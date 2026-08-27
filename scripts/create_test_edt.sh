#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

# При запуске двойным кликом окно Git Bash закрывается сразу после выхода.
# Пауза включена по умолчанию; для запуска из терминала можно задать PAUSE_ON_EXIT=0.
pause_on_exit() {
  status=$?
  echo
  if [ "$status" -eq 0 ]; then
    echo "Готово."
  else
    echo "Ошибка. Код завершения: $status"
  fi

  if [ "${PAUSE_ON_EXIT:-1}" != "0" ]; then
    printf "Нажмите Enter для закрытия окна..."
    read -r _ || true
  fi

  exit "$status"
}

trap pause_on_exit EXIT

# В Windows/Git Bash удобнее py, в Linux обычно доступен python3.
if [ -z "${PYTHON:-}" ]; then
  if command -v py >/dev/null 2>&1; then
    PYTHON="py"
  else
    PYTHON="python3"
  fi
fi

# По умолчанию скрипт запускается из tests/unit/unit/scripts и пересоздает tests/unit/base.
OUTPUT_PROJECT="${OUTPUT_PROJECT:-$SCRIPT_DIR/../../base}"
BASE_PROJECT="${BASE_PROJECT:-$WORKSPACE_ROOT/adapter/base}"
ADAPTER_PROJECT="${ADAPTER_PROJECT:-$WORKSPACE_ROOT/adapter/adapter}"

# Основная логика merge живет в Python-скрипте.
"$PYTHON" "$SCRIPT_DIR/create_test_edt.py" \
  --output "$OUTPUT_PROJECT" \
  --base "$BASE_PROJECT" \
  --adapter "$ADAPTER_PROJECT"
