# 🧬 Evolution Simulation

A natural-selection simulation (in the spirit of Primer's *Simulating Natural Selection*).
Creatures live on a 2-D board, forage randomly-spawned **food** for **energy**, and pass
slightly-mutated **traits** to their offspring. Over thousands of ticks, selection reshapes the
population — and you can watch the generations evolve on an interactive dashboard.

Pure standard-library **Python 3.9+** — no third-party packages, no build step.

## The model

Each creature has four heritable traits:

| Trait     | Helps it…                                       | …but costs energy as |
|-----------|-------------------------------------------------|----------------------|
| `speed`   | reach food faster (more distance per tick)      | **speed²** when moving |
| `sense`   | spot food / prey from farther away              | **sense²** (scanned area) |
| `size`    | eat smaller creatures (predation)               | **size²** metabolism, **size** drag |
| `reserve` | **bank surplus calories** for lean times        | **upkeep ∝ size·reserve** every tick |

Energy is measured in food units (1 pellet = 1 energy). Each tick a creature pays:

```
cost = base_metabolism·size^metabolism_exponent
       + move_coef·size^move_size_exponent·speed²·(fraction moved)
       + sense_coef·sense² + storage_upkeep·size·reserve
```

(`metabolism_exponent` defaults to 2 and `move_size_exponent` to 1 — gentle enough on big bodies that
predation is a viable strategy. Crank `metabolism_exponent` toward 3 to punish size again.)

- **Eat** to gain energy: a food pellet gives 1; eating a creature ≥ `predation_ratio`× smaller
  gives `predation_gain · prey.size` (body value) **plus `predation_steal` × the prey's banked
  energy** — so fat, well-fed prey are a windfall, and growing big enough to hunt them pays off.
- **Store** energy up to a cap `storage_base + storage_per_size · size · reserve`. Food eaten beyond
  the cap is **wasted**, so a bigger tank lets a creature stockpile. The tank costs a little upkeep
  every tick, so reserves are dead weight in plenty but life-saving in a drought.
- **Die** when energy hits 0, at `max_lifespan`, or by being eaten.
- **Reproduce** (asexually, alone) once `age ≥ maturity_age`, a `reproduction_cooldown` has passed
  since the last birth, and energy ≥ `reproduction_threshold`. Each offspring trait is the parent's
  × (1 ± up to 5%).
- **Carrying capacity** is set by food inflow (`food_per_tick`); a `max_population` cap guards
  performance (and is reported if ever hit).

### Droughts

Starting at `drought_start` (default tick 12,000 — well after the population has settled), food
spawning drops to `drought_food_factor` of normal for `drought_duration` ticks, recurring every
`drought_interval` ticks. The long pre-drought stretch is your *"without droughts"* baseline; the
later stretch is the same world *with* recurring famines — a clean before/after natural experiment in
one run. Each drought is a survivable **bottleneck** (population crashes, then rebounds), and the
survivors are enriched for whatever traits help — most visibly **reserve**. Disable with
`--set drought_enabled=False` to see the pure baseline.

A uniform **spatial grid** makes "nearest food/prey within sense" near-O(1), so ~100–2000 creatures
over tens of thousands of ticks run in seconds in plain Python.

## Run it

```bash
python3 run.py                              # full default run: 24,000 ticks, 50 founders, droughts from tick 12k
python3 run.py --ticks 3000 --seed 7        # shorter run, different seed
python3 run.py --set drought_enabled=False  # no droughts (the pure baseline)
python3 run.py --pop 80 --set food_per_tick=12 --set move_coef=0.03
```

This writes:
- `docs/results.json` — consumed by the dashboard
- `history.csv` — raw timeseries, for plotting elsewhere

Every knob lives in [`config.py`](config.py) and can be overridden on the CLI with
`--set KEY=VALUE`.

### Calibration

`python3 calibrate.py` runs short simulations across seeds and coefficient variants and reports
whether each stays **STABLE** (vs. EXTINCT / EXPLODES). The shipped defaults are calibrated so a
50-creature founding population settles into a healthy, breathing population — the condition for
selection to actually act.

## View the results

The dashboard is a single static file, [`docs/index.html`](docs/index.html) (Plotly via CDN). It shows:

1. **Trait evolution across generations** — each trait's mean per generation, relative to the founders.
2. **Watch a generation ▶** — an animated/slider view of each generation's mean traits (±1 std).
3. **Population & food over time** — drought periods shaded.
4. **Mean traits over time** — drought periods shaded.

Browsers block `fetch()` on `file://`, so view it over a local server:

```bash
cd docs && python3 -m http.server
# open http://localhost:8000
```

### Hosted on GitHub Pages

The whole `docs/` folder is GitHub-Pages-ready. After pushing this repo:
**Settings → Pages → Source: *Deploy from a branch* → Branch `main`, Folder `/docs` → Save.**
The dashboard goes live at `https://<user>.github.io/<repo>/`.

## A sample result

The default run (24k ticks, seed 1) evolved **~165 generations** with **~1,900 predation kills**:

- **size** rose ~1.0 → **~1.9** (peaks above 2) — with metabolism only ∝ size² and predation paying
  off, growing big to eat your neighbours became a winning strategy. Cannibalism is now a major
  ecological force rather than a curiosity.
- **speed** rose ~1.0 → **~2** — still useful for catching food and prey.
- **sense** held roughly steady (~13).
- **reserve** tells the thrifty-gene story: it stays near 1 in plenty, then is held up by the droughts
  (and by the value of carrying calories a predator can't always replace).

Each drought still crashes the (smaller, predator-heavy) population to a handful of survivors before
it rebounds — a textbook bottleneck. Predator ecosystems carry fewer individuals, so the droughts are
tuned gentler than they'd need to be for a pure-forager world.

## Files

| File | Purpose |
|------|---------|
| `config.py`        | all tunable parameters (one dataclass) |
| `simulation.py`    | `Creature`, `SpatialGrid`, `World` (the model + stats) |
| `run.py`           | CLI: run a simulation, write `results.json` + `history.csv` |
| `calibrate.py`     | coefficient sweep to verify energy balance |
| `docs/index.html`  | interactive dashboard |
| `docs/results.json`| latest run's data (committed so the site has data) |
