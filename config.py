"""Central configuration for the evolution simulation.

Every tunable knob lives here so the model can be retuned without touching logic.
Energy is measured in *food units*: one food pellet = ``food_energy`` (1.0) energy.

The defaults are calibrated (see calibrate.py) so a 50-creature founding population
neither goes instantly extinct nor explodes -- it settles around a food-limited
carrying capacity, which is what lets selection actually act on the traits.
"""
from dataclasses import dataclass, asdict


@dataclass
class Config:
    # --- world ---
    world_width: float = 300.0
    world_height: float = 300.0

    # --- run length / sampling ---
    ticks: int = 15000            # how many ticks the simulation runs
    seed: int = 1                 # RNG seed -> fully reproducible runs
    sample_interval: int = 20     # record timeseries stats every N ticks

    # --- starting population ---
    start_population: int = 50
    founder_trait_spread: float = 0.10   # +/- spread on founders' traits
    start_energy: float = 8.0

    # --- baseline traits (founders centred here) ---
    base_speed: float = 1.0
    base_sense: float = 15.0
    base_size: float = 1.0

    # --- trait mutation on reproduction (your <=5% rule) ---
    mutation: float = 0.05        # each offspring trait *= 1 + U(-mutation, +mutation)
    min_trait: float = 0.05       # floor so traits stay positive/sane

    # --- per-tick energy economics --------------------------------------
    #   cost = base_metabolism * size**3                          (mass)
    #        + move_coef * size**2 * speed**2 * moved_fraction    (movement, your speed^2 rule)
    #        + sense_coef * sense**2                              (sensing = scanned area)
    base_metabolism: float = 0.02
    move_coef: float = 0.02
    sense_coef: float = 0.0002
    food_energy: float = 1.0

    # --- reproduction (asexual; only after a cooldown -- your spec) ------
    maturity_age: int = 40            # ticks from birth before first reproduction
    reproduction_cooldown: int = 40   # ticks between births
    reproduction_threshold: float = 10.0  # min energy to reproduce
    reproduction_cost: float = 6.0        # energy the parent pays
    offspring_energy: float = 4.0         # energy the newborn starts with
    offspring_spawn_radius: float = 5.0   # newborn appears within this radius of parent

    # --- death ---
    max_lifespan: int = 400       # ticks; set very large to effectively disable

    # --- predation (size lets you eat smaller creatures) ----------------
    predation_ratio: float = 1.3  # predator.size must be >= prey.size * ratio
    predation_gain: float = 5.0   # energy gained = predation_gain * prey.size

    # --- food supply = carrying capacity --------------------------------
    food_per_tick: float = 8.0    # new pellets spawned per tick (may be fractional)
    food_max: int = 1500          # max pellets allowed on the board at once
    initial_food: int = 400       # pellets present at tick 0

    # --- safety caps ---
    max_population: int = 3000    # performance guard; reproduction pauses if reached

    def to_dict(self):
        return asdict(self)
