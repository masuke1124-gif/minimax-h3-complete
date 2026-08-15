#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def one(nodes, node_type):
    found = [node for node in nodes if node.get("type") == node_type]
    assert len(found) == 1, (node_type, len(found))
    return found[0]


def main(root):
    root = Path(root)
    workflows = sorted((root / "workflows").glob("*.json"))
    assert len(workflows) == 2

    for path in workflows:
        data = json.loads(path.read_text(encoding="utf-8"))
        top = data["nodes"]
        auto = one(top, "H3AutoInternalSize")
        saver = one(top, "H3SaveVideoExact")
        generator = one(top, "4c314f31-ecda-4b08-ae98-faaba1bf613f")
        assert auto["widgets_values"] == [0.4]
        assert saver["widgets_values"] == ["video/MiniMax_H3", 18]
        assert generator["widgets_values"][3] == 15
        assert generator["widgets_values"][5:] == [
            "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
            "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
            "minimax_h3_video_vae_fp16.safetensors",
            "minimax_h3_audio_vae_fp32.safetensors",
        ]

        subgraph = data["definitions"]["subgraphs"][0]
        nodes = subgraph["nodes"]
        one(nodes, "H3ResizeOutputToReference")
        scheduler = one(nodes, "BasicScheduler")
        assert scheduler["widgets_values"][0] == "simple"
        assert scheduler["widgets_values"][1] in (8, 20)
        assert not any("SageAttention" in str(node.get("type")) for node in nodes)

        if scheduler["widgets_values"][1] == 8:
            one(nodes, "MiniMaxH3TurboLoRA")
            one(nodes, "MiniMaxH3TurboSampler")

    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "0f1fa67ad8a68b62c65ebc97a7bf485df2459c3a" in dockerfile
    assert "4274783a23afcfdbea3b4876cb79effd6c510785" in dockerfile
    assert "SageAttention" not in dockerfile
    assert "patch_comfy_quant.py" in dockerfile
    patcher = (root / "scripts" / "patch_comfy_quant.py").read_text(encoding="utf-8")
    assert "layer_conf_bytes.strip" in patcher
    assert "\\x00" in patcher
    print("bundle static validation: PASS")


if __name__ == "__main__":
    main(sys.argv[1])
