#!/usr/bin/env python3
import hashlib
import importlib.util
import sys
import tempfile
from pathlib import Path


class MissingObject(Exception):
    response = {
        "ResponseMetadata": {"HTTPStatusCode": 404},
        "Error": {"Code": "NoSuchKey"},
    }


class FakeS3:
    def __init__(self):
        self.objects = {}

    def list_objects_v2(self, Bucket, Prefix="", MaxKeys=1000, **_kwargs):
        contents = [
            {"Key": key, "Size": len(value[0])}
            for (bucket, key), value in self.objects.items()
            if bucket == Bucket and key.startswith(Prefix)
        ]
        return {"Contents": contents[:MaxKeys]}

    def head_object(self, Bucket, Key):
        try:
            data, metadata = self.objects[(Bucket, Key)]
        except KeyError as error:
            raise MissingObject() from error
        return {"ContentLength": len(data), "Metadata": metadata}

    def download_file(self, Bucket, Key, Filename):
        Path(Filename).write_bytes(self.objects[(Bucket, Key)][0])

    def upload_file(self, Filename, Bucket, Key, ExtraArgs):
        self.objects[(Bucket, Key)] = (
            Path(Filename).read_bytes(),
            ExtraArgs["Metadata"],
        )


def load_module(path):
    spec = importlib.util.spec_from_file_location("s3_sync", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(path):
    module = load_module(path)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        client = FakeS3()
        store = module.S3Store(client, root, "volume-123", "H3")

        output = root / "output" / "clip.mp4"
        output.parent.mkdir(parents=True)
        output.write_bytes(b"video-data")
        uploaded, skipped = store.push(("output",))
        assert (uploaded, skipped) == (1, 0)

        uploaded, skipped = store.push(("output",))
        assert (uploaded, skipped) == (0, 1)

        output.unlink()
        downloaded, skipped = store.pull(("output",))
        assert (downloaded, skipped) == (1, 0)
        assert output.read_bytes() == b"video-data"

        key = ("volume-123", "H3/input/reference.png")
        data = b"image-data"
        client.objects[key] = (data, {"sha256": hashlib.sha256(data).hexdigest()})
        downloaded, _ = store.pull(("input",))
        assert downloaded == 1
        assert (root / "input" / "reference.png").read_bytes() == data

        client.objects[("volume-123", "H3/../escape.txt")] = (b"bad", {})
        try:
            store.pull(("output",))
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe key was accepted")

        assert module.parse_dirs("models,output,models", ()) == ("models", "output")
        try:
            module.parse_dirs("../outside", ())
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe directory was accepted")

    print("s3 sync tests: PASS")


if __name__ == "__main__":
    main(sys.argv[1])
