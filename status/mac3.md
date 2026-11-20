# Mac3 status

Done:
- Installed the shared requirements on Python 3.12.16 with PyTorch 2.15.0.
- Downloaded the official `google/gemma-2-2b-it` checkpoint. The final shard passed SHA-256 verification after a resumable HTTP transfer.
- Gemma generated a coherent answer with finite logits on `mps:0` and `attn_implementation="eager"` in both `torch.float16` and `torch.bfloat16`. This was a single harmless smoke prompt per dtype. The current `configs/mac3_gemma.yaml` selects the verified bfloat16 setting.
- Gemma's chat template rejects the `system` role. The smoke prompt used one `user` message.

Doing:
- Removed two temporary mac3 download folders and the incomplete Gemma cache shard. The completed checkpoint remains cached.

Blocked:
- Offline direction extraction read all 128 rows (64 harmful, 64 harmless) and then failed while initializing the Gemma tokenizer. Transformers attempted a Hugging Face model metadata lookup with `HF_HUB_OFFLINE=1`. No layer, alpha, or tau was produced.
- Last 20 lines of `logs/mac3_gemma_direction.log`:

```text
    model = model_info(model_id)
            ^^^^^^^^^^^^^^^^^^^^
  File "/Users/vivek/starkii_bighack/.venv/lib/python3.12/site-packages/huggingface_hub/utils/_validators.py", line 114, in _inner_fn
    return fn(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^
  File "/Users/vivek/starkii_bighack/.venv/lib/python3.12/site-packages/huggingface_hub/hf_api.py", line 2660, in model_info
    r = get_session().get(path, headers=headers, timeout=timeout, params=params)
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/vivek/starkii_bighack/.venv/lib/python3.12/site-packages/requests/sessions.py", line 671, in get
    return self.request("GET", url, params=params, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/vivek/starkii_bighack/.venv/lib/python3.12/site-packages/requests/sessions.py", line 651, in request
    resp = self.send(prep, **send_kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/vivek/starkii_bighack/.venv/lib/python3.12/site-packages/requests/sessions.py", line 784, in send
    r = adapter.send(request, **kwargs)
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/vivek/starkii_bighack/.venv/lib/python3.12/site-packages/huggingface_hub/utils/_http.py", line 107, in send
    raise OfflineModeIsEnabled(
huggingface_hub.errors.OfflineModeIsEnabled: Cannot reach https://huggingface.co/api/models/google/gemma-2-2b-it: offline mode is enabled. To disable it, please unset the `HF_HUB_OFFLINE` environment variable.
```

Next:
- Resume when Mac1 provides an offline-compatible loading path. `data_tools/output/pilot.jsonl` is also pending.
