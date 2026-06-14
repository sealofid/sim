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
    """Return (end_reason, mid_pop, end_pop, mean_speed, mean_sense, mean_size, max_gen)."""
    world = World(cfg)
    world.run()
    ts = world.timeseries
    mid = ts[len(ts) // 2]["population"] if ts else 0
    last = ts[-1]
    return (world.end_reason, mid, last["population"],
            last["mean_speed"], last["mean_sense"], last["mean_size"],
            last["max_generation"])


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
    end_reasons = [r[0] for r in rows]
    end_pops = [r[2] for r in rows]
    mid_pops = [r[1] for r in rows]
    v = verdict(end_reasons, end_pops, Config().max_population)
    print("%-28s  %-9s  mid~%4d  end~%4d  speed %.2f sense %.1f size %.2f  gen~%d"
          % (name, v,
             round(statistics.mean(mid_pops)),
             round(statistics.mean(end_pops)),
             statistics.mean(r[3] for r in rows),
             statistics.mean(r[4] for r in rows),
             statistics.mean(r[5] for r in rows),
             round(statistics.mean(r[6] for r in rows))))


def main():
    print("Calibration sweep: %d ticks x seeds %s\n" % (TICKS, SEEDS))
    print("%-28s  %-9s  %-9s %-9s  traits (final mean)             %s"
          % ("variant", "verdict", "mid pop", "end pop", "gens"))
    print("-" * 100)
    run_variant("baseline (defaults)")
    run_variant("less food (food_per_tick=5)", food_per_tick=5.0)
    run_variant("more food (food_per_tick=12)", food_per_tick=12.0)
    run_variant("cheaper move (move_coef=0.01)", move_coef=0.01)
    run_variant("pricier move (move_coef=0.04)", move_coef=0.04)
    run_variant("cheaper sense (sense_coef=0.0001)", sense_coef=0.0001)
    run_variant("no predation (ratio huge)", predation_ratio=100.0)
    print("\nAim for the baseline to read STABLE with a healthy mid/end population.")


if __name__ == "__main__":
    main()
