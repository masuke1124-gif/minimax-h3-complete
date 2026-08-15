#!/usr/bin/env python3
import re
import sys
from pathlib import Path


def patch(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(?P<indent>^[ \t]*)layer_conf = json\.loads\(layer_conf\.numpy\(\)\.tobytes\(\)\)$",
        re.MULTILINE,
    )

    matches = list(pattern.finditer(source))
    if not matches:
        if "layer_conf_bytes.strip(b\"\\x00\")" in source:
            print("Comfy quant compatibility patch: already applied")
            return
        raise RuntimeError("ComfyUI quant loader changed; refusing an unverified patch")

    if len(matches) != 2:
        raise RuntimeError(
            f"Expected 2 ComfyUI quant decode sites, found {len(matches)}"
        )

    def replacement(match: re.Match) -> str:
        indent = match.group("indent")
        return (
            f"{indent}layer_conf_bytes = layer_conf.numpy().tobytes()\n"
            f"{indent}layer_conf = (\n"
            f"{indent}    json.loads(layer_conf_bytes)\n"
            f"{indent}    if layer_conf_bytes.strip(b\"\\x00\")\n"
            f"{indent}    else None\n"
            f"{indent})"
        )

    patched = pattern.sub(replacement, source)
    path.write_text(patched, encoding="utf-8")

    check = path.read_text(encoding="utf-8")
    if check.count("layer_conf_bytes.strip(b\"\\x00\")") != 2:
        raise RuntimeError("Comfy quant compatibility patch verification failed")
    print("Comfy quant compatibility patch: PASS")


if __name__ == "__main__":
    patch(Path(sys.argv[1]))

