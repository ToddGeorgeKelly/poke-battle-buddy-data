"""A tiny slice of every source build_breeding.py reads: real rows from PokeAPI's CSVs (only the columns it uses), with
made-up learnset rows, and a made-up Showdown learnsets file."""

# PokeAPI data/v2/csv
POKEMON_SPECIES = """id,identifier,evolves_from_species_id,evolution_chain_id,gender_rate,is_baby,hatch_counter
25,pikachu,172,10,4,0,10
26,raichu,25,10,4,0,10
81,magnemite,,34,-1,0,20
132,ditto,,66,-1,0,20
143,snorlax,446,72,1,0,40
172,pichu,,10,4,1,10
183,marill,298,90,4,0,10
184,azumarill,183,90,4,0,10
298,azurill,,90,6,1,10
446,munchlax,,72,1,1,40
489,phione,,250,-1,0,40
490,manaphy,,250,-1,0,10
677,espurr,,348,4,0,20
133,eevee,,67,1,0,35
244,entei,,113,-1,0,80
29,nidoran-f,,12,8,0,20
32,nidoran-m,,13,0,0,20
313,volbeat,,156,0,0,15
314,illumise,,157,8,0,15
678,meowstic,677,348,4,0,20
"""

EVOLUTION_CHAINS = """id,baby_trigger_item_id
12,
13,
67,
113,
156,
157,
10,
34,
66,
72,293
90,231
250,
348,
"""

ITEMS = """id,identifier
231,sea-incense
293,full-incense
"""

EGG_GROUPS = """id,identifier
3,bug
8,humanshape
1,monster
2,water1
5,ground
6,fairy
10,mineral
13,ditto
15,no-eggs
"""

POKEMON_EGG_GROUPS = """species_id,egg_group_id
25,5
25,6
26,5
26,6
81,10
132,13
143,1
172,15
183,2
183,6
184,2
184,6
298,15
446,15
489,2
489,6
490,2
490,6
677,5
678,5
133,5
244,15
29,1
29,5
32,1
32,5
313,3
313,8
314,3
314,8
"""

POKEMON = """id,identifier,species_id,is_default
25,pikachu,25,1
26,raichu,26,1
81,magnemite,81,1
132,ditto,132,1
143,snorlax,143,1
172,pichu,172,1
183,marill,183,1
184,azumarill,184,1
298,azurill,298,1
446,munchlax,446,1
489,phione,489,1
490,manaphy,490,1
677,espurr,677,1
678,meowstic-male,678,1
10025,meowstic-female,678,0
10100,raichu-alola,26,0
10160,pichu-spiky-eared,172,0
133,eevee,133,1
10159,eevee-starter,133,0
244,entei,244,1
"""

MOVES = """id,identifier
8,ice-punch
9,thunder-punch
33,tackle
57,surf
58,ice-beam
84,thunder-shock
85,thunderbolt
186,sweet-kiss
187,belly-drum
204,charm
273,wish
344,volt-tackle
245,extreme-speed
"""

VERSION_GROUPS = """id,identifier,generation_id
1,red-blue,1
3,gold-silver,2
4,crystal,2
23,brilliant-diamond-shining-pearl,8
24,legends-arceus,8
25,scarlet-violet,9
26,the-teal-mask,9
"""

POKEMON_MOVE_METHODS = """id,identifier
1,level-up
2,egg
3,tutor
4,machine
6,light-ball-egg
"""

# method 1 level-up, 2 egg, 3 tutor, 4 machine, 6 light-ball-egg (Volt Tackle, left out)
POKEMON_MOVES = """pokemon_id,version_group_id,move_id,pokemon_move_method_id
25,1,84,1
25,1,85,4
172,3,186,2
172,3,84,1
25,3,85,4
26,3,85,4
172,4,186,2
172,4,8,3
25,4,186,3
25,4,8,3
172,25,186,2
172,25,273,2
172,25,344,6
25,25,186,2
25,25,273,2
25,25,85,4
26,25,85,4
10100,25,85,4
26,25,273,1
183,25,187,2
184,25,187,1
446,25,204,2
143,25,204,4
678,25,204,2
10025,25,204,2
183,26,57,2
10160,25,186,2
10160,25,273,2
244,25,245,2
183,26,57,4
446,24,33,1
446,23,204,2
143,23,204,1
"""

# Showdown data/learnsets.ts (Gen 9) and data/mods/gen8bdsp/learnsets.ts: egg moves on the lowest stage only, ids
# without hyphens. syclar is a CAP Pokemon PokeAPI doesn't have; meowstic is Showdown's name for meowstic-male.
SHOWDOWN_GEN9 = """export const Learnsets: import('../sim/dex-species').LearnsetDataTable = {
\tpichu: {
\t\tlearnset: {
\t\t\tsweetkiss: ["9E", "8E", "7E"],
\t\t\twish: ["9E"],
\t\t\tvolttackle: ["9R", "8R"],
\t\t},
\t},
\tmarill: {
\t\tlearnset: {
\t\t\tbellydrum: ["9E", "8E"],
\t\t\tsurf: ["9M", "9E"],
\t\t},
\t},
\tmunchlax: {
\t\tlearnset: {
\t\t\tcharm: ["9E"],
\t\t},
\t},
\tmeowstic: {
\t\tlearnset: {
\t\t\tcharm: ["9E"],
\t\t},
\t},
\tmeowsticf: {
\t\tlearnset: {
\t\t\tcharm: ["9E"],
\t\t},
\t},
\tsnorlax: {
\t\tlearnset: {
\t\t\tcharm: ["9M", "8E"],
\t\t},
\t},
\teeveestarter: {
\t\tlearnset: {
\t\t\twish: ["9E"],
\t\t},
\t},
\tsyclar: {
\t\tlearnset: {
\t\t\ticebeam: ["9E"],
\t\t},
\t},
};
"""

SHOWDOWN_BDSP = """export const Learnsets: import('../../../sim/dex-species').ModdedLearnsetDataTable = {
\tmunchlax: {
\t\tlearnset: {
\t\t\tcharm: ["8E"],
\t\t},
\t},
};
"""

# The app's games (GameDataTable.swift), with the version groups that count for each.
GAMES = {"scarlet-violet": ["scarlet-violet", "the-teal-mask"], "legends-arceus": ["legends-arceus"],
         "brilliant-diamond-shining-pearl": ["brilliant-diamond-shining-pearl"], "crystal": ["crystal"],
         "gold-silver": ["gold-silver"], "red-blue": ["red-blue"]}
