"""Core evolution simulation: Creature, SpatialGrid, World.

Pure standard-library Python (3.9+), no third-party dependencies.

Model summary
-------------
Creatures live on a 2-D board and forage randomly-spawned food (1 pellet = 1 energy).
Each tick a creature moves toward the nearest food (or the nearest creature it can
prey on) within its ``sense`` radius, paying energy to move (cost grows with speed^2),
to sense (cost grows with sense^2 = scanned area) and just to exist (metabolism grows
with size^3 = mass). Run out of energy -> die. Bank enough energy and survive a
maturation/cooldown period -> reproduce, passing on each trait mutated by <=5%.

A uniform spatial grid makes "nearest food/prey within radius" near-O(1) so the whole
thing stays fast in plain Python.
"""
import math
import random


class Creature:
    __slots__ = ("x", "y", "energy", "speed", "sense", "size", "reserve",
                 "cap", "age", "cooldown", "generation", "alive")

    def __init__(self, x, y, energy, speed, sense, size, reserve, cap, generation):
        self.x = x
        self.y = y
        self.speed = speed
        self.sense = sense
        self.size = size
        self.reserve = reserve     # calorie-storage trait
        self.cap = cap             # max energy this creature can bank
        self.energy = energy if energy < cap else cap
        self.age = 0
        self.cooldown = 0          # ticks since birth / last reproduction
        self.generation = generation
        self.alive = True


class SpatialGrid:
    """Uniform grid bucketing points by cell, for fast neighbourhood queries."""

    __slots__ = ("cell", "buckets")

    def __init__(self, cell_size):
        self.cell = cell_size
        self.buckets = {}

    def insert(self, item, x, y):
        key = (int(x / self.cell), int(y / self.cell))
        bucket = self.buckets.get(key)
        if bucket is None:
            self.buckets[key] = [item]
        else:
            bucket.append(item)

    def neighbors(self, x, y, radius):
        """Yield every item whose cell lies within ``radius`` of (x, y).

        Returns a superset of the true neighbours (whole cells), so callers must
        still distance-check; but it caps the scan to the relevant cells.
        """
        cx = int(x / self.cell)
        cy = int(y / self.cell)
        r = int(radius / self.cell) + 1
        get = self.buckets.get
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                bucket = get((cx + dx, cy + dy))
                if bucket:
                    for item in bucket:
                        yield item


class World:
    def __init__(self, config):
        self.cfg = config
        self.rng = random.Random(config.seed)
        self.tick = 0
        self.creatures = []
        self.food = []            # list of [x, y] pellets
        self._food_accum = 0.0    # accumulates fractional food_per_tick
        self.cell = max(config.base_sense, 10.0)

        # cumulative event counters (reset each sample window)
        self.births = 0
        self.deaths = 0
        self.predation_events = 0
        self.pop_cap_hit = False
        self.end_reason = "completed"

        # time series + per-generation accumulators
        self.timeseries = []
        self._gen = {}            # generation -> accumulator dict

        self._spawn_founders()
        self._spawn_initial_food()

    # ---- helpers -------------------------------------------------------
    def _cap(self, size, reserve):
        """Max energy a creature of this size/reserve can bank."""
        cfg = self.cfg
        return cfg.storage_base + cfg.storage_per_size * size * reserve

    def _in_drought(self, tick):
        cfg = self.cfg
        if not cfg.drought_enabled or tick < cfg.drought_start:
            return False
        phase = (tick - cfg.drought_start) % cfg.drought_interval
        return phase < cfg.drought_duration

    # ---- setup ---------------------------------------------------------
    def _spawn_founders(self):
        cfg = self.cfg
        rng = self.rng
        s = cfg.founder_trait_spread
        for _ in range(cfg.start_population):
            speed = cfg.base_speed * (1 + rng.uniform(-s, s))
            sense = cfg.base_sense * (1 + rng.uniform(-s, s))
            size = cfg.base_size * (1 + rng.uniform(-s, s))
            reserve = cfg.base_reserve * (1 + rng.uniform(-s, s))
            c = Creature(
                x=rng.uniform(0, cfg.world_width),
                y=rng.uniform(0, cfg.world_height),
                energy=cfg.start_energy,
                speed=speed, sense=sense, size=size, reserve=reserve,
                cap=self._cap(size, reserve), generation=0,
            )
            self.creatures.append(c)
            self._record_birth(c)

    def _spawn_initial_food(self):
        cfg = self.cfg
        for _ in range(cfg.initial_food):
            self.food.append([self.rng.uniform(0, cfg.world_width),
                              self.rng.uniform(0, cfg.world_height)])

    # ---- per-generation bookkeeping ------------------------------------
    def _record_birth(self, c):
        g = self._gen.get(c.generation)
        if g is None:
            g = {"n": 0, "s_sp": 0.0, "ss_sp": 0.0, "s_se": 0.0, "ss_se": 0.0,
                 "s_si": 0.0, "ss_si": 0.0, "s_re": 0.0, "ss_re": 0.0,
                 "n_dead": 0, "s_life": 0.0}
            self._gen[c.generation] = g
        g["n"] += 1
        g["s_sp"] += c.speed
        g["ss_sp"] += c.speed * c.speed
        g["s_se"] += c.sense
        g["ss_se"] += c.sense * c.sense
        g["s_si"] += c.size
        g["ss_si"] += c.size * c.size
        g["s_re"] += c.reserve
        g["ss_re"] += c.reserve * c.reserve

    def _record_death(self, c):
        g = self._gen.get(c.generation)
        if g is not None:
            g["n_dead"] += 1
            g["s_life"] += c.age

    # ---- food ----------------------------------------------------------
    def _spawn_food(self):
        cfg = self.cfg
        rate = cfg.food_per_tick
        if self._in_drought(self.tick):
            rate *= cfg.drought_food_factor
        self._food_accum += rate
        n = int(self._food_accum)
        self._food_accum -= n
        room = cfg.food_max - len(self.food)
        if n > room:
            n = max(0, room)
        rng = self.rng
        w, h = cfg.world_width, cfg.world_height
        for _ in range(n):
            self.food.append([rng.uniform(0, w), rng.uniform(0, h)])

    # ---- main step -----------------------------------------------------
    def step(self):
        cfg = self.cfg
        rng = self.rng
        self.tick += 1

        self._spawn_food()

        # Build spatial grids from start-of-tick positions.
        food_grid = SpatialGrid(self.cell)
        for i, f in enumerate(self.food):
            food_grid.insert(i, f[0], f[1])
        creature_grid = SpatialGrid(self.cell)
        for c in self.creatures:
            creature_grid.insert(c, c.x, c.y)

        eaten_food = set()
        newborns = []

        # Process creatures in a shuffled order so no one has a permanent
        # first-mover advantage on contested food.
        order = self.creatures[:]
        rng.shuffle(order)

        for c in order:
            if not c.alive:
                continue
            c.age += 1
            c.cooldown += 1

            sense_sq = c.sense * c.sense

            # --- find nearest edible prey within sense ---
            prey = None
            prey_d2 = sense_sq
            max_prey_size = c.size / cfg.predation_ratio
            if max_prey_size > 0:
                for other in creature_grid.neighbors(c.x, c.y, c.sense):
                    if other is c or not other.alive or other.size > max_prey_size:
                        continue
                    dx = other.x - c.x
                    dy = other.y - c.y
                    d2 = dx * dx + dy * dy
                    if d2 < prey_d2:
                        prey_d2 = d2
                        prey = other

            target_x = target_y = None
            target_dist = None
            target_is_prey = False

            if prey is not None:
                target_x, target_y = prey.x, prey.y
                target_dist = math.sqrt(prey_d2)
                target_is_prey = True
            else:
                # --- find nearest food within sense ---
                best_i = -1
                best_d2 = sense_sq
                for i in food_grid.neighbors(c.x, c.y, c.sense):
                    if i in eaten_food:
                        continue
                    f = self.food[i]
                    dx = f[0] - c.x
                    dy = f[1] - c.y
                    d2 = dx * dx + dy * dy
                    if d2 < best_d2:
                        best_d2 = d2
                        best_i = i
                if best_i >= 0:
                    f = self.food[best_i]
                    target_x, target_y = f[0], f[1]
                    target_dist = math.sqrt(best_d2)

            # --- move ---
            if target_x is not None:
                if target_dist <= c.speed:
                    # reaches the target this tick
                    moved = target_dist
                    c.x, c.y = target_x, target_y
                    reached = True
                else:
                    moved = c.speed
                    inv = c.speed / target_dist
                    c.x += (target_x - c.x) * inv
                    c.y += (target_y - c.y) * inv
                    reached = False
            else:
                # nothing sensed -> wander at full speed
                ang = rng.uniform(0, 2 * math.pi)
                c.x += math.cos(ang) * c.speed
                c.y += math.sin(ang) * c.speed
                moved = c.speed
                reached = False

            # keep inside the board
            if c.x < 0:
                c.x = 0.0
            elif c.x > cfg.world_width:
                c.x = cfg.world_width
            if c.y < 0:
                c.y = 0.0
            elif c.y > cfg.world_height:
                c.y = cfg.world_height

            # --- eat what we reached (banked energy is capped by storage) ---
            if target_x is not None and reached:
                if target_is_prey:
                    if prey.alive:
                        prey.alive = False
                        self.deaths += 1
                        self.predation_events += 1
                        self._record_death(prey)
                        # body value + a share of the prey's saved calories
                        c.energy += (cfg.predation_gain * prey.size
                                     + cfg.predation_steal * prey.energy)
                else:
                    if best_i not in eaten_food:
                        eaten_food.add(best_i)
                        c.energy += cfg.food_energy
                if c.energy > c.cap:        # surplus beyond the tank is wasted
                    c.energy = c.cap

            # --- pay energy cost for the tick (incl. upkeep of the tank) ---
            moved_fraction = moved / c.speed if c.speed > 0 else 0.0
            cost = (cfg.base_metabolism * c.size ** cfg.metabolism_exponent
                    + cfg.move_coef * c.size ** cfg.move_size_exponent * c.speed * c.speed * moved_fraction
                    + cfg.sense_coef * sense_sq
                    + cfg.storage_upkeep * c.size * c.reserve)
            c.energy -= cost

            # --- death by starvation / old age ---
            if c.energy <= 0 or c.age >= cfg.max_lifespan:
                c.alive = False
                self.deaths += 1
                self._record_death(c)
                continue

            # --- reproduction ---
            if (c.age >= cfg.maturity_age
                    and c.cooldown >= cfg.reproduction_cooldown
                    and c.energy >= cfg.reproduction_threshold):
                if len(self.creatures) + len(newborns) < cfg.max_population:
                    c.energy -= cfg.reproduction_cost
                    c.cooldown = 0
                    child = self._make_child(c)
                    newborns.append(child)
                    self._record_birth(child)
                    self.births += 1
                else:
                    self.pop_cap_hit = True

        # --- reap dead, add newborns ---
        if self.deaths:
            self.creatures = [c for c in self.creatures if c.alive]
        self.creatures.extend(newborns)

        # --- compact eaten food ---
        if eaten_food:
            self.food = [f for i, f in enumerate(self.food) if i not in eaten_food]

    def _make_child(self, parent):
        cfg = self.cfg
        rng = self.rng
        m = cfg.mutation
        floor = cfg.min_trait
        speed = max(floor, parent.speed * (1 + rng.uniform(-m, m)))
        sense = max(floor, parent.sense * (1 + rng.uniform(-m, m)))
        size = max(floor, parent.size * (1 + rng.uniform(-m, m)))
        reserve = max(floor, parent.reserve * (1 + rng.uniform(-m, m)))
        ang = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0, cfg.offspring_spawn_radius)
        x = min(max(parent.x + math.cos(ang) * r, 0.0), cfg.world_width)
        y = min(max(parent.y + math.sin(ang) * r, 0.0), cfg.world_height)
        return Creature(x, y, cfg.offspring_energy, speed, sense, size, reserve,
                        self._cap(size, reserve), parent.generation + 1)

    # ---- stats ---------------------------------------------------------
    def sample(self):
        creatures = self.creatures
        n = len(creatures)
        rec = {"tick": self.tick, "population": n,
               "births": self.births, "deaths": self.deaths,
               "predation_events": self.predation_events,
               "food_count": len(self.food),
               "drought": 1 if self._in_drought(self.tick) else 0}
        if n:
            sp = se = si = re = en = ge = 0.0
            sp2 = se2 = si2 = re2 = 0.0
            gmax = 0
            for c in creatures:
                sp += c.speed; se += c.sense; si += c.size; re += c.reserve
                sp2 += c.speed * c.speed
                se2 += c.sense * c.sense
                si2 += c.size * c.size
                re2 += c.reserve * c.reserve
                en += c.energy; ge += c.generation
                if c.generation > gmax:
                    gmax = c.generation
            rec.update({
                "mean_speed": sp / n, "std_speed": _std(sp, sp2, n),
                "mean_sense": se / n, "std_sense": _std(se, se2, n),
                "mean_size": si / n, "std_size": _std(si, si2, n),
                "mean_reserve": re / n, "std_reserve": _std(re, re2, n),
                "mean_energy": en / n,
                "mean_generation": ge / n, "max_generation": gmax,
            })
        else:
            for k in ("mean_speed", "std_speed", "mean_sense", "std_sense",
                      "mean_size", "std_size", "mean_reserve", "std_reserve",
                      "mean_energy", "mean_generation", "max_generation"):
                rec[k] = 0.0
        self.timeseries.append(rec)
        # reset window counters
        self.births = self.deaths = self.predation_events = 0

    def by_generation(self):
        out = []
        for g in sorted(self._gen):
            d = self._gen[g]
            n = d["n"]
            if n == 0:
                continue
            out.append({
                "generation": g,
                "count": n,
                "mean_speed": d["s_sp"] / n, "std_speed": _std(d["s_sp"], d["ss_sp"], n),
                "mean_sense": d["s_se"] / n, "std_sense": _std(d["s_se"], d["ss_se"], n),
                "mean_size": d["s_si"] / n, "std_size": _std(d["s_si"], d["ss_si"], n),
                "mean_reserve": d["s_re"] / n, "std_reserve": _std(d["s_re"], d["ss_re"], n),
                "mean_lifespan": (d["s_life"] / d["n_dead"]) if d["n_dead"] else None,
            })
        return out

    # ---- driver --------------------------------------------------------
    def run(self, progress_cb=None, progress_every=1000):
        """Run the whole simulation. ``progress_cb(tick, population)`` is called
        every ``progress_every`` ticks for reporting."""
        cfg = self.cfg
        self.sample()  # tick 0 snapshot
        for _ in range(cfg.ticks):
            self.step()
            if self.tick % cfg.sample_interval == 0:
                self.sample()
            if not self.creatures:
                self.end_reason = "extinction"
                if self.tick % cfg.sample_interval != 0:
                    self.sample()
                break
            if progress_cb and self.tick % progress_every == 0:
                progress_cb(self.tick, len(self.creatures))
        if self.pop_cap_hit and self.end_reason == "completed":
            self.end_reason = "completed (population cap reached at times)"


def _std(s, ss, n):
    if n <= 0:
        return 0.0
    var = ss / n - (s / n) ** 2
    return math.sqrt(var) if var > 0 else 0.0
