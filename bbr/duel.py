"""Vectorised 1-v-1 duel between every ordered pair of Pokemon in one generation.

Both sides: level 100, 31 IVs, 84 EVs in every stat, neutral nature, no item (NFE Pokemon get Eviolite in Gen 5+;
LEFTOVERS = True gives everyone Leftovers).
Each Pokemon carries at most 4 attacks (chosen once, for the best average damage over the field); each turn a side
attacks with the best of those against this opponent (or a priority move when that's better),
heals with reliable recovery when it's losing the damage race, and may open with a setup or status move when
that wins it the matchup (best response, chosen per opponent).
"""
import numpy as np
from bbrlib import *

# Experimental: every Pokemon holds Leftovers (heals 1/16 of its max HP at the end of each turn, Gen 4+).
LEFTOVERS = False

# ------------------------------------------------------------------ per-side tables
IMMUNE = {"levitate": "Ground", "eartheater": "Ground", "flashfire": "Fire", "wellbakedbody": "Fire",
          "voltabsorb": "Electric", "lightningrod": "Electric", "motordrive": "Electric", "waterabsorb": "Water",
          "stormdrain": "Water", "dryskin": "Water", "sapsipper": "Grass"}
SUN, RAIN, SAND, HAIL, WIND = 1, 2, 3, 4, 5
WEATHER_AB = {"deltastream": WIND, "drought": SUN, "desolateland": SUN, "orichalcumpulse": SUN, "drizzle": RAIN, "primordialsea": RAIN,
              "sandstream": SAND, "snowwarning": HAIL}
ELEC, PSY, GRASSY, MISTY = 1, 2, 3, 4
TERRAIN_AB = {"electricsurge": ELEC, "hadronengine": ELEC, "psychicsurge": PSY, "grassysurge": GRASSY,
              "mistysurge": MISTY, "seedsower": 0}
INTIM_IMMUNE = {"clearbody", "hypercutter", "whitesmoke", "fullmetalbody", "innerfocus", "oblivious", "owntempo",
                "scrappy", "guarddog", "mirrorarmor"}
SETUP_COST = {"bellydrum": 1 / 2, "filletaway": 1 / 2, "clangoroussoul": 1 / 3}  # share of max HP
POWDER = {"spore", "sleeppowder", "stunspore", "poisonpowder"}
# damage kinds: which stats a move uses (attacker's / defender's), and its damage class (0 physical, 1 special)
KINDS = ("phys", "spec", "psyshock", "bodypress", "foulplay", "freezedry")
KI = {k: i for i, k in enumerate(KINDS)}
NK = len(KINDS)
DCLASS = np.array([0, 1, 1, 0, 0, 1])
NSLOT = 18 * NK * 2 * 2  # type, kind, contact, priority


def slot(t, c, k, p):
    return ((t * NK + c) * 2 + k) * 2 + p


# abilities that raise a stat by one stage when the Pokemon comes in
START_STAGE = {"intrepidsword": "atk", "dauntlessshield": "def", "embodyaspectteal": "spe",
               "embodyaspecthearthflame": "atk", "embodyaspectwellspring": "spd", "embodyaspectcornerstone": "def"}


def stat_line(g, mon, ability):
    b = list(mon["stats"])
    if ability == "stancechange":  # attacks from Blade Forme (the sim gives Shield Forme defences until then)
        blade = gendata(g)["pokedex"]["aegislashblade"]["baseStats"]
        b = [blade[k] for k in ("hp", "atk", "def", "spa", "spd", "spe")]
    if ability == "zerotohero":
        b = [100, 160, 97, 106, 87, 100]
    if ability == "schooling":
        b = [45, 140, 130, 140, 135, 30]
    hp = 1 if mon["id"] == "shedinja" else 2 * b[0] + 31 + 21 + 110
    st = [2 * x + 31 + 21 + 5 for x in b[1:]]
    atk, df, spa, spd, spe = map(float, st)
    if ability in ("hugepower", "purepower"): atk *= 2
    if ability in ("hustle", "gorillatactics"): atk *= 1.5
    if ability == "furcoat": df *= 2
    if ability == "orichalcumpulse": atk *= 4 / 3
    if ability == "hadronengine": spa *= 4 / 3
    if mon["nfe"] and g >= 5: df *= 1.5; spd *= 1.5
    return float(hp), np.array([atk, spa]), np.array([df, spd]), spe


class Side:
    """Everything about one configuration of the roster (each Pokemon with one chosen ability)."""

    def __init__(self, g, mons, abilities, field=None):
        """`field`: the Side whose Pokemon the movesets are tuned against (default: this side itself)."""
        self.g, self.n = g, len(mons)
        self.ids = [m["id"] for m in mons]
        n = self.n
        eff1 = type_matrix(g)
        self.hp = np.zeros(n); self.atk = np.zeros((n, 2)); self.df = np.zeros((n, 2)); self.spe = np.zeros(n)
        self.P = np.zeros((n, NSLOT)); self.fixed = np.zeros((n, 18))
        self.rec = np.zeros((n, NSLOT)); self.drn = np.zeros((n, NSLOT))  # recoil / drain share of each slot's move
        self.stab = np.ones((n, 18)); self.E = np.ones((n, 18))  # E: how hard each type hits it
        self.dmod = np.ones((n, 18, 2, 2))  # defender ability multiplier by type, category, contact
        self.ab = list(abilities)
        self.isType = np.zeros((n, 18), bool)
        self.recover = np.zeros(n, bool); self.setup = [None] * n; self.status = [dict() for _ in range(n)]
        self.belly = np.zeros(n, bool); self.plainpoison = np.zeros(n, bool)
        self.shieldDf = np.zeros((n, 2)); self.shieldAtk = np.zeros(n); self.stance = np.array([a == "stancechange" for a in abilities], bool)
        mtab = move_table(g)
        self.slotmove = [dict() for _ in range(n)]; self.fixedmove = [dict() for _ in range(n)]
        for i, (m, a) in enumerate(zip(mons, abilities)):
            hp, atk, df, spe = stat_line(g, m, a)
            self.shieldDf[i] = stat_line(g, m, "")[2] if a == "stancechange" else df
            self.shieldAtk[i] = stat_line(g, m, "")[1][0] if a == "stancechange" else atk[0]
            self.hp[i], self.atk[i], self.df[i], self.spe[i] = hp, atk, df, spe
            for t in m["types"]:
                self.isType[i, TI[t]] = True
            for t in range(18):
                self.E[i, t] = np.prod([eff1[t, TI[x]] for x in m["types"]])
            stabmult = 2.0 if a == "adaptability" else 1.5
            for t in m["types"]:
                self.stab[i, TI[t]] = stabmult
            if a in ("protean", "libero"):
                self.stab[i, :] = 1.5
            for o in sorted(move_options(g, m, a), key=lambda o: o["id"]):
                t, c = TI[o["type"]], KI[o["kind"]]
                if o["fixed"]:
                    if 100 * o["acc"] > self.fixed[i, t]:
                        self.fixed[i, t] = 100 * o["acc"]; self.fixedmove[i][t] = o["id"]
                    continue
                s = slot(t, c, int(o["contact"]), int(o["prio"] > 0))
                if o["power"] > self.P[i, s]:
                    self.P[i, s] = o["power"]; self.slotmove[i][s] = o["id"]
                    self.rec[i, s], self.drn[i, s] = o["recoil"], o["drain"]
            # defensive ability
            dm = self.dmod[i]
            if a in IMMUNE: dm[TI[IMMUNE[a]]] = 0
            if a == "thickfat": dm[TI["Fire"]] *= .5; dm[TI["Ice"]] *= .5
            if a in ("heatproof", "waterbubble"): dm[TI["Fire"]] *= .5
            if a == "dryskin": dm[TI["Fire"]] *= 1.25
            if a == "purifyingsalt": dm[TI["Ghost"]] *= .5
            if a == "fluffy": dm[:, :, 1] *= .5; dm[TI["Fire"]] *= 2
            if a == "icescales": dm[:, 1, :] *= .5
            if a == "punkrock": pass
            mv = m["moves"]
            self.recover[i] = bool(mv & RECOVERY) or (a == "regenerator" and False)
            for s_ in sorted(mv & set(STATUS_MOVES)):
                st_, acc = STATUS_MOVES[s_]
                acc = mtab.get(s_, {}).get("accuracy", acc * 100)
                acc = 1.0 if acc is True else acc / 100
                if a == "compoundeyes": acc = min(1.0, acc * 1.3)
                if a == "noguard" or (s_ == "toxic" and g >= 6 and "Poison" in m["types"]): acc = 1.0
                # most accurate move per status; Yawn (delayed sleep) only when nothing else induces sleep
                rank = (acc, s_ != "yawn")
                old = self.status[i].get(st_)
                if old is None or rank > (old[0], old[1] != "yawn"):
                    self.status[i][st_] = (acc, s_)
            # plain poison (Poison Powder, Toxic Thread) stands in for Toxic when the Pokemon has no Toxic
            if "psn" in self.status[i] and "tox" not in self.status[i]:
                self.status[i]["tox"] = self.status[i]["psn"]; self.plainpoison[i] = True
        ab = np.array(abilities, dtype=object)
        f = lambda *names: np.isin(ab, names)
        self.weather = np.array([WEATHER_AB.get(a, 0) for a in abilities])
        self.primal = f("desolateland", "primordialsea", "deltastream")
        self.terrain = np.array([TERRAIN_AB.get(a, 0) for a in abilities]) if g >= 7 else np.zeros(n, int)
        self.airlock = f("airlock", "cloudnine")
        self.grounded = ~(self.isType[:, TI["Flying"]] | f("levitate"))
        self.mold = f("moldbreaker", "teravolt", "turboblaze")
        self.scrappy = f("scrappy", "mindseye")
        self.tinted = f("tintedlens")
        self.filter = f("filter", "solidrock", "prismarmor")
        self.wonder = f("wonderguard")
        self.multiscale = f("multiscale", "shadowshield")
        self.sturdy = f("sturdy")
        self.disguise = f("disguise")
        self.iceface = f("iceface")
        self.intimidate = f("intimidate")
        self.intimImmune = f(*INTIM_IMMUNE) if g >= 8 else f("clearbody", "hypercutter", "whitesmoke", "fullmetalbody")
        self.defiant = f("defiant"); self.competitive = f("competitive")
        self.unaware = f("unaware")
        self.download, self.guarddog, self.rattled = f("download"), f("guarddog"), f("rattled") & (g >= 8)
        self.start = {k: np.array([float(START_STAGE.get(a) == k) for a in abilities])
                      for k in ("atk", "spa", "def", "spd", "spe")}
        self.magicguard = f("magicguard")
        self.liquidooze = f("liquidooze")
        self.truant = f("truant")
        self.slowstart, self.defeatist = f("slowstart"), f("defeatist")
        self.speedboost = f("speedboost")
        self.guts = f("guts")
        self.poisonheal = f("poisonheal")
        self.prankster = f("prankster")
        self.statusproof = f("magicbounce", "goodasgold")
        self.simple = f("simple")
        self.swordruin, self.beadsruin = f("swordofruin"), f("beadsofruin")
        self.tabletsruin, self.vesselruin = f("tabletsofruin"), f("vesselofruin")
        self.wxspeed = {SUN: f("chlorophyll"), RAIN: f("swiftswim"), SAND: f("sandrush"), HAIL: f("slushrush")}
        self.solarpower = f("solarpower"); self.sandforce = f("sandforce")
        self.paradox_sun, self.paradox_elec = f("protosynthesis"), f("quarkdrive")
        self.sandimm = self.isType[:, TI["Rock"]] | self.isType[:, TI["Ground"]] | self.isType[:, TI["Steel"]] | f("magicguard", "overcoat", "sandveil", "sandrush", "sandforce")
        self.hailimm = self.isType[:, TI["Ice"]] | f("magicguard", "overcoat", "icebody", "snowcloak", "slushrush")
        # status immunities, keyed by status
        fire, ele, grass = self.isType[:, TI["Fire"]], self.isType[:, TI["Electric"]], self.isType[:, TI["Grass"]]
        pois = self.isType[:, TI["Poison"]] | self.isType[:, TI["Steel"]]
        self.immune = {
            "brn": fire | f("waterveil", "waterbubble", "thermalexchange", "comatose", "purifyingsalt"),
            "tox": pois | f("immunity", "pastelveil", "comatose", "purifyingsalt", "poisonheal"),
            "par": (ele if g >= 6 else np.zeros(n, bool)) | f("limber", "comatose", "purifyingsalt"),
            "slp": f("insomnia", "vitalspirit", "sweetveil", "comatose", "purifyingsalt"),
        }
        # move-specific immunities: powder moves (Grass types and Overcoat, Gen 6+), Thunder Wave (Electric)
        self.powderImm = (grass | f("overcoat")) if g >= 6 else np.zeros(n, bool)
        self.elecImm = (self.E[:, TI["Electric"]] == 0) | f("voltabsorb", "lightningrod", "motordrive")
        self.powder = {k: np.array([d.get(k, (0, ""))[1] in POWDER for d in self.status]) for k in ("slp", "par", "tox", "brn")}
        self.twave = np.array([d.get("par", (0, ""))[1] == "thunderwave" for d in self.status])
        self.immune["psn"] = self.immune["tox"]
        self.guts_burn = self.guts | f("magicguard")
        self._choose_moves(self if field is None else field)
        self.setup_id = [None] * n
        self.setupCost, self.geo = np.zeros(n), np.zeros(n, bool)
        for i, m in enumerate(mons):
            self._choose_setup(i, m["moves"])

    def _choose_setup(self, i, learnset):
        """Best setup move for this Pokemon's attacking category (physical/special share of its best hits)."""
        ph, sp = self.physShare[i], self.specShare[i]
        best = None
        for s_ in sorted(learnset & set(SETUP)):
            b = SETUP[s_]
            val = ph * b.get("atk", 0) + sp * b.get("spa", 0) + .6 * b.get("spe", 0) + .3 * (b.get("def", 0) + b.get("spd", 0)) \
                + self.defShare[i] * b.get("def", 0)
            if s_ == "bellydrum":
                val = 3.5 * ph
            if best is None or val > best[0] + 1e-12:
                best = (val, s_)
        if best and best[0] > 0:
            self.setup[i] = SETUP[best[1]]; self.belly[i] = best[1] == "bellydrum"; self.setup_id[i] = best[1]
            self.setupCost[i] = SETUP_COST.get(best[1], 0.0); self.geo[i] = best[1] == "geomancy"

    def _choose_moves(self, F):
        """Give each Pokemon a fixed set of at most 4 attacks: greedily the ones that maximise its average
        best-move damage (fraction of HP, capped at a KO) over the field F. Trims P/fixed to those moves and
        records each Pokemon's physical / special share of its best hits (used to value setup moves)."""
        n, normal, fighting = self.n, TI["Normal"], TI["Fighting"]
        P, fixed = np.zeros_like(self.P), np.zeros_like(self.fixed)
        self.moveset = [[] for _ in range(n)]
        self.physShare, self.specShare, self.defShare = np.zeros(n), np.zeros(n), np.zeros(n)
        noghost = {t: _eff_no_ghost(F, t) for t in (normal, fighting)}
        for i in range(n):
            slots, ftypes = np.nonzero(self.P[i])[0], np.nonzero(self.fixed[i])[0]
            if not len(slots) and not len(ftypes):
                continue
            t, c, k = slots // (NK * 4), (slots // 4) % NK, (slots // 2) % 2
            tt = np.concatenate([t, ftypes])
            E = F.E[:, tt].T.copy()
            E[:len(slots)][c == KI["freezedry"]] *= np.where(F.isType[:, TI["Water"]], 4.0, 1.0)
            if self.scrappy[i]:
                for r, x in enumerate(tt):
                    if x in noghost:
                        E[r] = noghost[x]
            if self.tinted[i]:
                E = np.where((E < 1) & (E > 0), E * 2, E)
            Ea, Ef = E[:len(slots)], E[len(slots):]
            if self.mold[i]:
                mod = np.ones_like(Ea); wgf = np.ones_like(Ef)
            else:
                mod = F.dmod[:, t, DCLASS[c], k].T * np.where(F.wonder[None, :] & (Ea <= 1), 0, 1.0) \
                    * np.where(F.filter[None, :] & (Ea > 1), .75, 1.0)
                wgf = np.where(F.wonder[None, :] & (Ef <= 1), 0, 1.0)
            ratio = kind_ratio(self.atk[i] * stage(np.array([self.start["atk"][i], self.start["spa"][i]])),
                               self.df[i], F.atk, F.df)
            ratio = np.stack(ratio)[c]
            Da = (42 * self.P[i, slots][:, None] * ratio / 50 + 2) * Ea * self.stab[i, t][:, None] * mod / F.hp
            Df = self.fixed[i, ftypes][:, None] * (Ef > 0) * wgf / F.hp
            D = np.minimum(np.vstack([Da, Df]), 1.0)
            chosen, cur = [], np.zeros(F.n)
            for _ in range(min(4, len(D))):
                gain = np.maximum(D, cur).mean(1)
                gain[chosen] = -1
                j = int(np.argmax(gain))
                if chosen and gain[j] <= cur.mean() + 1e-12:
                    break
                chosen.append(j); cur = np.maximum(cur, D[j])
            for j in chosen:
                if j < len(slots):
                    P[i, slots[j]] = self.P[i, slots[j]]; self.moveset[i].append(self.slotmove[i][slots[j]])
                else:
                    x = ftypes[j - len(slots)]
                    fixed[i, x] = self.fixed[i, x]; self.moveset[i].append(self.fixedmove[i][x])
            top = np.array(chosen)[np.argmax(D[chosen], axis=0)]
            hit = D[chosen].max(0) > 0
            isA = top < len(slots)
            cat = np.where(isA, c[np.minimum(top, len(slots) - 1)] if len(slots) else 0, -1)
            self.physShare[i] = np.mean(hit & (cat == KI["phys"]))
            self.specShare[i] = np.mean(hit & np.isin(cat, [KI["spec"], KI["psyshock"], KI["freezedry"]]))
            self.defShare[i] = np.mean(hit & (cat == KI["bodypress"]))
        self.Pall, self.fixedAll = self.P, self.fixed
        self.P, self.fixed = P, fixed


def kind_ratio(atk, df, fatk, fdf):
    """Attacking / defending stat ratio for each damage kind (KINDS order). atk, df: the attacker's
    (attack, sp. attack) and (defense, sp. defense); fatk, fdf: the defender's (arrays broadcast)."""
    phys, spec = atk[..., 0] / fdf[..., 0], atk[..., 1] / fdf[..., 1]
    return (phys, spec, atk[..., 1] / fdf[..., 0], df[..., 0] / fdf[..., 0], fatk[..., 0] / fdf[..., 0], spec)


def stage(x):
    x = np.clip(x, -6, 6)
    return (2 + np.maximum(x, 0)) / (2 - np.minimum(x, 0))


def pair_damage(R, C, rowLastOnTie=False, clear=False):
    """Expected damage per hit (fraction of the target's HP) for row attacking column.
    Returns dict of (N, N) arrays: phys, spec, fixed, prio_phys, prio_spec, plus weather/terrain matrices.
    rowLastOnTie: at equal Speed the row's weather/terrain comes in last (and stays). clear: the field after
    turn 5, when weather (Gen 6+) and terrain from abilities have run out; primal weather stays."""
    g, nR, nC = R.g, R.n, C.n
    sR, sC = R.spe[:, None], C.spe[None, :]
    rowLast = (sR < sC) | ((sR == sC) & rowLastOnTie)
    # weather: the slower setter's weather stays (it comes in last); primal weather can't be replaced
    Rp, Cp = R.primal[:, None] & np.ones((1, nC), bool), C.primal[None, :] & np.ones((nR, 1), bool)
    wR, wC = R.weather[:, None] * np.ones((1, nC), int), C.weather[None, :] * np.ones((nR, 1), int)
    if clear and g >= 6:
        wR, wC = np.where(Rp, wR, 0), np.where(Cp, wC, 0)
    srcR = (wR != 0) & ((wC == 0) | rowLast)
    srcR = np.where(Rp & ~Cp, True, np.where(Cp & ~Rp, False, srcR))
    w = np.where(srcR, wR, wC)
    wp = np.where(srcR, Rp, Cp) & (w != 0)
    calm = R.airlock[:, None] | C.airlock[None, :]
    w, wp = np.where(calm, 0, w), wp & ~calm
    tR, tC = R.terrain[:, None] * np.ones((1, nC), int), C.terrain[None, :] * np.ones((nR, 1), int)
    if clear:
        tR, tC = tR * 0, tC * 0
    ter = np.where(tR == 0, tC, np.where(tC == 0, tR, np.where(rowLast, tR, tC)))
    terboost = 1.5 if g == 7 else 1.3
    out = {k: np.zeros((nR, nC)) for k in ("phys", "spec", "prio_phys", "prio_spec", "fixed")}
    # attacker stats (pair-level modifiers)
    atkP = R.atk[:, 0][:, None] * np.ones((1, nC))
    atkS = R.atk[:, 1][:, None] * np.ones((1, nC))
    atkP = np.where(C.tabletsruin[None, :] & ~R.tabletsruin[:, None], atkP * .75, atkP)
    atkS = np.where(C.vesselruin[None, :] & ~R.vesselruin[:, None], atkS * .75, atkS)
    atkS = np.where((w == SUN) & R.solarpower[:, None], atkS * 1.5, atkS)
    # paradox abilities in their own field: best attacking stat x1.3
    par = ((w == SUN) & R.paradox_sun[:, None]) | ((ter == ELEC) & R.paradox_elec[:, None])
    phys_best = (R.atk[:, 0] >= R.atk[:, 1])[:, None]
    atkP = np.where(par & phys_best, atkP * 1.3, atkP)
    atkS = np.where(par & ~phys_best, atkS * 1.3, atkS)
    defP = C.df[:, 0][None, :] * np.ones((nR, 1))
    defS = C.df[:, 1][None, :] * np.ones((nR, 1))
    defS = np.where((w == SAND) & C.isType[:, TI["Rock"]][None, :], defS * 1.5, defS)
    if g >= 9:
        defP = np.where((w == HAIL) & C.isType[:, TI["Ice"]][None, :], defP * 1.5, defP)
    defP = np.where(R.swordruin[:, None] & ~C.swordruin[None, :], defP * .75, defP)
    defS = np.where(R.beadsruin[:, None] & ~C.beadsruin[None, :], defS * .75, defS)
    ratio = kind_ratio(np.stack([atkP, atkS], -1), R.df[:, None, :], C.atk[None, :, :], np.stack([defP, defS], -1))
    ooze = np.where(C.liquidooze[None, :], -1.0, 1.0)  # Liquid Ooze: draining it hurts instead

    def keep(key, dmg, s_):
        """Best hit per pair for this key, with that move's recoil / drain share (key_rec, key_drn)."""
        cur = out.setdefault(key, np.zeros((nR, nC)))
        better = dmg > cur
        out[key] = np.where(better, dmg, cur)
        for x, arr in (("_rec", R.rec[:, s_][:, None]), ("_drn", R.drn[:, s_][:, None] * ooze)):
            if arr.any() or key + x in out:
                out[key + x] = np.where(better, arr, out.get(key + x, 0.0))
    ghost, normal, fighting = TI["Ghost"], TI["Normal"], TI["Fighting"]
    flyweak = type_matrix(g)[:, TI["Flying"]] == 2
    for t in range(18):
        Et = C.E[:, t][None, :] * np.ones((nR, 1))
        if t in (normal, fighting):
            ghostmask = C.isType[:, ghost][None, :] & R.scrappy[:, None]
            Et = np.where(ghostmask, _eff_no_ghost(C, t)[None, :], Et)
        Et = np.where(R.tinted[:, None] & (Et < 1) & (Et > 0), Et * 2, Et)
        wmod = np.ones((nR, nC))
        if t == TI["Fire"]:  # Primordial Sea: Fire moves fail
            wmod = np.where(w == SUN, 1.5, np.where(w == RAIN, np.where(wp, 0, .5), 1.0))
        if t == TI["Water"]:  # Desolate Land: Water moves fail
            wmod = np.where(w == RAIN, 1.5, np.where(w == SUN, np.where(wp, 0, .5), 1.0))
        if flyweak[t]:  # Delta Stream: moves super effective on Flying are neutral on its Flying type
            Et = np.where((w == WIND) & C.isType[:, TI["Flying"]][None, :], Et / 2, Et)
        if t in (TI["Rock"], TI["Ground"], TI["Steel"]):
            wmod = np.where((w == SAND) & R.sandforce[:, None], 1.3, 1.0)
        tm = {TI["Electric"]: ELEC, TI["Psychic"]: PSY, TI["Grass"]: GRASSY}.get(t)
        if tm is not None:
            wmod = wmod * np.where((ter == tm) & R.grounded[:, None], terboost, 1.0)
        if t == TI["Dragon"]:
            wmod = wmod * np.where((ter == MISTY) & C.grounded[None, :], .5, 1.0)
        stab = R.stab[:, t][:, None]
        base_eff = Et * wmod * stab
        if R.fixed[:, t].any():
            fx = R.fixed[:, t][:, None] * (Et > 0) / C.hp[None, :]
            fx = np.where(C.wonder[None, :] & ~R.mold[:, None] & (Et <= 1), 0, fx)
            out["fixed"] = np.maximum(out["fixed"], fx)
        for c in range(NK):
            if c == KI["freezedry"]:
                if t != TI["Ice"] or not R.P[:, slot(t, c, 0, 0)].any():
                    continue
                Ec = Et * np.where(C.isType[:, TI["Water"]], 4.0, 1.0)[None, :]
                eff = Ec * wmod * stab
            else:
                Ec, eff = Et, base_eff
            for k in (0, 1):
                dm = np.where(R.mold[:, None], 1.0, C.dmod[:, t, DCLASS[c], k][None, :])
                wg = np.where(C.wonder[None, :] & ~R.mold[:, None] & (Ec <= 1), 0, 1.0)
                fl = np.where(C.filter[None, :] & ~R.mold[:, None] & (Ec > 1), .75, 1.0)
                mult = eff * dm * wg * fl
                for p in (0, 1):
                    s_ = slot(t, c, k, p)
                    P = R.P[:, s_]
                    if not P.any():
                        continue
                    dmg = (42 * P[:, None] * ratio[c] / 50 + 2) * mult * (P[:, None] > 0) / C.hp[None, :]
                    keep(KINDS[c], dmg, s_)
                    if p:
                        # Psychic Terrain blocks priority on grounded targets
                        blocked = (ter == PSY) & C.grounded[None, :]
                        keep("prio_" + KINDS[c], np.where(blocked, 0, dmg), s_)
    out["w"], out["wp"], out["ter"] = w, wp, ter
    out["_src"] = (R, C, rowLastOnTie, clear)
    return out


def variant(d, swap=False, clear=False):
    """The damage table d (from pair_damage) with the speed-tie field order swapped and/or the field cleared."""
    R, C, rowLast, clr = d["_src"]
    key = (rowLast ^ swap, clr or clear)
    if key == (rowLast, clr):
        return d
    cache = d.setdefault("_variants", {})
    if key not in cache:
        cache[key] = pair_damage(R, C, *key)
    return cache[key]


_eff_cache = {}


def _eff_no_ghost(C, t):
    """Effectiveness of type t on the column side, treating Ghost as neutral (Scrappy)."""
    if not hasattr(C, "_noghost"):
        C._noghost = {}
    _eff_cache = C._noghost
    key = t
    if key not in _eff_cache:
        eff1 = type_matrix(C.g)
        # recompute per Pokemon without the ghost immunity
        vals = []
        for i in range(C.n):
            types = np.where(C.isType[i])[0]
            vals.append(np.prod([1.0 if x == TI["Ghost"] else eff1[t, x] for x in types]))
        _eff_cache[key] = np.array(vals)
    return _eff_cache[key]


ATTACK, SETUP1, SETUP2, SLP, BRN, PAR, TOX = range(7)


def opening_stages(A, B, me, foe):
    """Stat stages side A starts with against B (me/foe broadcast A's and B's per-Pokemon arrays to pairs):
    its own entry boosts, Intimidate (with Defiant / Competitive / Guard Dog / Rattled), Download."""
    bo = {k: me(A.start[k]).astype(float) for k in ("atk", "spa", "def", "spd", "spe")}
    mult = np.where(me(A.simple), 2, 1)
    intim = foe(B.intimidate) & ~me(A.intimImmune)
    bo["atk"] = bo["atk"] - intim + 2 * (intim & me(A.defiant)) + (foe(B.intimidate) & me(A.guarddog))
    bo["spa"] = bo["spa"] + 2 * (intim & me(A.competitive))
    bo["spe"] = bo["spe"] + (foe(B.intimidate) & me(A.rattled))
    lowdef = foe(B.df[:, 0] < B.df[:, 1])  # Download raises Attack if the foe's Defense is lower, else Sp. Atk
    bo["atk"] = bo["atk"] + (me(A.download) & lowdef)
    bo["spa"] = bo["spa"] + (me(A.download) & ~lowdef)
    return {k: np.clip(v * mult, -6, 6) for k, v in bo.items()}


def simulate(R, C, dRC, dCR, stratR, stratC, rollR=.925, rollC=.925, rowFirstOnTie=True, turns=15,
             hitR=True, hitC=True, full=False):
    """Run the duel for every (row, column) pair. Returns row's score (1 win, 0 loss, .5 draw) as (N, N).
    hitR/hitC: whether each side's status move lands (bool or (N, N) mask). full: also return (hpR, hpC)."""
    g = R.g
    shape = (R.n, C.n)
    # the side that wins a speed tie comes in first, so the other side's weather / terrain is the one that stays
    if rowFirstOnTie:
        dCR = variant(dCR, swap=True)
    else:
        dRC = variant(dRC, swap=True)
    hpR, hpC = np.ones(shape), np.ones(shape)
    rowB = lambda arr: np.broadcast_to(arr[:, None], shape)
    colB = lambda arr: np.broadcast_to(arr[None, :], shape)
    boR, boC = opening_stages(R, C, rowB, colB), opening_stages(C, R, colB, rowB)
    stR, stC = np.zeros(shape, int), np.zeros(shape, int)  # 0 none, 1 brn, 2 par, 3 tox, 4 slp, 5 psn
    sleepR, sleepC = np.zeros(shape), np.zeros(shape)
    drowsyR, drowsyC = np.zeros(shape), np.zeros(shape)  # Yawn: turns until the target falls asleep
    toxR, toxC = np.zeros(shape), np.zeros(shape)
    chargeR, chargeC = np.zeros(shape, bool), np.zeros(shape, bool)  # Geomancy charged
    sizeRC = colB(C.hp) / rowB(R.hp)  # column's max HP in row HPs
    bladeR, bladeC = ~rowB(R.stance), ~colB(C.stance)  # Stance Change: Blade Forme once it has attacked
    shieldR = np.broadcast_to((R.disguise | R.iceface)[:, None], shape).copy()
    shieldC = np.broadcast_to((C.disguise | C.iceface)[None, :], shape).copy()
    setupsR, setupsC = np.zeros(shape), np.zeros(shape)
    usedStatusR, usedStatusC = np.zeros(shape, bool), np.zeros(shape, bool)
    doneR, doneC = np.zeros(shape, bool), np.zeros(shape, bool)  # fainted
    parSpeed = .5 if g >= 7 else .25
    chipBurn = 1 / 16 if g >= 7 else 1 / 8

    # per-side helpers expressed for "self" = row (A) or column (B); we write explicit code for both sides
    rowB = lambda arr: np.broadcast_to(arr[:, None], shape)
    colB = lambda arr: np.broadcast_to(arr[None, :], shape)
    yawnR = rowB(np.array([d.get("slp", (0, ""))[1] == "yawn" for d in R.status]))
    yawnC = colB(np.array([d.get("slp", (0, ""))[1] == "yawn" for d in C.status]))

    def setup_boosts(side_setup, bcast):
        out = {k: np.zeros(len(side_setup)) for k in ("atk", "spa", "def", "spd", "spe")}
        for i, s in enumerate(side_setup):
            if s:
                for k, v in s.items():
                    out[k][i] = v
        return {k: bcast(v) for k, v in out.items()}
    sbR, sbC = setup_boosts(R.setup, rowB), setup_boosts(C.setup, colB)
    hasSetupR, hasSetupC = rowB(np.array([s is not None for s in R.setup])), colB(np.array([s is not None for s in C.setup]))
    statusCodes = {SLP: ("slp", 4), BRN: ("brn", 1), PAR: ("par", 2), TOX: ("tox", 3)}

    def can_status(side, other_immune_b, strat_code):
        st_, _ = statusCodes[strat_code]
        has = np.array([st_ in d for d in side.status])
        return has

    hasStR = {k: rowB(np.array([statusCodes[k][0] in d for d in R.status])) for k in statusCodes}
    hasStC = {k: colB(np.array([statusCodes[k][0] in d for d in C.status])) for k in statusCodes}
    immR = {k: rowB(R.immune[statusCodes[k][0]] | R.statusproof) | (colB(C.powder[statusCodes[k][0]]) & rowB(R.powderImm))
            for k in statusCodes}
    immC = {k: colB(C.immune[statusCodes[k][0]] | C.statusproof) | (rowB(R.powder[statusCodes[k][0]]) & colB(C.powderImm))
            for k in statusCodes}
    immR[PAR] = immR[PAR] | (colB(C.twave) & rowB(R.elecImm))
    immC[PAR] = immC[PAR] | (rowB(R.twave) & colB(C.elecImm))
    if g >= 7:
        immR_pr = rowB(R.isType[:, TI["Dark"]])  # Prankster status fails on Dark types
        immC_pr = colB(C.isType[:, TI["Dark"]])
    else:
        immR_pr = immC_pr = np.zeros(shape, bool)

    for turn in range(1, turns + 1):
        alive = ~(doneR | doneC)
        if not alive.any():
            break
        if turn == 6 and g >= 6:  # ability weather (Gen 6+) and terrain last 5 turns
            dRC, dCR = variant(dRC, clear=True), variant(dCR, clear=True)
        w, wp, ter = dRC["w"], dRC["wp"], dRC["ter"]
        # ---- current damage per hit, with boosts
        def dmg(d, boA, boB, stA, unawareA, unawareB, roll, gutsA, offA, guardB):
            """A's damage per hit on B: (main, priority, (main without fixed, fixed), (recoil, drain) of the
            main hit, (recoil, drain) of the priority hit)."""
            up = lambda bo, k, ignore: stage(np.where(ignore, 0, bo[k]))
            burn = np.where((stA == 1) & ~gutsA, .5, np.where((stA == 1) & gutsA, 1.5, 1.0))
            para = np.where(stA == 2, .75, 1.0)
            dDef, dSpd = up(boB, "def", unawareA), up(boB, "spd", unawareA)
            spec = up(boA, "spa", unawareB) / dSpd * offA[1] * guardB[1]
            scale = {"phys": up(boA, "atk", unawareB) / dDef * offA[0] * guardB[0] * burn, "spec": spec,
                     "psyshock": up(boA, "spa", unawareB) / dDef * offA[1] * guardB[0],
                     "bodypress": up(boA, "def", unawareB) / dDef * guardB[0] * burn,
                     "foulplay": up(boB, "atk", unawareA) / dDef * guardB[0] * guardB[2] * burn, "freezedry": spec}

            def best(prefix):
                top, rec, drn = 0.0, 0.0, 0.0
                track = any(prefix + k + x in d for k in KINDS for x in ("_rec", "_drn"))
                for k in KINDS:
                    if prefix + k in d:
                        v = d[prefix + k] * scale[k]
                        if track:
                            better = v > top
                            rec = np.where(better, d.get(prefix + k + "_rec", 0.0), rec)
                            drn = np.where(better, d.get(prefix + k + "_drn", 0.0), drn)
                        top = np.maximum(top, v)
                return top * roll, rec, drn
            hit, rec, drn = best("")
            prio, recP, drnP = best("prio_")
            main = np.maximum(hit, d["fixed"]) * para
            # Seismic Toss / Night Shade: no damage roll, and not cut by Multiscale
            return main, prio * para, (hit * para, d["fixed"] * para), (rec, drn), (recP, drnP)
        gutsR, gutsC = rowB(R.guts), colB(C.guts)

        def guard(B, bcast, bladeB):
            """Damage multipliers (physical, special, Foul Play's use of B's Attack) on B while Aegislash is
            still in Shield Forme."""
            return tuple(np.where(bladeB, 1.0, bcast(B.df[:, c] / B.shieldDf[:, c])) for c in (0, 1)) + \
                (np.where(bladeB, 1.0, bcast(B.shieldAtk / B.atk[:, 0])),)

        def offense(A, bcast, hpA):
            """Attack-stat multipliers (physical, special) from Slow Start (first 5 turns) and Defeatist."""
            slow = bcast(A.slowstart) & (turn <= 5)
            weak = bcast(A.defeatist) & (hpA <= .5)
            return np.where(slow | weak, .5, 1.0), np.where(weak, .5, 1.0)

        dCRt = {k: v.T for k, v in dCR.items() if not k.startswith("_") and k not in ("w", "wp", "ter")}

        def hits():
            """Each side's damage per hit (main, priority, (normal, fixed)) in the current state."""
            return (dmg(dRC, boR, boC, stR, rowB(R.unaware), colB(C.unaware), rollR, gutsR, offense(R, rowB, hpR),
                        guard(C, colB, bladeC)),
                    dmg(dCRt, boC, boR, stC, colB(C.unaware), rowB(R.unaware), rollC, gutsC, offense(C, colB, hpC),
                        guard(R, rowB, bladeR)))
        hitsR, hitsC = hits()
        # speed
        spR = rowB(R.spe) * stage(boR["spe"]) * np.where(stR == 2, parSpeed, 1.0)
        spC = colB(C.spe) * stage(boC["spe"]) * np.where(stC == 2, parSpeed, 1.0)
        if turn <= 5:
            spR = np.where(rowB(R.slowstart), spR * .5, spR)
            spC = np.where(colB(C.slowstart), spC * .5, spC)
        for wx, mask in R.wxspeed.items():
            spR = np.where((w == wx) & rowB(mask), spR * 2, spR)
        for wx, mask in C.wxspeed.items():
            spC = np.where((w == wx) & colB(mask), spC * 2, spC)
        if turn > 1:
            spR = np.where(rowB(R.speedboost), spR * stage(np.full(shape, min(turn - 1, 6))), spR)
            spC = np.where(colB(C.speedboost), spC * stage(np.full(shape, min(turn - 1, 6))), spC)

        # ---- choose actions: 0 attack-main, 1 attack-prio, 2 setup, 3 status, 4 recover, 5 nothing
        def choose(strat, hpS, hpO, mainS, prioS, mainO, hasSetup, setups, usedStatus, hasSt, immO, stO, sleepS, truant, recover, spS, spO, cost):
            act = np.zeros(shape, int)
            # status first
            for code in (SLP, BRN, PAR, TOX):
                m = (strat == code) & ~usedStatus & hasSt[code] & ~immO[code] & (stO == 0)
                act = np.where(m, 3, act)
            want = np.where(strat == SETUP1, 1, np.where(strat == SETUP2, 2, 0))
            m = (act == 0) & hasSetup & (setups < want) & (hpS > cost)
            act = np.where(m, 2, act)
            # heal when losing the race and healing out-paces the damage taken
            m = (act == 0) & rowlike(recover) & (hpS <= .5) & (mainO < .45)
            act = np.where(m, 4, act)
            # priority: when it finishes the foe or I'd be KOd before moving
            usePrio = (prioS > 0) & ((prioS >= hpO) | ((spO > spS) & (mainO >= hpS))) & (act == 0)
            act = np.where(usePrio, 1, act)
            act = np.where(sleepS > 0, 5, act)
            if truant is not None:
                act = np.where(truant & (turn % 2 == 0), 5, act)
            return act

        def rowlike(x):
            return x
        (mainR, prioR, *_), (mainC, prioC, *_) = hitsR, hitsC
        actR = choose(stratR, hpR, hpC, mainR, prioR, mainC, hasSetupR, setupsR, usedStatusR, hasStR, immC, stC, sleepR,
                      rowB(R.truant), rowB(R.recover), spR, spC, rowB(R.setupCost))
        actC = choose(stratC, hpC, hpR, mainC, prioC, mainR, hasSetupC, setupsC, usedStatusC, hasStC, immR, stR, sleepC,
                      colB(C.truant), colB(C.recover), spC, spR, colB(C.setupCost))
        prR = np.where(actR == 1, 1, 0) + np.where((actR == 3) & rowB(R.prankster), 1, 0)
        prC = np.where(actC == 1, 1, 0) + np.where((actC == 3) & colB(C.prankster), 1, 0)
        rowFirst = (prR > prC) | ((prR == prC) & ((spR > spC) | ((spR == spC) & rowFirstOnTie)))

        def act_on(actA, hpA, hpB, hitsA, sizeAB, boA, sbA, setupsA, usedA, stB, sleepB, toxB, shieldB, multiB, sturdyB,
                   hasStA, immB, prankA, prImmB, simpleA, bellyA, recoverA, hitA, yawnA, drowsyB, moldA, plainA, costA, geoA, chargeA, mask):
            """Apply A's action to B where mask. Returns updated arrays."""
            # attacks
            mainA, prioA, fixA, rdM, rdP = hitsA
            hit = mask & ((actA == 0) | (actA == 1))
            d = np.where(actA == 1, prioA, mainA)
            ms = multiB & (hpB >= 1)
            if ms.any():
                d = np.where(ms & (actA == 1), d * .5, d)
                d = np.where(ms & (actA == 0), np.maximum(fixA[0] * .5, fixA[1]), d)
            if shieldB.any():
                blocked = hit & shieldB & ~moldA & (d > 0)  # Disguise / Ice Face (Mold Breaker ignores them)
                d = np.where(blocked, 1 / 8 if g >= 8 else 0, d)
                shieldB = np.where(blocked, False, shieldB)
            newhp = hpB - np.where(hit, d, 0)
            if any(np.ndim(x) for x in rdM + rdP):
                # recoil / drain: a share of the HP actually taken, in the user's own HP (none for fixed damage)
                tossed = (actA == 0) & (fixA[1] >= fixA[0] * np.where(ms, .5, 1))
                rec = np.where(actA == 1, rdP[0], np.where(tossed, 0, rdM[0]))
                drn = np.where(actA == 1, rdP[1], np.where(tossed, 0, rdM[1]))
                dealt = np.where(hit, np.minimum(d, np.maximum(hpB, 0)), 0) * sizeAB
                hpA = np.minimum(1, hpA - (rec - drn) * dealt)
            survive = hit & sturdyB & (hpB >= 1) & (newhp <= 0)
            newhp = np.where(survive, .01, newhp)
            hpB = newhp
            # setup
            su = mask & (actA == 2)
            if su.any():
                charging = su & geoA & ~chargeA  # Geomancy: charges on the first turn, boosts on the second
                chargeA[...] = np.where(su & geoA, ~chargeA, chargeA)
                su = su & ~charging
                for k in boA:
                    inc = sbA[k] * np.where(simpleA, 2, 1)
                    boA[k] = np.where(su, np.clip(boA[k] + np.where(bellyA & (k == "atk"), 6, inc), -6, 6), boA[k])
                hpA = np.where(su, hpA - costA, hpA)  # Belly Drum, Fillet Away, Clangorous Soul
                setupsA = setupsA + su
            # status
            st = mask & (actA == 3)
            if st.any():
                usedA = usedA | st
                for code, (name, val) in statusCodes.items():
                    ok = st & hitA & hasStA[code] & ~immB[code] & (stB == 0) & ~(prankA & prImmB)
                    # pick the first applicable status in strategy order: handled by strategy (one code per pair)
                    ok = ok & (stratOf == code)
                    if code == SLP:  # Yawn only makes the target drowsy; it falls asleep at the end of next turn
                        drowsyB = np.where(ok & yawnA & (drowsyB == 0), 2, drowsyB)
                        ok = ok & ~yawnA
                    stB = np.where(ok, np.where(plainA, 5, val) if code == TOX else val, stB)
                    sleepB = np.where(ok & (val == 4), 2.0, sleepB)
            # recover
            rc = mask & (actA == 4)
            if rc.any():
                hpA = np.where(rc, np.minimum(1, hpA + .5), hpA)
            return hpA, hpB, setupsA, usedA, stB, sleepB, shieldB, drowsyB

        # first mover then second mover (if still alive)
        for first in (True, False):
            if not first:
                # the second mover acts in the state the first mover left: newly asleep can't move, newly
                # paralysed/burned or freshly boosted/defended changes the hit
                hitsR, hitsC = hits()
                actR = np.where((stR == 4) & (sleepR > 0), 5, actR)
                actC = np.where((stC == 4) & (sleepC > 0), 5, actC)
            for side in ("R", "C"):
                goes = rowFirst if side == "R" else ~rowFirst
                mask = alive & (goes if first else ~goes)
                if side == "R":
                    mask = mask & (hpR > 0) & (hpC > 0)
                    stratOf = stratR
                    hpR, hpC, setupsR, usedStatusR, stC, sleepC, shieldC, drowsyC = act_on(
                        actR, hpR, hpC, hitsR, sizeRC, boR, sbR, setupsR, usedStatusR, stC, sleepC, toxC, shieldC,
                        colB(C.multiscale) & ~rowB(R.mold), colB(C.sturdy) & ~rowB(R.mold), hasStR, immC, rowB(R.prankster), immC_pr,
                        rowB(R.simple), rowB(R.belly), rowB(R.recover), hitR, yawnR, drowsyC, rowB(R.mold), rowB(R.plainpoison),
                        rowB(R.setupCost), rowB(R.geo), chargeR, mask)
                    bladeR = bladeR | (mask & (actR <= 1))
                else:
                    mask = mask & (hpR > 0) & (hpC > 0)
                    stratOf = stratC
                    hpC, hpR, setupsC, usedStatusC, stR, sleepR, shieldR, drowsyR = act_on(
                        actC, hpC, hpR, hitsC, 1 / sizeRC, boC, sbC, setupsC, usedStatusC, stR, sleepR, toxR, shieldR,
                        rowB(R.multiscale) & ~colB(C.mold), rowB(R.sturdy) & ~colB(C.mold), hasStC, immR, colB(C.prankster), immR_pr,
                        colB(C.simple), colB(C.belly), colB(C.recover), hitC, yawnC, drowsyR, colB(C.mold), colB(C.plainpoison),
                        colB(C.setupCost), colB(C.geo), chargeC, mask)
                    bladeC = bladeC | (mask & (actC <= 1))
                # mutations of dicts boR/boC happen in place
        # sleep counters tick for those who were asleep this turn
        sleepR = np.where(actR == 5, np.maximum(sleepR - 1, 0), sleepR)
        sleepC = np.where(actC == 5, np.maximum(sleepC - 1, 0), sleepC)
        stR = np.where((stR == 4) & (sleepR == 0), 0, stR)
        stC = np.where((stC == 4) & (sleepC == 0), 0, stC)
        # Yawn: drowsy Pokemon fall asleep at the end of the turn after the Yawn (if still status-free)
        def fall_asleep(drowsy, st_, sleep, imm):
            falls = (drowsy == 1) & (st_ == 0) & ~imm
            return np.maximum(drowsy - 1, 0), np.where(falls, 4, st_), np.where(falls, 2.0, sleep)
        drowsyR, stR, sleepR = fall_asleep(drowsyR, stR, sleepR, immR[SLP])
        drowsyC, stC, sleepC = fall_asleep(drowsyC, stC, sleepC, immC[SLP])
        # end of turn: weather, burn, toxic, grassy terrain
        live = alive & (hpR > 0) & (hpC > 0)
        for hpX, stX, toxX, mgX, sandX, hailX, phX, grX, nm in (
                (hpR, stR, toxR, rowB(R.magicguard), rowB(R.sandimm), rowB(R.hailimm), rowB(R.poisonheal), rowB(R.grounded), "R"),
                (hpC, stC, toxC, colB(C.magicguard), colB(C.sandimm), colB(C.hailimm), colB(C.poisonheal), colB(C.grounded), "C")):
            chip = np.zeros(shape)
            wchip = w if (g < 6 or turn <= 4) else np.where(wp, w, 0)  # no chip on the turn the weather ends
            chip += np.where((wchip == SAND) & ~sandX, 1 / 16, 0)
            if g <= 8:
                chip += np.where((wchip == HAIL) & ~hailX, 1 / 16, 0)
            chip += np.where((stX == 1) & ~mgX, chipBurn, 0)
            toxX += (stX == 3)
            chip += np.where((stX == 3) & ~mgX & ~phX, toxX / 16, 0)
            chip += np.where((stX == 5) & ~mgX & ~phX, 1 / 8, 0)  # plain poison
            chip -= np.where(((stX == 3) | (stX == 5)) & phX, 1 / 8, 0)
            chip -= np.where((ter == GRASSY) & grX, 1 / 16, 0)
            if LEFTOVERS:
                chip -= 1 / 16
            new = np.minimum(1, hpX - np.where(live, chip, 0))
            if nm == "R":
                hpR = np.where(live, new, hpR)
            else:
                hpC = np.where(live, new, hpC)
        doneR = doneR | (hpR <= 0)
        doneC = doneC | (hpC <= 0)

    score = np.where(doneC & ~doneR, 1.0, np.where(doneR & ~doneC, 0.0, .5))
    undecided = ~doneR & ~doneC
    score = np.where(undecided, np.where(hpR > hpC + 1e-9, 1.0, np.where(hpC > hpR + 1e-9, 0.0, .5)), score)
    return (score, hpR, hpC) if full else score


STATUS_OF = {SLP: "slp", BRN: "brn", PAR: "par", TOX: "tox"}


def status_accuracy(S, strat, rows):
    """(N, N) chance that side S's status move for the strategy in each pair lands (1 where it uses none)."""
    acc = np.ones(strat.shape)
    for code, name in STATUS_OF.items():
        a = np.array([d.get(name, (1.0, ""))[0] for d in S.status])
        acc = np.where(strat == code, a[:, None] if rows else a[None, :], acc)
    return acc


def expected_score(R, C, dRC, dCR, stratR, stratC, settings):
    """Row's score averaged over the damage-roll/speed-tie settings and over each side's status move
    hitting or missing (weighted by its accuracy)."""
    accR, accC = status_accuracy(R, stratR, True), status_accuracy(C, stratC, False)
    branches = [(hR, hC) for hR in (True, False) for hC in (True, False)
                if (hR or (accR < 1).any()) and (hC or (accC < 1).any())]
    total = 0
    for hR, hC in branches:
        p = (accR if hR else 1 - accR) * (accC if hC else 1 - accC)
        sims = np.mean([simulate(R, C, dRC, dCR, stratR, stratC, a, b, t, hitR=hR, hitC=hC) for a, b, t in settings], axis=0)
        total = total + p * sims
    return total


def duel_matrix(g, mons, abilities_row, abilities_col=None, quick=False, mons_col=None):
    """Expected score of row vs column, with best-response strategies on both sides.

    Production: rows and columns can be different Pokemon (mons_col, the field); by default they're the same.
    The column side's movesets are tuned against itself and the rows' against the columns, so a row that is
    also a column gets exactly the research's square-matrix result."""
    if mons_col is None and abilities_col is None:
        R = C = Side(g, mons, abilities_row)
    else:  # both sides tune their movesets against the column field
        C = Side(g, mons if mons_col is None else mons_col, abilities_row if abilities_col is None else abilities_col)
        R = Side(g, mons, abilities_row, field=C)
    dRC, dCR = pair_damage(R, C), pair_damage(C, R)
    n = len(mons)
    settings = [(.925, .925, True), (.925, .925, False)] if quick else \
        [(.925, .925, True), (.925, .925, False), (.85, 1.0, True), (1.0, .85, False)]
    shape = (R.n, C.n)
    att = np.full(shape, ATTACK)

    def run(sR, sC):
        return expected_score(R, C, dRC, dCR, sR, sC, settings)
    # best response of the row against a column that just attacks
    base = run(att, att)
    best, bestStrat = base.copy(), att.copy()
    for s in (SETUP1, SETUP2, SLP, BRN, PAR, TOX):
        v = run(np.full(shape, s), att)
        better = v > best + 1e-9
        best, bestStrat = np.where(better, v, best), np.where(better, s, bestStrat)
    if C is R:
        colStrat = bestStrat.T
    else:
        # column's best response against an attacking row
        bestC, colStrat = 1 - base, att.copy()
        for s in (SETUP1, SETUP2, SLP, BRN, PAR, TOX):
            v = 1 - run(att, np.full(shape, s))
            better = v > bestC + 1e-9
            bestC, colStrat = np.where(better, v, bestC), np.where(better, s, colStrat)
    final = run(bestStrat, colStrat)
    # Imposter: Ditto transforms into an exact copy of its foe, so every duel is even
    final[np.array([a == "imposter" for a in R.ab]), :] = .5
    final[:, np.array([a == "imposter" for a in C.ab])] = .5
    return final


def default_abilities(g, mons):
    """Each Pokemon's highest-rated ability (Showdown's ability ratings)."""
    abr = gendata(g)["abilities"]
    return [max(m["abil"], key=lambda a: abr.get(a, {}).get("rating", 0)) if m["abil"] else "" for m in mons]


def choose_abilities(g, mons):
    """Each Pokemon's best ability: the one with the highest average score against the field (on default
    abilities). Ties keep the earlier slot; Imposter always wins (Ditto is useless without it)."""
    default = default_abilities(g, mons)
    best, bestScore = list(default), None
    for k in range(3):
        rowab = [m["abil"][k] if len(m["abil"]) > k else default[i] for i, m in enumerate(mons)]
        W = duel_matrix(g, mons, rowab, default, quick=True)
        np.fill_diagonal(W, np.nan)
        sc = np.nanmean(W, axis=1)
        if bestScore is None:
            bestScore, best = sc.copy(), list(rowab)
            continue
        for i in range(len(mons)):
            if sc[i] > bestScore[i] + 1e-9:
                bestScore[i], best[i] = sc[i], rowab[i]
    return ["imposter" if "imposter" in m["abil"] else a for m, a in zip(mons, best)]
