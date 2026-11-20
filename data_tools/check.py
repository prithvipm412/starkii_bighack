"""Print random sample rows and counts from generated variant JSONL."""
import argparse
import random
from collections import Counter
from .common import read_jsonl, text_field


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSONL produced by data_tools.build")
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    try:
        rows = read_jsonl(args.input)
        rng = random.Random(args.seed)
        variants = sorted({row.get("variant", "unknown") for row in rows})
        print("Counts per split/variant:")
        counts = Counter((str(row.get("split", "unspecified")), str(row.get("variant", "unknown"))) for row in rows)
        for (split, variant), count in sorted(counts.items()):
            print(f"  split={split} variant={variant}: {count}")
        for variant in variants:
            pool = [row for row in rows if row.get("variant", "unknown") == variant]
            print(f"\nRandom sample: variant={variant} ({min(10, len(pool))}/{len(pool)})")
            for row in rng.sample(pool, min(10, len(pool))):
                print(f"prompt_id={row.get('prompt_id', '<missing>')} split={row.get('split', 'unspecified')} text={row[text_field(row)]}")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
