#!/usr/bin/env python3
"""Run the evolution simulation and write results for the dashboard.

Examples
--------
    python3 run.py                          # full default run (15k ticks)
    python3 run.py --ticks 2000 --seed 7    # short run, different seed
    python3 run.py --pop 80 --set food_per_tick=12 --set move_coef=0.03

Outputs (next to this file):
    docs/results.json   consumed by docs/index.html (the dashboard)
    history.csv         raw timeseries, for re-plotting elsewhere
"""
import argparse
import csv
import json
import os
import time

from config import Config
from simulation import World

HERE = os.path.dirname(os.path.abspath(__file__))


def parse_args():
    p = argparse.ArgumentParser(description="Evolution simulation")
    p.add_argument("--ticks", type=int, help="number of ticks to run")
    p.add_argument("--seed", type=int, help="RNG seed")
    p.add_argument("--pop", type=int, help="starting population")
    p.add_argument("--world", type=float, help="world width = height")
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                   help="override any Config field, e.g. --set food_per_tick=12")
    p.add_argument("--out", default=os.path.join(HERE, "docs", "results.json"),
                   help="path for results.json")
    p.add_argument("--csv", default=os.path.join(HERE, "history.csv"),
                   help="path for history.csv")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def build_config(args):
    cfg = Config()
    if args.ticks is not None:
        cfg.ticks = args.ticks
    if args.seed is not None:
        cfg.seed = args.seed
    if args.pop is not None:
        cfg.start_population = args.pop
    if args.world is not None:
        cfg.world_width = cfg.world_height = args.world
    for item in args.set:
        if "=" not in item:
            raise SystemExit("--set expects KEY=VALUE, got %r" % item)
        key, val = item.split("=", 1)
        if not hasattr(cfg, key):
            raise SystemExit("unknown config field: %s" % key)
        cur = getattr(cfg, key)
        caster = type(cur)
        setattr(cfg, key, caster(val))
    return cfg


def main():
    args = parse_args()
    cfg = build_config(args)

    if not args.quiet:
        print("Running %d ticks, seed %d, %d founders on a %gx%g board..."
              % (cfg.ticks, cfg.seed, cfg.start_population,
                 cfg.world_width, cfg.world_height))

    world = World(cfg)
    t0 = time.time()

    def report(tick, pop):
        if not args.quiet:
            print("  tick %6d  population %5d" % (tick, pop))

    world.run(progress_cb=report, progress_every=max(1000, cfg.ticks // 15 or 1))
    elapsed = time.time() - t0

    by_gen = world.by_generation()
    result = {
        "meta": {
            "config": cfg.to_dict(),
            "end_reason": world.end_reason,
            "ticks_run": world.tick,
            "final_population": len(world.creatures),
            "generations_reached": (by_gen[-1]["generation"] if by_gen else 0),
            "wall_seconds": round(elapsed, 2),
        },
        "timeseries": world.timeseries,
        "by_generation": by_gen,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(result, fh, separators=(",", ":"))

    # raw timeseries CSV
    if world.timeseries:
        fields = list(world.timeseries[0].keys())
        with open(args.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(world.timeseries)

    if not args.quiet:
        m = result["meta"]
        print("\nDone in %.1fs." % elapsed)
        print("  end reason:          %s" % m["end_reason"])
        print("  ticks run:           %d" % m["ticks_run"])
        print("  final population:    %d" % m["final_population"])
        print("  generations reached: %d" % m["generations_reached"])
        if world.timeseries:
            last = world.timeseries[-1]
            print("  final mean traits:   speed %.3f | sense %.2f | size %.3f"
                  % (last["mean_speed"], last["mean_sense"], last["mean_size"]))
        print("\n  wrote %s" % args.out)
        print("  wrote %s" % args.csv)


if __name__ == "__main__":
    main()
