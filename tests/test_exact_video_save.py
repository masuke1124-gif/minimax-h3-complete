#!/usr/bin/env python3
import importlib.util
import os
import sys
import tempfile
import types
from pathlib import Path


try:
    import av
    import torch
except ModuleNotFoundError:
    if os.environ.get("H3_REQUIRE_MEDIA_TESTS") == "1":
        raise
    print("exact video save tests: SKIP (torch/av unavailable locally)")
    raise SystemExit(0)


node_path = Path(sys.argv[1])
with tempfile.TemporaryDirectory() as directory:
    output_dir = Path(directory)
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_output_directory = lambda: str(output_dir)
    folder_paths.get_save_image_path = (
        lambda prefix, root, width, height: (str(output_dir), "h3_exact", 1, "", prefix)
    )
    sys.modules["folder_paths"] = folder_paths

    spec = importlib.util.spec_from_file_location("h3_complete_media", node_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    components = types.SimpleNamespace(
        images=torch.zeros((2, 387, 369, 3), dtype=torch.float32),
        audio={
            "sample_rate": 48000,
            "waveform": torch.zeros((1, 2, 48000), dtype=torch.float32),
        },
        frame_rate=2,
    )

    class FakeVideo:
        def get_components(self):
            return components

    result = module.H3SaveVideoExact().save(
        FakeVideo(), "video/test", 18, prompt={"test": True}
    )
    path = output_dir / "h3_exact_00001_.mp4"
    assert path.is_file()
    assert result["ui"]["gifs"][0]["filename"] == path.name

    with av.open(str(path)) as container:
        video_stream = container.streams.video[0]
        assert (video_stream.width, video_stream.height) == (369, 387)
        assert video_stream.pix_fmt == "yuv444p"
        assert len(container.streams.audio) == 1
        assert container.streams.audio[0].layout.name == "stereo"

print("exact video save tests: PASS")

