#!/usr/bin/env python3
import importlib.util
import sys
import tempfile
from pathlib import Path


root = Path(__file__).resolve().parents[1]
patcher_path = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else root / "scripts" / "patch_comfy_quant.py"
)
spec = importlib.util.spec_from_file_location("patch_comfy_quant", patcher_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

fixture = '''
def first(layer_conf):
    if layer_conf is not None:
        layer_conf = json.loads(layer_conf.numpy().tobytes())

def second(layer_conf):
    if layer_conf is not None:
        layer_conf = json.loads(layer_conf.numpy().tobytes())
'''.lstrip()

with tempfile.TemporaryDirectory() as directory:
    target = Path(directory) / "ops.py"
    target.write_text(fixture, encoding="utf-8")
    module.patch(target)
    patched = target.read_text(encoding="utf-8")
    assert patched.count('layer_conf_bytes.strip(b"\\x00")') == 2
    compile(patched, str(target), "exec")
    module.patch(target)

print("comfy quant patch tests: PASS")
