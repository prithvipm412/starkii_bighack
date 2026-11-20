"""Difference-in-means refusal direction per layer.

python -m pipeline.extract_direction --config configs/mac1_qwen.yaml [--prompts data_tools/output/direction.jsonl]

Uses rows with split == "direction" (English; category "harmful" vs "harmless"). Residual stream = output of
decoder block l (hidden_states[l + 1]) at the last prompt token.
Writes outputs/directions/<name>.pt and results/<machine>/<name>_direction.json.
"""
import argparse
import json
import os
import time

import torch

from pipeline.data import load_prompts
from pipeline.model import encode, load_config, load_model


@torch.no_grad()
def last_token_acts(model, tok, prompts, bs):
    """[n_prompts, n_layers, d_model] float32 on CPU."""
    acts = []
    for i in range(0, len(prompts), bs):
        enc = encode(tok, prompts[i:i + bs], model.device)
        hs = model(**enc, output_hidden_states=True).hidden_states[1:]  # drop embeddings
        acts.append(torch.stack([h[:, -1, :] for h in hs], dim=1).float().cpu())  # left-padded -> -1 is last
    return torch.cat(acts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--prompts", default="data_tools/output/direction.jsonl")
    ap.add_argument("--layer", type=int, default=None, help="override chosen layer")
    ap.add_argument("--limit", type=int, default=None, help="max prompts per class")
    args = ap.parse_args()
    cfg = load_config(args.config)

    try:
        rows = load_prompts(args.prompts, splits={"direction"})
    except FileNotFoundError:
        raise SystemExit(f"{args.prompts} not found (AirDrop it into data_tools/output/)")
    harm = [r["text"] for r in rows if r["category"] == "harmful"][:args.limit]
    safe = [r["text"] for r in rows if r["category"] == "harmless"][:args.limit]
    if len(harm) < 2 or len(safe) < 2:
        raise SystemExit(f"need >=2 harmful and >=2 harmless prompts, got {len(harm)}/{len(safe)}")
    print(f"[direction] {len(harm)} harmful, {len(safe)} harmless")

    model, tok = load_model(cfg)
    t0 = time.time()
    a_h = last_token_acts(model, tok, harm, cfg["batch_size"])
    a_s = last_token_acts(model, tok, safe, cfg["batch_size"])
    print(f"[direction] activations in {time.time() - t0:.0f}s")

    diff = a_h.mean(0) - a_s.mean(0)                  # [L, d]
    diff_norm = diff.norm(dim=-1)                     # [L]
    dirs = diff / diff_norm[:, None].clamp_min(1e-8)  # unit per layer
    p_h = torch.einsum("nld,ld->nl", a_h, dirs)       # projections [n, L]
    p_s = torch.einsum("nld,ld->nl", a_s, dirs)
    pooled = ((p_h.var(0) + p_s.var(0)) / 2).sqrt().clamp_min(1e-8)
    sep = (p_h.mean(0) - p_s.mean(0)) / pooled         # Cohen's d per layer

    n_layers = dirs.shape[0]
    lo, hi = n_layers // 3, 2 * n_layers // 3
    best = lo + int(sep[lo:hi].argmax())
    layer = args.layer if args.layer is not None else best
    tau = float((p_h[:, layer].mean() + p_s[:, layer].mean()) / 2)

    os.makedirs("outputs/directions", exist_ok=True)
    pt = f"outputs/directions/{cfg['name']}.pt"
    torch.save({"directions": dirs, "diff_norm": diff_norm, "separation": sep, "layer": layer,
                "tau": tau, "alpha": float(diff_norm[layer]), "model_id": cfg["model_id"],
                "mean_proj_harmful": p_h.mean(0), "mean_proj_harmless": p_s.mean(0)}, pt)

    out_dir = f"results/{cfg['machine']}"
    os.makedirs(out_dir, exist_ok=True)
    summary = {
        "model": cfg["name"], "model_id": cfg["model_id"], "n_harmful": len(harm), "n_harmless": len(safe),
        "n_layers": n_layers, "middle_third": [lo, hi - 1], "best_layer_middle_third": best,
        "chosen_layer": layer, "default_tau": round(tau, 4), "default_alpha": round(float(diff_norm[layer]), 4),
        "per_layer": [{"layer": l, "separation": round(float(sep[l]), 4),
                       "diff_norm": round(float(diff_norm[l]), 4),
                       "mean_proj_harmful": round(float(p_h[:, l].mean()), 4),
                       "mean_proj_harmless": round(float(p_s[:, l].mean()), 4)} for l in range(n_layers)],
    }
    js = f"{out_dir}/{cfg['name']}_direction.json"
    with open(js, "w") as f:
        json.dump(summary, f, indent=1)
    print(f"[direction] layer={layer} sep={sep[layer]:.2f} tau={tau:.2f} alpha={diff_norm[layer]:.2f}")
    print(f"[direction] wrote {pt} and {js}")


if __name__ == "__main__":
    main()
