#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${H3_ROOT:-/workspace/H3}"
PORT="${H3_PORT:-8188}"
JPORT="${JUPYTER_PORT:-8888}"
APP="/opt/h3/ComfyUI"
LOG_DIR="$ROOT/logs"

mkdir -p "$ROOT" "$LOG_DIR"

if command -v jupyter >/dev/null 2>&1; then
  nohup jupyter lab \
    --ip=0.0.0.0 \
    --port="$JPORT" \
    --no-browser \
    --allow-root \
    --ServerApp.token="${JUPYTER_TOKEN:-}" \
    --ServerApp.password='' \
    --notebook-dir=/workspace \
    >"$LOG_DIR/jupyter.log" 2>&1 &
fi

/opt/h3/bin/bootstrap.sh

PROFILE_JSON="$(python /opt/h3/bin/gpu_profile.py)"
printf '%s\n' "$PROFILE_JSON" | tee "$ROOT/gpu-profile.json"

VRAM_CLASS="$(printf '%s' "$PROFILE_JSON" | jq -r '.vram_class')"
EXTRA_ARGS=()
if [ "$VRAM_CLASS" = "large" ]; then
  EXTRA_ARGS+=(--highvram)
fi

cd "$APP"
exec python main.py \
  --listen 0.0.0.0 \
  --port "$PORT" \
  --disable-auto-launch \
  --enable-manager \
  --extra-model-paths-config "$ROOT/extra_model_paths.yaml" \
  --output-directory "$ROOT/output" \
  --temp-directory "$ROOT/temp" \
  --input-directory "$ROOT/input" \
  --preview-method auto \
  "${EXTRA_ARGS[@]}"

