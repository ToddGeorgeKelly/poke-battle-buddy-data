"""A tiny slice of every source build_forms.py reads, copied from the real files (only the columns it uses)."""

# PokeAPI data/v2/csv
POKEMON_SPECIES = """id,identifier,gender_rate,has_gender_differences
19,rattata,4,1
20,raticate,4,1
25,pikachu,4,1
26,raichu,4,1
201,unown,-1,0
327,spinda,4,0
351,castform,4,0
664,scatterbug,4,0
666,vivillon,4,0
668,pyroar,7,1
678,meowstic,4,1
681,aegislash,4,0
716,xerneas,-1,0
774,minior,-1,0
1007,koraidon,-1,0
128,tauros,0,0
29,nidoran-f,8,0
"""

POKEMON = """id,identifier,species_id,is_default
19,rattata,19,1
20,raticate,20,1
25,pikachu,25,1
26,raichu,26,1
29,nidoran-f,29,1
128,tauros,128,1
201,unown,201,1
327,spinda,327,1
351,castform,351,1
664,scatterbug,664,1
666,vivillon,666,1
668,pyroar-male,668,1
678,meowstic-male,678,1
681,aegislash-shield,681,1
716,xerneas,716,1
774,minior-red-meteor,774,1
1007,koraidon,1007,1
10025,meowstic-female,678,0
10026,aegislash-blade,681,0
10085,pikachu-cosplay,25,0
10091,rattata-alola,19,0
10093,raticate-totem-alola,20,0
10094,pikachu-original-cap,25,0
10100,raichu-alola,26,0
10136,minior-red,774,0
10158,pikachu-starter,25,0
10199,pikachu-gmax,25,0
10250,tauros-paldea-combat-breed,128,0
10264,koraidon-limited-build,1007,0
10304,raichu-mega-x,26,0
"""

POKEMON_FORMS = """id,identifier,form_identifier,pokemon_id,is_default,is_battle_only,is_mega
19,rattata,,19,1,0,0
20,raticate,,20,1,0,0
25,pikachu,,25,1,0,0
26,raichu,,26,1,0,0
29,nidoran-f,,29,1,0,0
128,tauros,,128,1,0,0
201,unown-a,a,201,1,0,0
327,spinda,,327,1,0,0
351,castform,,351,1,0,0
664,scatterbug-icy-snow,icy-snow,664,1,0,0
666,vivillon-meadow,meadow,666,1,0,0
668,pyroar-male,male,668,1,0,0
678,meowstic-male,male,678,1,0,0
681,aegislash-shield,shield,681,1,0,0
716,xerneas-active,active,716,0,1,0
774,minior-red-meteor,red-meteor,774,1,0,0
1007,koraidon-apex-build,apex-build,1007,1,0,0
10026,unown-exclamation,exclamation,201,0,0,0
10087,vivillon-polar,polar,666,0,0,0
10092,vivillon-fancy,fancy,666,0,0,0
10124,meowstic-female,female,10025,1,0,0
10125,aegislash-blade,blade,10026,1,1,0
10132,xerneas-neutral,neutral,716,1,0,0
10162,vivillon-poke-ball,poke-ball,666,0,0,0
10187,pikachu-cosplay,cosplay,10085,1,0,0
10190,castform-sunny,sunny,351,0,1,0
10195,raticate-totem-alola,totem-alola,10093,1,0,0
10196,pikachu-original-cap,original-cap,10094,1,0,0
10200,rattata-alola,alola,10091,1,0,0
10202,raichu-alola,alola,10100,1,0,0
10255,minior-red,red,10136,1,0,0
10271,scatterbug-polar,polar,664,0,0,0
10300,koraidon-limited-build,limited-build,10264,0,0,0
10317,pikachu-starter,starter,10158,1,0,0
10368,pikachu-gmax,gmax,10199,1,1,0
10400,tauros-paldea-combat-breed,paldea-combat-breed,10250,1,0,0
10529,raichu-mega-x,mega-x,10304,1,1,1
10551,pyroar-female,female,668,0,0,0
"""

POKEMON_FORM_NAMES = """pokemon_form_id,local_language_id,form_name,pokemon_name
10087,9,Polar Pattern,
10087,5,Motif Banquise,
666,9,Meadow Pattern,
10202,9,Alolan Form,Alolan Raichu
10196,9,Original Cap,
201,9,A,
"""

# PokeAPI/sprites sprites/pokemon/female/*.png and sprites/pokemon/*.png (names without .png)
FEMALE_SPRITES = {"19", "20", "25", "26", "668", "678", "10158"}
POKEAPI_SPRITES = {"25", "26", "666", "666-polar", "666-fancy", "666-poke-ball", "201", "201-exclamation", "10100",
                   "10094", "10158", "10085", "10091", "10136", "10025", "664-polar", "716-active", "10250"}

# play.pokemonshowdown.com/sprites/home/ and /ani/ (names without the extension)
SHOWDOWN_SPRITES = {"pikachu", "pikachu-f", "pikachu-original", "pikachu-starter", "pikachu-starter-f",
                    "pikachu-cosplay", "raichu", "raichu-alola", "vivillon", "vivillon-polar", "vivillon-fancy",
                    "vivillon-pokeball", "unown", "unown-exclamation", "meowstic", "meowstic-f", "minior", "rattata", "rattata-alola",
                    "taurospaldeacombat", "tauros-paldeacombat", "alcremie", "alcremie-rubyswirl-berry",
                    "alcremie-vanillacream-berry", "alcremie-rubyswirl", "xerneas", "xerneas-neutral"}

# Pokedex Tracker seeds/pokemon.csv and seeds/locations.csv
TRACKER_POKEMON = """national_id,name,id,form
19,Rattata,19,
19,Rattata,804,alola
26,Raichu,805,alola
128,Tauros,1010,paldea
25,Pikachu,830,gigantamax
"""

TRACKER_LOCATIONS = """game_id,pokemon_id,value
sun,805,Evolve Pikachu
moon,805,Evolve Pikachu
ultra_sun,805,Evolve Pikachu
lets_go_pikachu,805,Saffron City Trade
sword,805,Refer to Sword and Shield (Expansion Pass)
sword_expansion_pass,805,Gift from Diglett Master (Find 40 Diglett)
legends_za,805,Trade Raichu to Griddella at Quasartico Inc. (Side Mission 108)
sun,804,"Route 1, Route 2"
sword,804,Transfer from Pokémon HOME
scarlet,1010,"East Province Area One, East Province Area Two"
scarlet_expansion_pass,1010,Refer to Scarlet and Violet
sword,19,Route 1
"""

# Showdown formats-data.ts for one game: an entry that's in the game, one that's "Past", one cleared with null.
SHOWDOWN_FORMATS = """export const FormatsData: import('../sim/dex-species').SpeciesFormatsDataTable = {
	raichualola: {
		tier: "ZU",
		doublesTier: "(DUU)",
	},
	rattataalola: {
		isNonstandard: "Past",
		tier: "Illegal",
	},
	taurospaldeacombat: {
		isNonstandard: null,
	},
};
"""
