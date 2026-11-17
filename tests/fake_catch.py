"""A tiny slice of every source build_catch.py reads: PokeAPI's CSVs (only the columns it uses; the Viridian Forest and
Great Marsh rows are real, the rest made up) and Pokedex Tracker's seeds (made-up rows in the real wording)."""

# PokeAPI data/v2/csv
VERSIONS = """id,version_group_id,identifier
1,1,red
2,1,blue
4,3,gold
5,3,silver
12,8,diamond
13,8,pearl
15,10,heartgold
16,10,soulsilver
"""

VERSION_GROUPS = """id,identifier,generation_id
1,red-blue,1
3,gold-silver,2
8,diamond-pearl,4
10,heartgold-soulsilver,4
"""

POKEMON_SPECIES = """id,identifier,generation_id,evolves_from_species_id
25,pikachu,1,172
26,raichu,1,25
41,zubat,1,
42,golbat,1,41
81,magnemite,1,
82,magneton,1,81
144,articuno,1,
150,mewtwo,1,
151,mew,1,
163,hoothoot,2,
164,noctowl,2,163
169,crobat,2,42
172,pichu,2,
251,celebi,2,
462,magnezone,4,82
"""

POKEMON = """id,identifier,species_id,is_default
25,pikachu,25,1
26,raichu,26,1
41,zubat,41,1
42,golbat,42,1
81,magnemite,81,1
82,magneton,82,1
144,articuno,144,1
150,mewtwo,150,1
151,mew,151,1
163,hoothoot,163,1
164,noctowl,164,1
169,crobat,169,1
172,pichu,172,1
251,celebi,251,1
462,magnezone,462,1
10100,raichu-alola,26,0
10195,pikachu-gmax,25,0
"""

EGG_GROUPS = """id,identifier
4,flying
5,ground
6,fairy
10,mineral
15,no-eggs
"""

POKEMON_EGG_GROUPS = """species_id,egg_group_id
25,5
25,6
26,5
26,6
41,4
42,4
169,4
81,10
82,10
462,10
144,15
163,4
164,4
172,15
"""

ENCOUNTER_METHODS = """id,identifier
1,walk
4,super-rod
18,gift
"""

ENCOUNTER_METHOD_PROSE = """encounter_method_id,local_language_id,name
1,9,Walking in tall grass or a cave
1,5,Marcher dans les hautes herbes
4,9,Fishing with a Super Rod
"""

ENCOUNTER_SLOTS = """id,version_group_id,encounter_method_id,slot,rarity
75,1,1,9,4
76,1,1,10,1
80,1,1,1,20
3,8,1,3,10
4,8,1,4,10
200,3,1,1,30
201,3,1,2,20
300,10,1,1,40
301,10,18,,
"""

ENCOUNTER_CONDITION_VALUES = """id,encounter_condition_id,identifier,is_default
3,2,time-morning,0
4,2,time-day,1
5,2,time-night,0
"""

ENCOUNTER_CONDITION_VALUE_PROSE = """encounter_condition_value_id,local_language_id,name
3,9,In the morning
4,9,During the day
5,9,At night
5,5,La nuit
"""

LOCATIONS = """id,identifier
11,great-marsh
155,viridian-forest
160,seafoam-islands
170,route-29
180,power-plant
"""

LOCATION_NAMES = """location_id,local_language_id,name,subtitle
11,9,Great Marsh,
155,9,Viridian Forest,
155,6,Vertania-Wald,
160,9,Seafoam Islands,
170,9,Route 29,
180,9,Power Plant,
"""

LOCATION_AREAS = """id,location_id,game_index,identifier
24,11,24,area-1
321,155,138,
330,160,140,1f
340,170,150,
350,180,160,
"""

LOCATION_AREA_PROSE = """location_area_id,local_language_id,name
24,9,Great Marsh Area 1
321,9,Viridian Forest
321,6,Vertania-Wald
340,9,Route 29
350,9,Power Plant
"""

# Pikachu in Viridian Forest in Red and Blue (real: Lv 3 at 4% plus Lv 5 at 1%; the Lv 3 row is listed twice, as
# PokeAPI does for some slots), Golbat in Seafoam Islands in Red only, Magnemite in the Power Plant, Hoothoot in the
# Great Marsh at night (real) and Noctowl there by day in Diamond and Pearl, Noctowl on Route 29 at night in Gold and
# Silver, Pikachu there too, Magnemite in HeartGold / SoulSilver plus a gift Articuno.
ENCOUNTERS = """id,version_id,location_area_id,encounter_slot_id,pokemon_id,min_level,max_level
24267,1,321,75,25,3,3
24268,1,321,76,25,5,5
24269,1,321,75,25,3,3
24847,2,321,75,25,3,3
24848,2,321,76,25,5,5
5000,1,330,80,42,30,32
5001,1,350,80,81,21,23
5002,2,350,80,81,21,23
582,12,24,3,163,24,24
583,13,24,3,163,24,24
584,12,24,4,164,30,30
585,13,24,4,164,30,30
6000,4,340,200,164,10,10
6001,5,340,200,164,10,10
6002,4,340,201,25,4,4
6003,5,340,201,25,4,4
7000,15,350,300,81,20,20
7001,16,350,300,81,20,20
7002,15,330,301,144,50,50
7003,16,330,301,144,50,50
"""

ENCOUNTER_CONDITION_VALUE_MAP = """encounter_id,encounter_condition_value_id
582,5
583,5
584,4
585,4
6000,5
6001,5
"""

POKEAPI = {"versions": VERSIONS, "version_groups": VERSION_GROUPS, "pokemon_species": POKEMON_SPECIES,
           "pokemon": POKEMON, "egg_groups": EGG_GROUPS, "pokemon_egg_groups": POKEMON_EGG_GROUPS,
           "encounter_methods": ENCOUNTER_METHODS, "encounter_method_prose": ENCOUNTER_METHOD_PROSE,
           "encounter_slots": ENCOUNTER_SLOTS, "encounter_condition_values": ENCOUNTER_CONDITION_VALUES,
           "encounter_condition_value_prose": ENCOUNTER_CONDITION_VALUE_PROSE,
           "encounter_condition_value_map": ENCOUNTER_CONDITION_VALUE_MAP, "encounters": ENCOUNTERS,
           "locations": LOCATIONS, "location_names": LOCATION_NAMES, "location_areas": LOCATION_AREAS,
           "location_area_prose": LOCATION_AREA_PROSE}

# Pokedex Tracker seeds/
TRACKER_POKEMON = """national_id,name,id,form
25,Pikachu,25,
26,Raichu,26,
41,Zubat,41,
151,Mew,151,
163,Hoothoot,163,
164,Noctowl,164,
172,Pichu,172,
251,Celebi,251,
26,Raichu,1100,alola
26,Raichu,1102,alola
25,Pikachu,1101,gigantamax
"""

# X / Y: Pikachu in both, Raichu by evolving, Pichu by breeding, Hoothoot caught in Y only (X trades for it), Mew
# event-only, Celebi transfer-only, Zubat not in the game. Sword / Shield: Alolan Raichu in the expansion pass only
# (listed twice by Tracker), Gigantamax Pikachu's raid counts for Pikachu.
TRACKER_LOCATIONS = """game_id,pokemon_id,value,values
x,25,Santalune Forest,"{""Santalune Forest""}"
y,25,Santalune Forest,"{""Santalune Forest""}"
x,26,Evolve Pikachu,"{""Evolve Pikachu""}"
y,26,Evolve Pikachu,"{""Evolve Pikachu""}"
x,172,Breed Pikachu/Raichu,"{""Breed Pikachu/Raichu""}"
y,172,Breed Pikachu/Raichu,"{""Breed Pikachu/Raichu""}"
x,163,Trade from Y,"{""Trade from Y""}"
y,163,"Route 3,  Route 4 ","{""Route 3"","" Route 4 ""}"
x,151,Event Only,"{""Event Only""}"
y,151,Event Only,"{""Event Only""}"
x,251,Transfer required,"{""Transfer required""}"
y,251,Transfer required,"{""Transfer required""}"
x,41,Currently unavailable,"{""Currently unavailable""}"
y,41,Currently unavailable,"{""Currently unavailable""}"
sword,25,Route 4,"{""Route 4""}"
shield,25,Route 4,"{""Route 4""}"
sword,1101,Gigantamax Raid Battles: Lake of Outrage,"{""Gigantamax Raid Battles: Lake of Outrage""}"
sword,1100,Refer to Sword and Shield (Expansion Pass),"{""Refer to Sword and Shield (Expansion Pass)""}"
shield,1100,Refer to Sword and Shield (Expansion Pass),"{""Refer to Sword and Shield (Expansion Pass)""}"
sword_expansion_pass,1100,Max Raid Battles: Workout Sea,"{""Max Raid Battles: Workout Sea""}"
shield_expansion_pass,1102,Max Raid Battles: Workout Sea,"{""Max Raid Battles: Workout Sea""}"
sword_expansion_pass,25,Refer to Sword and Shield,"{""Refer to Sword and Shield""}"
"""

TRACKER = {"pokemon": TRACKER_POKEMON, "locations": TRACKER_LOCATIONS}

# The games the fake sources cover, in the app's order.
GAMES = ["sword-shield", "x-y", "heartgold-soulsilver", "diamond-pearl", "gold-silver", "red-blue"]
