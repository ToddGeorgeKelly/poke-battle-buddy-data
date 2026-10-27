# Poke Battle Buddy data

Usage stats for the Poke Battle Buddy (iOS) Team Builder: the most-used Pokémon in each
competitive format, with their common moves, items, abilities, Tera types, EV spreads, teammates, and checks and counters.

- `meta.json` is what the app downloads (about once a day per device).
- `bbr.json` is every Pokémon's BBR (Battle Buddy Rating): one number for how good it is in singles battles, on
  Smogon BSR's scale (average 420). `build_bbr.py` makes it from Pokémon Showdown's data with a one-on-one battle
  simulation of every pair of Pokémon plus stats, typing, abilities and key moves, weighted by how well each part
  predicted Smogon's tiers in Generations 4–9 (code in `bbr/`; the research is in the app's "BBR Research" folder).
  It's only recomputed when Showdown's data changes.
- `build_meta.py` builds meta.json. A [GitHub Action](.github/workflows/update.yml) runs it every day, finds the newest month,
  generation and most-played VGC/Champions formats on its own, and commits only when something changed.

## Credits

- Usage statistics: [Smogon University](https://www.smogon.com/stats/), from battles on [Pokémon Showdown](https://pokemonshowdown.com/).
- Tiers, Pokémon, move and ability data for BBR: [Pokémon Showdown](https://github.com/smogon/pokemon-showdown) (MIT license).

Pokémon is © Nintendo, Creatures Inc. and GAME FREAK inc. This project isn't affiliated with them, Smogon or Pokémon Showdown.
