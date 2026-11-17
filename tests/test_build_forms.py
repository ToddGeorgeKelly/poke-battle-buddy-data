"""build_forms.py: the form dex's forms, gender flags, sprites, per-game availability and shiny locks."""
import pytest
import build_forms as bf
import fake_forms as fake


@pytest.fixture
def api():
    return bf.parse_pokeapi({"pokemon_species": fake.POKEMON_SPECIES, "pokemon": fake.POKEMON,
                             "pokemon_forms": fake.POKEMON_FORMS, "pokemon_form_names": fake.POKEMON_FORM_NAMES})


@pytest.fixture
def forms(api):
    return bf.species_forms(api)


def keys(forms, species):
    return [f["k"] for f in forms[species]["forms"]]


def form(forms, key):
    return next(f for s in forms.values() for f in s["forms"] if f["k"] == key)


# Which forms there are, and their catch-log keys


def test_a_pokemons_default_form_is_keyed_by_the_pokemon_name_and_cosmetic_forms_by_the_form_name(forms):
    assert keys(forms, "vivillon") == ["vivillon", "vivillon-polar", "vivillon-fancy", "vivillon-poke-ball"]
    assert keys(forms, "unown") == ["unown", "unown-exclamation"]
    assert keys(forms, "raichu") == ["raichu", "raichu-alola"]
    assert forms["vivillon"]["n"] == 666


def test_battle_only_forms_megas_gigantamax_totems_and_ride_modes_are_left_out(forms):
    assert keys(forms, "pikachu") == ["pikachu", "pikachu-cosplay", "pikachu-original-cap", "pikachu-starter"]
    assert keys(forms, "aegislash") == ["aegislash-shield"]
    assert keys(forms, "castform") == ["castform"]
    assert keys(forms, "raticate") == ["raticate"]
    assert keys(forms, "koraidon") == ["koraidon"]


def test_minior_has_its_cores_and_no_meteor_form(forms):
    assert keys(forms, "minior") == ["minior-red"]


def test_spinda_gets_no_form_marks(forms):
    assert "spinda" not in forms


def test_pyroars_female_form_is_dropped_since_its_gender_marks_cover_it(forms):
    assert keys(forms, "pyroar") == ["pyroar-male"]


def test_look_alike_and_held_item_forms_are_hidden(forms):
    assert form(forms, "scatterbug-polar")["h"] is True
    assert "h" not in form(forms, "scatterbug")
    assert keys(forms, "xerneas") == ["xerneas", "xerneas-active"]
    assert form(forms, "xerneas-active")["h"] is True


def test_event_forms_are_flagged(forms):
    for key in ("vivillon-fancy", "vivillon-poke-ball", "pikachu-original-cap", "pikachu-cosplay", "pikachu-starter"):
        assert form(forms, key)["ev"] is True
    assert "ev" not in form(forms, "vivillon-polar")


def test_forms_that_are_their_own_pokedex_row_are_flagged(forms):
    assert form(forms, "raichu-alola")["r"] is True
    assert form(forms, "pikachu-original-cap")["r"] is True
    assert "r" not in form(forms, "raichu")          # the species row itself
    assert "r" not in form(forms, "vivillon-polar")  # a cosmetic form has no row


def test_labels_are_the_english_form_names(forms):
    assert form(forms, "vivillon-polar")["l"] == "Polar Pattern"
    assert form(forms, "vivillon")["l"] == "Meadow Pattern"
    assert form(forms, "raichu-alola")["l"] == "Alolan Form"
    assert "l" not in form(forms, "raichu")


# Gender


def test_gender_lists_name_the_genderless_and_single_gender_species(api):
    assert bf.gender_lists(api) == {"n": ["koraidon", "minior", "unown", "xerneas"], "m": ["tauros"],
                                    "f": ["nidoran-f"]}


def test_species_with_a_visible_gender_difference_are_flagged(forms):
    assert {s for s, v in forms.items() if v.get("gd")} == {"rattata", "raticate", "pikachu", "raichu", "pyroar",
                                                            "meowstic"}


@pytest.fixture
def sprited(forms, api):
    return bf.add_sprites(forms, api, fake.FEMALE_SPRITES, fake.POKEAPI_SPRITES, fake.SHOWDOWN_SPRITES)


def test_a_form_gets_a_female_mark_only_where_a_female_sprite_exists(sprited):
    female = {f["k"] for s in sprited.values() for f in s["forms"] if f.get("f")}
    assert female == {"pikachu", "pikachu-starter", "raichu", "rattata", "raticate", "pyroar-male"}


def test_gender_forms_and_single_gender_forms_say_their_gender(sprited):
    assert form(sprited, "meowstic-male")["g"] == "m" and form(sprited, "meowstic-female")["g"] == "f"
    assert form(sprited, "pikachu-original-cap")["g"] == "m"
    assert form(sprited, "pikachu-cosplay")["g"] == "f"
    assert "g" not in form(sprited, "pikachu")


def test_showdown_sprite_ids(sprited):
    expect = {"pikachu": "pikachu", "pikachu-original-cap": "pikachu-original", "pikachu-starter": "pikachu-starter",
              "raichu-alola": "raichu-alola", "vivillon-poke-ball": "vivillon-pokeball", "unown": "unown",
              "unown-exclamation": "unown-exclamation", "meowstic-female": "meowstic-f", "minior-red": "minior",
              "vivillon": "vivillon", "meowstic-male": "meowstic", "xerneas": "xerneas-neutral",
              "xerneas-active": "xerneas"}
    assert {k: form(sprited, k)["s"] for k in expect} == expect
    assert "s" not in form(sprited, "scatterbug-polar")  # Showdown has no such sprite


def test_alcremie_showdown_ids_name_the_cream_and_the_sweet():
    have = fake.SHOWDOWN_SPRITES
    assert bf.showdown_sprite("alcremie", "alcremie", have) == "alcremie"
    assert bf.showdown_sprite("alcremie", "alcremie-ruby-swirl-berry-sweet", have) == "alcremie-rubyswirl-berry"
    assert bf.showdown_sprite("alcremie", "alcremie-vanilla-cream-berry-sweet", have) == "alcremie-vanillacream-berry"
    assert bf.showdown_sprite("alcremie", "alcremie-ruby-swirl-strawberry-sweet", have) == "alcremie-rubyswirl"


def test_pokeapi_sprite_ids_for_forms_other_than_the_species_own(sprited):
    assert form(sprited, "vivillon-polar")["p"] == "666-polar"
    assert form(sprited, "raichu-alola")["p"] == "10100"
    assert form(sprited, "scatterbug-polar")["p"] == "664-polar"
    assert "p" not in form(sprited, "pikachu")  # the species' own sprite is its dex number


# Regional forms per game


def test_showdown_formats_data_lists_the_pokemon_a_game_has():
    assert bf.parse_showdown_formats(fake.SHOWDOWN_FORMATS) == {"raichualola", "taurospaldeacombat"}


@pytest.fixture
def regional(forms):
    tracker = {"pokemon": bf.rows(fake.TRACKER_POKEMON), "locations": bf.rows(fake.TRACKER_LOCATIONS)}
    present = {"scarlet-violet": {"raichualola", "taurospaldeacombat"}, "sword-shield": {"raichualola", "rattataalola"},
               "legends-za": {"raichualola"}}
    return bf.regional_games(forms, tracker, present)


def test_a_regional_form_is_caught_where_pokedex_tracker_has_a_location_for_it(regional):
    assert regional["raichu-alola"]["c"] == ["legends-za", "sword-shield", "lets-go-pikachu-lets-go-eevee",
                                             "ultra-sun-ultra-moon", "sun-moon"]
    assert regional["tauros-paldea-combat-breed"]["c"] == ["scarlet-violet"]


def test_alolan_raichu_can_only_be_transferred_into_scarlet_violet(regional):
    assert regional["raichu-alola"]["t"] == ["scarlet-violet"]


def test_a_transfer_location_means_transfer_only_and_showdown_decides_which_home_games_take_a_form(regional):
    assert regional["rattata-alola"] == {"c": ["sun-moon"], "t": ["sword-shield"]}
    assert "t" not in regional["tauros-paldea-combat-breed"]


def test_only_regional_forms_get_game_lists(regional):
    assert set(regional) == {"raichu-alola", "rattata-alola", "tauros-paldea-combat-breed"}


# The whole file

FORM_GAMES = {
    "vivillon-fancy": {"c": ["x-y", "scarlet-violet"], "t": ["home"], "verified": True, "note": "XY event"},
    "unown-exclamation": {"x": ["crystal", "gold-silver"], "verified": True, "note": "added in Gen 3"},
    "pikachu-cosplay": {"c": ["omega-ruby-alpha-sapphire"], "nh": True, "verified": True, "note": "ORAS gift"},
    "pikachu-starter": {"c": [], "t": ["home"], "verified": False, "note": "an empty c: can't be caught anywhere"},
}
SHINY_LOCKS = {
    "pikachu-original-cap": {"never": True, "verified": True, "note": "event gifts"},
    "koraidon": {"locked": ["scarlet-violet"], "verified": False, "note": "a single-form species is fine too"},
}


def sources(api, **changes):
    s = dict(api=api, female=fake.FEMALE_SPRITES, pokeapi_sprites=fake.POKEAPI_SPRITES,
             showdown_sprites=fake.SHOWDOWN_SPRITES,
             tracker={"pokemon": bf.rows(fake.TRACKER_POKEMON), "locations": bf.rows(fake.TRACKER_LOCATIONS)},
             present={"scarlet-violet": {"raichualola"}}, form_games=FORM_GAMES, shiny_locks=SHINY_LOCKS,
             commits={"pokeapi": "p1", "pokedextracker": "t1", "showdown": "s1", "sprites": "x1"},
             built="2026-11-16T00:00:00Z")
    s.update(changes)
    return s


@pytest.fixture
def doc(api):
    return bf.build(**sources(api))


def doc_form(doc, key):
    return next(f for s in doc["species"].values() for f in s["forms"] if f["k"] == key)


def test_file_shape(doc):
    assert set(doc) == {"schema", "built", "sources", "gender", "species", "shiny"}
    assert doc["schema"] == 1 and doc["built"] == "2026-11-16T00:00:00Z"
    assert doc["sources"] == {"pokeapi": "p1", "pokedextracker": "t1", "showdown": "s1", "sprites": "x1"}
    assert doc["gender"]["n"] == ["koraidon", "minior", "unown", "xerneas"]


def test_only_species_with_form_or_gender_marks_are_listed(doc):
    assert sorted(doc["species"]) == ["meowstic", "pikachu", "pyroar", "raichu", "raticate", "rattata", "scatterbug",
                                      "tauros", "unown", "vivillon", "xerneas"]
    assert "spinda" not in doc["species"] and "castform" not in doc["species"]


def test_nothing_internal_is_written(doc):
    assert all(not k.startswith("_") for s in doc["species"].values() for f in s["forms"] for k in f)


def test_hand_written_games_and_regional_games_are_merged_into_the_forms(doc):
    assert doc_form(doc, "vivillon-fancy") == {"k": "vivillon-fancy", "ev": True, "s": "vivillon-fancy",
                                              "p": "666-fancy", "c": ["scarlet-violet", "x-y"], "t": ["home"]}
    assert doc_form(doc, "unown-exclamation")["x"] == ["crystal", "gold-silver"]
    assert doc_form(doc, "pikachu-cosplay")["nh"] is True
    assert doc_form(doc, "pikachu-starter")["c"] == []
    assert doc_form(doc, "raichu-alola")["t"] == ["scarlet-violet"]
    assert "c" not in doc_form(doc, "vivillon-polar")  # wherever the species is


def test_shiny_locks_list_never_shiny_forms_and_locks_per_game(doc):
    assert doc["shiny"] == {"never": ["pikachu-original-cap"], "locked": {"koraidon": ["scarlet-violet"]}}


def test_hand_written_keys_and_games_must_be_real(api):
    with pytest.raises(ValueError, match="pikachu-typo"):
        bf.build(**sources(api, shiny_locks={"pikachu-typo": {"never": True}}))
    with pytest.raises(ValueError, match="castform-sunny"):  # battle-only, so not tracked
        bf.build(**sources(api, form_games={"castform-sunny": {"c": ["x-y"]}}))
    with pytest.raises(ValueError, match="sword"):
        bf.build(**sources(api, form_games={"vivillon-polar": {"c": ["sword"]}}))


def test_a_rebuild_with_nothing_new_keeps_the_old_built_time(doc, tmp_path):
    path = tmp_path / "forms.json"
    assert bf.write(doc, path) is True
    again = {**doc, "built": "2026-12-01T00:00:00Z"}
    assert bf.write(again, path) is False
    assert bf.json.loads(path.read_text())["built"] == "2026-11-16T00:00:00Z"
    changed = {**again, "gender": {"n": [], "m": [], "f": []}}
    assert bf.write(changed, path) is True
    assert bf.json.loads(path.read_text())["built"] == "2026-12-01T00:00:00Z"


# Reading the downloads


def test_sprite_names_from_a_showdown_folder_listing():
    html = '<a href="../">..</a><a href="./pikachu-f.png">x</a><a href="./alcremie-rubyswirl-berry.gif">y</a>' \
           '<a href="./?sort=size">z</a>'
    assert bf.listing_names(html) == {"pikachu-f", "alcremie-rubyswirl-berry"}


def test_sprite_names_from_a_github_tree():
    tree = {"truncated": False, "tree": [{"path": "666-polar.png", "type": "blob"}, {"path": "female", "type": "tree"},
                                         {"path": "25.png", "type": "blob"}]}
    assert bf.tree_names(tree) == {"666-polar", "25"}
