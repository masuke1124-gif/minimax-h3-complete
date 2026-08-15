#!/usr/bin/env python3
import importlib.util
from pathlib import Path


root = Path(__file__).resolve().parents[1]
path = root / "scripts" / "gpu_profile.py"
spec = importlib.util.spec_from_file_location("gpu_profile", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

cheap = module.classify_gpu("A40", 44.7, 8, 6)
assert cheap["vram_class"] == "standard"
assert cheap["model_profile"] == "universal-int8"
assert cheap["sage_attention"] is False

fast = module.classify_gpu("H100", 79.2, 9, 0)
assert fast["vram_class"] == "large"

blackwell = module.classify_gpu("RTX PRO 6000 Blackwell", 95.0, 12, 0)
assert blackwell["vram_class"] == "large"

for args in (("RTX 4090", 24.0, 8, 9), ("V100", 32.0, 7, 0)):
    try:
        module.classify_gpu(*args)
    except SystemExit:
        pass
    else:
        raise AssertionError(f"unsupported GPU was accepted: {args}")

print("GPU profile tests: PASS")

