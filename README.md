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
| `size`    | eat smaller creatures (predation)               | **size³** metabolism, **size²** drag |
| `reserve` | **bank surplus calories** for lean times        | **upkeep ∝ size·reserve** every tick |

Energy is measured in food units (1 pellet = 1 energy). Each tick a creature pays:

```
cost = base_metabolism·size³ + move_coef·size²·speed²·(fraction moved)
       + sense_coef·sense² + storage_upkeep·size·reserve
```

- **Eat** to gain energy: a food pellet gives 1; eating a creature ≥ `predation_ratio`× smaller
  gives `predation_gain · prey.size`.
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

The default run (24k ticks, seed 1) evolved **148 generations**:

- **speed** rose ~1.0 → **3.8** — reaching food first is strongly favoured.
- **size** fell ~1.0 → **0.34** — small bodies dodge the size³ metabolism tax.
- **sense** held roughly steady (~15).
- **reserve** told the prettiest story: it drifted *down* (~1.0 → 0.92) during the long pre-drought
  plenty (stored fat is just upkeep when food is everywhere), then climbed *back up* (~1.1–1.2) once
  the droughts began and stockpiling started saving lives — the classic thrifty-gene tradeoff.

Each drought crashed the population to a handful of survivors (min ~9) before it rebounded — a
textbook evolutionary bottleneck.

## Files

| File | Purpose |
|------|---------|
| `config.py`        | all tunable parameters (one dataclass) |
| `simulation.py`    | `Creature`, `SpatialGrid`, `World` (the model + stats) |
| `run.py`           | CLI: run a simulation, write `results.json` + `history.csv` |
| `calibrate.py`     | coefficient sweep to verify energy balance |
| `docs/index.html`  | interactive dashboard |
| `docs/results.json`| latest run's data (committed so the site has data) |
