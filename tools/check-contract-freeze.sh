#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PROTO="$ROOT_DIR/proto/contract/v1/contract.proto"
EXPECTED_FILE="$ROOT_DIR/proto/contract/v1/contract.sha256"

if command -v sha256sum >/dev/null 2>&1; then
  ACTUAL=$(sha256sum "$PROTO" | awk '{print $1}')
else
  ACTUAL=$(shasum -a 256 "$PROTO" | awk '{print $1}')
fi
EXPECTED=$(awk '{print $1}' "$EXPECTED_FILE")

if [ "$ACTUAL" != "$EXPECTED" ]; then
  echo "Contrato alterado: checksum esperado $EXPECTED, recebido $ACTUAL" >&2
  echo "Mudanças exigem decisão explícita de versão e regeneração dos stubs." >&2
  exit 1
fi

echo "Contrato 1.0.0 congelado e íntegro: $ACTUAL"
