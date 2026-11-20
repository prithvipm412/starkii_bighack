"""Residual-stream steering with a forward hook on decoder block L.

Conditions:
  none          no change to activations (a read-only hook only records the projection)
  steer_always  add alpha * d at every position, every forward step
  steer_gated   per prompt: proj = <h_L[last prompt token], d>; if proj > tau AND prompt is
                non-English (Indic script or romanized/code-mixed detector) -> add alpha * d at
                every position for that prompt; otherwise leave it untouched.
"""
import torch

from pipeline.data import is_non_english
from pipeline.model import decoder_layers

CONDITIONS = ("none", "steer_always", "steer_gated")


def load_direction(cfg, layer=None, alpha=None, tau=None):
    """Resolve L/alpha/tau: CLI override > config > defaults stored by extract_direction."""
    path = f"outputs/directions/{cfg['name']}.pt"
    try:
        blob = torch.load(path, map_location="cpu")
    except FileNotFoundError:
        raise SystemExit(f"{path} not found: run pipeline.extract_direction first")
    L = layer if layer is not None else cfg.get("layer")
    L = blob["layer"] if L is None else int(L)
    a = alpha if alpha is not None else cfg.get("alpha")
    a = float(blob["diff_norm"][L]) if a is None else float(a)
    t = tau if tau is not None else cfg.get("tau")
    if t is None:  # midpoint at this layer (recomputed so a different L gets its own tau)
        t = float((blob["mean_proj_harmful"][L] + blob["mean_proj_harmless"][L]) / 2)
    return blob["directions"][L].clone(), L, a, float(t)


class Steerer:
    """Use as a context manager around one generate() call (one batch)."""

    def __init__(self, model, direction, layer, alpha, tau, condition, prompts):
        assert condition in CONDITIONS, condition
        p = next(model.parameters())
        self.d = direction.to(device=p.device, dtype=p.dtype)
        self.layer, self.alpha, self.tau, self.condition = layer, alpha, tau, condition
        self.block = decoder_layers(model)[layer]
        self.non_en = torch.tensor([is_non_english(x) for x in prompts], device=p.device)
        self.proj = None   # [B] projection at last prompt token (before steering)
        self.mask = None   # [B] bool, which rows get steered
        self.handle = None

    def _hook(self, module, inputs, output):
        h = output[0] if isinstance(output, tuple) else output
        if self.proj is None:  # first call = prefill; last position = last prompt token (left padding)
            self.proj = (h[:, -1, :].float() @ self.d.float())
            if self.condition == "steer_always":
                self.mask = torch.ones_like(self.non_en)
            elif self.condition == "steer_gated":
                self.mask = (self.proj > self.tau) & self.non_en
            else:
                self.mask = torch.zeros_like(self.non_en)
        if self.condition == "none" or not bool(self.mask.any()):
            return output
        add = (self.alpha * self.d)[None, None, :] * self.mask[:, None, None].to(h.dtype)
        h = h + add
        return (h,) + tuple(output[1:]) if isinstance(output, tuple) else h

    def __enter__(self):
        self.handle = self.block.register_forward_hook(self._hook)
        return self

    def __exit__(self, *exc):
        if self.handle is not None:
            self.handle.remove()
        return False

    def results(self):
        proj = self.proj.cpu().tolist() if self.proj is not None else [None] * len(self.non_en)
        mask = self.mask.cpu().tolist() if self.mask is not None else [False] * len(self.non_en)
        return proj, [int(m) for m in mask], [int(x) for x in self.non_en.cpu().tolist()]
