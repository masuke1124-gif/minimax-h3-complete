#!/usr/bin/env python3
import json
import torch


def main():
    if not torch.cuda.is_available():
        raise SystemExit("CUDA GPUが認識されていません。")

    props = torch.cuda.get_device_properties(0)
    name = torch.cuda.get_device_name(0)
    major, minor = torch.cuda.get_device_capability(0)
    vram = props.total_memory / 1024**3

    if major < 8:
        raise SystemExit(
            f"非対応GPUです: {name} / Compute Capability {major}.{minor}。8.0以上が必要です。"
        )
    if vram < 44:
        raise SystemExit(
            f"VRAM不足です: {name} / {vram:.1f}GiB。安定運用には48GB級以上が必要です。"
        )

    result = {
        "gpu": name,
        "vram_gib": round(vram, 1),
        "compute_capability": f"{major}.{minor}",
        "vram_class": "large" if vram >= 75 else "standard",
        "model_profile": "universal-int8",
        "sage_attention": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

