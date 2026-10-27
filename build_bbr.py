"""Builds bbr.json: every Pokemon's BBR (Battle Buddy Rating), for Poke Battle Buddy.

BBR is one number for how good a Pokemon is in singles battles, on BSR's scale (average 420, standard deviation 120).
It adds up 11 parts, each weighted by how well it predicted Smogon's tiers in Generations 4-9 (fitted on five
generations and checked on the sixth). The research behind it is in the app's "BBR Research" folder.

    python3 build_bbr.py --data gen9.json --source <showdown commit>   # writes bbr.json if anything changed
    python3 build_bbr.py ... --swift FILE                               # also writes the app's built-in copy
    python3 build_bbr.py --swift-only FILE                              # only the app's copy, from bbr.json

gen9.json is Pokemon Showdown's current data (pokedex, formats-data, moves, abilities, typechart, learnsets),
made by bbr/export_showdown.mjs. Run every day by the GitHub Action; it only recomputes when Showdown's data
or the model changed, since the battle simulation takes several minutes.
"""
import json, math, os, sys, time
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "bbr"))
import bbrlib
from bbrlib import ORD, TYPES, TI, sid, type_matrix, learnable
from duel import duel_matrix, Side, pair_damage

MODEL = "2026-10-26"  # change when the weights or the parts change, so every Pokemon is recomputed
SCHEMA = 1

# Weights per standard deviation of each part (BBR Research/final_model.py).
WEIGHTS = {
    "app_core": 1.9249, "typ_def_uniform": 0.1311, "typ_off": 0.3994, "duel": 0.8254, "st_minbulk": -0.3289,
    "ab_rating": 0.3182, "knockoff": 0.2264, "screens": 0.1557, "hazards": 0.2162, "def_typing": 0.5448,
    "prio": 0.2016,
}
HAZARDS = {"stealthrock", "spikes", "toxicspikes", "stickyweb", "stoneaxe", "ceaselessedge"}
SCREENS = {"reflect", "lightscreen", "auroraveil"}
aRPT, aRST, aLRT = 53736.6, 52437.9, 47836.5
APP_IMMUNE = {"levitate": "Ground", "flashfire": "Fire", "wellbakedbody": "Fire", "voltabsorb": "Electric",
              "lightningrod": "Electric", "motordrive": "Electric", "waterabsorb": "Water", "stormdrain": "Water",
              "dryskin": "Water", "sapsipper": "Grass", "eartheater": "Ground"}


def app_effect(a):
    """The app's on-device BBR ability multipliers (BattleBuddyRating.swift)."""
    e = dict(at=1, de=1, sa=1, sd=1, sp=1, bulk=1, off=1)
    if a in ("hugepower", "purepower"): e["at"] = 2
    if a == "truant": e["off"] = .5; e["bulk"] = .6
    if a == "slowstart": e["at"] = .6; e["sp"] = .6
    if a == "defeatist": e["at"] = e["sa"] = .8
    if a == "furcoat": e["de"] = 2
    if a == "icescales": e["sd"] = 1.6
    if a == "fluffy": e["de"] = 1.4
    if a in ("multiscale", "shadowshield"): e["bulk"] = 1.25
    if a == "regenerator": e["bulk"] = 1.15
    if a == "intimidate": e["de"] = 1.15
    if a == "magicguard": e["bulk"] = 1.1
    if a == "wonderguard": e["bulk"] = 3
    if a == "gorillatactics": e["at"] = 1.35
    if a == "adaptability": e["off"] = 1.2
    if a in ("sheerforce", "technician", "toughclaws", "strongjaw", "ironfist", "sharpness", "punkrock", "transistor",
             "dragonsmaw", "rockypayload", "steelworker", "waterbubble", "protosynthesis", "quarkdrive", "beastboost",
             "moxie", "chillingneigh", "grimneigh", "asoneglastrier", "asonespectrier", "speedboost", "libero", "protean"):
        e["off"] = 1.15
    if a in ("drought", "drizzle", "sandstream", "snowwarning", "orichalcumpulse", "hadronengine", "electricsurge",
             "psychicsurge", "grassysurge"):
        e["off"] = 1.1
    return e


def roster(data, research=False):
    """Every Pokemon to rate, and which of them make up the field (the Pokemon everything is compared against).

    Normal run: every Showdown Pokemon (not CAP), with moves from any generation (National Dex); the field is
    everything with a National Dex tier. research=True reproduces the research setup: Gen 9 tiered Pokemon only."""
    dex, fmt, ls = data["pokedex"], data["formats"], data["learnsets"]
    mons = []
    for k, p in dex.items():
        f = fmt.get(k, {})
        if p.get("num", 0) <= 0 or f.get("isNonstandard") in ("CAP", "Custom") or p.get("forme") in ("Totem", "Gmax"):
            continue
        tier = f.get("tier") if research else f.get("natDexTier")
        if research and tier not in ORD:
            continue
        s = p["baseStats"]
        evos = [e for e in p.get("evos", []) if sid(e) in dex and fmt.get(sid(e), {}).get("isNonstandard") not in ("CAP", "Custom")]
        mons.append(dict(id=k, name=p["name"], stats=[s["hp"], s["atk"], s["def"], s["spa"], s["spd"], s["spe"]],
                         types=p["types"], abil=[sid(a) for a in p["abilities"].values()], nfe=bool(evos),
                         weight=p.get("weightkg", 50), field=tier in ORD,
                         moves=learnable(9, k, dex, ls, natdex=not research)))
    return mons


def duel_scores(mons, field):
    """Each Pokemon's win rate in the 1v1 simulation against the field, with its best ability."""
    abr = bbrlib.gendata(9)["abilities"]
    default = lambda m: max(m["abil"], key=lambda a: abr.get(a, {}).get("rating", 0)) if m["abil"] else ""
    fab = [default(m) for m in field]
    best, bestScore = [default(m) for m in mons], None
    fieldIndex = {m["id"]: j for j, m in enumerate(field)}
    def mean_vs_field(W):
        mask = np.ones(W.shape, bool)
        for i, m in enumerate(mons):
            if m["id"] in fieldIndex:
                mask[i, fieldIndex[m["id"]]] = False
        return (W * mask).sum(1) / mask.sum(1)
    for k in range(3):
        rowab = [m["abil"][k] if len(m["abil"]) > k else default(m) for m in mons]
        sc = mean_vs_field(duel_matrix(9, mons, rowab, fab, quick=True, mons_col=field))
        if bestScore is None:
            bestScore, best = sc, list(rowab)
        else:
            for i in range(len(mons)):
                if sc[i] > bestScore[i] + 1e-9:
                    bestScore[i], best[i] = sc[i], rowab[i]
        print(f"  ability pass {k + 1}/3 done", file=sys.stderr, flush=True)
    chosen = {m["id"]: a for m, a in zip(mons, best)}
    for m in mons:
        m["ability"] = chosen[m["id"]]
    W = duel_matrix(9, mons, best, [chosen[m["id"]] for m in field], mons_col=field)
    # Inside the field, average each battle with its mirror (A vs B and B vs A are the same battle).
    rowOf = {m["id"]: i for i, m in enumerate(mons)}
    rows = [rowOf[m["id"]] for m in field]
    block = W[rows, :]
    W[rows, :] = (block + (1 - block.T)) / 2
    for i, m in enumerate(mons):
        if m["ability"] == "imposter":
            W[i, :] = .5
    return mean_vs_field(W)


def features(mons, field_mask, duel):
    eff = type_matrix(9)
    abr = bbrlib.gendata(9)["abilities"]
    mv = bbrlib.gendata(9)["moves"]
    field = [m for m, f in zip(mons, field_mask) if f]
    n = len(mons)
    f = {k: np.zeros(n) for k in WEIGHTS}
    # BSR 4.0 with the app's ability multipliers and T = 2.5, scaled to the field.
    speeds = np.sort([m["stats"][5] for m in field])
    def speed_factor(v):
        lo, hi = np.searchsorted(speeds, v, "left"), np.searchsorted(speeds, v, "right")
        return (lo + (hi - lo) / 2) / len(speeds)
    T = 2.5
    raw = np.zeros((n, 3))
    for i, m in enumerate(mons):
        best = None
        for a in (m["abil"] or [None]):
            e = app_effect(a)
            hp, at, de, sa, sd, sp = m["stats"]
            H = hp * 2 + 141
            A = (at * 2 + 36) * e["at"] * e["off"]; S = (sa * 2 + 36) * e["sa"] * e["off"]
            D = (de * 2 + 36) * e["de"]; SD = (sd * 2 + 36) * e["sd"]
            sf = speed_factor(sp * e["sp"])
            b = max(A / aRPT, S / aRST, math.sqrt(A * S) / aLRT)
            r = (H * D * e["bulk"], H * SD * e["bulk"], b * (aRPT + aRST) / 2 * (sf + T) / (1 - sf + T))
            key = r[0] / aRPT + r[1] / aRST + 2 * r[2] / ((aRPT + aRST) / 2)
            if best is None or key > best[0]:
                best = (key, r)
        raw[i] = best[1]
    fm = np.array(field_mask)
    zf = lambda v: (v - v[fm].mean()) / v[fm].std()
    parts = [zf(raw[:, k]) * 30 + 75 for k in range(3)]
    f["app_core"] = parts[0] + parts[1] + 2 * parts[2]
    # Typing: the field's own types decide how often each attack type shows up.
    share = np.zeros(18)
    for m in field:
        for t in m["types"]:
            share[TI[t]] += 1
    share /= share.sum()
    for i, m in enumerate(mons):
        ab = m.get("ability")
        def mult(att):
            v = np.prod([eff[TI[att], TI[t]] for t in m["types"]])
            return 0 if ab and APP_IMMUNE.get(ab) == att else v
        f["typ_def_uniform"][i] = -sum(math.log2(max(mult(a), .25)) for a in TYPES) / 18
        f["typ_off"][i] = sum(max(eff[TI[a], TI[d]] for a in m["types"]) for d in TYPES) / 18
        f["def_typing"][i] = -sum(share[t] * math.log2(max(np.prod([eff[t, TI[x]] for x in m["types"]]), .25)) for t in range(18))
        hp, at, de, sa, sd, sp = m["stats"]
        H = 2 * hp + 141
        f["st_minbulk"][i] = min(math.log(H * (2 * de + 36)), math.log(H * (2 * sd + 36)))
        f["ab_rating"][i] = max([abr.get(a, {}).get("rating", 0) for a in m["abil"]] or [0])
        moves = {x for x in m["moves"] if not (mv.get(x) or {}).get("isNonstandard")}
        f["knockoff"][i] = float("knockoff" in moves)
        f["screens"][i] = float(bool(moves & SCREENS))
        f["hazards"][i] = float(bool(moves & HAZARDS))
    p = np.clip(duel, 1e-3, 1 - 1e-3)
    f["duel"] = np.log(p / (1 - p))
    # Priority: how hard its best priority move hits the field, on average.
    R = Side(9, mons, [m["ability"] for m in mons])
    C = Side(9, field, [m["ability"] for m in field])
    d = pair_damage(R, C)
    prio = np.minimum(np.maximum(d["prio_phys"], d["prio_spec"]), 1)
    fieldIndex = {m["id"]: j for j, m in enumerate(field)}
    for i, m in enumerate(mons):
        mask = np.ones(len(field), bool)
        if m["id"] in fieldIndex:
            mask[fieldIndex[m["id"]]] = False
        f["prio"][i] = prio[i, mask].mean()
    return f


def ratings(mons, duel):
    fm = np.array([m["field"] for m in mons])
    f = features(mons, fm, duel)
    score = np.zeros(len(mons))
    for k, w in WEIGHTS.items():
        v = f[k]
        sd = v[fm].std()
        score += w * ((v - v[fm].mean()) / sd if sd > 0 else 0)
    return (score - score[fm].mean()) / score[fm].std() * 120 + 420


def write_swift(doc, text, path):
    """The app's built-in copy of bbr.json."""
    assert '"##' not in text
    with open(path, "w") as fh:
        fh.write(f'''//
//  BBRTable.swift
//  PokeBattleBuddy
//
//  GENERATED FILE, don't edit by hand. The built-in copy of every Pokemon's BBR (model {doc["model"]}, built {doc["built"]}).
//  The app downloads a newer copy each day from https://github.com/ToddGeorgeKelly/poke-battle-buddy-data
//  (bbr.json, made by build_bbr.py from Pokemon Showdown's data). Keys are Showdown IDs. Refresh with
//  `python3 build_bbr.py --swift-only FILE` before an app release.
//

let bbrTableJSON = ##"{text}"##
''')


def main():
    args = sys.argv[1:]
    if "--swift-only" in args:  # just write the app's copy from the current bbr.json
        text = open("bbr.json").read()
        write_swift(json.loads(text), text, args[args.index("--swift-only") + 1])
        return
    data_path = args[args.index("--data") + 1]
    source = args[args.index("--source") + 1] if "--source" in args else "unknown"
    research = "--research" in args
    out = "bbr.json"
    if not research and os.path.exists(out) and "--force" not in args:
        old = json.load(open(out))
        if old.get("source") == source and old.get("model") == MODEL:
            print("bbr.json is already up to date", file=sys.stderr)
            return
    bbrlib.load_gendata(9, data_path)
    started = time.time()
    mons = roster(bbrlib.gendata(9), research=research)
    field = [m for m in mons if m["field"]]
    print(f"{len(mons)} Pokemon, field of {len(field)}", file=sys.stderr, flush=True)
    duel = duel_scores(mons, field)
    bbr = ratings(mons, duel)
    # Kept between 0 and 999 (only joke-strong forms like Eternamax Eternatus go above, a few babies go below 0).
    table = {m["id"]: int(round(min(999, max(0, v)))) for m, v in zip(mons, bbr)}
    print(f"done in {time.time() - started:.0f} s", file=sys.stderr)
    if research:
        for name in ("clefable", "gholdengo", "kingambit", "slaking", "regigigas", "heatran", "torkoal", "ironvaliant"):
            print(f"  {name}: {table.get(name)}", file=sys.stderr)
        return
    doc = {"schema": SCHEMA, "model": MODEL, "source": source, "built": time.strftime("%Y-%m-%d"), "ratings": table}
    text = json.dumps(doc, separators=(",", ":"), sort_keys=True)
    with open(out, "w") as fh:
        fh.write(text)
    print(f"bbr.json: {len(table)} Pokemon, {len(text) // 1024} KB", file=sys.stderr)
    if "--swift" in args:
        write_swift(doc, text, args[args.index("--swift") + 1])

if __name__ == "__main__":
    main()
