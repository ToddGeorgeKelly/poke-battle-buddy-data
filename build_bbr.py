"""Builds bbr.json: every Pokemon's BBR (Battle Buddy Rating), for Poke Battle Buddy.

BBR is one number for how good a Pokemon is in singles battles, on BSR's scale (average 420, standard deviation 120).
It adds up 11 parts, each weighted by how well it predicted Smogon's tiers in Generations 4-9 (fitted on five
generations and checked on the sixth). The research behind it is in the app's "BBR Research" folder
(BBR_RESEARCH.md, part 3); bbr/bbrlib.py and bbr/duel.py are copies of the research's, plus production helpers.

Every Showdown Pokemon (~1,300) is rated against the validated field: Gen 9's tiered Pokemon, picked exactly
as the research picks them. All averages, z-scores and the 420/120 scale come from that field, so a field
Pokemon gets the research's own number. Pokemon in Gen 9 use Gen 9 moves; the rest use moves from every gen.
Ditto and Smeargle don't fit the model and are listed under "unrated" instead.

    python3 build_bbr.py --data gen9.json --source <showdown commit>   # writes bbr.json if anything changed
    python3 build_bbr.py ... --swift FILE                               # also writes the app's built-in copy
    python3 build_bbr.py --swift-only FILE                              # only the app's copy, from bbr.json

gen9.json is Pokemon Showdown's current data (pokedex, formats-data, moves, abilities, typechart, learnsets),
made by bbr/export_showdown.mjs. Run every day by the GitHub Action; it only recomputes when Showdown's data
or the model changed, since the battle simulation takes several minutes. Tests: `pytest tests`
(add --runslow for the parity check against the research).
"""
import json, math, os, sys, time
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "bbr"))
import bbrlib
from bbrlib import ORD, TYPES, TI, sid, type_matrix, learnable, usable_abilities
from duel import duel_matrix, default_abilities, Side, pair_damage

MODEL = "2026-10-27"  # change when the weights or the parts change, so every Pokemon is recomputed
SCHEMA = 1

# Weights per standard deviation of each part (BBR Research/common.py SEL, fitted by final_model.py).
WEIGHTS = {
    "app_core": 1.93944, "typ_off": 0.31410, "duel": 1.23185, "ab_rating": 0.44676, "st_minbulk": -0.33907,
    "sr_weak": -0.28761, "removal": 0.22965, "def_typing": 0.59186, "hazards": 0.21686, "ab_intimidate": -0.19517,
    "prio": 0.13577,
}
HAZARDS = {"stealthrock", "spikes", "toxicspikes", "stickyweb", "stoneaxe", "ceaselessedge"}
REMOVAL = {"rapidspin", "defog", "mortalspin", "tidyup", "courtchange"}
UNRATED = ["ditto", "smeargle"]  # Imposter / Sketch: no stats-and-learnset model fits them
# Forms that always battle as another form: they get that form's rating.
BATTLES_AS = {"palafin": "palafinhero", "terapagos": "terapagosterastal"}
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


def roster(data):
    """Every Pokemon to rate, field first (field=True): the research's Gen 9 roster (bbrlib.roster), then every
    other Showdown Pokemon (not CAP, Totem or Gmax). Pokemon in Gen 9 get Gen 9 moves, the rest National Dex moves."""
    bbrlib.set_gendata(9, data)
    dex, fmt, ls = data["pokedex"], data["formats"], data["learnsets"]
    field = [dict(m, field=True) for m in bbrlib.roster(9)]
    taken = {m["id"] for m in field}
    rest = []
    for k, p in dex.items():
        f = fmt.get(k, {})
        if k in taken or p.get("num", 0) <= 0 or f.get("isNonstandard") in ("CAP", "Custom") \
                or p.get("forme", "").endswith(("Totem", "Gmax")):
            continue
        s = p["baseStats"]
        evos = [e for e in p.get("evos", []) if sid(e) in fmt and fmt[sid(e)].get("tier") not in (None, "Illegal")]
        rest.append(dict(id=k, name=p["name"], stats=[s["hp"], s["atk"], s["def"], s["spa"], s["spd"], s["spe"]],
                         types=p["types"], abil=usable_abilities(9, p), nfe=bool(evos), weight=p.get("weightkg", 50),
                         field=False, moves=learnable(9, k, dex, ls, natdex=bool(f.get("isNonstandard")))))
    return field + rest


def _mean_vs_field(W, mons, field):
    """Each row's average over the field, leaving out the battle against itself."""
    col = {m["id"]: j for j, m in enumerate(field)}
    mask = np.ones(W.shape, bool)
    for i, m in enumerate(mons):
        if m["id"] in col:
            mask[i, col[m["id"]]] = False
    return (W * mask).sum(1) / mask.sum(1)


def duel_scores(mons, field):
    """Each Pokemon's win rate in the 1v1 simulation against the field, with its best ability (duel.choose_abilities
    with the field as the columns). Sets m["ability"]. Field Pokemon must be the first rows."""
    nf = len(field)
    assert [m["id"] for m in mons[:nf]] == [m["id"] for m in field]
    default_f = default_abilities(9, field)
    default = default_abilities(9, mons)
    best, bestScore = list(default), None
    for k in range(3):
        rowab = [m["abil"][k] if len(m["abil"]) > k else default[i] for i, m in enumerate(mons)]
        sc = _mean_vs_field(duel_matrix(9, mons, rowab, default_f, quick=True, mons_col=field), mons, field)
        if bestScore is None:
            bestScore, best = sc.copy(), list(rowab)
        else:
            for i in range(len(mons)):
                if sc[i] > bestScore[i] + 1e-9:
                    bestScore[i], best[i] = sc[i], rowab[i]
        print(f"  ability pass {k + 1}/3 done", file=sys.stderr, flush=True)
    best = ["imposter" if "imposter" in m["abil"] else a for m, a in zip(mons, best)]
    for m, a in zip(mons, best):
        m["ability"] = a
    W = duel_matrix(9, mons, best, best[:nf], mons_col=field)
    # Inside the field, average each battle with its mirror (A vs B and B vs A are the same battle).
    block = W[:nf, :]
    W[:nf, :] = (block + (1 - block.T)) / 2
    return _mean_vs_field(W, mons, field)


def features(mons, field_mask, duel):
    """The model's 11 parts for every Pokemon, with the field as the reference (research: baselines.bsr,
    addfeat, features.utility_features, mech.mech_features)."""
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
    fm = np.asarray(field_mask)
    zf = lambda v: (v - v[fm].mean()) / v[fm].std()
    parts = [zf(raw[:, k]) * 30 + 75 for k in range(3)]
    f["app_core"] = parts[0] + parts[1] + 2 * parts[2]
    # Defensive typing: the field's own types decide how often each attack type shows up.
    share = np.zeros(18)
    for m in field:
        for t in m["types"]:
            share[TI[t]] += 1
    share /= share.sum()
    for i, m in enumerate(mons):
        prod = lambda t: np.prod([eff[t, TI[x]] for x in m["types"]])
        f["typ_off"][i] = sum(max(eff[TI[a], TI[d]] for a in m["types"]) for d in TYPES) / 18
        f["def_typing"][i] = -sum(share[t] * math.log2(max(prod(t), .25)) for t in range(18))
        f["sr_weak"][i] = math.log2(max(prod(TI["Rock"]), .25))
        hp, at, de, sa, sd, sp = m["stats"]
        H = 2 * hp + 141
        f["st_minbulk"][i] = min(math.log(H * (2 * de + 36)), math.log(H * (2 * sd + 36)))
        f["ab_rating"][i] = max([abr.get(a, {}).get("rating", 0) for a in m["abil"]] or [0])
        f["ab_intimidate"][i] = float("intimidate" in m["abil"])
        moves = {x for x in m["moves"] if not (mv.get(x, {}) or {}).get("isNonstandard")}
        f["hazards"][i] = float(bool(moves & HAZARDS))
        f["removal"][i] = float(bool(moves & REMOVAL))
    p = np.clip(duel, 1e-3, 1 - 1e-3)
    f["duel"] = np.log(p / (1 - p))
    # Priority: how hard its best priority move hits the field, on average.
    C = Side(9, field, [m["ability"] for m in field])
    R = Side(9, mons, [m["ability"] for m in mons], field=C)
    d = pair_damage(R, C)
    f["prio"] = _mean_vs_field(np.minimum(np.maximum(d["prio_phys"], d["prio_spec"]), 1), mons, field)
    return f


def ratings(mons, duel):
    """BBR on the 420/120 scale, every z-score taken over the field."""
    fm = np.array([m["field"] for m in mons])
    f = features(mons, fm, duel)
    score = np.zeros(len(mons))
    for k, w in WEIGHTS.items():
        v = f[k]
        sd = v[fm].std()
        score += w * ((v - v[fm].mean()) / sd if sd > 0 else 0)
    return (score - score[fm].mean()) / score[fm].std() * 120 + 420


def built_now():
    """Full UTC timestamp, so a same-day rebuild sorts after an earlier one (and after old day-only dates)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def make_doc(values, source, built):
    """bbr.json's content from {id: BBR}: rounded and kept between 0 and 999 (only joke-strong forms like Eternamax
    Eternatus go above, a few babies go below 0); battle-as forms copied; Ditto and Smeargle listed as unrated."""
    table = {k: int(round(min(999, max(0, float(v))))) for k, v in values.items() if k not in UNRATED}
    for k, form in BATTLES_AS.items():
        if form in table:
            table[k] = table[form]
    return {"schema": SCHEMA, "model": MODEL, "source": source, "built": built, "ratings": table,
            "unrated": list(UNRATED)}


def to_json(doc):
    return json.dumps(doc, separators=(",", ":"), sort_keys=True)


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
    out = args[args.index("--out") + 1] if "--out" in args else "bbr.json"
    if os.path.exists(out) and "--force" not in args:
        old = json.load(open(out))
        if old.get("source") == source and old.get("model") == MODEL:
            print(f"{out} is already up to date", file=sys.stderr)
            return
    bbrlib.load_gendata(9, data_path)
    started = time.time()
    mons = roster(bbrlib.gendata(9))
    field = [m for m in mons if m["field"]]
    print(f"{len(mons)} Pokemon, field of {len(field)}", file=sys.stderr, flush=True)
    bbr = ratings(mons, duel_scores(mons, field))
    print(f"done in {time.time() - started:.0f} s", file=sys.stderr)
    doc = make_doc({m["id"]: v for m, v in zip(mons, bbr)}, source, built_now())
    text = to_json(doc)
    with open(out, "w") as fh:
        fh.write(text)
    print(f"{out}: {len(doc['ratings'])} Pokemon, {len(text) // 1024} KB", file=sys.stderr)
    if "--swift" in args:
        write_swift(doc, text, args[args.index("--swift") + 1])


if __name__ == "__main__":
    main()
