#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${H3_ROOT:-/workspace/H3}"
APP="/opt/h3/ComfyUI"
MODEL_ROOT="$ROOT/models"
WORKFLOW_ROOT="$ROOT/workflows"

mkdir -p \
  "$MODEL_ROOT/diffusion_models" \
  "$MODEL_ROOT/text_encoders" \
  "$MODEL_ROOT/vae" \
  "$MODEL_ROOT/loras" \
  "$ROOT/output" "$ROOT/temp" "$ROOT/input" "$ROOT/logs" \
  "$WORKFLOW_ROOT" "$APP/user/default/workflows"

cat > "$ROOT/extra_model_paths.yaml" <<YAML
h3_network_volume:
    base_path: $MODEL_ROOT
    is_default: true
    diffusion_models: diffusion_models/
    text_encoders: text_encoders/
    vae: vae/
    loras: loras/
YAML

download_verified() {
  local url="$1" dest="$2" expected="$3"
  local part="${dest}.part" actual rc

  mkdir -p "$(dirname "$dest")"

  if [ -f "$dest" ]; then
    actual="$(sha256sum "$dest" | awk '{print $1}')"
    if [ "$actual" = "$expected" ]; then
      echo "✅ 取得済み: $(basename "$dest")"
      return 0
    fi
    mv "$dest" "${dest}.bad.$(date +%Y%m%d_%H%M%S)"
  fi

  echo "↓ 取得・再開: $(basename "$dest")"
  set +e
  curl --location --fail --retry 20 --retry-delay 5 --retry-all-errors \
    --connect-timeout 30 --continue-at - "$url" --output "$part"
  rc=$?
  set -e

  if [ -f "$part" ]; then
    actual="$(sha256sum "$part" | awk '{print $1}')"
    if [ "$actual" = "$expected" ]; then
      mv "$part" "$dest"
      echo "✅ SHA-256: $(basename "$dest")"
      return 0
    fi
  fi

  if [ "$rc" -eq 33 ]; then
    echo "再開位置を作り直します: $(basename "$dest")"
    rm -f "$part"
    curl --location --fail --retry 20 --retry-delay 5 --retry-all-errors \
      --connect-timeout 30 "$url" --output "$part"
    actual="$(sha256sum "$part" | awk '{print $1}')"
    [ "$actual" = "$expected" ] || {
      echo "SHA-256不一致: $(basename "$dest")" >&2
      exit 1
    }
    mv "$part" "$dest"
    echo "✅ SHA-256: $(basename "$dest")"
    return 0
  fi

  echo "ダウンロード中断。.partは残したため、次回起動で続行します。" >&2
  exit "${rc:-1}"
}

if [ "${H3_SKIP_MODEL_DOWNLOAD:-0}" != "1" ]; then
  FREE_BYTES="$(df -PB1 "$ROOT" | awk 'NR==2 {print $4}')"
  if [ "${FREE_BYTES:-0}" -lt 50000000000 ]; then
    echo "Network Volumeの空き容量が50GB未満です。" >&2
    exit 1
  fi

  BASE="https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main"
  download_verified \
    "$BASE/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors?download=true" \
    "$MODEL_ROOT/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors" \
    "e889202c41dafb67b10d67b97f0d8541508036a6090af23425a5c2615d03c47a"
  download_verified \
    "$BASE/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors?download=true" \
    "$MODEL_ROOT/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors" \
    "35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6"
  download_verified \
    "$BASE/vae/minimax_h3_video_vae_fp16.safetensors?download=true" \
    "$MODEL_ROOT/vae/minimax_h3_video_vae_fp16.safetensors" \
    "7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522"
  download_verified \
    "$BASE/vae/minimax_h3_audio_vae_fp32.safetensors?download=true" \
    "$MODEL_ROOT/vae/minimax_h3_audio_vae_fp32.safetensors" \
    "8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48"
  download_verified \
    "https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora/resolve/main/minimax_h3_turbo_v4_step600_ema.safetensors?download=true" \
    "$MODEL_ROOT/loras/minimax_h3_turbo_v4_step600_ema.safetensors" \
    "5f3a626cd72c93a8b9318d6760c510bc5092d2ab13aaba1f932c5bab07a416d3"
fi

for workflow in /opt/h3/workflows/*.json; do
  cp -f "$workflow" "$WORKFLOW_ROOT/"
  cp -f "$workflow" "$APP/user/default/workflows/"
done

python -m py_compile "$APP/custom_nodes/H3-Complete/__init__.py"
echo "✅ MiniMax H3 bundle ready"

