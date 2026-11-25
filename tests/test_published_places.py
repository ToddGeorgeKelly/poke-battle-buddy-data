"""The places.json about to be committed, and the Kanto table behind it, against catch.json."""
import json, os, pathlib
import pytest
import build_places as bp

ROOT = pathlib.Path(__file__).parent.parent
PLACES_JSON = pathlib.Path(os.environ.get("PLACES_JSON", ROOT / "places.json"))
CATCH_JSON = pathlib.Path(os.environ.get("CATCH_JSON", ROOT / "catch.json"))


@pytest.fixture(scope="module")
def doc():
    return json.loads(PLACES_JSON.read_text())


@pytest.fixture(scope="module")
def source():
    return bp.load()


@pytest.fixture(scope="module")
def kanto(source):
    return source["kanto"]


@pytest.fixture(scope="module")
def catch_names(kanto):
    catch = json.loads(CATCH_JSON.read_text())
    return {catch["loc"][r[1]] for g in kanto["games"] for r in catch["games"][g]["en"]}


def test_the_published_file_matches_a_fresh_build(doc, source):
    assert doc == bp.build(source, built=doc["built"])


def test_kanto_table_has_no_errors(kanto):
    assert bp.check("kanto", kanto) == []


def test_kanto_covers_the_four_kanto_games(doc):
    assert doc["schema"] == 1
    assert doc["regions"]["kanto"]["games"] == ["red-blue", "yellow", "firered-leafgreen",
                                                "lets-go-pikachu-lets-go-eevee"]


def test_routes_1_to_25_exist_and_19_to_21_are_sea(kanto):
    for n in range(1, 26):
        p = kanto["places"][f"route-{n}"]
        assert p["n"] == f"Route {n}" and p["k"] == ("sea" if n in (19, 20, 21) else "route")
        assert p["url"] == f"https://bulbapedia.bulbagarden.net/wiki/Kanto_Route_{n}"


def test_the_ten_towns_and_the_plateau_are_towns(kanto):
    towns = {i for i, p in kanto["places"].items() if p["k"] == "town"}
    assert towns == {"pallet-town", "viridian-city", "pewter-city", "cerulean-city", "vermilion-city",
                     "lavender-town", "celadon-city", "saffron-city", "fuchsia-city", "cinnabar-island",
                     "indigo-plateau"}


def test_every_url_is_a_bulbapedia_wiki_page(kanto):
    for i, p in kanto["places"].items():
        assert p["url"].startswith("https://bulbapedia.bulbagarden.net/wiki/"), i


def test_every_kanto_mainland_catch_name_maps_to_a_place(kanto, catch_names):
    unmapped = sorted(n for n in catch_names if n not in kanto["alias"] and not bp.skipped(n, kanto["skip"]))
    assert unmapped == []


def test_every_alias_is_a_real_catch_name(kanto, catch_names):
    assert sorted(set(kanto["alias"]) - catch_names) == []


def test_every_skip_entry_is_still_in_catch_json(kanto, catch_names):
    stale = [s for s in kanto["skip"] if not any(bp.skipped(n, {s: ""}) for n in catch_names)]
    assert stale == []


def test_no_alias_is_a_sevii_name(kanto):
    assert [n for n in kanto["alias"] if bp.skipped(n, kanto["skip"])] == []
    sevii = ("One Island", "Two Island", "Three Is", "Four Island", "Five Is", "Six Island", "Seven Island",
             "Chamber", "Tanoby", "Mount Ember", "Altering Cave", "Lost Cave", "Icefall Cave")
    assert [n for n in kanto["alias"] if any(s in n for s in sevii)] == []


@pytest.mark.parametrize("name, place", [
    ("Road 1", "route-1"), ("Route 1", "route-1"), ("Road 2 (north, towards Pewter City)", "route-2"),
    ("Road 2 (south, towards Viridian City)", "route-2"), ("Mount Moon (B2F)", "mt-moon"), ("Mt. Moon", "mt-moon"),
    ("Digletts Cave", "digletts-cave"), ("Diglett's Cave", "digletts-cave"), ("Pokemon Mansion (B1F)", "pokemon-mansion"),
    ("Pokémon Mansion", "pokemon-mansion"), ("Safari Zone (Area 1, east)", "safari-zone"),
    ("Victory Road 2 (3F)", "victory-road"), ("Cerulean City Trade", "cerulean-city"),
    ("Saffron City Fighting Dojo Gift", "fighting-dojo"), ("Revive Dome Fossil in Cinnabar Island Research Lab", "cinnabar-lab"),
    ("Pokemon Center (Road 3)", "route-3"), ("S.S. Anne dock", "vermilion-city"), ("S.S. Anne", "ss-anne"),
    ("Celadon City Prize Corner", "celadon-game-corner"), ("Silph Co. Gift", "silph-co")])
def test_known_names_map_to_the_right_place(kanto, name, place):
    assert kanto["alias"][name] == place


def test_junk_and_sevii_names_stay_unmapped(kanto):
    for n in ("1091", "Roaming Kanto", "One Island", "Lost Cave (room 3)", "Tanoby Ruins", "Altering Cave (A)"):
        assert n not in kanto["alias"] and bp.skipped(n, kanto["skip"]), n


def test_buildings_sit_in_their_towns(kanto):
    inside = {i: p["in"] for i, p in kanto["places"].items() if "in" in p}
    assert inside["pokemon-tower"] == "lavender-town" and inside["silph-co"] == "saffron-city"
    assert inside["pokemon-mansion"] == "cinnabar-island" and inside["ss-anne"] == "vermilion-city"
