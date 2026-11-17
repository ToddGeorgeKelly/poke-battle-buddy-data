"""build_catch.py: where each Pokemon can be caught in each game, and how each game has it (catch, evolve, ...)."""
import json
import pytest
import build_catch as bc
import fake_catch as fake


@pytest.fixture
def doc():
    return bc.build(bc.parse_pokeapi(fake.POKEAPI), bc.parse_tracker(fake.TRACKER),
                    commits={"pokeapi": "abc", "pokedextracker": "def"}, built="2026-11-16T00:00:00Z",
                    games=fake.GAMES)


def status(doc, game, pokemon):
    return bc.availability(doc, game).get(pokemon)


# PokeAPI games: encounters


def test_a_pokeapi_encounter_has_place_method_chance_levels_and_versions(doc):
    assert bc.encounters(doc, "red-blue", "pikachu") == [
        {"place": "Viridian Forest", "method": "Walking in tall grass or a cave", "chance": 5, "min": 3, "max": 5,
         "conditions": [], "versions": ["red", "blue"]}]


def test_a_slot_listed_twice_is_counted_once(doc):
    assert bc.encounters(doc, "red-blue", "pikachu")[0]["chance"] == 4 + 1


def test_a_version_exclusive_encounter_names_its_version(doc):
    golbat = bc.encounters(doc, "red-blue", "golbat")
    assert [e["versions"] for e in golbat] == [["red"]]


def test_an_area_without_an_english_name_goes_by_its_location_and_identifier(doc):
    assert bc.encounters(doc, "red-blue", "golbat")[0]["place"] == "Seafoam Islands (1f)"


def test_time_of_day_conditions_are_kept_and_not_merged_across_conditions(doc):
    assert bc.encounters(doc, "diamond-pearl", "hoothoot") == [
        {"place": "Great Marsh Area 1", "method": "Walking in tall grass or a cave", "chance": 10, "min": 24,
         "max": 24, "conditions": ["At night"], "versions": ["diamond", "pearl"]}]
    assert bc.encounters(doc, "diamond-pearl", "noctowl")[0]["conditions"] == ["During the day"]


def test_a_method_without_a_rarity_has_no_chance(doc):
    gift = bc.encounters(doc, "heartgold-soulsilver", "articuno")[0]
    assert gift["chance"] == 0 and gift["min"] == gift["max"] == 50


def test_pokeapi_games_name_their_source_and_versions(doc):
    assert doc["games"]["red-blue"]["src"] == "pokeapi"
    assert doc["games"]["red-blue"]["v"] == ["red", "blue"]


# PokeAPI games: availability


def test_a_pokemon_with_an_encounter_is_catch(doc):
    assert status(doc, "red-blue", "pikachu") == "c" and status(doc, "red-blue", "golbat") == "c"


def test_an_evolution_of_a_catchable_pokemon_is_evolve(doc):
    assert status(doc, "red-blue", "raichu") == "e"
    assert status(doc, "red-blue", "magneton") == "e"
    assert status(doc, "diamond-pearl", "magnezone") is None  # no Magnemite in this fake Diamond / Pearl


def test_an_evolution_from_a_later_generation_is_left_out(doc):
    assert status(doc, "red-blue", "crobat") is None and status(doc, "red-blue", "magnezone") is None


def test_a_location_evolution_the_game_lacks_is_left_out(doc):
    assert status(doc, "heartgold-soulsilver", "magneton") == "e"
    assert status(doc, "heartgold-soulsilver", "magnezone") is None  # no Mt. Coronet in Johto


def test_a_first_stage_whose_evolution_is_catchable_is_breed_in_a_game_with_breeding(doc):
    assert status(doc, "gold-silver", "hoothoot") == "b"
    assert status(doc, "gold-silver", "pichu") == "b"
    assert status(doc, "red-blue", "zubat") is None  # Red / Blue have no breeding


def test_a_pokemon_no_source_has_is_left_out(doc):
    assert status(doc, "red-blue", "mew") is None and status(doc, "red-blue", "mewtwo") is None


# Pokedex Tracker games


def test_tracker_values_are_a_postgres_array_of_trimmed_strings():
    assert bc.tracker_values('{"Route 3"," Route 4 ",Cortondo}') == ["Route 3", "Route 4", "Cortondo"]
    assert bc.tracker_values('{"Say \\"hi\\""}') == ['Say "hi"']
    assert bc.tracker_values("{}") == []


@pytest.mark.parametrize("value, code", [
    ("Evolve Pikachu", "e"), ("Evovle Slowpoke", "e"), ("Breed Pikachu/Raichu", "b"),
    ("Trade from Y", "t"), ("Trade from Moon/Ultra Moon", "t"), ("Transfer required", "x"),
    ("Transfer from Pokémon GO", "x"), ("Event Only", "ev"), ("Receive from event", "ev"),
    ("Special Event through Mystery Gift", "ev"), ("Tera Raid Battle Events", "ev"),
    ("Transfer or receive from event", "ev"), ("Currently unavailable", None), ("Not available yet", None),
    ("Refer to Sword and Shield", None), ("Route 3", "c"), ("Trade Slowpoke to Quille on South Boulevard", "c"),
    ("Cerulean City Trade", "c"), ("Gift for linking Pokémon Go", "c")])
def test_tracker_wording_gives_the_status(value, code):
    assert bc.tracker_status(value) == code


def test_a_place_is_a_location_and_a_status_word_is_not(doc):
    assert bc.encounters(doc, "x-y", "pikachu") == [{"place": "Santalune Forest", "versions": ["x", "y"]}]
    assert bc.encounters(doc, "x-y", "raichu") == []


def test_tracker_statuses(doc):
    assert [status(doc, "x-y", p) for p in ("pikachu", "raichu", "pichu", "mew", "celebi", "zubat")] == \
        ["c", "e", "b", "ev", "x", None]


def test_a_version_exclusive_is_catch_with_its_version_named(doc):
    assert status(doc, "x-y", "hoothoot") == "c"
    assert bc.encounters(doc, "x-y", "hoothoot") == [{"place": "Route 3", "versions": ["y"]},
                                                     {"place": "Route 4", "versions": ["y"]}]


def test_only_trade_counts_as_trade():
    assert bc.best(["t", "x"]) == "t" and bc.best(["x"]) == "x"


def test_the_best_status_wins():
    assert bc.best(["x", "ev", "t", "b", "e", "c"]) == "c"
    assert bc.best(["x", "ev", "t", "b", "e"]) == "e"
    assert bc.best(["x", "ev", "t", "b"]) == "b"
    assert bc.best(["x", "ev", "t"]) == "t"
    assert bc.best(["x", "ev"]) == "ev"
    assert bc.best([]) is None


def test_an_expansion_pass_counts_for_its_game_and_version(doc):
    assert doc["games"]["sword-shield"]["v"] == ["sword", "shield"]
    assert status(doc, "sword-shield", "raichu-alola") == "c"
    assert bc.encounters(doc, "sword-shield", "raichu-alola") == [
        {"place": "Max Raid Battles: Workout Sea", "versions": ["sword", "shield"]}]


def test_a_gigantamax_entry_counts_for_its_species(doc):
    assert bc.encounters(doc, "sword-shield", "pikachu") == [
        {"place": "Gigantamax Raid Battles: Lake of Outrage", "versions": ["sword"]},
        {"place": "Route 4", "versions": ["sword", "shield"]}]
    assert "pikachu-gmax" not in doc["pk"]


def test_tracker_games_name_their_source(doc):
    assert doc["games"]["x-y"]["src"] == "pokedextracker"


def test_a_tracker_form_pokeapi_doesnt_have_fails_the_build():
    tracker = bc.parse_tracker({"pokemon": fake.TRACKER_POKEMON + "25,Pikachu,1200,paldea\n",
                                "locations": fake.TRACKER_LOCATIONS})
    with pytest.raises(ValueError, match="paldea"):
        bc.build(bc.parse_pokeapi(fake.POKEAPI), tracker, commits={}, built="", games=fake.GAMES)


# The file


def test_the_file_shape(doc):
    assert set(doc) == {"schema", "built", "sources", "pk", "loc", "m", "c", "cs", "games", "shiny"}
    assert doc["schema"] == 1 and doc["sources"] == {"pokeapi": "abc", "pokedextracker": "def"}
    assert list(doc["games"]) == fake.GAMES
    assert doc["shiny"] == {}  # no hand-written shiny files given (tests/test_build_catch_shiny.py has them)
    assert doc["cs"][0] == []


def test_pokemon_are_in_pokeapi_order_and_each_has_one_status_per_game(doc):
    ids = {n: i for i, n in enumerate(["pikachu", "raichu", "zubat", "golbat", "magnemite", "magneton", "articuno",
                                       "mewtwo", "mew", "hoothoot", "noctowl", "crobat", "pichu", "celebi",
                                       "magnezone", "raichu-alola"])}
    assert doc["pk"] == sorted(doc["pk"], key=ids.__getitem__)
    for g in doc["games"].values():
        listed = [i for ps in g["a"].values() for i in ps]
        assert len(listed) == len(set(listed)) and all(0 <= i < len(doc["pk"]) for i in listed)


def test_rows_are_fixed_length_ints(doc):
    for g in doc["games"].values():
        size = 8 if g["src"] == "pokeapi" else 3
        assert all(len(r) == size and all(isinstance(x, int) for x in r) for r in g["en"])


def test_write_skips_a_rebuild_that_only_changes_the_built_time(doc, tmp_path):
    path = tmp_path / "catch.json"
    assert bc.write(doc, path) is True
    assert bc.write({**doc, "built": "2026-11-17T00:00:00Z"}, path) is False
    assert json.loads(path.read_text())["built"] == "2026-11-16T00:00:00Z"
