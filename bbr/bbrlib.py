"""Data + mechanics for the BBR research.

Per generation (4-9): the tiered Pokemon, their level-100 stats, types, abilities, learnable moves,
and a vectorised 1-v-1 duel simulation over every ordered pair.
"""
import json, math, re
import numpy as np

ORD = {"AG": 8, "Uber": 7, "OU": 6, "UUBL": 5.5, "UU": 5, "RUBL": 4.5, "RU": 4, "NUBL": 3.5, "NU": 3,
       "PUBL": 2.5, "PU": 2, "ZUBL": 1.5, "ZU": 1}
TIER_ALIAS = {"(OU)": "OU"}  # Showdown's tag for low-usage Pokemon that are still OU
TYPES = ["Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison", "Ground", "Flying",
         "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"]
TI = {t: i for i, t in enumerate(TYPES)}


def sid(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ---------------------------------------------------------------- loading
_cache = {}


def gendata(g):
    if g not in _cache:
        with open(f"/tmp/bbr/gen/gen{g}.json") as fh:
            _cache[g] = json.load(fh)
    return _cache[g]


def set_gendata(g, data):
    """Production: use this data (one Showdown export) for generation g."""
    _cache[g] = data


def load_gendata(g, path):
    """Production: use this file for generation g's data (the research reads /tmp/bbr/gen by default)."""
    with open(path) as fh:
        set_gendata(g, json.load(fh))


def type_matrix(g):
    """eff[a, d] = multiplier of attack type a on single defending type d."""
    tc = gendata(g)["typechart"]
    n = 18 if g >= 6 else 17
    eff = np.ones((18, 18))
    for d in TYPES[:n]:
        dt = tc[sid(d)]["damageTaken"]
        for a in TYPES[:n]:
            eff[TI[a], TI[d]] = {0: 1, 1: 2, 2: 0.5, 3: 0}[dt.get(a, 0)]
    return eff


def learnable(g, mon_id, dex, ls, natdex=False):
    """Moves a Pokemon can have in gen g (own + prevo chain + base species), as a set of move IDs.

    natdex (production, for Pokemon not in gen g): also keep moves that no longer exist in gen g (National Dex).

    Like Showdown, a move learned in any gen up to g counts (transfer forward, incl. Virtual Console "7V"
    and Let's Go "8V" sources), except moves that no longer exist in gen g (`isNonstandard`, e.g. Pursuit
    and Hidden Power in Gens 8-9)."""
    gone = set() if natdex else {m for m, x in gendata(g)["moves"].items() if x.get("isNonstandard")}
    out = set()
    seen = set()
    cur = mon_id
    def src_ok(s):
        try:
            sg = int(s[0])
        except ValueError:
            return False
        return sg <= g
    stack = [mon_id]
    while stack:
        cur = stack.pop()
        if cur in seen or cur not in dex:
            continue
        seen.add(cur)
        entry = ls.get(cur, {}).get("learnset")
        if entry:
            for mv, srcs in entry.items():
                if mv not in gone and any(src_ok(s) for s in srcs):
                    out.add(mv)
        p = dex[cur]
        if p.get("prevo"):
            stack.append(sid(p["prevo"]))
        # Forms without their own learnset use the base species' (Megas, most cosmetic forms).
        if (not entry or len(entry) < 5 or p.get("battleOnly")) and p.get("baseSpecies") and sid(p["baseSpecies"]) != cur:
            stack.append(sid(p["baseSpecies"]))
        if p.get("changesFrom"):
            stack.append(sid(p["changesFrom"]))
    return out


# Species whose alternate forms are cosmetic or a type swap of the base (one row, like Arceus):
# Pikachu caps / Cosplay / Partner, Silvally memories.
BASE_FORM_ONLY = {"Pikachu", "Silvally"}
EVENT_ONLY = {"pichuspikyeared"}


def not_a_teambuilder_pick(p):
    """Forms that carry a tier in Showdown's data but aren't a separate Pokemon you build a team with."""
    forme = p.get("forme", "")
    if forme.endswith("Gmax") or forme.endswith("Totem") or sid(p["name"]) in EVENT_ONLY:
        return True
    if forme and p.get("baseSpecies") in BASE_FORM_ONLY:
        return True
    if p.get("battleOnly"):
        # Mid-battle transformations (Zen Mode, Blade Forme, Ash-Greninja, Ultra Burst...) belong to the
        # out-of-battle form. Keep the ones a held item locks in from turn 1, like Megas and Primals
        # (Zacian/Zamazenta-Crowned); a Z-Crystal (Ultranecrozium Z) only triggers a mid-battle change.
        item = p.get("requiredItem") or ""
        return not item or item.endswith(" Z")
    return False


def usable_abilities(g, p):
    """Ability IDs a Pokemon can actually have in gen g: no Hidden Abilities before Gen 5, and none that
    Showdown flags `unreleasedHidden` for that gen (e.g. Gen 5 Serperior's Contrary)."""
    if g < 3:
        return []
    hidden_ok = g >= 5 and not p.get("unreleasedHidden")
    return [sid(a) for slot, a in p["abilities"].items() if slot != "H" or hidden_ok]


# Smeargle learns everything through Sketch, which a learnset can't express. Use the moves of its standard
# competitive sets instead (Smogon analyses, Gens 4-9: Spore lead with entry hazards / Sticky Web, Rapid Spin,
# Whirlwind, Taunt); moves that don't exist in a gen are dropped.
GEN_LAST_MOVE = {4: 467, 5: 559}  # highest move number introduced by that gen (the gen 4-5 data lists later moves)
SKETCH_SET = {"spore", "stickyweb", "stealthrock", "spikes", "rapidspin", "whirlwind", "taunt"}


def roster(g):
    """Every Pokemon with a real singles tier in gen g."""
    d = gendata(g)
    dex, fmt, ls = d["pokedex"], d["formats"], d["learnsets"]
    mons, seen = [], set()
    for k, f in fmt.items():
        t = TIER_ALIAS.get(f.get("tier"), f.get("tier"))
        if t not in ORD or k not in dex:
            continue
        p = dex[k]
        if p.get("num", 0) <= 0 or not_a_teambuilder_pick(p):
            continue
        s = p["baseStats"]
        stats = [s["hp"], s["atk"], s["def"], s["spa"], s["spd"], s["spe"]]
        abil = usable_abilities(g, p)
        evos = [e for e in p.get("evos", []) if sid(e) in fmt and fmt[sid(e)].get("tier") not in (None, "Illegal")]
        moves = learnable(g, k, dex, ls)
        if k == "smeargle":
            moves = {m for m in SKETCH_SET if m in d["moves"] and not d["moves"][m].get("isNonstandard")
                     and d["moves"][m].get("num", 0) <= GEN_LAST_MOVE.get(g, 10 ** 6)}
        # Forms identical in battle (Genesect drives, Keldeo-Resolute) count once; the base comes first.
        key = (tuple(stats), tuple(p["types"]), tuple(sorted(abil)), frozenset(moves))
        if key in seen:
            continue
        seen.add(key)
        mons.append(dict(id=k, name=p["name"], gen=g, tier=t, y=ORD[t], stats=stats, types=p["types"],
                         abil=abil, nfe=bool(evos), weight=p.get("weightkg", 50),
                         moves=moves))
    return mons


# ---------------------------------------------------------------- move model
SPECIAL_BP = {  # basePowerCallback moves -> typical power in a 1v1 at full-ish HP
    "acrobatics": 110, "avalanche": 60, "crushgrip": 100, "dragonenergy": 120, "electroball": 70, "eruption": 120,
    "waterspout": 120, "grassknot": 75, "lowkick": 75, "heatcrash": 80, "heavyslam": 80, "gyroball": 60, "hardpress": 80,
    "hex": 65, "infernalparade": 60, "lastrespects": 50, "payback": 75, "ragefist": 75, "risingvoltage": 70,
    "stompingtantrum": 75, "temperflare": 75, "terablast": 80, "tripleaxel": 94, "triplekick": 47, "watershuriken": 15,
    "return": 102, "frustration": 102, "knockoff": None, "wringout": 100, "boltbeak": 127, "fishiousrend": 127,
    "magnitude": 71, "punishment": 60, "pursuit": 40, "trumpcard": 0, "naturalgift": 0, "fling": 0, "present": 0,
    "beatup": 0, "flail": 0, "reversal": 0, "rollout": 0, "iceball": 0, "furycutter": 0, "storedpower": 0,
    "powertrip": 0, "spitup": 0, "echoedvoice": 40, "round": 60, "assurance": 60, "firepledge": 80, "grasspledge": 80,
    "waterpledge": 80, "electroshot": 130, "weatherball": 50, "terrainpulse": 50, "brine": 85,
}
EXCLUDE = {"focuspunch", "belch", "lastresort", "dreameater", "synchronoise", "fakeout", "firstimpression",
           "steelroller", "shelltrap", "spitup", "explosion", "selfdestruct", "mistyexplosion", "memento",
           "finalgambit", "counter", "mirrorcoat", "metalburst", "bide", "comeuppance", "superfang", "ruination",
           "naturesmadness", "endeavor", "skydrop", "hyperspacefury", "aurawheel", "darkestlariat_",
           "mindblown", "chloroblast", "steelbeam", "burnup", "doubleshock", "futuresight", "doomdesire",
           "snore", "sleeptalk", "uproar", "thrash", "outrage_", "suckerpunch_", "dynamaxcannon", "behemothblade",
           "behemothbash", "eternabeam", "struggle", "upperhand", "poltergeist_"}
CONTACT_BOOST = {"toughclaws": 1.3}
FLAG_BOOST = {"strongjaw": ("bite", 1.5), "ironfist": ("punch", 1.2), "sharpness": ("slicing", 1.5),
              "megalauncher": ("pulse", 1.5), "punkrock": ("sound", 1.3)}
TYPE_BOOST = {"transistor": ("Electric", 1.5), "dragonsmaw": ("Dragon", 1.5), "steelworker": ("Steel", 1.5),
              "rockypayload": ("Rock", 1.5), "waterbubble": ("Water", 2.0), "steelyspirit": ("Steel", 1.5)}
ATE = {"aerilate": "Flying", "pixilate": "Fairy", "refrigerate": "Ice", "galvanize": "Electric"}


def move_table(g):
    return gendata(g)["moves"]


def move_options(g, mon, ability):
    """List of (type, category, contact, priority, effective power, sound) for every usable attack."""
    mv = move_table(g)
    out = []
    for m in mon["moves"]:
        x = mv.get(m)
        if not x or x.get("category") == "Status" or m in EXCLUDE:
            continue
        if x.get("isNonstandard") or x.get("isZ") or x.get("isMax") or x.get("ohko"):
            continue
        flags = x.get("flags", {}) or {}
        if flags.get("charge") and not (m == "solarbeam" and ability == "drought") and m not in ("electroshot",):
            continue
        typ, cat = x["type"], x["category"]
        if typ not in TI:
            continue
        if g <= 3:
            continue
        bp = x.get("basePower", 0) or 0
        fixed = None
        if x.get("damage") == "level":
            fixed = 100
        elif m in SPECIAL_BP:
            bp = SPECIAL_BP[m] if SPECIAL_BP[m] is not None else bp * (1.5 if g >= 6 else 1.0)
        elif x.get("basePowerCallback") and bp == 0:
            continue
        if m == "knockoff" and g >= 6:
            bp = 97.5
        if bp <= 0 and fixed is None:
            continue
        acc = x.get("accuracy", 100)
        acc = 1.0 if acc is True else acc / 100
        if ability == "noguard":
            acc = 1.0
        elif ability == "compoundeyes":
            acc = min(1.0, acc * 1.3)
        elif ability == "hustle" and cat == "Physical":
            acc *= 0.8
        hits = 1.0
        mh = x.get("multihit")
        if isinstance(mh, list):
            hits = 5 if ability == "skilllink" else (3.1 if g >= 5 else 3.0)
        elif isinstance(mh, int):
            hits = mh
        if m == "populationbomb":
            hits = 10 if ability == "skilllink" else 6.5
        if m in ("tripleaxel", "triplekick"):
            hits = 1
        power = bp * hits * acc
        if flags.get("recharge"):
            power *= 0.5
        sb = (x.get("self") or {}).get("boosts") or {}
        drop = min(sb.get("atk", 0), sb.get("spa", 0))
        if drop <= -2:
            power *= 0.8 if ability != "contrary" else 1.2
        elif drop == -1:
            power *= 0.9
        rec = x.get("recoil")  # the user loses this share of the damage it deals (the sim charges it)
        recoil = rec[0] / rec[1] if rec and ability not in ("rockhead", "magicguard") else 0.0
        dr = x.get("drain")  # ... or heals this share
        drain = dr[0] / dr[1] if dr else 0.0
        if x.get("mindBlownRecoil"):
            continue
        # attacker ability modifiers on power
        if ability in ATE and typ == "Normal":
            typ = ATE[ability]
            power *= 1.2 if g >= 7 else 1.3
        if ability == "normalize":
            typ = "Normal"
        if ability == "technician" and 0 < bp <= 60:
            power *= 1.5
        if ability in CONTACT_BOOST and flags.get("contact"):
            power *= CONTACT_BOOST[ability]
        if ability in FLAG_BOOST and flags.get(FLAG_BOOST[ability][0]):
            power *= FLAG_BOOST[ability][1]
        if ability in TYPE_BOOST and typ == TYPE_BOOST[ability][0]:
            mult = TYPE_BOOST[ability][1]
            if ability == "transistor" and g >= 9:
                mult = 1.3
            power *= mult
        if ability == "sheerforce" and (x.get("secondary") or x.get("secondaries")):
            power *= 1.3
        if ability == "reckless" and (rec or x.get("hasCrashDamage")):
            power *= 1.2
        if ability == "ironfist" and False:
            pass
        prio = x.get("priority", 0)
        if m == "grassyglide":
            prio = 1 if ability == "grassysurge" else 0
        if ability == "galewings" and typ == "Flying":
            prio = 1
        if ability == "triage" and x.get("drain"):
            prio = 3
        if m in ("suckerpunch", "thunderclap"):
            power *= 0.9  # fails if the foe doesn't attack
        # which stats the damage uses: Psyshock-likes hit Defense, Body Press attacks with Defense,
        # Foul Play with the target's Attack; Freeze-Dry is super effective on Water
        kind = "phys" if cat == "Physical" else "spec"
        if x.get("overrideDefensiveStat") == "def":
            kind = "psyshock"
        elif x.get("overrideOffensiveStat") == "def":
            kind = "bodypress"
        elif x.get("overrideOffensivePokemon") == "target":
            kind = "foulplay"
        elif m == "freezedry":
            kind = "freezedry"
        out.append(dict(type=typ, cat=cat, contact=bool(flags.get("contact")), prio=prio, power=power,
                        fixed=fixed, acc=acc, sound=bool(flags.get("sound")), id=m, kind=kind,
                        recoil=recoil, drain=drain))
    return out


STATUS_MOVES = {  # move -> (status, accuracy)
    "willowisp": ("brn", .85), "toxic": ("tox", .90), "thunderwave": ("par", .90), "glare": ("par", 1.0),
    "stunspore": ("par", .75), "spore": ("slp", 1.0), "sleeppowder": ("slp", .75), "hypnosis": ("slp", .6),
    "darkvoid": ("slp", .8), "lovelykiss": ("slp", .75), "sing": ("slp", .55), "grasswhistle": ("slp", .55),
    "yawn": ("slp", 1.0), "poisonpowder": ("psn", .75), "toxicthread": ("psn", 1.0), "poisongas": ("psn", .9),
}
RECOVERY = {"recover", "softboiled", "roost", "slackoff", "milkdrink", "shoreup", "healorder", "moonlight",
            "morningsun", "synthesis", "strengthsap", "lunarblessing", "junglehealing", "rest_", "wish_"}
SETUP = {  # move -> boosts on self
    "swordsdance": {"atk": 2}, "nastyplot": {"spa": 2}, "dragondance": {"atk": 1, "spe": 1},
    "quiverdance": {"spa": 1, "spd": 1, "spe": 1}, "calmmind": {"spa": 1, "spd": 1}, "bulkup": {"atk": 1, "def": 1},
    "shellsmash": {"atk": 2, "spa": 2, "spe": 2, "def": -1, "spd": -1}, "shiftgear": {"atk": 1, "spe": 2},
    "coil": {"atk": 1, "def": 1}, "victorydance": {"atk": 1, "def": 1, "spe": 1}, "tailglow": {"spa": 3},
    "geomancy": {"spa": 2, "spd": 2, "spe": 2}, "bellydrum": {"atk": 6}, "agility": {"spe": 2},
    "rockpolish": {"spe": 2}, "autotomize": {"spe": 2}, "workup": {"atk": 1, "spa": 1}, "growth": {"atk": 1, "spa": 1},
    "honeclaws": {"atk": 1}, "tidyup": {"atk": 1, "spe": 1}, "filletaway": {"atk": 2, "spa": 2, "spe": 2},
    "clangoroussoul": {"atk": 1, "def": 1, "spa": 1, "spd": 1, "spe": 1}, "noretreat": {"atk": 1, "def": 1, "spa": 1, "spd": 1, "spe": 1},
    "curse": {"atk": 1, "def": 1, "spe": -1}, "irondefense": {"def": 2}, "amnesia": {"spd": 2},
    "cosmicpower": {"def": 1, "spd": 1}, "acidarmor": {"def": 2}, "barrier": {"def": 2},
}
