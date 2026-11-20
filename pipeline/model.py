"""Load a chat model from a YAML config; chat-template + greedy batched generation."""
import gc
import random
import time

import numpy as np
import torch
import yaml
from transformers import AutoModelForCausalLM, AutoTokenizer

DTYPES = {"float16": torch.float16, "bfloat16": torch.bfloat16, "float32": torch.float32}
DEFAULTS = {"device": "mps", "dtype": "float16", "attn_implementation": "sdpa", "seed": 0,
            "max_new_tokens": 64, "batch_size": 8, "layer": None, "alpha": None, "tau": None}


def load_config(path):
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
    for k in ("name", "model_id", "machine"):
        if k not in cfg:
            raise SystemExit(f"config {path} is missing '{k}'")
    return {**DEFAULTS, **cfg}


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def pick_device(want):
    if want == "mps" and not torch.backends.mps.is_available():
        print("[model] MPS not available, falling back to CPU")
        return "cpu"
    return want


def load_model(cfg):
    set_seed(cfg["seed"])
    device = pick_device(cfg["device"])
    tok = AutoTokenizer.from_pretrained(cfg["model_id"])
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    t0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        cfg["model_id"], dtype=DTYPES[cfg["dtype"]], attn_implementation=cfg["attn_implementation"])
    model.to(device).eval()
    print(f"[model] loaded {cfg['model_id']} on {device} ({cfg['dtype']}) in {time.time() - t0:.0f}s")
    return model, tok


def decoder_layers(model):
    """The list of transformer blocks (Qwen2 / Llama / Gemma2 all use model.model.layers)."""
    return model.model.layers


def apply_chat(tok, prompts):
    # user turn only: gemma-2 has no system role, so no system prompt for any model (keeps it uniform)
    return [tok.apply_chat_template([{"role": "user", "content": p}], tokenize=False,
                                    add_generation_prompt=True) for p in prompts]


def encode(tok, prompts, device):
    texts = apply_chat(tok, prompts)
    # chat template already contains BOS where the model needs it
    return tok(texts, return_tensors="pt", padding=True, add_special_tokens=False).to(device)


@torch.no_grad()
def generate(model, tok, prompts, max_new_tokens=64):
    """Greedy decode a batch. Returns (replies, n_generated_tokens_per_reply)."""
    enc = encode(tok, prompts, model.device)
    out = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False, temperature=None,
                         top_p=None, top_k=None, repetition_penalty=1.0,
                         pad_token_id=tok.pad_token_id)
    gen = out[:, enc["input_ids"].shape[1]:]
    replies, ntoks = [], []
    eos = model.generation_config.eos_token_id
    stop_ids = {tok.pad_token_id, tok.eos_token_id, *(eos if isinstance(eos, list) else [eos])}
    for row in gen:
        ids = row.tolist()
        n = len(ids)
        for j, t in enumerate(ids):
            if t in stop_ids:
                n = j
                break
        ntoks.append(n)
        replies.append(tok.decode(ids[:n], skip_special_tokens=True).strip())
    return replies, ntoks


def free():
    """Call after `del model` in the caller to return memory to the OS."""
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
