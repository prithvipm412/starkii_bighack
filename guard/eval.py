"""Run python -m guard.eval with the cached models and local Git history."""
import json
from pathlib import Path
from statistics import median
import subprocess
from types import ModuleType

from guard.guard import LanguageBarrierGuard

ROOT = Path(__file__).resolve().parents[1]
OLD_COMMIT = "a0106f0"
VARIANTS = ("en", "kn", "kn_latn", "kn_mix")


def old_guard():
    source = subprocess.check_output(
        ["git", "show", f"{OLD_COMMIT}:guard/guard.py"], cwd=ROOT, timeout=10
    )
    module = ModuleType("guard_reference")
    exec(compile(source, f"{OLD_COMMIT}:guard/guard.py", "exec"), module.__dict__)
    return module.LanguageBarrierGuard(), module


def metrics(labels, blocks):
    positives = sum(labels)
    negatives = len(labels) - positives
    return (
        100 * sum(label == block for label, block in zip(labels, blocks)) / len(labels),
        100 * sum(label and block for label, block in zip(labels, blocks)) / positives,
        100 * sum(not label and block for label, block in zip(labels, blocks)) / negatives,
    )


def calibrate(rows, scores):
    labels = [row["harmful"] for row in rows]
    candidates = []
    for percent in range(1, 100):
        threshold = percent / 100
        blocks = [score > threshold for score in scores]
        accuracy, recall, false_blocks = metrics(labels, blocks)
        if false_blocks <= 10:
            candidates.append((threshold, recall, false_blocks, accuracy))
    return max(candidates, key=lambda c: (c[1], -c[2], -abs(c[0] - 0.5)))


def main():
    rows = [json.loads(line) for line in (ROOT / "guard/testset.jsonl").read_text().splitlines()]
    guard = LanguageBarrierGuard()
    old, old_module = old_guard()
    old._guard = guard.guard
    old_blocks, new_blocks, new_result = [], [], []
    for row in rows:
        text = row["text"]
        detected = old.detect(text)
        _, raw = old.guard(text)
        english = old.to_english(text, detected)
        score = max(raw, old.guard(english)[1]) if english != text else raw
        threshold = old_module.THRESHOLD
        if detected == "en" and old_module.PROCESS_REQUEST_RE.fullmatch(text):
            threshold = old_module.PROCESS_THRESHOLD
        old_blocks.append(score > threshold)
    del old
    if guard._dev() == "mps":
        guard.guard.torch.mps.empty_cache()
    guard.preload()
    guard.check("ivattu weather hegidhe?")
    for row in rows:
        result = guard.check(row["text"])
        new_blocks.append(result["blocked"])
        new_result.append(result)

    print("| Variant | N | OLD accuracy | OLD harmful recall | OLD harmless false-blocks | NEW accuracy | NEW harmful recall | NEW harmless false-blocks |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for variant in (*VARIANTS, "ALL"):
        indices = [i for i, row in enumerate(rows) if variant == "ALL" or row["variant"] == variant]
        labels = [rows[i]["harmful"] for i in indices]
        rates = metrics(labels, [old_blocks[i] for i in indices]) + metrics(labels, [new_blocks[i] for i in indices])
        print(f"| {variant} | {len(indices)} | " + " | ".join(f"{rate:.1f}%" for rate in rates) + " |")

    scores = [result["p_unsafe"] for result in new_result]
    threshold, recall, false_blocks, _ = calibrate(rows, scores)
    times = [result["latency_ms"] for result in new_result]
    print(f"Threshold (global calibration): {threshold:.2f}; recall: {recall:.1f}%; false-blocks: {false_blocks:.1f}%")
    print(f"Warm latency (ms), median / max: {median(times):.0f} / {max(times)}")


if __name__ == "__main__":
    main()
