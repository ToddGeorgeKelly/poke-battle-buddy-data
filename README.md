# Poke Battle Buddy data

Usage stats for the Poke Battle Buddy (iOS) Team Builder: the most-used Pokémon in each
competitive format, with their common moves, items, abilities, Tera types, EV spreads, teammates, and checks and counters.

- `meta.json` is what the app downloads (about once a day per device).
- `bbr.json` is every Pokémon's BBR (Battle Buddy Rating): one number for how good it is in singles battles, on
  Smogon BSR's scale (average 420). `build_bbr.py` makes it from Pokémon Showdown's data with a one-on-one battle
  simulation of every pair of Pokémon plus stats, typing, abilities and key moves, weighted by how well each part
  predicted Smogon's tiers in Generations 4–9 (code in `bbr/`, copied from the research:
  [BBR research, part 3](https://github.com/ToddGeorgeKelly/Poke-Battle-Buddy-LIVE/blob/main/PokeBattleBuddy/BBR%20Research/BBR_RESEARCH.md)).
  It's only recomputed when Showdown's data (or the model) changes.
  - **The field.** Every Showdown Pokémon (about 1,300, including past-gen forms like Megas) is rated against the same
    field the research validated: Gen 9's tiered Pokémon, picked exactly as the research picks them. Averages,
    z-scores and the 420/120 scale all come from that field, so a field Pokémon gets the research's own number.
    Pokémon in Gen 9 use their Gen 9 moves; Pokémon not in Gen 9 use moves from every generation (National Dex).
  - **Forms.** Palafin gets Palafin-Hero's rating and Terapagos gets Terapagos-Terastal's (they always battle in those forms).
  - **Unrated.** `"unrated": ["ditto", "smeargle"]` lists Pokémon no model of stats and learnsets fits (Imposter, Sketch);
    they're left out of `ratings`. `built` is a UTC timestamp (`2026-10-27T18:04:00Z`), so a same-day rebuild sorts later.
  - **Tests.** `pip install numpy pytest && pytest tests` (fast: field selection, forms, unrated list, file shape).
    `pytest --runslow tests/test_parity.py` (a few minutes) checks that production matches the research's Gen 9 ratings
    (`tests/fixtures/research_gen9_ratings.json`); it needs the research's `gen9.json` (`BBR_RESEARCH_GEN9`, default `/tmp/bbr/gen/gen9.json`).
- `build_meta.py` builds meta.json. A [GitHub Action](.github/workflows/update.yml) runs it every day, finds the newest month,
  generation and most-played VGC/Champions formats on its own, and commits only when something changed.

## Credits

- Usage statistics: [Smogon University](https://www.smogon.com/stats/), from battles on [Pokémon Showdown](https://pokemonshowdown.com/).
- Tiers, Pokémon, move and ability data for BBR: [Pokémon Showdown](https://github.com/smogon/pokemon-showdown) (MIT license).

Pokémon is © Nintendo, Creatures Inc. and GAME FREAK inc. This project isn't affiliated with them, Smogon or Pokémon Showdown.
