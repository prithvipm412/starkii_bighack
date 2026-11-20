"""Generate + score.

python -m pipeline.run --config configs/mac1_qwen.yaml --prompts data_tools/output/pilot.jsonl \
    --conditions none,steer_always,steer_gated [--limit N] [--layer L --alpha A --tau T]

Sweep (one model load, every L x alpha combo -> results/<machine>/sweep_<name>_<cond>_L<L>_a<A>.csv):
python -m pipeline.run --config ... --prompts ... --conditions steer_gated --limit 150 \
    --layers 10,14,18 --alphas 4,8,12

Generation for all conditions runs first (model in memory, saved after every batch), then the
model is freed and the scorer models load. Resume key = (prompt_id, variant): rows already in the
reply file are not regenerated, rows already in the CSV are not rescored.
Raw replies -> outputs/replies/*.jsonl (gitignored). CSVs hold scores only (CLAUDE.md format).
Gate diagnostics (projection, steered, detected_non_en; no text) -> results/<machine>/gate/<stem>.csv (subfolder so result loaders globbing results/macN/*.csv never see it).
latency_ms = generation wall time of the batch / batch size (scoring not included).
"""
import argparse
import csv
import hashlib
import json
import os
import subprocess
import time

from pipeline.data import is_non_english, load_prompts
from pipeline.model import free, generate, load_config, load_model
from pipeline.steer import CONDITIONS, Steerer, load_direction

CSV_FIELDS = ["prompt_id", "split", "category", "variant", "model", "condition",
              "refused", "judge_score", "latency_ms", "commit"]
GATE_FIELDS = ["prompt_id", "split", "variant", "condition", "layer", "alpha", "tau",
               "projection", "steered", "detected_non_en"]


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def text_hash(t):
    return hashlib.sha1(t.encode("utf-8")).hexdigest()[:10]


def key(r):
    return (str(r["prompt_id"]), r.get("variant", "en"))


def read_jsonl(path):
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # half-written last line from a crash
    return out


def read_csv_keys(path):
    if not os.path.exists(path):
        return set()
    with open(path, newline="") as f:
        return {key(r) for r in csv.DictReader(f)}


def append_csv(path, fields, rows):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})


def fmt(x):
    return f"{x:g}" if isinstance(x, float) else str(x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--conditions", default="none", help="comma list of " + ",".join(CONDITIONS))
    ap.add_argument("--limit", type=int, default=None, help="first N prompt_ids (all variants of each)")
    ap.add_argument("--layer", type=int, default=None)
    ap.add_argument("--alpha", type=float, default=None)
    ap.add_argument("--tau", type=float, default=None)
    ap.add_argument("--layers", default=None, help="sweep: comma list of layers")
    ap.add_argument("--alphas", default=None, help="sweep: comma list of alphas")
    ap.add_argument("--rescore", action="store_true", help="no generation; rescore all saved replies, rewrite CSVs")
    args = ap.parse_args()

    cfg = load_config(args.config)
    conds = [c.strip() for c in args.conditions.split(",") if c.strip()]
    bad = [c for c in conds if c not in CONDITIONS]
    if bad:
        raise SystemExit(f"unknown condition(s) {bad}; choose from {CONDITIONS}")
    try:
        rows = load_prompts(args.prompts, splits={"harmful", "harmless"}, limit=args.limit)
    except FileNotFoundError:
        raise SystemExit(f"{args.prompts} not found (AirDrop it into data_tools/output/)")
    if not rows:
        raise SystemExit(f"no harmful/harmless prompts in {args.prompts}")
    print(f"[run] {len(rows)} rows ({len({r['prompt_id'] for r in rows})} prompt_ids), conditions={conds}")
    commit = git_commit()
    out_dir = f"results/{cfg['machine']}"
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs("outputs/replies", exist_ok=True)

    # ---- jobs: (condition, layer, alpha, tau, stem)
    sweep = bool(args.layers or args.alphas)
    jobs = []
    for c in conds:
        if sweep and c != "none":
            Ls = [int(x) for x in args.layers.split(",")] if args.layers else [args.layer]
            As = [float(x) for x in args.alphas.split(",")] if args.alphas else [args.alpha]
            for Lx in Ls:
                for Ax in As:
                    _, L, a, t = load_direction(cfg, Lx, Ax, args.tau)
                    jobs.append((c, L, a, t, f"sweep_{cfg['name']}_{c}_L{L}_a{fmt(a)}"))
            continue
        if c == "none":
            try:  # direction only used for a read-only projection log
                _, L, a, t = load_direction(cfg, args.layer, args.alpha, args.tau)
            except SystemExit:
                L = a = t = None
        else:
            _, L, a, t = load_direction(cfg, args.layer, args.alpha, args.tau)
        jobs.append((c, L, a, t, f"{cfg['name']}_{c}"))

    # ---- phase 1: generation
    model = tok = None
    if not args.rescore:
        for c, L, a, t, stem in jobs:
            rep_path = f"outputs/replies/{stem}.jsonl"
            saved = read_jsonl(rep_path)
            done = {key(r) for r in saved}
            want = {key(r): text_hash(r["text"]) for r in rows}
            clash = [key(r) for r in saved if r.get("text_sha1") and key(r) in want and r["text_sha1"] != want[key(r)]]
            if clash:
                raise SystemExit(f"[gen] {stem}: {len(clash)} saved replies were made from DIFFERENT prompt text "
                                 f"for the same (prompt_id, variant), e.g. {clash[:3]}. Not mixing them. Move "
                                 f"{rep_path} and results/{cfg['machine']}/{stem}.csv aside, then rerun.")
            todo = [r for r in rows if key(r) not in done]
            print(f"[gen] {stem}: {len(done)} done, {len(todo)} to do (L={L} alpha={a} tau={t})")
            if not todo:
                continue
            if model is None:
                model, tok = load_model(cfg)
            direction = load_direction(cfg, L, a, t)[0] if L is not None else None
            bs, tot_tok, tot_t = cfg["batch_size"], 0, 0.0
            for i in range(0, len(todo), bs):
                batch = todo[i:i + bs]
                prompts = [r["text"] for r in batch]
                t0 = time.time()
                if direction is None:
                    replies, ntok = generate(model, tok, prompts, cfg["max_new_tokens"])
                    proj, steered = [None] * len(batch), [0] * len(batch)
                    non_en = [int(is_non_english(x)) for x in prompts]
                else:
                    with Steerer(model, direction, L, a, t, c, prompts) as st:
                        replies, ntok = generate(model, tok, prompts, cfg["max_new_tokens"])
                    proj, steered, non_en = st.results()
                dt = time.time() - t0
                tot_tok, tot_t = tot_tok + sum(ntok), tot_t + dt
                with open(rep_path, "a", encoding="utf-8") as f:
                    for r, rep, n, p, s, ne in zip(batch, replies, ntok, proj, steered, non_en):
                        f.write(json.dumps({
                            "prompt_id": r["prompt_id"], "variant": r["variant"], "split": r["split"],
                            "category": r["category"], "text_sha1": text_hash(r["text"]), "condition": c, "layer": L, "alpha": a, "tau": t,
                            "projection": None if p is None else round(p, 4), "steered": s,
                            "detected_non_en": ne, "reply": rep, "reply_tokens": n,
                            "latency_ms": round(dt * 1000 / len(batch))}, ensure_ascii=False) + "\n")
                print(f"[gen] {stem} {i + len(batch)}/{len(todo)}  {sum(ntok) / max(dt, 1e-9):.1f} tok/s")
            if tot_t:
                print(f"[gen] {stem} done: {tot_tok} tokens in {tot_t:.0f}s = {tot_tok / tot_t:.1f} tok/s")
        if model is not None:
            del model, tok
            free()

    # ---- phase 2: scoring (scorer models load only now)
    text_by_key = {key(r): r["text"] for r in rows}
    pending = []  # (stem, rec)
    for c, L, a, t, stem in jobs:
        csv_path = f"{out_dir}/{stem}.csv"
        if args.rescore:
            for p in (csv_path, f"{out_dir}/gate/{stem}.csv"):
                if os.path.exists(p):
                    os.remove(p)
        scored = read_csv_keys(csv_path)
        latest = {key(r): r for r in read_jsonl(f"outputs/replies/{stem}.jsonl")}
        for k, rec in latest.items():
            if k not in scored and k in text_by_key:
                rec["prompt"] = text_by_key[k]
                pending.append((stem, rec))
    print(f"[score] {len(pending)} replies to score")
    if not pending:
        return
    from pipeline.score import score_records
    score_records([rec for _, rec in pending])
    for stem in dict.fromkeys(s for s, _ in pending):
        recs = [r for s, r in pending if s == stem]
        for r in recs:
            r["model"], r["commit"] = cfg["model_id"], commit
        append_csv(f"{out_dir}/{stem}.csv", CSV_FIELDS, recs)
        if recs[0].get("layer") is not None:
            os.makedirs(f"{out_dir}/gate", exist_ok=True)
            append_csv(f"{out_dir}/gate/{stem}.csv", GATE_FIELDS, recs)
        print(f"[score] wrote {out_dir}/{stem}.csv")


if __name__ == "__main__":
    main()
