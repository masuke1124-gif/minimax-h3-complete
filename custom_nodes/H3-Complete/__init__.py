import json
import math
import os
from fractions import Fraction

import torch
import torch.nn.functional as F


def h3_internal_size(width: int, height: int, megapixels: float):
    if width <= 0 or height <= 0:
        raise ValueError(f"無効な入力画像サイズです: {width}x{height}")

    multiple = 32
    max_short = 768
    max_long = 1344
    target_pixels = max(0.1, float(megapixels)) * 1_000_000.0
    area_cap = max(target_pixels * 1.5, 150_000.0)
    source_ratio = width / height
    candidates = []

    for out_w in range(multiple, max_long + 1, multiple):
        for out_h in range(multiple, max_long + 1, multiple):
            if max(out_w, out_h) > max_long:
                continue
            if min(out_w, out_h) > max_short:
                continue
            if out_w * out_h > area_cap:
                continue
            if width < height and not (out_w < out_h):
                continue
            if width > height and not (out_w > out_h):
                continue
            if width == height and out_w != out_h:
                continue

            ratio_error = abs((out_w / out_h) - source_ratio) / source_ratio
            area_error = abs((out_w * out_h) - target_pixels) / target_pixels
            candidates.append((ratio_error, area_error, out_w, out_h))

    if not candidates:
        raise ValueError(f"H3内部解像度を作成できません: {width}x{height}")

    almost_exact = [candidate for candidate in candidates if candidate[0] <= 0.001]
    pool = almost_exact or candidates
    if almost_exact:
        ratio_error, _, out_w, out_h = min(
            pool, key=lambda item: (item[1], item[0], item[2] * item[3])
        )
    else:
        ratio_error, _, out_w, out_h = min(
            pool, key=lambda item: (item[0], item[1], item[2] * item[3])
        )
    return int(out_w), int(out_h), ratio_error


def exact_h264_pixel_format(width: int, height: int) -> str:
    return "yuv444p" if width % 2 or height % 2 else "yuv420p"


class H3AutoInternalSize:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "megapixels": (
                    "FLOAT",
                    {"default": 0.4, "min": 0.1, "max": 2.0, "step": 0.05},
                ),
            }
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "calculate"
    CATEGORY = "MiniMax H3"

    def calculate(self, image, megapixels):
        if image is None or getattr(image, "ndim", 0) != 4:
            raise ValueError("入力画像のサイズを取得できません。")
        height = int(image.shape[1])
        width = int(image.shape[2])
        out_w, out_h, error = h3_internal_size(width, height, megapixels)
        print(
            f"H3 Auto Internal Size: input={width}x{height} "
            f"-> internal={out_w}x{out_h} (aspect error={error * 100:.3f}%)"
        )
        return out_w, out_h


class H3ResizeOutputToReference:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"images": ("IMAGE",), "reference": ("IMAGE",)}}

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("IMAGE",)
    FUNCTION = "resize"
    CATEGORY = "MiniMax H3"

    def resize(self, images, reference):
        if images is None or getattr(images, "ndim", 0) != 4:
            raise ValueError("生成フレームの形状が不正です。")
        if reference is None or getattr(reference, "ndim", 0) != 4:
            raise ValueError("参照画像の形状が不正です。")

        target_h = int(reference.shape[1])
        target_w = int(reference.shape[2])
        if int(images.shape[1]) == target_h and int(images.shape[2]) == target_w:
            return (images,)

        tensor = images.movedim(-1, 1)
        try:
            resized = F.interpolate(
                tensor,
                size=(target_h, target_w),
                mode="bicubic",
                align_corners=False,
                antialias=True,
            )
        except RuntimeError:
            resized = F.interpolate(
                tensor,
                size=(target_h, target_w),
                mode="bilinear",
                align_corners=False,
            )
        resized = resized.movedim(1, -1).clamp(0.0, 1.0)
        if tuple(resized.shape[1:3]) != (target_h, target_w):
            raise RuntimeError("最終サイズ検査に失敗しました。")
        print(f"H3 Exact Final Size: {target_w}x{target_h}")
        return (resized,)


class H3PromptIdentityGuard:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "mode": (["identity+body", "identity", "off"],),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "enhance"
    CATEGORY = "MiniMax H3"

    def enhance(self, prompt, mode):
        if mode == "off":
            return (prompt,)
        identity = (
            " Preserve the subject's exact facial identity, hairstyle, skin tone, "
            "clothing design, and distinctive features consistently in every frame."
        )
        body = (
            " Preserve the subject's original body proportions, limb length, posture, "
            "and anatomy; no morphing, duplication, or proportion drift."
        )
        suffix = identity + (body if mode == "identity+body" else "")
        return ((prompt.rstrip() + suffix).strip(),)


class H3SaveVideoExact:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video": ("VIDEO",),
                "filename_prefix": (
                    "STRING",
                    {"default": "video/MiniMax_H3"},
                ),
                "crf": ("INT", {"default": 18, "min": 0, "max": 51, "step": 1}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ("VIDEO",)
    RETURN_NAMES = ("video",)
    FUNCTION = "save"
    CATEGORY = "MiniMax H3"
    OUTPUT_NODE = True

    def save(self, video, filename_prefix, crf, prompt=None, extra_pnginfo=None):
        import av
        import folder_paths

        components = video.get_components()
        images = components.images
        if images is None or getattr(images, "ndim", 0) != 4 or images.shape[0] < 1:
            raise ValueError("保存する動画フレームがありません。")

        height = int(images.shape[1])
        width = int(images.shape[2])
        pix_fmt = exact_h264_pixel_format(width, height)
        output_dir, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
            filename_prefix,
            folder_paths.get_output_directory(),
            width,
            height,
        )
        file = f"{filename}_{counter:05}_.mp4"
        path = os.path.join(output_dir, file)

        frame_rate = Fraction(round(float(components.frame_rate) * 1000), 1000)
        with av.open(
            path,
            mode="w",
            options={"movflags": "use_metadata_tags+faststart"},
        ) as container:
            if prompt is not None:
                container.metadata["prompt"] = json.dumps(prompt)
            if extra_pnginfo:
                for key, value in extra_pnginfo.items():
                    container.metadata[key] = json.dumps(value)

            stream = container.add_stream("libx264", rate=frame_rate)
            stream.width = width
            stream.height = height
            stream.pix_fmt = pix_fmt
            stream.options = {"crf": str(int(crf)), "preset": "medium"}

            audio_stream = None
            waveform = None
            audio = components.audio
            if audio:
                sample_rate = int(audio["sample_rate"])
                waveform = audio["waveform"]
                if waveform.ndim == 3:
                    waveform = waveform[0]
                max_samples = math.ceil(
                    (sample_rate / float(frame_rate)) * int(images.shape[0])
                )
                waveform = waveform[:, :max_samples].float().cpu().contiguous()
                channels = int(waveform.shape[0])
                if channels not in (1, 2, 6):
                    raise ValueError(
                        f"非対応の音声チャンネル数です: {channels}。1/2/6chに対応します。"
                    )
                layout = {1: "mono", 2: "stereo", 6: "5.1"}[channels]
                audio_stream = container.add_stream(
                    "aac", rate=sample_rate, layout=layout
                )

            for image in images:
                array = (image[..., :3] * 255).clamp(0, 255).byte().cpu().numpy()
                frame = av.VideoFrame.from_ndarray(array, format="rgb24")
                frame = frame.reformat(format=pix_fmt)
                for packet in stream.encode(frame):
                    container.mux(packet)
            for packet in stream.encode(None):
                container.mux(packet)

            if audio_stream is not None:
                audio_frame = av.AudioFrame.from_ndarray(
                    waveform.numpy(), format="fltp", layout=layout
                )
                audio_frame.sample_rate = sample_rate
                audio_frame.pts = 0
                for packet in audio_stream.encode(audio_frame):
                    container.mux(packet)
                for packet in audio_stream.encode(None):
                    container.mux(packet)

        print(f"H3 Exact Video Saved: {width}x{height} / {pix_fmt} / {path}")
        return {
            "ui": {
                "gifs": [
                    {
                        "filename": file,
                        "subfolder": subfolder,
                        "type": "output",
                        "format": "video/mp4",
                    }
                ]
            },
            "result": (video,),
        }


NODE_CLASS_MAPPINGS = {
    "H3AutoInternalSize": H3AutoInternalSize,
    "H3ResizeOutputToReference": H3ResizeOutputToReference,
    "H3PromptIdentityGuard": H3PromptIdentityGuard,
    "H3SaveVideoExact": H3SaveVideoExact,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3AutoInternalSize": "H3 Auto Internal Size",
    "H3ResizeOutputToReference": "H3 Exact Final Size",
    "H3PromptIdentityGuard": "H3 Identity / Body Guard",
    "H3SaveVideoExact": "H3 Save Exact MP4",
}
