# Poke Battle Buddy data

Usage stats for the Poke Battle Buddy (iOS) Team Builder: the most-used Pokémon in each
competitive format, with their common moves, items, abilities, Tera types, EV spreads, teammates, and checks and counters.

- `meta.json` is what the app downloads (about once a day per device).
- `sets.json` is the most popular set of every Pokémon in each format, for the Pokédex's SET tab (also downloaded at
  most once a day). `meta.json` keeps only the top 50 of the newest month; `sets.json` keeps every Pokémon that reached
  1% usage in some month since 2022-11, with the set from the newest such month and that month (`"mo": "2026-09"`).
  Same fields as `meta.json`, same formats and the same 1500 rating cutoff. `build_sets.py` merges each new month over
  the old file, so a Pokémon missing this month keeps its last set. `build_sets.py --backfill 2022-11` rebuilds it from
  every month since then (it was made that way once).
- `bbr.json` is every Pokémon's BBR (Battle Buddy Rating) in Generations 1–9: one number for how good it is in singles
  battles, on Smogon BSR's scale (average 420). `build_bbr.py` makes it from Pokémon Showdown's data with a one-on-one battle
  simulation of every pair of Pokémon plus stats, typing, abilities and key moves, weighted by how well each part
  predicted Smogon's tiers in Generations 4–9 (code in `bbr/`, copied from the research:
  [BBR research, part 3](https://github.com/ToddGeorgeKelly/Poke-Battle-Buddy-LIVE/blob/main/PokeBattleBuddy/BBR%20Research/BBR_RESEARCH.md)).
  It's only recomputed when Showdown's data (or the model) changes.
  - **The field.** Each generation is rated against its own field, the one the research validated: that gen's tiered
    Pokémon, picked exactly as the research picks them, with that gen's moves, abilities, type chart and mechanics.
    Averages, z-scores and the 420/120 scale all come from that field, so a field Pokémon gets the research's own number
    for that gen; the 11 weights are the same in every gen. In Gen 9 every Showdown Pokémon (about 1,300, including
    past-gen forms like Megas) is rated: Pokémon in Gen 9 use their Gen 9 moves, Pokémon not in Gen 9 use moves from
    every generation (National Dex). Gens 1–8 rate the Pokémon in that gen's games, NFEs and untiered ones included.
  - **Gens 1–3.** The research fitted and checked the model on Gens 4–9 only; Gens 1–3 use the same weights with
    their own mechanics: a move's type decides whether it's physical or special, Gen 1 has 15 types (one Special stat,
    which Showdown's data gives as equal Sp. Atk and Sp. Def), Gen 1–2 Pokémon have no abilities (so the ability parts
    add nothing), and Stealth Rock (Gen 4) counts for nothing. Checked against Smogon's tiers in those gens (rank
    correlation over each field, model not refitted): Gen 1 0.78, Gen 2 0.85, Gen 3 0.81, against 0.58, 0.80 and 0.81
    for Gen 4's ratings, which the app used for them before.
  - **Shape.** Gen 9 is at the top level (`ratings`, `unrated`), as it was before the older gens, so older app versions
    keep working. Gens 1–8 are under `gens`, keyed by the gen as a string, each with its own `ratings` and `unrated`:
    `{"schema": 1, "model": …, "source": <Showdown commit>, "built": …, "ratings": {…}, "unrated": […],
    "gens": {"1": {"ratings": {"mewtwo": 864, …}, "unrated": ["ditto", "smeargle"]}, …, "8": {…}}}`.
    Keys are Showdown IDs; ratings are whole numbers from 0 to 999. A Pokémon missing from a gen's `ratings` isn't in
    that gen's games (or is unrated).
  - **Forms.** Palafin gets Palafin-Hero's rating and Terapagos gets Terapagos-Terastal's (they always battle in those
    forms), in every gen that has them.
  - **Unrated.** `"unrated": ["ditto", "smeargle"]` lists Pokémon no model of stats and learnsets fits (Imposter, Sketch);
    they're left out of `ratings`. `built` is a UTC timestamp (`2026-10-27T18:04:00Z`), so a same-day rebuild sorts later.
  - **Data.** `node bbr/export_showdown.mjs ps/data gen` turns a checkout of Showdown's `data/` (with `data/mods/gen1`–`gen8`)
    into `gen/gen1.json` … `gen9.json`, each gen's mods applied the way the research's `load.mjs` does;
    `python3 build_bbr.py --data gen --source <commit>` rates every gen (about half an hour). Gens 1–3 are only
    exported, and rated, when the checkout has `data/mods/gen1`–`gen3`; without them bbr.json has Gens 4–9.
  - **Tests.** Set up once with `python3 -m venv .venv && .venv/bin/pip install numpy pytest` (`.venv` is gitignored),
    then `.venv/bin/python -m pytest tests` (fast: field selection per gen, forms, unrated list, file shape,
    the per-gen export, plus meta.json's output and sets.json's merging). `pytest --runslow tests/test_parity.py`
    (about 20 minutes) checks that production matches the research's ratings in every gen
    (`tests/fixtures/research_gen<g>_ratings.json`, made by `tests/fixtures/research_ref.py`); it needs the research's
    `gen4.json` … `gen9.json` (`BBR_RESEARCH_GEN`, default `/tmp/bbr/gen`).
- `forms.json` is the form dex (about 56 KB): every species' collectable forms and gender looks, which games have each
  form, and which can't be had shiny. `python3 build_forms.py` builds it from pinned commits of PokeAPI's CSVs and
  sprite repo, Pokédex Tracker's seeds and Showdown's formats-data (commits at the top of `build_forms.py`, written to
  `sources`), Showdown's sprite folders as they are that day, and two hand-written files in `forms/`. It rewrites the
  file only when something besides `built` changed.
  - **Shape.** `{"schema": 1, "built": …, "sources": {"pokeapi", "sprites", "pokedextracker", "showdown": <commit>},
    "gender": {"n": [genderless species], "m": [male only], "f": [female only]}, "species": {<PokeAPI species name>:
    {"n": 666, "gd": true, "forms": [{…}, …]}}, "shiny": {"never": [keys], "locked": {key: [game ids]}}}`. A species
    not in `gender` can be either gender. `species` lists only species with two or more forms or a gender difference
    (Spinda gets none); `gd` means a visible gender difference (PokeAPI's `has_gender_differences`, 102 species). The
    species' own form is first, then PokeAPI's order.
  - **A form.** `k` is the catch-log key. A Pokémon's default form goes by its PokeAPI Pokémon name, so the app's
    existing keys stay valid (`vivillon`, `raichu-alola`, `meowstic-female`); any other form goes by its PokeAPI form
    name (`vivillon-polar`). `l` is PokeAPI's English form name ("Polar Pattern"). `s` is the Showdown sprite name
    (`home/`, `ani/`), missing when Showdown has none (then use PokeAPI's). `p` is the PokeAPI sprite name
    (`666-polar`, `10100`), missing for the species' own form, whose sprite is its dex number. Flags, left out when
    false:
    - `f`: a female sprite exists, so the form gets a ♀ mark.
    - `g`: `"m"` or `"f"`, the form is one gender only (caps, Cosplay Pikachu, and the rows of Meowstic and the other
      species split by gender).
    - `ev`: event-only.
    - `h`: a look-alike or held-item form (Scatterbug and Spewpa patterns, Mothim cloaks, Arceus, Silvally and Genesect
      types, Xerneas Active…), shown only when the player turns them on.
    - `r`: already its own row in the app's Pokédex list (regional forms, Rotom, Therians, fusions, caps…). It's still
      listed so the form bar shows it; it uses the same key, so a mark isn't counted twice.
  - **Games** use the app's game ids, newest first, plus `home`.
    - No `c`: the form is wherever its species is.
    - `c`: the games it can be caught or received in (an empty list means none). The form is then only in `c` and `t`.
    - `t`: games it can only be transferred or traded into.
    - `x`: games that have the species but not this form.
    - `nh`: it can't go to HOME. Every other form can.
    - Regional forms get `c` from Pokédex Tracker's locations (a "Transfer…" location doesn't count). They get `t` for
      each HOME game whose Showdown data has the form when Tracker has nowhere to get it there. For example, Alolan
      Raichu is `"t": ["scarlet-violet"]`.
  - **Left out:** battle-only forms, Megas, Primals, Gigantamax, Totems, Eternamax, Minior's Meteor shell, Koraidon's and
    Miraidon's ride modes, and Arceus's ??? type. Pyroar's, Frillish's and Jellicent's female forms are left out too,
    because their ♀ marks cover them. The lists are at the top of `build_forms.py`.
  - **Hand-written** (`forms/`, one entry per line):
    - `form_games.json`: per-game exceptions (`c`, `t`, `x`, `nh`) for cosmetic and event forms.
    - `shiny_locks.json`: `"never": true` or `"locked": [games]`.
    - Each entry has `verified` and a `note`, which aren't shipped. They were checked against Serebii, Bulbapedia, PokéPC
      and news posts, and nothing was copied from them. The build fails on a key that isn't a tracked form or on an
      unknown game id.
  - **Tests.** `tests/test_build_forms.py` (fixtures in `tests/fake_forms.py`, no network). `tests/test_published_forms.py`
    checks the built file: Vivillon has 20 patterns, Unown 28, Alcremie 63, there are no Megas, Gigantamax or Totems, no
    Spinda, and Alolan Raichu is transfer-only in Scarlet / Violet.
- `build_meta.py` builds meta.json. A [GitHub Action](.github/workflows/update.yml) runs it (and `build_sets.py`) every day, finds the newest month,
  generation and most-played VGC/Champions formats on its own, and commits only when something changed.

## Credits

- Usage statistics: [Smogon University](https://www.smogon.com/stats/), from battles on [Pokémon Showdown](https://pokemonshowdown.com/).
- Tiers, Pokémon, move and ability data for BBR: [Pokémon Showdown](https://github.com/smogon/pokemon-showdown) (MIT license).
- Forms, genders and sprite names in forms.json: [PokéAPI](https://github.com/PokeAPI/pokeapi) (BSD-3-Clause license),
  Copyright (c) © 2013–2023 Paul Hallett and PokéAPI contributors; and the [PokéAPI sprites](https://github.com/PokeAPI/sprites) repo (CC0).
- Regional forms per game in forms.json: [Pokédex Tracker](https://github.com/pokedextracker/pokedextracker.com) seed
  data (MIT license), Copyright (c) 2016 Pokédex Tracker.
- Which forms each HOME game accepts, and sprite names, in forms.json: [Pokémon Showdown](https://github.com/smogon/pokemon-showdown) (MIT license).

Pokémon is © Nintendo, Creatures Inc. and GAME FREAK inc. This project isn't affiliated with them, Smogon or Pokémon Showdown.
