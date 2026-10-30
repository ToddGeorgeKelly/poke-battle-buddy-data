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
- `bbr.json` is every Pokémon's BBR (Battle Buddy Rating) in Generations 4–9: one number for how good it is in singles
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
    every generation (National Dex). Gens 4–8 rate the Pokémon in that gen's games, NFEs and untiered ones included.
  - **Shape.** Gen 9 is at the top level (`ratings`, `unrated`), as it was before the older gens, so older app versions
    keep working. Gens 4–8 are under `gens`, keyed by the gen as a string, each with its own `ratings` and `unrated`:
    `{"schema": 1, "model": …, "source": <Showdown commit>, "built": …, "ratings": {…}, "unrated": […],
    "gens": {"4": {"ratings": {"garchomp": 652, …}, "unrated": ["ditto", "smeargle"]}, …, "8": {…}}}`.
    Keys are Showdown IDs; ratings are whole numbers from 0 to 999. A Pokémon missing from a gen's `ratings` isn't in
    that gen's games (or is unrated).
  - **Forms.** Palafin gets Palafin-Hero's rating and Terapagos gets Terapagos-Terastal's (they always battle in those
    forms), in every gen that has them.
  - **Unrated.** `"unrated": ["ditto", "smeargle"]` lists Pokémon no model of stats and learnsets fits (Imposter, Sketch);
    they're left out of `ratings`. `built` is a UTC timestamp (`2026-10-27T18:04:00Z`), so a same-day rebuild sorts later.
  - **Data.** `node bbr/export_showdown.mjs ps/data gen` turns a checkout of Showdown's `data/` (with `data/mods/gen4`–`gen8`)
    into `gen/gen4.json` … `gen9.json`, each gen's mods applied the way the research's `load.mjs` does;
    `python3 build_bbr.py --data gen --source <commit>` rates all six gens (about half an hour).
  - **Tests.** `pip install numpy pytest && pytest tests` (fast: field selection per gen, forms, unrated list, file shape,
    the per-gen export, plus meta.json's output and sets.json's merging). `pytest --runslow tests/test_parity.py`
    (about 20 minutes) checks that production matches the research's ratings in every gen
    (`tests/fixtures/research_gen<g>_ratings.json`, made by `tests/fixtures/research_ref.py`); it needs the research's
    `gen4.json` … `gen9.json` (`BBR_RESEARCH_GEN`, default `/tmp/bbr/gen`).
- `build_meta.py` builds meta.json. A [GitHub Action](.github/workflows/update.yml) runs it (and `build_sets.py`) every day, finds the newest month,
  generation and most-played VGC/Champions formats on its own, and commits only when something changed.

## Credits

- Usage statistics: [Smogon University](https://www.smogon.com/stats/), from battles on [Pokémon Showdown](https://pokemonshowdown.com/).
- Tiers, Pokémon, move and ability data for BBR: [Pokémon Showdown](https://github.com/smogon/pokemon-showdown) (MIT license).

Pokémon is © Nintendo, Creatures Inc. and GAME FREAK inc. This project isn't affiliated with them, Smogon or Pokémon Showdown.
