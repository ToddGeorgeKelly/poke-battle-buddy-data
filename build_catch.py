"""Builds catch.json: where each Pokemon can be caught in each game, and how each game has it (caught, evolved, bred,
traded in, from an event, or transferred in).

    python3 build_catch.py   # fetches the pinned sources below, writes catch.json

Sources (pinned to a commit so a rebuild gives the same file):
- Red / Blue through Black 2 / White 2: PokeAPI's encounter CSVs (BSD-3), https://github.com/PokeAPI/pokeapi
- X / Y through Legends: Z-A: Pokedex Tracker's seeds/locations.csv (MIT, (c) 2016 Pokedex Tracker),
  https://github.com/pokedextracker/pokedextracker.com/tree/master/seeds
Part 2 (hand-written shiny rules and locks) will fill in the top-level "shiny" key.
"""
import collections, csv, datetime, sys
import build_forms as bf
import build_breeding as bb

SCHEMA = 1
ENGLISH = "9"

# The games PokeAPI's encounters cover well (game id = PokeAPI version group). Pokedex Tracker covers the rest.
POKEAPI_GAMES = ["black-2-white-2", "black-white", "heartgold-soulsilver", "platinum", "diamond-pearl", "emerald",
                 "firered-leafgreen", "ruby-sapphire", "crystal", "gold-silver", "yellow", "red-blue"]
GAMES = [g for g in bf.GAMES if g != "home"]

# Evolutions by place that a game doesn't have, though the species is in its generation: Johto has no Mt. Coronet,
# moss rock or ice rock.
NO_EVOLVE = {"heartgold-soulsilver": {"magnezone", "probopass", "leafeon", "glaceon"}}

# Statuses, best first: c caught (or received) in the game, e evolved, b bred, t traded in from another game,
# ev from an event only, x transferred in.
ORDER = ["c", "e", "b", "t", "ev", "x"]


def best(codes):
    codes = [c for c in codes if c]
    return min(codes, key=ORDER.index) if codes else None


def english(rows, key, field="name"):
    return {r[key]: r[field] for r in rows if r["local_language_id"] == ENGLISH and r[field]}


def parse_pokeapi(texts):
    """PokeAPI's CSVs (name -> text) as lookup tables."""
    rows = {n: bf.rows(t) for n, t in texts.items()}
    by_id = lambda n: {r["id"]: r for r in rows[n]}
    no_eggs = {r["id"] for r in rows["egg_groups"] if r["identifier"] == bb.UNDISCOVERED}
    eggs = collections.defaultdict(set)
    for r in rows["pokemon_egg_groups"]:
        eggs[r["species_id"]].add(r["egg_group_id"])
    location_names = english(rows["location_names"], "location_id")
    areas = {}
    prose = english(rows["location_area_prose"], "location_area_id")
    for r in rows["location_areas"]:
        place = location_names.get(r["location_id"], r["location_id"])
        areas[r["id"]] = prose.get(r["id"]) or (f"{place} ({r['identifier']})" if r["identifier"] else place)
    methods = english(rows["encounter_method_prose"], "encounter_method_id")
    conditions = english(rows["encounter_condition_value_prose"], "encounter_condition_value_id")
    cmap = collections.defaultdict(list)
    for r in rows["encounter_condition_value_map"]:
        cmap[r["encounter_id"]].append(r["encounter_condition_value_id"])
    return {"species": by_id("pokemon_species"), "pokemon": by_id("pokemon"), "versions": by_id("versions"),
            "version_groups": by_id("version_groups"), "slots": by_id("encounter_slots"),
            "methods": {r["id"]: methods.get(r["id"], r["identifier"]) for r in rows["encounter_methods"]},
            "conditions": {r["id"]: conditions.get(r["id"], r["identifier"])
                           for r in rows["encounter_condition_values"]},
            "areas": areas, "encounters": rows["encounters"], "cmap": dict(cmap),
            "breeds": {sid for sid in by_id("pokemon_species") if eggs.get(sid) and not eggs[sid] & no_eggs},
            "default": {p["species_id"]: p["identifier"] for p in rows["pokemon"] if p["is_default"] == "1"}}


def pokeapi_game(api, game):
    """One PokeAPI game: (versions, {pokemon: status}, [(pokemon, place, method, chance, min, max, (conditions),
    (versions))]). Rows of one Pokemon, place, method, conditions and version are merged: their slots' chances add up
    (a slot listed twice counts once) and the levels span them all."""
    vg = next(v for v in api["version_groups"].values() if v["identifier"] == game)
    versions = [v["identifier"] for v in sorted(api["versions"].values(), key=lambda v: int(v["id"]))
                if v["version_group_id"] == vg["id"]]
    merged = {}
    for e in api["encounters"]:
        version = api["versions"].get(e["version_id"])
        if not version or version["version_group_id"] != vg["id"]:
            continue
        slot = api["slots"][e["encounter_slot_id"]]
        conds = tuple(sorted({api["conditions"][c] for c in api["cmap"].get(e["id"], [])}))
        key = (api["pokemon"][e["pokemon_id"]]["identifier"], api["areas"][e["location_area_id"]],
               api["methods"][slot["encounter_method_id"]], conds, version["identifier"])
        m = merged.setdefault(key, {"slots": {}, "min": int(e["min_level"]), "max": int(e["max_level"])})
        m["slots"][slot["id"]] = int(slot["rarity"] or 0)
        m["min"], m["max"] = min(m["min"], int(e["min_level"])), max(m["max"], int(e["max_level"]))
    by_versions = collections.defaultdict(set)
    for (pokemon, place, method, conds, version), m in merged.items():
        by_versions[(pokemon, place, method, sum(m["slots"].values()), m["min"], m["max"], conds)].add(version)
    rows = [(*k, tuple(v for v in versions if v in vs)) for k, vs in by_versions.items()]
    return versions, pokeapi_statuses(api, game, int(vg["generation_id"]), {r[0] for r in rows}), rows


def pokeapi_statuses(api, game, gen, caught):
    """c for every Pokemon with an encounter. Then by species: e for an evolution of one the game has (not from a later
    generation, nor by a place the game lacks), b for a first stage whose evolution the game has and can breed (in a
    game with breeding). Trade and transfer aren't guessed."""
    sp = api["species"]
    out = {p: "c" for p in caught}
    have = {api["pokemon"][pid]["species_id"] for pid in api["pokemon"] if api["pokemon"][pid]["identifier"] in caught}
    in_gen = lambda sid: int(sp[sid]["generation_id"]) <= gen and sp[sid]["identifier"] not in NO_EVOLVE.get(game, ())

    def evolve():
        grew = True
        while grew:
            grew = False
            for sid, s in sp.items():
                if sid not in have and s["evolves_from_species_id"] in have and in_gen(sid):
                    have.add(sid)
                    out.setdefault(api["default"][sid], "e")
                    grew = True

    evolve()
    if game not in bb.NO_BREEDING:
        children = collections.defaultdict(list)
        for sid, s in sp.items():
            children[s["evolves_from_species_id"]].append(sid)
        descendants = lambda sid: [d for c in children.get(sid, []) for d in (c, *descendants(c))]
        for sid, s in sp.items():
            first = not s["evolves_from_species_id"]
            if sid not in have and first and in_gen(sid) and any(d in have and d in api["breeds"]
                                                                 for d in descendants(sid)):
                have.add(sid)
                out.setdefault(api["default"][sid], "b")
        evolve()
    return out


# Pokedex Tracker


def tracker_values(text):
    """Tracker's "values" column, a Postgres text array ({"Route 3",Cortondo}), as trimmed strings."""
    inner = text.strip()[1:-1]
    if not inner:
        return []
    row = next(csv.reader([inner], escapechar="\\", doublequote=False))
    return [v.strip() for v in row if v.strip()]


NOT_IN_GAME = ("Currently unavailable", "Not available yet")


def tracker_status(value):
    """What one of Tracker's location strings says: a status code ("c" for a place), or None when it says the
    Pokemon isn't in the game ("Currently unavailable") or points at the base game or expansion ("Refer to ...")."""
    low = value.lower()
    if value.startswith(NOT_IN_GAME) or value.startswith("Refer to"):
        return None
    if value.startswith(("Evolve ", "Evovle ")):
        return "e"
    if value.startswith("Breed "):
        return "b"
    if value.startswith("Trade from "):
        return "t"
    if "event" in low and (value.startswith(("Event", "Receive", "Special Event", "Tera Raid Battle Event",
                                             "Transfer"))):
        return "ev"
    if value.startswith("Transfer"):
        return "x"
    return "c"


def parse_tracker(texts):
    return {n: bf.rows(t) for n, t in texts.items()}


def tracker_version(tracker_game):
    """Tracker's game id as a version id: an expansion pass counts as its version (sword_expansion_pass: sword)."""
    v = tracker_game.replace("_expansion_pass", "").replace("legends_za_mega_dimension", "legends_za")
    return v.replace("_", "-")


def tracker_names(api, tracker):
    """Tracker's Pokemon ids -> PokeAPI Pokemon names. A regional form is the species' first Pokemon named
    <species>-<region>; Gigantamax counts as the species itself."""
    out = {}
    pokemon = sorted(api["pokemon"].values(), key=lambda p: int(p["id"]))
    for r in tracker["pokemon"]:
        species = api["species"].get(r["national_id"])
        if not species:
            raise ValueError(f"Tracker's Pokemon {r['name']} ({r['national_id']}) isn't in PokeAPI")
        if r["form"] in ("", "gigantamax"):
            out[r["id"]] = api["default"][species["id"]]
            continue
        prefix = f"{species['identifier']}-{r['form']}"
        match = [p["identifier"] for p in pokemon if p["species_id"] == species["id"]
                 and (p["identifier"] == prefix or p["identifier"].startswith(prefix + "-"))]
        if not match:
            raise ValueError(f"Tracker's form {r['name']} {r['form']} has no PokeAPI Pokemon")
        out[r["id"]] = match[0]
    return out


def tracker_game(names, tracker, game):
    """One Tracker game (all its versions and expansion passes): (versions, {pokemon: status}, [(pokemon, place,
    (versions))])."""
    ids = [t for t, g in bf.TRACKER_GAMES.items() if g == game]
    versions = list(dict.fromkeys(tracker_version(t) for t in ids))
    codes, places = collections.defaultdict(list), collections.defaultdict(set)
    for r in tracker["locations"]:
        if r["game_id"] not in ids:
            continue
        pokemon = names[r["pokemon_id"]]
        for value in tracker_values(r["values"]):
            code = tracker_status(value)
            codes[pokemon].append(code)
            if code == "c":
                places[(pokemon, value)].add(tracker_version(r["game_id"]))
    statuses = {p: best(c) for p, c in codes.items() if best(c)}
    rows = [(p, place, tuple(v for v in versions if v in vs)) for (p, place), vs in places.items()]
    return versions, statuses, rows


# The file


def build(api, tracker, commits, built, games=GAMES):
    """catch.json as a dict (see the README for the fields)."""
    names = tracker_names(api, tracker)
    raw = {}
    for game in games:
        src = "pokeapi" if game in POKEAPI_GAMES else "pokedextracker"
        raw[game] = (src, *(pokeapi_game(api, game) if src == "pokeapi" else tracker_game(names, tracker, game)))
    order = {p["identifier"]: int(p["id"]) for p in api["pokemon"].values()}
    pk = sorted({p for _, _, st, rows in raw.values() for p in (*st, *(r[0] for r in rows))}, key=order.__getitem__)
    loc = sorted({r[1] for _, _, _, rows in raw.values() for r in rows})
    m = sorted({r[2] for src, _, _, rows in raw.values() if src == "pokeapi" for r in rows})
    c = sorted({x for src, _, _, rows in raw.values() if src == "pokeapi" for r in rows for x in r[6]})
    cs = sorted({tuple(sorted(c.index(x) for x in r[6])) for src, _, _, rows in raw.values() if src == "pokeapi"
                 for r in rows} | {()}, key=lambda t: (len(t), t))
    index = lambda xs: {x: i for i, x in enumerate(xs)}
    ipk, iloc, im, ic, ics = index(pk), index(loc), index(m), index(c), index(cs)
    out = {}
    for game, (src, versions, statuses, rows) in raw.items():
        mask = lambda vs: sum(1 << versions.index(v) for v in vs)
        if src == "pokeapi":
            en = [[ipk[p], iloc[place], im[method], chance, lo, hi, ics[tuple(sorted(ic[x] for x in conds))], mask(vs)]
                  for p, place, method, chance, lo, hi, conds, vs in rows]
        else:
            en = [[ipk[p], iloc[place], mask(vs)] for p, place, vs in rows]
        a = {code: sorted(ipk[p] for p, s in statuses.items() if s == code) for code in ORDER}
        out[game] = {"src": src, "v": versions, "a": {k: v for k, v in a.items() if v}, "en": sorted(en)}
    return {"schema": SCHEMA, "built": built, "sources": commits, "pk": pk, "loc": loc, "m": m, "c": c,
            "cs": [list(t) for t in cs], "games": out, "shiny": {}}


def availability(doc, game):
    """{Pokemon name: status code} of one game, read back from the file."""
    return {doc["pk"][i]: code for code, ps in doc["games"][game]["a"].items() for i in ps}


def encounters(doc, game, pokemon):
    """One Pokemon's rows in one game, read back from the file as dicts."""
    g = doc["games"][game]
    i = doc["pk"].index(pokemon) if pokemon in doc["pk"] else None
    versions = lambda mask: [v for b, v in enumerate(g["v"]) if mask >> b & 1]
    out = []
    for r in g["en"]:
        if r[0] != i:
            continue
        if g["src"] == "pokeapi":
            out.append({"place": doc["loc"][r[1]], "method": doc["m"][r[2]], "chance": r[3], "min": r[4], "max": r[5],
                        "conditions": [doc["c"][x] for x in doc["cs"][r[6]]], "versions": versions(r[7])})
        else:
            out.append({"place": doc["loc"][r[1]], "versions": versions(r[2])})
    return out


def write(doc, path="catch.json"):
    """Writes catch.json unless only the built time would change. Returns whether it wrote."""
    return bf.write(doc, path)


# Pinned sources. Bump a commit (and rebuild) to take in newer data.
POKEAPI = bf.POKEAPI    # PokeAPI/pokeapi, data/v2/csv (the commit forms.json and breeding.json use)
TRACKER = bf.TRACKER    # pokedextracker/pokedextracker.com, seeds/
CSVS = ("versions", "version_groups", "pokemon_species", "pokemon", "egg_groups", "pokemon_egg_groups",
        "encounter_methods", "encounter_method_prose", "encounter_slots", "encounter_condition_values",
        "encounter_condition_value_prose", "encounter_condition_value_map", "encounters", "locations",
        "location_names", "location_areas", "location_area_prose")


def main(argv):
    api = parse_pokeapi({n: bf.raw("PokeAPI/pokeapi", POKEAPI, f"data/v2/csv/{n}.csv") for n in CSVS})
    tracker = parse_tracker({n: bf.raw("pokedextracker/pokedextracker.com", TRACKER, f"seeds/{n}.csv")
                             for n in ("pokemon", "locations")})
    doc = build(api, tracker, commits={"pokeapi": POKEAPI, "pokedextracker": TRACKER},
                built=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    empty = [g for g, v in doc["games"].items() if not v["en"]]
    if empty:
        raise SystemExit(f"no encounters for {empty}")
    wrote = write(doc)
    print(f"catch.json: {'written' if wrote else 'unchanged'}, {len(bf.to_json(doc)) // 1024} KB, "
          f"{len(doc['pk'])} Pokemon, {len(doc['loc'])} places", file=sys.stderr)
    for g, v in doc["games"].items():
        counts = ", ".join(f"{k} {len(ps)}" for k, ps in v["a"].items())
        print(f"  {g} ({v['src']}): {len({r[0] for r in v['en']})} with encounters; {counts}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
