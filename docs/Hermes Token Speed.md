# Hermes token speed

Verified against the local Hermes source on 7 October 2026. No Hermes files were changed.

`agent/agent_init.py` creates paired latency/output deques with `maxlen=10`. `agent/turn_usage.py` records `api_duration` and canonical output-token counts after API calls. `tui_gateway/server.py`, `_get_usage`, returns `avg_tps = sum(output history) / sum(latency history)`. This is a weighted aggregate, not the arithmetic mean of individual rates. The desktop's `tokensPerSecondLabel` rounds `usage.avg_tps` for display. Missing/invalid timings omit the field.

The gateway source explicitly notes that the Codex route reports no latency. Exact provider API-call timing therefore cannot be copied from the current notification contract. The original first-to-last-delta estimator excluded prefill and first-token waiting and could inflate speed substantially; it is superseded.

The corrected observer starts timing at turn start and uses token-usage updates as model-response boundaries. It subtracts the union of observed tool-execution intervals, includes time before the first visible token, and applies the same weighted last-ten formula. It retains a visible approximation marker because those desktop events are not provider API timestamps. A mid-turn attach has no observed start and stays unknown. No numeric calibration or fixed “22” rate is applied: the regression example has 109 output tokens in five measured seconds, which rounds to 22 rather than the old delta-only 109.
