#!/usr/bin/env python3
"""Quick calibration sweep for the energy economics.

The central tuning problem in this kind of simulation is energy balance: if the
per-tick costs are too high relative to food income the founders go extinct in a
few hundred ticks; too low and they explode straight into the population cap.
Either way selection can't act.

This script runs short simulations across several seeds for the baseline config
and for a few coefficient variants, and prints whether each settles into a stable,
breathing population. Use it to confirm (or adjust) the defaults in config.py.

    python3 calibrate.py
"""
import copy
import statistics

from config import Config
from simulation import World

TICKS = 3000
SEEDS = [1, 2, 3]


def trial(cfg):
    """Return dict of end-of-run summary numbers for one simulation."""
    world = World(cfg)
    world.run()
    ts = world.timeseries
    mid = ts[len(ts) // 2]["population"] if ts else 0
    last = ts[-1]
    return {"end_reason": world.end_reason, "mid": mid, "end": last["population"],
            "speed": last["mean_speed"], "sense": last["mean_sense"],
            "size": last["mean_size"], "reserve": last["mean_reserve"],
            "pred": sum(s["predation_events"] for s in ts),
            "gen": last["max_generation"]}


def verdict(end_reasons, end_pops, cap):
    if all(p == 0 for p in end_pops):
        return "EXTINCT"
    if any("cap" in r for r in end_reasons) or max(end_pops) >= cap * 0.95:
        return "EXPLODES"
    return "STABLE"


def run_variant(name, **overrides):
    rows = []
    for seed in SEEDS:
        cfg = Config()
        cfg.ticks = TICKS
        cfg.seed = seed
        for k, v in overrides.items():
            setattr(cfg, k, v)
        rows.append(trial(cfg))
    end_reasons = [r["end_reason"] for r in rows]
    end_pops = [r["end"] for r in rows]
    mid_pops = [r["mid"] for r in rows]
    v = verdict(end_reasons, end_pops, Config().max_population)
    print("%-30s  %-9s  mid~%4d  end~%4d  speed %.2f sense %.1f size %.2f reserve %.2f  pred~%d  gen~%d"
          % (name, v,
             round(statistics.mean(mid_pops)),
             round(statistics.mean(end_pops)),
             statistics.mean(r["speed"] for r in rows),
             statistics.mean(r["sense"] for r in rows),
             statistics.mean(r["size"] for r in rows),
             statistics.mean(r["reserve"] for r in rows),
             round(statistics.mean(r["pred"] for r in rows)),
             round(statistics.mean(r["gen"] for r in rows))))


def main():
    print("Calibration sweep: %d ticks x seeds %s\n" % (TICKS, SEEDS))
    print("(droughts default to starting at tick 12000, so most rows run drought-free)\n")
    print("%-30s  %-9s  %-9s %-9s  traits (final mean)                          %s"
          % ("variant", "verdict", "mid pop", "end pop", "gens"))
    print("-" * 116)
    run_variant("baseline (no drought reached)")
    run_variant("less food (food_per_tick=5)", food_per_tick=5.0)
    run_variant("more food (food_per_tick=12)", food_per_tick=12.0)
    run_variant("cheaper move (move_coef=0.01)", move_coef=0.01)
    run_variant("pricier move (move_coef=0.04)", move_coef=0.04)
    run_variant("cheaper sense (sense_coef=0.0001)", sense_coef=0.0001)
    run_variant("no predation (ratio huge)", predation_ratio=100.0)
    print()
    # --- drought stress tests: bring droughts forward so they actually fire ---
    run_variant("early droughts (mild x0.35)",
                drought_start=800, drought_interval=1000, drought_duration=400,
                drought_food_factor=0.35)
    run_variant("early droughts (harsh x0.20)",
                drought_start=800, drought_interval=1000, drought_duration=400,
                drought_food_factor=0.20)
    print("\nBaseline should read STABLE. Drought rows should survive (not EXTINCT)")
    print("and ideally show a HIGHER reserve than the drought-free baseline.")


if __name__ == "__main__":
    main()
