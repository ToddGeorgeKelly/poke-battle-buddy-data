"""Vectorised 1-v-1 duel between every ordered pair of Pokemon in one generation.

Both sides: level 100, 31 IVs, 84 EVs in every stat, neutral nature, no item (NFE Pokemon get Eviolite in Gen 5+).
Each turn a side attacks with its best move against this opponent (or a priority move when that's better),
heals with reliable recovery when it's losing the damage race, and may open with a setup or status move when
that wins it the matchup (best response, chosen per opponent).
"""
import numpy as np
from bbrlib import *

# ------------------------------------------------------------------ per-side tables
IMMUNE = {"levitate": "Ground", "eartheater": "Ground", "flashfire": "Fire", "wellbakedbody": "Fire",
          "voltabsorb": "Electric", "lightningrod": "Electric", "motordrive": "Electric", "waterabsorb": "Water",
          "stormdrain": "Water", "dryskin": "Water", "sapsipper": "Grass"}
SUN, RAIN, SAND, HAIL = 1, 2, 3, 4
WEATHER_AB = {"drought": SUN, "desolateland": SUN, "orichalcumpulse": SUN, "drizzle": RAIN, "primordialsea": RAIN,
              "sandstream": SAND, "snowwarning": HAIL}
ELEC, PSY, GRASSY, MISTY = 1, 2, 3, 4
TERRAIN_AB = {"electricsurge": ELEC, "hadronengine": ELEC, "psychicsurge": PSY, "grassysurge": GRASSY,
              "mistysurge": MISTY, "seedsower": 0}
INTIM_IMMUNE = {"clearbody", "hypercutter", "whitesmoke", "fullmetalbody", "innerfocus", "oblivious", "owntempo",
                "scrappy", "guarddog", "mirrorarmor"}
NSLOT = 18 * 2 * 2 * 2  # type, category, contact, priority


def slot(t, c, k, p):
    return ((t * 2 + c) * 2 + k) * 2 + p


def stat_line(g, mon, ability):
    b = list(mon["stats"])
    if ability == "stancechange":  # attacks from Blade Forme
        b = [b[0], b[3], b[1], b[3], b[2], b[5]]
        b = [60, 140, 50, 140, 50, 60] if mon["id"].startswith("aegislash") else b
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
    if ability == "slowstart": atk *= .5; spe *= .5
    if ability == "defeatist": atk *= .75; spa *= .75
    if ability == "orichalcumpulse": atk *= 4 / 3
    if ability == "hadronengine": spa *= 4 / 3
    if mon["nfe"] and g >= 5: df *= 1.5; spd *= 1.5
    if ability == "intrepidsword": atk *= 1.5
    if ability == "dauntlessshield": df *= 1.5
    if ability == "download": atk *= 1.25; spa *= 1.25
    if ability == "embodyaspectteal": spe *= 1.5
    if ability == "embodyaspecthearthflame": atk *= 1.5
    if ability == "embodyaspectwellspring": spd *= 1.5
    if ability == "embodyaspectcornerstone": df *= 1.5
    return float(hp), np.array([atk, spa]), np.array([df, spd]), spe


class Side:
    """Everything about one configuration of the roster (each Pokemon with one chosen ability)."""

    def __init__(self, g, mons, abilities):
        self.g, self.n = g, len(mons)
        n = self.n
        eff1 = type_matrix(g)
        self.hp = np.zeros(n); self.atk = np.zeros((n, 2)); self.df = np.zeros((n, 2)); self.spe = np.zeros(n)
        self.P = np.zeros((n, NSLOT)); self.fixed = np.zeros((n, 18))
        self.stab = np.ones((n, 18)); self.E = np.ones((n, 18))  # E: how hard each type hits it
        self.dmod = np.ones((n, 18, 2, 2))  # defender ability multiplier by type, category, contact
        self.ab = list(abilities)
        self.isType = np.zeros((n, 18), bool)
        self.recover = np.zeros(n, bool); self.setup = [None] * n; self.status = [dict() for _ in range(n)]
        self.belly = np.zeros(n, bool)
        for i, (m, a) in enumerate(zip(mons, abilities)):
            hp, atk, df, spe = stat_line(g, m, a)
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
            for o in move_options(g, m, a):
                t, c = TI[o["type"]], 0 if o["cat"] == "Physical" else 1
                if o["fixed"]:
                    self.fixed[i, t] = max(self.fixed[i, t], 100 * o["acc"])
                    continue
                s = slot(t, c, int(o["contact"]), int(o["prio"] > 0))
                self.P[i, s] = max(self.P[i, s], o["power"])
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
            best = None
            for s_ in mv & set(SETUP):
                b = SETUP[s_]
                val = max(b.get("atk", 0), b.get("spa", 0)) + .6 * b.get("spe", 0) + .3 * (b.get("def", 0) + b.get("spd", 0))
                if s_ == "bellydrum": val = 3.5
                if best is None or val > best[0]: best = (val, s_)
            if best and best[0] > 0:
                self.setup[i] = SETUP[best[1]]; self.belly[i] = best[1] == "bellydrum"
            for s_ in mv & set(STATUS_MOVES):
                st_, acc = STATUS_MOVES[s_]
                if a == "noguard" or (s_ == "toxic" and g >= 6 and "Poison" in m["types"]): acc = 1.0
                if acc >= .75 and acc > self.status[i].get(st_, (0, ""))[0]:
                    self.status[i][st_] = (acc, s_)
        ab = np.array(abilities, dtype=object)
        f = lambda *names: np.isin(ab, names)
        self.weather = np.array([WEATHER_AB.get(a, 0) for a in abilities])
        self.primal = f("desolateland", "primordialsea")
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
        self.magicguard = f("magicguard")
        self.truant = f("truant")
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
            "slp": f("insomnia", "vitalspirit", "sweetveil", "comatose", "purifyingsalt") | (grass if g >= 6 else np.zeros(n, bool)),
        }
        self.immune["psn"] = self.immune["tox"]
        self.guts_burn = self.guts | f("magicguard")


def stage(x):
    x = np.clip(x, -6, 6)
    return np.where(x >= 0, (2 + x) / 2, 2 / (2 - x))


def pair_damage(R, C):
    """Expected damage per hit (fraction of the target's HP) for row attacking column.
    Returns dict of (N, N) arrays: phys, spec, fixed, prio_phys, prio_spec, plus weather/terrain matrices."""
    g, nR, nC = R.g, R.n, C.n
    sR, sC = R.spe[:, None], C.spe[None, :]
    # weather: the slower setter's weather stays (it comes in last); primal weather can't be replaced
    wR, wC = R.weather[:, None] * np.ones((1, nC), int), C.weather[None, :] * np.ones((nR, 1), int)
    w = np.where(wR == 0, wC, np.where(wC == 0, wR, np.where(sR < sC, wR, wC)))
    w = np.where(R.primal[:, None] & ~C.primal[None, :], wR, np.where(C.primal[None, :] & ~R.primal[:, None], wC, w))
    w = np.where(R.airlock[:, None] | C.airlock[None, :], 0, w)
    tR, tC = R.terrain[:, None] * np.ones((1, nC), int), C.terrain[None, :] * np.ones((nR, 1), int)
    ter = np.where(tR == 0, tC, np.where(tC == 0, tR, np.where(sR < sC, tR, tC)))
    terboost = 1.5 if g == 7 else 1.3
    out = {k: np.zeros((nR, nC)) for k in ("phys", "spec", "prio_phys", "prio_spec", "fixed")}
    # attacker stats (pair-level modifiers)
    atkP = R.atk[:, 0][:, None] * np.ones((1, nC))
    atkS = R.atk[:, 1][:, None] * np.ones((1, nC))
    intim = C.intimidate[None, :] & ~R.intimImmune[:, None]
    atkP = np.where(intim, atkP * np.where(R.defiant[:, None], 4 / 3, 2 / 3), atkP)
    atkS = np.where(intim & R.competitive[:, None], atkS * 2, atkS)
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
    ratio = (atkP / defP, atkS / defS)
    ghost, normal, fighting = TI["Ghost"], TI["Normal"], TI["Fighting"]
    for t in range(18):
        Et = C.E[:, t][None, :] * np.ones((nR, 1))
        if t in (normal, fighting):
            ghostmask = C.isType[:, ghost][None, :] & R.scrappy[:, None]
            Et = np.where(ghostmask, _eff_no_ghost(C, t)[None, :], Et)
        Et = np.where(R.tinted[:, None] & (Et < 1) & (Et > 0), Et * 2, Et)
        wmod = np.ones((nR, nC))
        if t == TI["Fire"]:
            wmod = np.where(w == SUN, 1.5, np.where(w == RAIN, .5, 1.0))
        if t == TI["Water"]:
            wmod = np.where(w == RAIN, 1.5, np.where(w == SUN, .5, 1.0))
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
        for c in (0, 1):
            for k in (0, 1):
                dm = np.where(R.mold[:, None], 1.0, C.dmod[:, t, c, k][None, :])
                wg = np.where(C.wonder[None, :] & ~R.mold[:, None] & (Et <= 1), 0, 1.0)
                fl = np.where(C.filter[None, :] & ~R.mold[:, None] & (Et > 1), .75, 1.0)
                mult = base_eff * dm * wg * fl
                for p in (0, 1):
                    P = R.P[:, slot(t, c, k, p)]
                    if not P.any():
                        continue
                    dmg = (42 * P[:, None] * ratio[c] / 50 + 2) * mult * (P[:, None] > 0) / C.hp[None, :]
                    key = ("phys", "spec")[c]
                    out[key] = np.maximum(out[key], dmg)
                    if p:
                        # Psychic Terrain blocks priority on grounded targets
                        blocked = (ter == PSY) & C.grounded[None, :]
                        out["prio_" + key] = np.maximum(out["prio_" + key], np.where(blocked, 0, dmg))
    out["w"], out["ter"] = w, ter
    return out


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


def simulate(R, C, dRC, dCR, stratR, stratC, rollR=.925, rollC=.925, rowFirstOnTie=True, turns=15):
    """Run the duel for every (row, column) pair. Returns row's score (1 win, 0 loss, .5 draw) as (N, N)."""
    g = R.g
    shape = (R.n, C.n)
    w, ter = dRC["w"], dRC["ter"]
    hpR, hpC = np.ones(shape), np.ones(shape)
    boR = {k: np.zeros(shape) for k in ("atk", "spa", "def", "spd", "spe")}
    boC = {k: np.zeros(shape) for k in ("atk", "spa", "def", "spd", "spe")}
    stR, stC = np.zeros(shape, int), np.zeros(shape, int)  # 0 none, 1 brn, 2 par, 3 tox, 4 slp
    sleepR, sleepC = np.zeros(shape), np.zeros(shape)
    toxR, toxC = np.zeros(shape), np.zeros(shape)
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
    immR = {k: rowB(R.immune[statusCodes[k][0]] | R.statusproof) for k in statusCodes}
    immC = {k: colB(C.immune[statusCodes[k][0]] | C.statusproof) for k in statusCodes}
    # Thunder Wave can't hit Ground types; approximated for all paralysis moves except Glare/Stun Spore users
    immR[PAR] = immR[PAR] | rowB(R.E[:, TI["Electric"]] == 0)
    immC[PAR] = immC[PAR] | colB(C.E[:, TI["Electric"]] == 0)
    if g >= 7:
        immR_pr = rowB(R.isType[:, TI["Dark"]])  # Prankster status fails on Dark types
        immC_pr = colB(C.isType[:, TI["Dark"]])
    else:
        immR_pr = immC_pr = np.zeros(shape, bool)

    for turn in range(1, turns + 1):
        alive = ~(doneR | doneC)
        if not alive.any():
            break
        # ---- current damage per hit, with boosts
        def dmg(d, boA, boB, stA, unawareA, unawareB, roll, gutsA):
            aP = stage(np.where(unawareB, 0, boA["atk"])) / stage(np.where(unawareA, 0, boB["def"]))
            aS = stage(np.where(unawareB, 0, boA["spa"])) / stage(np.where(unawareA, 0, boB["spd"]))
            burn = np.where((stA == 1) & ~gutsA, .5, np.where((stA == 1) & gutsA, 1.5, 1.0))
            para = np.where(stA == 2, .75, 1.0)
            main = np.maximum(np.maximum(d["phys"] * aP * burn, d["spec"] * aS), d["fixed"]) * roll * para
            prio = np.maximum(d["prio_phys"] * aP * burn, d["prio_spec"] * aS) * roll * para
            return main, prio
        gutsR, gutsC = rowB(R.guts), colB(C.guts)
        mainR, prioR = dmg(dRC, boR, boC, stR, rowB(R.unaware), colB(C.unaware), rollR, gutsR)
        dCRt = {k: v.T for k, v in dCR.items() if k in ("phys", "spec", "fixed", "prio_phys", "prio_spec")}
        mainC, prioC = dmg(dCRt, boC, boR, stC, colB(C.unaware), rowB(R.unaware), rollC, gutsC)
        # speed
        spR = rowB(R.spe) * stage(boR["spe"]) * np.where(stR == 2, parSpeed, 1.0)
        spC = colB(C.spe) * stage(boC["spe"]) * np.where(stC == 2, parSpeed, 1.0)
        for wx, mask in R.wxspeed.items():
            spR = np.where((w == wx) & rowB(mask), spR * 2, spR)
        for wx, mask in C.wxspeed.items():
            spC = np.where((w == wx) & colB(mask), spC * 2, spC)
        if turn > 1:
            spR = np.where(rowB(R.speedboost), spR * stage(np.full(shape, min(turn - 1, 6))), spR)
            spC = np.where(colB(C.speedboost), spC * stage(np.full(shape, min(turn - 1, 6))), spC)

        # ---- choose actions: 0 attack-main, 1 attack-prio, 2 setup, 3 status, 4 recover, 5 nothing
        def choose(strat, hpS, hpO, mainS, prioS, mainO, hasSetup, setups, usedStatus, hasSt, immO, stO, sleepS, truant, recover, spS, spO):
            act = np.zeros(shape, int)
            # status first
            for code in (SLP, BRN, PAR, TOX):
                m = (strat == code) & ~usedStatus & hasSt[code] & ~immO[code] & (stO == 0)
                act = np.where(m, 3, act)
            want = np.where(strat == SETUP1, 1, np.where(strat == SETUP2, 2, 0))
            m = (act == 0) & hasSetup & (setups < want)
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
        actR = choose(stratR, hpR, hpC, mainR, prioR, mainC, hasSetupR, setupsR, usedStatusR, hasStR, immC, stC, sleepR,
                      rowB(R.truant), rowB(R.recover), spR, spC)
        actC = choose(stratC, hpC, hpR, mainC, prioC, mainR, hasSetupC, setupsC, usedStatusC, hasStC, immR, stR, sleepC,
                      colB(C.truant), colB(C.recover), spC, spR)
        prR = np.where(actR == 1, 1, 0) + np.where((actR == 3) & rowB(R.prankster), 1, 0)
        prC = np.where(actC == 1, 1, 0) + np.where((actC == 3) & colB(C.prankster), 1, 0)
        rowFirst = (prR > prC) | ((prR == prC) & ((spR > spC) | ((spR == spC) & rowFirstOnTie)))

        def act_on(actA, hpA, hpB, mainA, prioA, boA, sbA, setupsA, usedA, stB, sleepB, toxB, shieldB, multiB, sturdyB,
                   hasStA, immB, prankA, prImmB, simpleA, bellyA, recoverA, mask):
            """Apply A's action to B where mask. Returns updated arrays."""
            # attacks
            hit = mask & ((actA == 0) | (actA == 1))
            d = np.where(actA == 1, prioA, mainA)
            d = np.where(multiB & (hpB >= 1), d * .5, d)
            blocked = hit & shieldB & (d > 0)
            d = np.where(blocked, 1 / 8 if g >= 8 else 0, d)
            shieldB = np.where(blocked, False, shieldB)
            newhp = hpB - np.where(hit, d, 0)
            survive = hit & sturdyB & (hpB >= 1) & (newhp <= 0)
            newhp = np.where(survive, .01, newhp)
            hpB = newhp
            # setup
            su = mask & (actA == 2)
            for k in boA:
                inc = sbA[k] * np.where(simpleA, 2, 1)
                boA[k] = np.where(su, np.clip(boA[k] + np.where(bellyA & (k == "atk"), 6, inc), -6, 6), boA[k])
            hpA = np.where(su & bellyA, hpA - .5, hpA)
            setupsA = setupsA + su
            # status
            st = mask & (actA == 3)
            usedA = usedA | st
            for code, (name, val) in statusCodes.items():
                ok = st & hasStA[code] & ~immB[code] & (stB == 0) & ~(prankA & prImmB)
                # pick the first applicable status in strategy order: handled by strategy (one code per pair)
                stB = np.where(ok & (stratOf == code), val, stB)
                sleepB = np.where(ok & (stratOf == code) & (val == 4), 2.0, sleepB)
            # recover
            rc = mask & (actA == 4)
            hpA = np.where(rc, np.minimum(1, hpA + .5), hpA)
            return hpA, hpB, setupsA, usedA, stB, sleepB, shieldB

        # first mover then second mover (if still alive)
        for first in (True, False):
            for side in ("R", "C"):
                goes = rowFirst if side == "R" else ~rowFirst
                mask = alive & (goes if first else ~goes)
                if side == "R":
                    mask = mask & (hpR > 0) & (hpC > 0)
                    stratOf = stratR
                    hpR, hpC, setupsR, usedStatusR, stC, sleepC, shieldC = act_on(
                        actR, hpR, hpC, mainR, prioR, boR, sbR, setupsR, usedStatusR, stC, sleepC, toxC, shieldC,
                        colB(C.multiscale), colB(C.sturdy), hasStR, immC, rowB(R.prankster), immC_pr,
                        rowB(R.simple), rowB(R.belly), rowB(R.recover), mask)
                else:
                    mask = mask & (hpR > 0) & (hpC > 0)
                    stratOf = stratC
                    hpC, hpR, setupsC, usedStatusC, stR, sleepR, shieldR = act_on(
                        actC, hpC, hpR, mainC, prioC, boC, sbC, setupsC, usedStatusC, stR, sleepR, toxR, shieldR,
                        rowB(R.multiscale), rowB(R.sturdy), hasStC, immR, colB(C.prankster), immR_pr,
                        colB(C.simple), colB(C.belly), colB(C.recover), mask)
                # mutations of dicts boR/boC happen in place
        # sleep counters tick for those who were asleep this turn
        sleepR = np.where(actR == 5, np.maximum(sleepR - 1, 0), sleepR)
        sleepC = np.where(actC == 5, np.maximum(sleepC - 1, 0), sleepC)
        stR = np.where((stR == 4) & (sleepR == 0), 0, stR)
        stC = np.where((stC == 4) & (sleepC == 0), 0, stC)
        # end of turn: weather, burn, toxic, grassy terrain
        live = alive & (hpR > 0) & (hpC > 0)
        for hpX, stX, toxX, mgX, sandX, hailX, phX, grX, nm in (
                (hpR, stR, toxR, rowB(R.magicguard), rowB(R.sandimm), rowB(R.hailimm), rowB(R.poisonheal), rowB(R.grounded), "R"),
                (hpC, stC, toxC, colB(C.magicguard), colB(C.sandimm), colB(C.hailimm), colB(C.poisonheal), colB(C.grounded), "C")):
            chip = np.zeros(shape)
            chip += np.where((w == SAND) & ~sandX, 1 / 16, 0)
            if g <= 8:
                chip += np.where((w == HAIL) & ~hailX, 1 / 16, 0)
            chip += np.where((stX == 1) & ~mgX, chipBurn, 0)
            toxX += (stX == 3)
            chip += np.where((stX == 3) & ~mgX & ~phX, toxX / 16, 0)
            chip -= np.where((stX == 3) & phX, 1 / 8, 0)
            chip -= np.where((ter == GRASSY) & grX, 1 / 16, 0)
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
    return score


def duel_matrix(g, mons, abilities_row, abilities_col=None, quick=False, mons_col=None):
    """Expected score of row vs column, with best-response strategies on both sides.
    Rows and columns can be different Pokemon (mons_col); by default they're the same."""
    R = Side(g, mons, abilities_row)
    if mons_col is None and abilities_col is None:
        C = R
    else:
        C = Side(g, mons_col if mons_col is not None else mons, abilities_col if abilities_col is not None else abilities_row)
    dRC, dCR = pair_damage(R, C), pair_damage(C, R)
    shape = (R.n, C.n)
    settings = [(.925, .925, True), (.925, .925, False)] if quick else \
        [(.925, .925, True), (.925, .925, False), (.85, 1.0, True), (1.0, .85, False)]
    att = np.full(shape, ATTACK)

    def run(sR, sC):
        return np.mean([simulate(R, C, dRC, dCR, sR, sC, a, b, t) for a, b, t in settings], axis=0)
    base = run(att, att)
    best, bestStrat = base.copy(), att.copy()
    for s in (SETUP1, SETUP2, SLP, BRN, PAR, TOX):
        v = run(np.full(shape, s), att)
        better = v > best + 1e-9
        best, bestStrat = np.where(better, v, best), np.where(better, s, bestStrat)
    if C is R:
        colStrat = bestStrat.T
    else:
        bestC, colStrat = 1 - base, att.copy()
        for s in (SETUP1, SETUP2, SLP, BRN, PAR, TOX):
            v = 1 - run(att, np.full(shape, s))
            better = v > bestC + 1e-9
            bestC, colStrat = np.where(better, v, bestC), np.where(better, s, colStrat)
    return run(bestStrat, colStrat)
