#!/usr/bin/env bash
# Prepara un clon nuevo del repo (entorno cloud o maquina limpia).
#   bash scripts/setup.sh
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
fail=0
note() { printf '  %-12s %s\n' "$1" "$2"; }

echo ""
echo "Setup de Claude-Image-Generation"
echo "--------------------------------"

# 1. Node >= 20 (el CLI usa fetch nativo y node:util/parseArgs).
if command -v node >/dev/null 2>&1; then
  major=$(node -p 'process.versions.node.split(".")[0]')
  if [ "$major" -ge 20 ]; then
    note "Node" "$(node --version) OK"
  else
    note "Node" "$(node --version) DEMASIADO ANTIGUO, se necesita >= 20"
    fail=1
  fi
else
  note "Node" "NO ENCONTRADO, se necesita >= 20"
  fail=1
fi

# 2. Hook de pre-commit: core.hooksPath no viaja en el clon, hay que activarlo.
if git rev-parse --git-dir >/dev/null 2>&1; then
  git config core.hooksPath .githooks
  chmod +x .githooks/* 2>/dev/null
  note "Hooks" "core.hooksPath = .githooks (bloquea imagenes con metadatos)"
else
  note "Hooks" "no es un repo git, omitido"
fi

# 3. La API key. En cloud va como variable de entorno, no como archivo .env.
if [ -n "${APIMART_API_KEY:-}" ]; then
  note "API key" "presente en el entorno (${#APIMART_API_KEY} chars)"
elif [ -f .env ] && grep -q '^APIMART_API_KEY=sk-' .env; then
  note "API key" "presente en .env"
else
  note "API key" "FALTA -> exporta APIMART_API_KEY (ver docs/cloud.md)"
  fail=1
fi

# 4. Python es opcional: solo para los scripts de stickers / mockups / PDF.
if command -v python3 >/dev/null 2>&1; then
  if python3 -c 'import PIL, numpy' >/dev/null 2>&1; then
    note "Python" "$(python3 --version 2>&1 | cut -d' ' -f2) con dependencias OK"
  else
    note "Python" "$(python3 --version 2>&1 | cut -d' ' -f2), faltan libs -> pip install -r requirements.txt"
  fi
else
  note "Python" "ausente (opcional: solo scripts de stickers/impresion)"
fi

echo ""
if [ "$fail" -ne 0 ]; then
  echo "Faltan cosas. Revisa los puntos marcados arriba."
  exit 1
fi

echo "Listo. Verifica la conexion con la API:"
echo "  npm run check"
echo ""
