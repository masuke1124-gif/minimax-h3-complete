#!/usr/bin/env python3
"""Non-destructive synchronization with a RunPod Network Volume S3 endpoint."""

from __future__ import annotations

import argparse
import hashlib
import os
import signal
import sys
import time
from pathlib import Path, PurePosixPath


DEFAULT_PULL_DIRS = ("models", "input", "output", "workflows", "logs")
DEFAULT_PUSH_DIRS = ("input", "output", "workflows", "logs")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_dirs(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = value.split(",") if value else default
    result = []
    for item in raw:
        name = item.strip().strip("/")
        if not name or "/" in name or name in (".", ".."):
            raise ValueError(f"Invalid synchronized directory: {item!r}")
        if name not in result:
            result.append(name)
    return tuple(result)


class S3Store:
    def __init__(self, client, root: Path, bucket: str, prefix: str = "H3"):
        self.client = client
        self.root = root.resolve()
        self.bucket = bucket
        self.prefix = prefix.strip("/")

    def _key(self, relative: Path) -> str:
        relative_key = relative.as_posix().lstrip("/")
        return f"{self.prefix}/{relative_key}" if self.prefix else relative_key

    def _relative_from_key(self, key: str) -> Path | None:
        if self.prefix:
            prefix = f"{self.prefix}/"
            if not key.startswith(prefix):
                return None
            key = key[len(prefix) :]

        pure = PurePosixPath(key)
        if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
            raise ValueError(f"Unsafe S3 key: {key!r}")
        destination = (self.root / Path(*pure.parts)).resolve()
        if not destination.is_relative_to(self.root):
            raise ValueError(f"S3 key escapes H3 root: {key!r}")
        return destination.relative_to(self.root)

    def check(self) -> None:
        self.client.list_objects_v2(Bucket=self.bucket, MaxKeys=1)

    def list_remote(self):
        kwargs = {"Bucket": self.bucket, "MaxKeys": 1000}
        if self.prefix:
            kwargs["Prefix"] = f"{self.prefix}/"
        while True:
            response = self.client.list_objects_v2(**kwargs)
            yield from response.get("Contents", [])
            token = response.get("NextContinuationToken")
            if not token:
                break
            kwargs["ContinuationToken"] = token

    def pull(self, directories: tuple[str, ...]) -> tuple[int, int]:
        allowed = set(directories)
        downloaded = skipped = 0
        for item in self.list_remote():
            relative = self._relative_from_key(item["Key"])
            if relative is None or not relative.parts or relative.parts[0] not in allowed:
                continue

            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            head = self.client.head_object(Bucket=self.bucket, Key=item["Key"])
            remote_hash = head.get("Metadata", {}).get("sha256")
            remote_size = int(head.get("ContentLength", item.get("Size", -1)))
            if destination.is_file() and destination.stat().st_size == remote_size:
                if not remote_hash or sha256_file(destination) == remote_hash:
                    skipped += 1
                    continue

            partial = destination.with_name(f"{destination.name}.s3part")
            self.client.download_file(self.bucket, item["Key"], str(partial))
            if remote_hash and sha256_file(partial) != remote_hash:
                partial.unlink(missing_ok=True)
                raise RuntimeError(f"S3 SHA-256 mismatch: {relative}")
            partial.replace(destination)
            downloaded += 1
        return downloaded, skipped

    def push(self, directories: tuple[str, ...]) -> tuple[int, int]:
        uploaded = skipped = 0
        for directory in directories:
            base = self.root / directory
            if not base.exists():
                continue
            for path in sorted(base.rglob("*")):
                if not path.is_file() or path.name.endswith((".part", ".s3part")):
                    continue
                if path == self.root / "logs" / "s3-sync.log":
                    continue
                relative = path.relative_to(self.root)
                key = self._key(relative)
                digest = sha256_file(path)
                try:
                    head = self.client.head_object(Bucket=self.bucket, Key=key)
                except Exception as error:
                    response = getattr(error, "response", {})
                    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                    code = response.get("Error", {}).get("Code")
                    if status != 404 and code not in ("404", "NoSuchKey", "NotFound"):
                        raise
                else:
                    if (
                        int(head.get("ContentLength", -1)) == path.stat().st_size
                        and head.get("Metadata", {}).get("sha256") == digest
                    ):
                        skipped += 1
                        continue

                self.client.upload_file(
                    str(path),
                    self.bucket,
                    key,
                    ExtraArgs={"Metadata": {"sha256": digest}},
                )
                uploaded += 1
        return uploaded, skipped


def config_from_environment():
    endpoint = os.environ.get("RUNPOD_S3_ENDPOINT_URL") or os.environ.get(
        "RUNPOD_S3_ENDPOINT"
    )
    bucket = os.environ.get("RUNPOD_NETWORK_VOLUME_ID")
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    missing = [
        name
        for name, value in (
            ("RUNPOD_S3_ENDPOINT_URL", endpoint),
            ("RUNPOD_NETWORK_VOLUME_ID", bucket),
            ("AWS_ACCESS_KEY_ID", access_key),
            ("AWS_SECRET_ACCESS_KEY", secret_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("Missing required S3 settings: " + ", ".join(missing))
    return endpoint, bucket, access_key, secret_key


def make_store(root: Path) -> S3Store:
    endpoint, bucket, access_key, secret_key = config_from_environment()
    try:
        import boto3
        from botocore.config import Config
    except ImportError as error:
        raise RuntimeError("boto3 is not installed in this image") from error

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 12, "mode": "adaptive"},
            s3={"addressing_style": "path"},
        ),
    )
    return S3Store(
        client,
        root,
        bucket,
        os.environ.get("H3_S3_PREFIX", "H3"),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "pull", "push", "daemon"))
    parser.add_argument("--root", default=os.environ.get("H3_ROOT", "/workspace/H3"))
    parser.add_argument("--dirs")
    parser.add_argument(
        "--interval", type=int, default=int(os.environ.get("H3_S3_SYNC_INTERVAL", "60"))
    )
    args = parser.parse_args()

    if os.environ.get("H3_SKIP_S3_SYNC", "0") == "1":
        print("S3 sync skipped by H3_SKIP_S3_SYNC=1")
        return 0

    try:
        store = make_store(Path(args.root))
        if args.command == "check":
            store.check()
            print("RunPod S3 connection: PASS")
        elif args.command == "pull":
            dirs = parse_dirs(args.dirs, DEFAULT_PULL_DIRS)
            downloaded, skipped = store.pull(dirs)
            print(f"S3 pull complete: downloaded={downloaded} unchanged={skipped}")
        elif args.command == "push":
            dirs = parse_dirs(args.dirs, DEFAULT_PUSH_DIRS)
            uploaded, skipped = store.push(dirs)
            print(f"S3 push complete: uploaded={uploaded} unchanged={skipped}")
        else:
            if args.interval < 15:
                raise ValueError("Sync interval must be at least 15 seconds")
            dirs = parse_dirs(args.dirs, DEFAULT_PUSH_DIRS)
            stopping = False

            def stop(_signum, _frame):
                nonlocal stopping
                stopping = True

            signal.signal(signal.SIGTERM, stop)
            signal.signal(signal.SIGINT, stop)
            while not stopping:
                try:
                    uploaded, skipped = store.push(dirs)
                    print(f"S3 periodic sync: uploaded={uploaded} unchanged={skipped}")
                except Exception as error:
                    print(f"S3 periodic sync failed; retrying: {error}", file=sys.stderr)
                for _ in range(args.interval):
                    if stopping:
                        break
                    time.sleep(1)
            try:
                uploaded, skipped = store.push(dirs)
                print(f"S3 final sync: uploaded={uploaded} unchanged={skipped}")
            except Exception as error:
                print(f"S3 final sync failed: {error}", file=sys.stderr)
    except Exception as error:
        print(f"S3 sync failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
