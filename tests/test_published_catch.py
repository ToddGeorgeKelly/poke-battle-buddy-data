"""The catch.json about to be committed: known catch facts hold (the daily job runs this before committing)."""
import json, os, pathlib
import pytest
import build_catch as bc
import build_forms as bf

CATCH_JSON = pathlib.Path(os.environ.get("CATCH_JSON", pathlib.Path(__file__).parent.parent / "catch.json"))


@pytest.fixture(scope="module")
def doc():
    return json.loads(CATCH_JSON.read_text())


def test_shape_and_pinned_sources(doc):
    assert doc["schema"] == 1
    assert doc["sources"] == {"pokeapi": bf.POKEAPI, "pokedextracker": bf.TRACKER}
    assert set(doc["games"]) == {g for g in bf.GAMES if g != "home"}  # keys are written sorted
    assert doc["shiny"] == {}  # part 2 fills this in
    assert len(doc["pk"]) == len(set(doc["pk"])) and len(doc["pk"]) > 1000


def test_every_index_resolves(doc):
    for game, g in doc["games"].items():
        assert g["src"] == ("pokeapi" if game in bc.POKEAPI_GAMES else "pokedextracker")
        listed = [i for ps in g["a"].values() for i in ps]
        assert set(g["a"]) <= set(bc.ORDER) and len(listed) == len(set(listed))
        assert all(0 <= i < len(doc["pk"]) for i in listed)
        full = (1 << len(g["v"])) - 1
        for r in g["en"]:
            assert 0 <= r[0] < len(doc["pk"]) and 0 <= r[1] < len(doc["loc"]) and 0 < r[-1] <= full
            if g["src"] == "pokeapi":
                assert len(r) == 8 and 0 <= r[2] < len(doc["m"]) and 0 <= r[6] < len(doc["cs"]) and r[4] <= r[5]
            else:
                assert len(r) == 3
        caught = {doc["pk"][r[0]] for r in g["en"]}
        assert {p for p, s in bc.availability(doc, game).items() if s == "c"} == caught
    assert all(0 <= x < len(doc["c"]) for cs in doc["cs"] for x in cs)


def test_every_game_has_plenty_of_encounters(doc):
    for game, g in doc["games"].items():
        assert len({r[0] for r in g["en"]}) >= 100, game


def test_pikachu_in_viridian_forest_in_red_and_blue(doc):
    forest = [e for e in bc.encounters(doc, "red-blue", "pikachu") if e["place"] == "Viridian Forest"]
    assert forest == [{"place": "Viridian Forest", "method": "Walking in tall grass or a cave", "chance": 5, "min": 3,
                       "max": 5, "conditions": [], "versions": ["red", "blue"]}]


def test_hoothoot_comes_out_at_night_in_diamond_and_pearl(doc):
    rows = bc.encounters(doc, "diamond-pearl", "hoothoot")
    assert rows and all("At night" in e["conditions"] for e in rows)


def test_dunsparce_swarms_in_gold_and_silver(doc):
    assert any("During a swarm" in e["conditions"] for e in bc.encounters(doc, "gold-silver", "dunsparce"))


def test_version_exclusives(doc):
    assert {tuple(e["versions"]) for e in bc.encounters(doc, "red-blue", "ekans")} == {("red",)}
    assert {tuple(e["versions"]) for e in bc.encounters(doc, "scarlet-violet", "larvitar")} == {("scarlet",)}


def test_tracker_games(doc):
    assert "Santalune Forest" in [e["place"] for e in bc.encounters(doc, "x-y", "pikachu")]
    assert any(e["place"].startswith("South Province Area") for e in bc.encounters(doc, "scarlet-violet", "pawmi"))
    assert bc.availability(doc, "sword-shield").get("pidgey") is None  # not in Sword / Shield


def test_evolve_breed_and_transfer_only(doc):
    assert bc.availability(doc, "yellow")["raichu"] == "e" and bc.availability(doc, "red-blue")["charizard"] == "e"
    assert bc.availability(doc, "x-y")["pichu"] == "b" and bc.availability(doc, "gold-silver")["pichu"] == "b"
    assert bc.availability(doc, "x-y")["mew"] == "x"
    assert bc.availability(doc, "scarlet-violet")["mew"] == "ev"
    assert "crobat" not in bc.availability(doc, "red-blue")  # a Gen 2 evolution
