#!/usr/bin/env bash

set -euo pipefail

TRIBUNAL_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TRIBUNAL_PYTHON="${TRIBUNAL_PYTHON:-python3}"
TRIBUNAL_VENV="$TRIBUNAL_DIR/.venv"
TRIBUNAL_REQUIREMENTS_STAMP="$TRIBUNAL_VENV/.requirements-installed"

cd "$TRIBUNAL_DIR"

if ! command -v "$TRIBUNAL_PYTHON" >/dev/null 2>&1; then
    echo "Erro: Python 3 não encontrado. Instale o Python 3 e tente novamente."
    exit 1
fi

if [[ ! -x "$TRIBUNAL_VENV/bin/python" ]]; then
    echo "Criando ambiente virtual..."
    "$TRIBUNAL_PYTHON" -m venv "$TRIBUNAL_VENV"
fi

if [[ ! -f "$TRIBUNAL_REQUIREMENTS_STAMP" ]] || ! cmp -s requirements.txt "$TRIBUNAL_REQUIREMENTS_STAMP"; then
    echo "Instalando dependências..."
    "$TRIBUNAL_VENV/bin/python" -m pip install --upgrade pip
    "$TRIBUNAL_VENV/bin/python" -m pip install -r requirements.txt
    cp requirements.txt "$TRIBUNAL_REQUIREMENTS_STAMP"
fi

echo "Iniciando Tribunal 2.0 em http://localhost:8501"
exec "$TRIBUNAL_VENV/bin/python" -m streamlit run app.py "$@"
