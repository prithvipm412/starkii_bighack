# Mac2 status

Done:
- Llama-3.2-3B (unsloth copy) direction: layer 15, alpha 10.13, tau -2.35 (results/mac2/Llama-3.2-3B-Instruct_direction.json).
- Pilot, 256 tokens, 3 conditions on MPS (results/mac2/*.csv, finished 02:07).
- Finding: steer_gated RAISES harmful compliance on Llama (kn 58% -> 78%, kn_mix 52% -> 72%, n=50 each). The gate fires on ~100% of non-English prompts because tau (-2.35) is below almost all Kannada projections. Negative result, for the failure analysis.

Doing:
- Full run, condition none, 1800 rows, started 02:24, ETA ~04:30.

Blocked:
- None.

Next:
- When the full none run lands, the Mac4 auto-refresh picks it up for the 3-model gap.
