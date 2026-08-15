#!/usr/bin/env python3
import importlib.util
import sys
import types
from pathlib import Path


try:
    import torch
except ModuleNotFoundError:
    torch = None
    fake_torch = types.ModuleType("torch")
    fake_nn = types.ModuleType("torch.nn")
    fake_functional = types.ModuleType("torch.nn.functional")
    fake_nn.functional = fake_functional
    fake_torch.nn = fake_nn
    sys.modules["torch"] = fake_torch
    sys.modules["torch.nn"] = fake_nn
    sys.modules["torch.nn.functional"] = fake_functional


path = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("h3_complete", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

assert module.h3_internal_size(100, 1000, 0.4)[:2] == (128, 1280)
assert module.h3_internal_size(600, 1200, 0.4)[:2] == (448, 896)
assert module.h3_internal_size(369, 387, 0.4)[:2] == (672, 704)
assert module.exact_h264_pixel_format(369, 387) == "yuv444p"
assert module.exact_h264_pixel_format(600, 1200) == "yuv420p"

if torch is not None:
    reference = torch.zeros((1, 387, 369, 3), dtype=torch.float32)
    frames = torch.zeros((2, 480, 448, 3), dtype=torch.float32)
    output = module.H3ResizeOutputToReference().resize(frames, reference)[0]
    assert tuple(output.shape) == (2, 387, 369, 3)

guarded = module.H3PromptIdentityGuard().enhance("A woman walks.", "identity+body")[0]
assert "facial identity" in guarded
assert "body proportions" in guarded

print("exact node tests: PASS")
