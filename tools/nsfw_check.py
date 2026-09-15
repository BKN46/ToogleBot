"""Download and benchmark the NSFW model without importing bot runtime state."""

import argparse
import io
import json
import resource
import statistics
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

from tools.nsfw_model import (
    DEFAULT_MODEL_PATH, MODEL_FILE, MODEL_REPO, MODEL_REVISION,
    NsfwDetector, verify_model,
)


def download(path: Path, endpoint: str) -> None:
    import requests

    if path.exists():
        verify_model(path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"{endpoint.rstrip('/')}/{MODEL_REPO}/resolve/{MODEL_REVISION}/{MODEL_FILE}"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            with requests.get(url, stream=True, timeout=(10, 60)) as response:
                response.raise_for_status()
                for chunk in response.iter_content(1024 * 1024):
                    output.write(chunk)
        verify_model(temporary)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def benchmark(args) -> dict:
    if args.manifest:
        manifest = json.loads(args.manifest.read_text())
        if not manifest or any(row.get("label") not in (0, 1) for row in manifest):
            raise ValueError("Manifest must contain path and binary label (0=SFW, 1=NSFW)")
        images = [(args.manifest.parent / row["path"]).read_bytes() for row in manifest]
    else:
        manifest = None
        images = []
        rng = np.random.default_rng(42)
        for shape in [(256, 256), (720, 1280), (1024, 768)]:
            with Image.fromarray(rng.integers(0, 256, (*shape, 3), dtype=np.uint8)) as im:
                buffer = io.BytesIO()
                im.save(buffer, format="JPEG")
                images.append(buffer.getvalue())

    start = time.perf_counter()
    if args.backend == "legacy":
        import opennsfw2

        def predict(data):
            with tempfile.NamedTemporaryFile() as stream:
                stream.write(data)
                stream.flush()
                return opennsfw2.predict_image(stream.name)
    else:
        detector = NsfwDetector(args.model, args.threads)

        def predict(data):
            return detector.predict(data, cache=False)

    predict(images[0])
    cold = time.perf_counter() - start
    for _ in range(3):
        predict(images[0])
    times, predictions = [], []
    for _ in range(args.rounds):
        for data in images:
            start = time.perf_counter()
            predictions.append(predict(data))
            times.append((time.perf_counter() - start) * 1000)
    result = {
        "backend": args.backend, "samples": len(images), "rounds": args.rounds,
        "cold_seconds": cold, "median_ms": statistics.median(times),
        "p95_ms": float(np.percentile(times, 95)),
        "max_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "synthetic": manifest is None,
    }
    if manifest:
        threshold = args.threshold if args.threshold is not None else (0.25 if args.backend == "legacy" else 0.5)
        labels = [row["label"] for row in manifest] * args.rounds
        predicted = [int(score >= threshold) for score in predictions]
        tp = sum(p == y == 1 for p, y in zip(predicted, labels))
        fp = sum(p == 1 and y == 0 for p, y in zip(predicted, labels))
        fn = sum(p == 0 and y == 1 for p, y in zip(predicted, labels))
        result.update(threshold=threshold,
                      accuracy=sum(p == y for p, y in zip(predicted, labels)) / len(labels),
                      precision=tp / (tp + fp) if tp + fp else None,
                      recall=tp / (tp + fn) if tp + fn else None,
                      false_positives=fp, false_negatives=fn)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["download", "benchmark"])
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--endpoint", default="https://huggingface.co")
    parser.add_argument("--backend", choices=["onnx", "legacy"], default="onnx")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--threshold", type=float)
    args = parser.parse_args()
    if args.rounds < 1 or (args.threshold is not None and not 0 <= args.threshold <= 1):
        parser.error("rounds must be positive and threshold must be in [0, 1]")
    if args.command == "download":
        download(args.model, args.endpoint)
        print("NSFW model verified")
    else:
        print(json.dumps(benchmark(args), indent=2))


if __name__ == "__main__":
    main()
