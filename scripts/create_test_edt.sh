#!/usr/bin/env sh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

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

# По умолчанию скрипт запускается из tests и пересоздает tests/unit.
OUTPUT_PROJECT="${OUTPUT_PROJECT:-$SCRIPT_DIR/unit/base}"
BASE_PROJECT="${BASE_PROJECT:-$ROOT_DIR/adapter/base}"
ADAPTER_PROJECT="${ADAPTER_PROJECT:-$ROOT_DIR/adapter/adapter}"
EXAMPLES_PROJECT="${EXAMPLES_PROJECT:-$ROOT_DIR/adapter/examples}"

# YAXUNIT не входит в workspace, поэтому берем только EDT-проект exts/yaxunit
# из внешнего репозитория через sparse checkout.
YAXUNIT_REPO="${YAXUNIT_REPO:-https://github.com/bia-technologies/yaxunit.git}"
YAXUNIT_REF="${YAXUNIT_REF:-develop}"
YAXUNIT_CACHE="${YAXUNIT_CACHE:-$SCRIPT_DIR/.cache/yaxunit}"
YAXUNIT_PROJECT="${YAXUNIT_PROJECT:-$YAXUNIT_CACHE/exts/yaxunit}"

ensure_yaxunit_project() {
  # Если путь явно передали и там уже EDT-проект, сеть не нужна.
  if [ -f "$YAXUNIT_PROJECT/.project" ] && [ -d "$YAXUNIT_PROJECT/src" ]; then
    return
  fi

  if [ "$YAXUNIT_PROJECT" != "$YAXUNIT_CACHE/exts/yaxunit" ]; then
    echo "ERROR: YAXUNIT_PROJECT is not an EDT project: $YAXUNIT_PROJECT" >&2
    exit 1
  fi

  # Cache можно переиспользовать между запусками; при повторном запуске
  # обновляем его до заданной ветки/ссылки.
  mkdir -p "$(dirname "$YAXUNIT_CACHE")"
  if [ ! -d "$YAXUNIT_CACHE/.git" ]; then
    if [ -z "$YAXUNIT_CACHE" ] || [ "$YAXUNIT_CACHE" = "/" ]; then
      echo "ERROR: unsafe YAXUNIT_CACHE: $YAXUNIT_CACHE" >&2
      exit 1
    fi
    rm -rf "$YAXUNIT_CACHE"
    git clone --depth 1 --branch "$YAXUNIT_REF" --filter=blob:none --sparse "$YAXUNIT_REPO" "$YAXUNIT_CACHE"
  else
    git -C "$YAXUNIT_CACHE" fetch --depth 1 origin "$YAXUNIT_REF"
    git -C "$YAXUNIT_CACHE" checkout --detach FETCH_HEAD
  fi

  git -C "$YAXUNIT_CACHE" sparse-checkout set exts/yaxunit
}

ensure_yaxunit_project

# Основная логика merge живет в Python-скрипте.
"$PYTHON" "$ROOT_DIR/tests/create_test_edt.py" \
  --output "$OUTPUT_PROJECT" \
  --base "$BASE_PROJECT" \
  --adapter "$ADAPTER_PROJECT" \
  --examples "$EXAMPLES_PROJECT" \
  --yaxunit "$YAXUNIT_PROJECT"
