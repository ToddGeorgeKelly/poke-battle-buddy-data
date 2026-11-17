"""Builds breeding.json: what Poke Battle Buddy's breeding section needs. Every species' egg groups, gender ratio,
hatch cycles and baby facts, and for each game that has breeding, every egg move with who learns it and how, so the
app can work out egg move partners itself.

    python3 build_breeding.py   # fetches the pinned sources below, writes breeding.json

Sources (pinned to a commit so a rebuild gives the same file):
- Species, egg groups, babies, incense and learnsets: PokeAPI's CSVs (BSD-3), https://github.com/PokeAPI/pokeapi
- The check of Scarlet / Violet's and BDSP's egg moves: Pokemon Showdown's learnsets (MIT),
  https://github.com/smogon/pokemon-showdown
"""
import collections, datetime, sys
import build_forms as bf

SCHEMA = 1

# The app's games (GameDataTable.swift), newest first, with the PokeAPI version groups whose learnsets count.
GAMES = {
    "legends-za": ["legends-za", "mega-dimension"],
    "scarlet-violet": ["scarlet-violet", "the-teal-mask", "the-indigo-disk"],
    "legends-arceus": ["legends-arceus"],
    "brilliant-diamond-shining-pearl": ["brilliant-diamond-shining-pearl"],
    "sword-shield": ["sword-shield", "the-isle-of-armor", "the-crown-tundra"],
    "lets-go-pikachu-lets-go-eevee": ["lets-go-pikachu-lets-go-eevee"],
    "ultra-sun-ultra-moon": ["ultra-sun-ultra-moon"], "sun-moon": ["sun-moon"],
    "omega-ruby-alpha-sapphire": ["omega-ruby-alpha-sapphire"], "x-y": ["x-y"],
    "black-2-white-2": ["black-2-white-2"], "black-white": ["black-white"],
    "heartgold-soulsilver": ["heartgold-soulsilver"], "platinum": ["platinum"], "diamond-pearl": ["diamond-pearl"],
    "emerald": ["emerald"], "firered-leafgreen": ["firered-leafgreen"], "ruby-sapphire": ["ruby-sapphire"],
    "crystal": ["crystal"], "gold-silver": ["gold-silver"], "yellow": ["yellow"], "red-blue": ["red-blue"],
}

# Games with no Day Care, picnic or Eggs (Bulbapedia, "Pokemon breeding"; Legends: Arceus's babies are wild).
NO_BREEDING = {"red-blue", "yellow", "lets-go-pikachu-lets-go-eevee", "legends-arceus", "legends-za"}

# PokeAPI's learn methods that count, by their code in breeding.json. Light Ball's Volt Tackle, form changes and the
# rest are left out.
METHODS = {"level-up": "l", "egg": "e", "machine": "m", "tutor": "t"}

UNDISCOVERED = "no-eggs"
OFFSPRING = {"manaphy": "phione"}  # Manaphy's eggs hatch into Phione (its own evolution chain in PokeAPI)
# Eggs that can also hatch into another line: Nidoran F's into Nidoran M, Illumise's into Volbeat.
ALSO_OFFSPRING = {"nidoran-f": ["nidoran-m"], "illumise": ["volbeat"]}


def rules(game, gen):
    """Hints for the app's partner rules: "father" only the father passes egg moves, "tm" he also passes TM/HM moves
    (Gens 2-5), "tutor" and tutor moves (Crystal), "mirror-herb" any Pokemon that knows the move can pass it at a
    picnic with a Mirror Herb (Scarlet / Violet)."""
    out = ["father", "tm"] if 2 <= gen <= 5 else []
    if game == "crystal":
        out.append("tutor")
    if game == "scarlet-violet":
        out.append("mirror-herb")
    return out


def parse_pokeapi(texts):
    """PokeAPI's CSVs (name -> text) as lookup tables, with the learnsets grouped by version group:
    "learnsets": {version group: [(pokemon, move, method code)]}."""
    rows = {n: bf.rows(t) for n, t in texts.items() if n != "pokemon_moves"}
    by_id = lambda n: {r["id"]: r for r in rows[n]}
    pokemon, moves = by_id("pokemon"), by_id("moves")
    vgs = by_id("version_groups")
    methods = {r["id"]: METHODS.get(r["identifier"]) for r in rows["pokemon_move_methods"]}
    learnsets = collections.defaultdict(list)
    for r in bf.rows(texts["pokemon_moves"]):
        code = methods.get(r["pokemon_move_method_id"])
        if code and r["pokemon_id"] in pokemon and r["move_id"] in moves:
            learnsets[vgs[r["version_group_id"]]["identifier"]].append(
                (pokemon[r["pokemon_id"]]["identifier"], moves[r["move_id"]]["identifier"], code))
    egg_group = {r["id"]: r["identifier"] for r in rows["egg_groups"]}
    egg_groups = collections.defaultdict(list)
    for r in rows["pokemon_egg_groups"]:
        egg_groups[r["species_id"]].append(egg_group[r["egg_group_id"]])
    return {"species": by_id("pokemon_species"), "pokemon": pokemon, "moves": moves,
            "pokemon_ids": {p["identifier"]: int(p["id"]) for p in pokemon.values()},
            "pokemon_species": {p["identifier"]: p["species_id"] for p in pokemon.values()},
            "chains": by_id("evolution_chains"), "items": by_id("items"), "egg_groups": dict(egg_groups),
            "version_groups": {r["identifier"]: r for r in rows["version_groups"]}, "learnsets": dict(learnsets)}


def ancestors(api, species_id):
    """The species and what it evolves from, up to its first stage: [self, parent, ..., first stage]."""
    out = [species_id]
    while api["species"][out[-1]]["evolves_from_species_id"] in api["species"]:
        out.append(api["species"][out[-1]]["evolves_from_species_id"])
    return out


def incense(api, species):
    item = api["chains"].get(species["evolution_chain_id"], {}).get("baby_trigger_item_id")
    return api["items"][item]["identifier"] if item else None


def species_table(api):
    """{species name: {"eg", "g", "h", and "b", "i", "bp", "o" when they apply}} (see the README)."""
    sp = api["species"]
    name = lambda sid: sp[sid]["identifier"]
    lines = {sid: ancestors(api, sid) for sid in sp}
    out = {}
    for sid in sorted(sp, key=int):
        s = sp[sid]
        eg = api["egg_groups"].get(sid, [])
        entry = {"eg": eg, "g": int(s["gender_rate"]), "h": int(s["hatch_counter"])}
        if s["is_baby"] == "1":
            entry["b"] = True
            if incense(api, s):
                entry["i"] = incense(api, s)
            entry["bp"] = [name(o) for o in sorted(sp, key=int)
                           if o != sid and sid in lines[o] and UNDISCOVERED not in api["egg_groups"].get(o, [])]
        if UNDISCOVERED not in eg:
            line = lines[sid]
            first = line[-1]
            if sp[first]["is_baby"] == "1" and incense(api, sp[first]) and len(line) > 1:
                first = line[-2]  # without the incense, the egg hatches into the stage after the baby
            offspring = OFFSPRING.get(s["identifier"], name(first))
            if offspring != s["identifier"]:
                entry["o"] = offspring
            if s["identifier"] in ALSO_OFFSPRING:
                entry["ao"] = ALSO_OFFSPRING[s["identifier"]]
        out[s["identifier"]] = entry
    return out


def pokemon_order(api, name):
    """PokeAPI's Pokemon id of a Pokemon name: lists of Pokemon are in this order."""
    return api["pokemon_ids"][name]


def hatches(api, pokemon):
    """Whether a Pokemon can come from an Egg: it breeds, or it's a baby (Pichu hatches from Pikachu's Eggs). PokeAPI
    lists "egg moves" for legendaries such as Entei too; those are left out."""
    species = api["species"][api["pokemon_species"][pokemon]]
    return species["is_baby"] == "1" or UNDISCOVERED not in api["egg_groups"].get(species["id"], [])


def learners(api, version_groups):
    """Every egg move in these version groups (a game and its DLC): {move: {method code: [Pokemon]}}, the Pokemon in
    PokeAPI's order. Only moves that are an egg move there of some Pokemon that can hatch are listed."""
    found = collections.defaultdict(lambda: collections.defaultdict(set))
    for vg in version_groups:
        for pokemon, move, code in api["learnsets"].get(vg, []):
            if code != "e" or hatches(api, pokemon):
                found[move][code].add(pokemon)
    return {move: {code: sorted(names, key=lambda n: pokemon_order(api, n)) for code, names in sorted(how.items())}
            for move, how in found.items() if "e" in how}


def generation(api, version_groups):
    return int(api["version_groups"][version_groups[0]]["generation_id"])


ENTRY_MOVES = bf.re.compile(r"^\t\t\t(\w+): \[(.*?)\]", bf.re.M)


def parse_showdown_egg_moves(text, gen):
    """Showdown's egg moves for one generation ("9E"): {Showdown id: {move ids}}, Pokemon with none left out."""
    out = {}
    for name, body in bf.ENTRY.findall(text):
        moves = {m for m, codes in ENTRY_MOVES.findall(body) if f'"{gen}E"' in codes}
        if moves:
            out[name] = moves
    return out


def showdown_names(api):
    """Showdown id -> PokeAPI Pokemon name: the Pokemon's own name without hyphens (or forms.json's Showdown name),
    or for a species' default Pokemon, the species name (Showdown's "basculin" is PokeAPI's basculin-red-striped)."""
    out = {}
    for p in api["pokemon"].values():
        if p["is_default"] == "1":
            out[bf.sid(api["species"][p["species_id"]]["identifier"])] = p["identifier"]
    for p in api["pokemon"].values():
        out[bf.sid(bf.SHOWDOWN_NAMES.get(p["identifier"], p["identifier"]))] = p["identifier"]
    return out


def disagreements(api, showdown, games=GAMES):
    """Where PokeAPI's egg moves differ from Showdown's: [(game, Pokemon, move, "pokeapi" or "showdown")], the side
    that has the move. Showdown lists egg moves on first stages only, so PokeAPI's evolved Pokemon are only compared
    when Showdown has them too; Showdown Pokemon PokeAPI doesn't have (CAP), or doesn't have in that game (Partner
    Eevee), are skipped. A form Showdown files under its species (Spiky-eared Pichu) is compared with the species."""
    names = showdown_names(api)
    move_names = {bf.sid(m["identifier"]): m["identifier"] for m in api["moves"].values()}
    species_of = {p["identifier"]: api["species"][p["species_id"]] for p in api["pokemon"].values()}
    out = []
    for game, theirs in showdown.items():
        ours = collections.defaultdict(set)
        for move, how in learners(api, games[game]).items():
            for pokemon in how["e"]:
                ours[pokemon].add(move)
        in_game = {p for vg in games[game] for p, _, _ in api["learnsets"].get(vg, [])}
        by_pokemon = {names[sd_id]: sd_moves for sd_id, sd_moves in theirs.items()
                      if names.get(sd_id) in in_game}
        default = {p["species_id"]: p["identifier"] for p in api["pokemon"].values() if p["is_default"] == "1"}

        def compare(pokemon, sd_moves):
            mine = {bf.sid(m): m for m in ours.get(pokemon, ())}
            return ([(game, pokemon, mine[m], "pokeapi") for m in mine.keys() - sd_moves] +
                    [(game, pokemon, move_names.get(m, m), "showdown") for m in sd_moves - mine.keys()])

        for pokemon, sd_moves in by_pokemon.items():
            out += compare(pokemon, sd_moves)
        for pokemon, moves in ours.items():
            if pokemon in by_pokemon:
                continue
            species_pokemon = default.get(api["pokemon_species"][pokemon])
            if species_pokemon in by_pokemon:
                out += compare(pokemon, by_pokemon[species_pokemon])
            elif not species_of[pokemon]["evolves_from_species_id"]:
                out += [(game, pokemon, m, "pokeapi") for m in moves]
    return sorted(out)


# Real disagreements between PokeAPI and Showdown at the pinned commits, left as PokeAPI has them (breeding.json ships
# PokeAPI's egg moves). Each is (game, Pokemon, move, the source that has it). The build fails on any other
# disagreement, and on an entry here that no longer disagrees, so this list stays current when a commit is bumped.
SV = "scarlet-violet"
ALLOWED = {
    # PokeAPI has Zangoose's SV egg moves (it came back in The Indigo Disk); Showdown lists none for Gen 9.
    *((SV, "zangoose", m, "pokeapi") for m in ("belly-drum", "counter", "curse", "disable", "double-hit", "double-kick",
                                              "feint", "final-gambit", "flail", "fury-swipes", "night-slash",
                                              "quick-guard")),
    (SV, "cramorant", "belch", "pokeapi"),
    (SV, "plusle", "nuzzle", "pokeapi"), (SV, "minun", "nuzzle", "pokeapi"),
    (SV, "fomantis", "superpower", "showdown"),
    (SV, "noibat", "switcheroo", "showdown"),
    (SV, "rockruff", "sucker-punch", "showdown"), (SV, "rockruff-own-tempo", "sucker-punch", "showdown"),
}


def check_showdown(found, allowed):
    unexplained = [d for d in found if d not in allowed]
    if unexplained:
        raise ValueError("PokeAPI and Showdown disagree on egg moves: " + "; ".join(map(str, unexplained)))
    stale = sorted(set(allowed) - set(found))
    if stale:
        raise ValueError("allowed disagreements that no longer disagree: " + "; ".join(map(str, stale)))


def build(api, showdown, commits, built, games=GAMES, allowed=ALLOWED):
    """breeding.json as a dict (see the README for the fields)."""
    check_showdown(disagreements(api, showdown, games), allowed)
    out, names = {}, set()
    for game, vgs in games.items():
        gen = generation(api, vgs)
        entry = {"gen": gen, "br": game not in NO_BREEDING}
        if entry["br"]:
            if rules(game, gen):
                entry["r"] = rules(game, gen)
            entry["em"] = learners(api, vgs)
            names |= {p for how in entry["em"].values() for ps in how.values() for p in ps}
        out[game] = entry
    pk = sorted(names, key=lambda n: pokemon_order(api, n))
    index = {n: i for i, n in enumerate(pk)}
    for entry in out.values():
        for how in entry.get("em", {}).values():
            for code in how:
                how[code] = [index[p] for p in how[code]]
    return {"schema": SCHEMA, "built": built, "sources": commits, "species": species_table(api), "games": out,
            "pk": pk}


def write(doc, path="breeding.json"):
    """Writes breeding.json unless only the built time would change. Returns whether it wrote."""
    return bf.write(doc, path)


# Pinned sources. Bump a commit (and rebuild) to take in newer data.
POKEAPI = "e4f981e5cb03c1fe33d436b1ee8e1197fbb0af84"         # PokeAPI/pokeapi, data/v2/csv
SHOWDOWN = "f827a1d41064e0dec4c19c6ea0394fcf0c23479c"        # smogon/pokemon-showdown, learnsets
SHOWDOWN_CHECKS = {"scarlet-violet": ("data/learnsets.ts", 9),
                   "brilliant-diamond-shining-pearl": ("data/mods/gen8bdsp/learnsets.ts", 8)}
CSVS = ("pokemon_species", "evolution_chains", "items", "egg_groups", "pokemon_egg_groups", "pokemon", "moves",
        "version_groups", "pokemon_move_methods", "pokemon_moves")


def main(argv):
    api = parse_pokeapi({n: bf.raw("PokeAPI/pokeapi", POKEAPI, f"data/v2/csv/{n}.csv") for n in CSVS})
    showdown = {g: parse_showdown_egg_moves(bf.raw("smogon/pokemon-showdown", SHOWDOWN, path), gen)
                for g, (path, gen) in SHOWDOWN_CHECKS.items()}
    doc = build(api, showdown, commits={"pokeapi": POKEAPI, "showdown": SHOWDOWN},
                built=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    wrote = write(doc)
    breeding = [g for g, v in doc["games"].items() if v["br"]]
    print(f"breeding.json: {'written' if wrote else 'unchanged'}, {len(bf.to_json(doc)) // 1024} KB, "
          f"{len(doc['species'])} species, {len(breeding)} breeding games, {len(doc['pk'])} Pokemon", file=sys.stderr)
    if ALLOWED:
        print(f"PokeAPI and Showdown disagree (allowed): {len(ALLOWED)}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
