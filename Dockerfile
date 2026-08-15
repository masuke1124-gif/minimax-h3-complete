FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404

ARG COMFYUI_COMMIT=0f1fa67ad8a68b62c65ebc97a7bf485df2459c3a
ARG TURBO_COMMIT=4274783a23afcfdbea3b4876cb79effd6c510785

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    CUDA_MODULE_LOADING=LAZY \
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    H3_ROOT=/workspace/H3 \
    H3_PORT=8188 \
    JUPYTER_PORT=8888

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl ffmpeg git git-lfs jq tini \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install

RUN mkdir -p /opt/h3 \
    && git clone https://github.com/Comfy-Org/ComfyUI.git /opt/h3/ComfyUI \
    && git -C /opt/h3/ComfyUI checkout "${COMFYUI_COMMIT}" \
    && python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r /opt/h3/ComfyUI/requirements.txt jupyterlab

RUN git clone https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo.git \
      /opt/h3/ComfyUI/custom_nodes/ComfyUI-MiniMax-H3-Turbo \
    && git -C /opt/h3/ComfyUI/custom_nodes/ComfyUI-MiniMax-H3-Turbo checkout "${TURBO_COMMIT}"

COPY custom_nodes/H3-Complete /opt/h3/ComfyUI/custom_nodes/H3-Complete
COPY workflows /opt/h3/workflows
COPY scripts /opt/h3/bin
COPY tests /opt/h3/tests
COPY Dockerfile /opt/h3/Dockerfile

RUN chmod 755 /opt/h3/bin/*.sh \
    && python -m py_compile /opt/h3/ComfyUI/custom_nodes/H3-Complete/__init__.py \
    && python /opt/h3/tests/validate_bundle.py /opt/h3 \
    && python /opt/h3/tests/test_exact_nodes.py \
         /opt/h3/ComfyUI/custom_nodes/H3-Complete/__init__.py

EXPOSE 8188 8888

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/opt/h3/bin/start.sh"]
