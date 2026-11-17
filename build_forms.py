"""Builds forms.json: the form dex of Poke Battle Buddy. Every species' collectable forms, which have a female look,
which games have each form, and which forms can't be had shiny.

    python3 build_forms.py   # fetches the pinned sources below, writes forms.json

Sources (pinned to a commit so a rebuild gives the same file):
- Forms, gender and sprites: PokeAPI's CSVs and sprite repo (BSD-3), https://github.com/PokeAPI/pokeapi
- Regional forms per game: Pokedex Tracker's seed data (MIT, (c) 2016 Pokedex Tracker),
  https://github.com/pokedextracker/pokedextracker.com/tree/master/seeds
- Which forms a HOME game accepts, and sprite names: Pokemon Showdown (MIT), https://github.com/smogon/pokemon-showdown
- Hand-written: forms/form_games.json (per-game exceptions) and forms/shiny_locks.json (shiny locks), checked against
  Serebii, Bulbapedia and PKHeX but not copied from them.
"""
import csv, datetime, io, json, os, re, sys
import build_meta as meta

SCHEMA = 1

# Forms nobody can catch or keep: Totems, Koraidon's and Miraidon's ride modes, Eternamax, Minior's Meteor shell
# (PokeAPI doesn't flag these as battle-only). Megas, Primals, Gigantamax and battle-only forms go by PokeAPI's flags.
SKIP_PARTS = ("-totem", "-gmax", "-primal", "-eternamax", "-meteor")
SKIP_SPECIES = {"spinda"}                     # its patterns are random per Pokemon: no form marks
SKIP_KEYS = {"arceus-unknown",                # the ??? type, never legitimately obtainable
             "pyroar-female", "frillish-female", "jellicent-female"}  # gender marks cover these
RIDE_MODES = {"koraidon", "miraidon"}          # every non-default form of these is a ride mode

# Shown only when the player turns on look-alike forms: they look the same as another form or come from a held item.
HIDDEN_SPECIES = {"scatterbug", "spewpa", "mothim", "arceus", "silvally", "genesect"}  # their non-default forms
HIDDEN_KEYS = {"xerneas-active", "greninja-battle-bond", "rockruff-own-tempo", "zygarde-10-power-construct",
               "zygarde-50-power-construct"}

CAPS = ("pikachu-original-cap", "pikachu-hoenn-cap", "pikachu-sinnoh-cap", "pikachu-unova-cap", "pikachu-kalos-cap",
        "pikachu-alola-cap", "pikachu-partner-cap", "pikachu-world-cap")
COSPLAY = ("pikachu-cosplay", "pikachu-rock-star", "pikachu-belle", "pikachu-pop-star", "pikachu-phd", "pikachu-libre")
EVENT_KEYS = set(CAPS) | set(COSPLAY) | {
    "pikachu-starter", "eevee-starter", "vivillon-fancy", "vivillon-poke-ball", "magearna-original", "zarude-dada",
    "pichu-spiky-eared", "floette-eternal", "keldeo-resolute"}

ENGLISH = "9"


def rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def parse_pokeapi(texts):
    """PokeAPI's CSVs (name -> text) as {"species": {id: row}, "pokemon": {id: row}, "forms": [row], "names": {form id:
    English form name}}."""
    return {"species": {r["id"]: r for r in rows(texts["pokemon_species"])},
            "pokemon": {r["id"]: r for r in rows(texts["pokemon"])},
            "forms": rows(texts["pokemon_forms"]),
            "names": {r["pokemon_form_id"]: r["form_name"] for r in rows(texts["pokemon_form_names"])
                      if r["local_language_id"] == ENGLISH and r["form_name"]}}


def form_key(form, pokemon):
    """The catch-log key: a Pokemon's default form goes by the PokeAPI Pokemon name (the app's existing keys),
    any other form by its PokeAPI form name."""
    return pokemon["identifier"] if form["is_default"] == "1" else form["identifier"]


def is_own(form, pokemon):
    """The species' own form: the default form of its default Pokemon."""
    return pokemon["is_default"] == "1" and form["is_default"] == "1"


def skipped(key, form, pokemon, species):
    if form["is_battle_only"] == "1" and key not in HIDDEN_KEYS:
        return True
    if form["is_mega"] == "1" or key in SKIP_KEYS or any(p in key for p in SKIP_PARTS):
        return True
    return species["identifier"] in RIDE_MODES and not is_own(form, pokemon)


def species_forms(api):
    """Every species' trackable forms, keyed by species name: {"n": dex number, "forms": [{"k": key, ...}]}.
    The species' own form comes first, then PokeAPI's order."""
    out = {}
    order = lambda f: (not is_own(f, api["pokemon"][f["pokemon_id"]]), int(f.get("order") or 0))
    for f in sorted(api["forms"], key=order):
        pokemon = api["pokemon"][f["pokemon_id"]]
        species = api["species"][pokemon["species_id"]]
        name, key = species["identifier"], form_key(f, pokemon)
        if name in SKIP_SPECIES or skipped(key, f, pokemon, species):
            continue
        # Fields starting with "_" are for the builder only and aren't written.
        own = is_own(f, pokemon)
        entry = {"k": key, "_pid": pokemon["id"], "_fid": f["form_identifier"], "_pdef": f["is_default"] == "1",
                 "_own": own}
        if f["id"] in api["names"]:
            entry["l"] = api["names"][f["id"]]
        if pokemon["is_default"] == "0" and f["is_default"] == "1":  # a Pokemon of its own: a row in the Pokedex
            entry["r"] = True
        if key in HIDDEN_KEYS or (name in HIDDEN_SPECIES and not own):
            entry["h"] = True
        if key in EVENT_KEYS:
            entry["ev"] = True
        sp = out.setdefault(name, {"n": int(species["id"]), "forms": []})
        if species["has_gender_differences"] == "1":
            sp["gd"] = True
        sp["forms"].append(entry)
    return out


def gender_lists(api):
    """Species that aren't both genders: "n" genderless, "m" male only, "f" female only (PokeAPI's gender_rate)."""
    lists = {"n": [], "m": [], "f": []}
    for s in api["species"].values():
        which = {"-1": "n", "0": "m", "8": "f"}.get(s["gender_rate"])
        if which:
            lists[which].append(s["identifier"])
    return {k: sorted(v) for k, v in lists.items()}


# Species whose genders are separate forms (each its own Pokedex row), and forms that are one gender only.
GENDER_FORM_SPECIES = {"meowstic", "indeedee", "basculegion", "oinkologne"}
FORM_GENDER = {**{k: "m" for k in CAPS}, **{k: "f" for k in COSPLAY}}

# Showdown sprite names that don't follow "<species>-<form>" with the hyphens inside each part dropped.
SHOWDOWN_NAMES = {
    **{k: k.replace("-cap", "") for k in CAPS},
    "minior-red": "minior", "xerneas": "xerneas-neutral", "xerneas-active": "xerneas",
    "maushold-family-of-four": "maushold-four", "meowstic-female": "meowstic-f", "indeedee-female": "indeedee-f",
    "basculegion-female": "basculegion-f", "oinkologne-female": "oinkologne-f",
    "tauros-paldea-combat-breed": "tauros-paldeacombat", "tauros-paldea-blaze-breed": "tauros-paldeablaze",
    "tauros-paldea-aqua-breed": "tauros-paldeaaqua", "darmanitan-galar-standard": "darmanitan-galar",
    "necrozma-dusk": "necrozma-duskmane", "necrozma-dawn": "necrozma-dawnwings",
    "greninja-battle-bond": "greninja-bond",
    "rockruff-own-tempo": "rockruff-dusk", "maushold-family-of-three": "maushold",
    "ogerpon-wellspring-mask": "ogerpon-wellspring", "ogerpon-hearthflame-mask": "ogerpon-hearthflame",
    "ogerpon-cornerstone-mask": "ogerpon-cornerstone",
    **{f"squawkabilly-{c}-plumage": f"squawkabilly-{c}" for c in ("blue", "yellow", "white")},
}
SWEETS = ("strawberry", "berry", "love", "star", "clover", "flower", "ribbon")


def sid(name):
    return name.replace("-", "")


def showdown_sprite(species, key, have, own=False):
    """The Showdown sprite name (home/, ani/) of a form, or None when Showdown has no such sprite. The species' own
    form (own) goes by the species name even when PokeAPI's has a suffix (deoxys-normal, meowstic-male)."""
    if key in SHOWDOWN_NAMES:
        name = SHOWDOWN_NAMES[key]
    elif own or key == species or not key.startswith(species + "-"):
        name = sid(species)
    elif species == "alcremie":  # alcremie-<cream>-<sweet>-sweet: Strawberry is left off, and Vanilla Cream with it
        cream, sweet = key[len("alcremie-"):-len("-sweet")].rsplit("-", 1)
        parts = [] if (cream, sweet) == ("vanilla-cream", "strawberry") else [sid(cream)]
        name = "-".join(["alcremie", *parts, *([] if sweet == "strawberry" else [sweet])])
    else:
        name = sid(species) + "-" + sid(key[len(species) + 1:])
    return name if name in have else None


def add_sprites(forms, api, female_ids, pokeapi_sprites, showdown_sprites):
    """Adds each form's sprites ("s" Showdown, "p" PokeAPI), female mark ("f") and one-gender mark ("g")."""
    for species, sp in forms.items():
        for f in sp["forms"]:
            s = showdown_sprite(species, f["k"], showdown_sprites, f["_own"])
            if s:
                f["s"] = s
            if not f["_own"]:
                p = f["_pid"] if f["_pdef"] else f"{sp['n']}-{f['_fid']}"
                if p in pokeapi_sprites:
                    f["p"] = p
            if species in GENDER_FORM_SPECIES:
                f["g"] = "f" if f["k"].endswith("-female") else "m"
            elif f["k"] in FORM_GENDER:
                f["g"] = FORM_GENDER[f["k"]]
            elif sp.get("gd") and f["_pdef"] and f["_pid"] in female_ids:
                f["f"] = True
    return forms


# The app's game ids, newest first (GameDataTable.swift), then Pokemon HOME.
GAMES = ["legends-za", "scarlet-violet", "legends-arceus", "brilliant-diamond-shining-pearl", "sword-shield",
         "lets-go-pikachu-lets-go-eevee", "ultra-sun-ultra-moon", "sun-moon", "omega-ruby-alpha-sapphire", "x-y",
         "black-2-white-2", "black-white", "heartgold-soulsilver", "platinum", "diamond-pearl", "emerald",
         "firered-leafgreen", "ruby-sapphire", "crystal", "gold-silver", "yellow", "red-blue", "home"]

# Pokedex Tracker's games (each version and expansion pass) as the app's games.
TRACKER_GAMES = {
    "x": "x-y", "y": "x-y", "omega_ruby": "omega-ruby-alpha-sapphire", "alpha_sapphire": "omega-ruby-alpha-sapphire",
    "sun": "sun-moon", "moon": "sun-moon", "ultra_sun": "ultra-sun-ultra-moon", "ultra_moon": "ultra-sun-ultra-moon",
    "lets_go_pikachu": "lets-go-pikachu-lets-go-eevee", "lets_go_eevee": "lets-go-pikachu-lets-go-eevee",
    "sword": "sword-shield", "shield": "sword-shield", "sword_expansion_pass": "sword-shield",
    "shield_expansion_pass": "sword-shield", "brilliant_diamond": "brilliant-diamond-shining-pearl",
    "shining_pearl": "brilliant-diamond-shining-pearl", "legends_arceus": "legends-arceus",
    "scarlet": "scarlet-violet", "violet": "scarlet-violet", "scarlet_expansion_pass": "scarlet-violet",
    "violet_expansion_pass": "scarlet-violet", "legends_za": "legends-za", "legends_za_mega_dimension": "legends-za"}

# The games Pokemon HOME can send Pokemon to, and the Showdown formats-data that says which Pokemon each one takes.
SHOWDOWN_GAMES = {"scarlet-violet": "data/formats-data.ts", "sword-shield": "data/mods/gen8/formats-data.ts",
                  "brilliant-diamond-shining-pearl": "data/mods/gen8bdsp/formats-data.ts",
                  "legends-arceus": "data/mods/gen8legends/formats-data.ts",
                  "legends-za": "data/mods/gen9legends/formats-data.ts"}

REGIONS = ("alola", "galar", "hisui", "paldea")
ENTRY = re.compile(r"^\t(\w+): \{(.*?)^\t\},?$", re.M | re.S)


def by_game(games):
    return sorted(set(games), key=GAMES.index)


def parse_showdown_formats(text):
    """The Pokemon (Showdown ids) a game has: every formats-data entry not marked nonstandard ("Past", "Future"...)."""
    return {k for k, body in ENTRY.findall(text) if not re.search(r'isNonstandard: "', body)}


def region_of(species, key):
    for r in REGIONS:
        if (key == f"{species}-{r}" or key.startswith(f"{species}-{r}-")) and not key.endswith("-cap"):
            return r
    return None


def regional_games(forms, tracker, present):
    """Games for each regional form: "c" where Pokedex Tracker has somewhere to get it, "t" the HOME games that take
    it (per Showdown) but have nowhere to get it, so it can only be transferred in."""
    ids = {r["id"]: (int(r["national_id"]), r["form"]) for r in tracker["pokemon"] if r["form"] in REGIONS}
    caught = {}
    for loc in tracker["locations"]:
        game, value = TRACKER_GAMES.get(loc["game_id"]), loc["value"]
        if loc["pokemon_id"] in ids and game and not value.startswith(("Transfer", "Refer to")):
            caught.setdefault(ids[loc["pokemon_id"]], set()).add(game)
    out = {}
    for species, sp in forms.items():
        for f in sp["forms"]:
            region = region_of(species, f["k"])
            if not region:
                continue
            c = caught.get((sp["n"], region), set())
            showdown_id = sid(SHOWDOWN_NAMES.get(f["k"], f["k"]))
            t = [g for g in present if showdown_id in present[g] and g not in c]
            out[f["k"]] = {"c": by_game(c), **({"t": by_game(t)} if t else {})}
    return out


FORM_GAME_FIELDS = ("c", "t", "x", "nh")


def check(known, entries, what):
    """Hand-written entries must name a tracked form and real game ids."""
    for key, v in entries.items():
        if key not in known:
            raise ValueError(f"{what}: {key} isn't a tracked form")
        for field in ("c", "t", "x", "locked"):
            bad = [g for g in v.get(field, []) if g not in GAMES]
            if bad:
                raise ValueError(f"{what}: {key} has unknown game ids {bad}")


def build(api, female, pokeapi_sprites, showdown_sprites, tracker, present, form_games, shiny_locks, commits, built):
    """forms.json as a dict (see the README for the fields)."""
    forms = add_sprites(species_forms(api), api, female, pokeapi_sprites, showdown_sprites)
    known = {f["k"] for sp in forms.values() for f in sp["forms"]}
    check(known, form_games, "form_games.json")
    check(known, shiny_locks, "shiny_locks.json")
    games = regional_games(forms, tracker, present)
    for key, v in form_games.items():
        games[key] = {k: (by_game(v[k]) if k != "nh" else v[k]) for k in FORM_GAME_FIELDS if k in v}
    species = {}
    for name, sp in forms.items():
        if len(sp["forms"]) < 2 and not sp.get("gd"):
            continue
        out = [{**{k: v for k, v in f.items() if not k.startswith("_")}, **games.get(f["k"], {})} for f in sp["forms"]]
        species[name] = {**{k: v for k, v in sp.items() if k != "forms"}, "forms": out}
    shiny = {"never": sorted(k for k, v in shiny_locks.items() if v.get("never")),
             "locked": {k: by_game(v["locked"]) for k, v in sorted(shiny_locks.items()) if v.get("locked")}}
    return {"schema": SCHEMA, "built": built, "sources": commits, "gender": gender_lists(api), "species": species,
            "shiny": shiny}


def to_json(doc):
    return json.dumps(doc, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def write(doc, path="forms.json"):
    """Writes forms.json unless only the built time would change. Returns whether it wrote."""
    try:
        with open(path) as f:
            old = json.load(f)
        if {**old, "built": doc["built"]} == doc:
            return False
    except FileNotFoundError:
        pass
    with open(path, "w") as f:
        f.write(to_json(doc))
    return True


# Pinned sources. Bump a commit (and rebuild) to take in newer data.
POKEAPI = "e4f981e5cb03c1fe33d436b1ee8e1197fbb0af84"         # PokeAPI/pokeapi, data/v2/csv
SPRITES = "c0542f7c51215d9672439012838c99f520596cbd"         # PokeAPI/sprites
TRACKER = "3f05678ab93a5c46851de7ff644e13a1d3eae52f"         # pokedextracker/pokedextracker.com, seeds/
SHOWDOWN = "f827a1d41064e0dec4c19c6ea0394fcf0c23479c"        # smogon/pokemon-showdown, formats-data
SHOWDOWN_SPRITE_DIRS = ("https://play.pokemonshowdown.com/sprites/home/",  # not versioned: read as of the build
                        "https://play.pokemonshowdown.com/sprites/ani/")
HERE = os.path.dirname(os.path.abspath(__file__))


def raw(repo, commit, path):
    return meta.fetch(f"https://raw.githubusercontent.com/{repo}/{commit}/{path}", as_json=False)


def listing_names(html):
    """Sprite names (no extension) in one of Showdown's folder listings."""
    return set(re.findall(r'href="\./([^"/?]+)\.(?:png|gif)"', html))


def tree_names(tree):
    """Image names (no .png) in one folder of a GitHub git tree."""
    assert not tree.get("truncated"), "GitHub truncated the tree listing"
    return {t["path"][:-4] for t in tree["tree"] if t["type"] == "blob" and t["path"].endswith(".png")}


def load_hand_written(name):
    with open(os.path.join(HERE, "forms", name)) as f:
        return json.load(f)


def main(argv):
    csvs = {n: raw("PokeAPI/pokeapi", POKEAPI, f"data/v2/csv/{n}.csv")
            for n in ("pokemon_species", "pokemon", "pokemon_forms", "pokemon_form_names")}
    trees = f"https://api.github.com/repos/PokeAPI/sprites/git/trees/{SPRITES}"
    tree = lambda path: tree_names(meta.fetch(f"{trees}:{path}"))
    showdown_sprites = set().union(*(listing_names(meta.fetch(u, as_json=False)) for u in SHOWDOWN_SPRITE_DIRS))
    tracker = {n: rows(raw("pokedextracker/pokedextracker.com", TRACKER, f"seeds/{n}.csv"))
               for n in ("pokemon", "locations")}
    present = {g: parse_showdown_formats(raw("smogon/pokemon-showdown", SHOWDOWN, path))
               for g, path in SHOWDOWN_GAMES.items()}
    doc = build(api=parse_pokeapi(csvs), female=tree("sprites/pokemon/female"), pokeapi_sprites=tree("sprites/pokemon"),
                showdown_sprites=showdown_sprites, tracker=tracker, present=present,
                form_games=load_hand_written("form_games.json"), shiny_locks=load_hand_written("shiny_locks.json"),
                commits={"pokeapi": POKEAPI, "sprites": SPRITES, "pokedextracker": TRACKER, "showdown": SHOWDOWN},
                built=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    wrote = write(doc)
    forms = [f for sp in doc["species"].values() for f in sp["forms"]]
    no_sprite = [f["k"] for f in forms if "s" not in f]
    print(f"forms.json: {'written' if wrote else 'unchanged'}, {len(to_json(doc)) // 1024} KB, "
          f"{len(doc['species'])} species, {len(forms)} forms", file=sys.stderr)
    if no_sprite:
        print(f"no Showdown sprite (the app uses PokeAPI's): {', '.join(no_sprite)}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
