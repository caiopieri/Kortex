#!/usr/bin/env bash
# Constrói a imagem do sandbox e escreve a config que a fixa por digest.
#
# O digest muda a cada rebuild, e é isso que se quer: a config aponta para a
# imagem EXATA que produziu a evidência. Rebuild sem regravar a config faria o
# motor recusar arrancar -- que é o comportamento certo, e não um incômodo.
#
#   ./sandbox/construir.sh            # grava exemplos/sandbox-kortex.json
#   ./sandbox/construir.sh --verificar # e roda a suíte causal contra ela
set -euo pipefail

raiz="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# O nome PRECISA ter uma barra: o adapter exige referência OCI completa, e
# `kortex-sandbox@sha256:...` sem repositório não é uma.
tag="localhost/kortex/sandbox:local"
config="$raiz/exemplos/sandbox-kortex.json"

docker build -t "$tag" "$raiz/sandbox"

referencia="$(docker image inspect --format '{{index .RepoDigests 0}}' "$tag")"
if [[ "$referencia" != *"@sha256:"* ]]; then
  echo "erro: imagem sem digest utilizável — o motor recusaria esta imagem" >&2
  exit 1
fi

cat > "$config" <<JSON
{
  "image_digest": "$referencia",
  "executaveis": ["/usr/local/bin/python3"]
}
JSON

echo "imagem:  $referencia"
echo "config:  $config"

if [[ "${1:-}" == "--verificar" ]]; then
  # Pré-requisito ausente FALHA, não pula: uma imagem que perdeu o isolamento
  # ou perdeu uma dependência não pode passar em silêncio.
  KORTEX_SANDBOX_IMAGE="$referencia" python3 -m pytest \
    "$raiz/tests/test_sandbox_causal.py" -q
fi
