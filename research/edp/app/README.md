# edp.app

This package hosts the application-level control logic for the EDP simulator.

## ControllerApp overview

`ControllerApp` drives the simulation loop:

- Generates link-level EPs on each tick.
- Advances request operations (GEN_LINK / SWAP / PURIFY) based on readiness.
- Tracks completed requests, wait times, and PSW statistics.
- Manages link decoherence and memory cleanup.

## PSW (Purify-while-Swap-waiting)

PSW is a best-effort, single-shot purification that triggers while a SWAP is
waiting on one side and the ready side has degraded below `psw_threshold`.

Flow (simplified):

1. Scan for waiting ops whose EP fidelity < `psw_threshold`.
2. Clone the target op tree and re-run it as a sacrificial path.
3. When the sacrificial root completes, run a PURIFY op using
   (sacrificial EP, target EP).
4. If PSW completes, the target EP fidelity is updated; otherwise the target
   is regenerated.

PSW is disabled when `enable_psw` is false or `psw_threshold` is None.

## PSW counters

- `psw_gen_link_scheduled`: number of PSW sacrificial runs started.
- `psw_purify_scheduled`: number of PSW purify ops scheduled.
- `psw_purify_success` / `psw_purify_fail`: PSW purify outcomes.
- `psw_cancelled`: PSW cancelled because swap-waiting ended.

## Notes

- PSW uses cloned op trees and does not modify the main request plan.
- PSW cancels if the target is no longer in swap-waiting state.
