"""build_places.py: the hand-written region tables in places/ are checked, then published as places.json."""
import copy, json
import pytest
import build_places as bp

URL = "https://bulbapedia.bulbagarden.net/wiki/"

TINY = {
    "name": "Tiny", "grid": [4, 3], "games": ["red-blue"],
    "places": {
        "home": {"n": "Home Town", "k": "town", "at": [0, 0], "url": URL + "Home_Town"},
        "road-1": {"n": "Road 1", "k": "route", "at": [1, 0], "url": URL + "Road_1"},
        "port": {"n": "Port City", "k": "town", "at": [2, 0], "url": URL + "Port_City"},
        "ship": {"n": "Ship", "k": "building", "in": "port", "url": URL + "Ship"},
        "sea-1": {"n": "Sea 1", "k": "sea", "at": [2, 2], "url": URL + "Sea_1"},
        "cave": {"n": "Cave", "k": "cave", "at": [3, 2], "url": URL + "Cave"},
    },
    "links": [["home", "road-1", "road-1"], ["road-1", "port", "road-1"], ["port", "sea-1", "sea-1"],
              ["sea-1", "cave", None]],
    "alias": {"Road 1": "road-1", "Ship (B1F)": "ship", "Port City Trade": "port"},
    "skip": {"Far Island": "another region's map"},
}


@pytest.fixture
def tiny():
    return copy.deepcopy(TINY)


def errors(region):
    return bp.check("tiny", region)


def test_a_good_region_has_no_errors(tiny):
    assert errors(tiny) == []


def test_build_ships_regions_without_the_skip_list(tiny):
    doc = bp.build({"tiny": tiny}, built="2026-11-25T00:00:00Z")
    assert doc["schema"] == 1 and doc["built"] == "2026-11-25T00:00:00Z"
    assert set(doc["regions"]["tiny"]) == {"name", "grid", "games", "places", "links", "alias"}
    assert doc["regions"]["tiny"]["places"]["ship"] == TINY["places"]["ship"]


def test_build_fails_on_a_bad_region(tiny):
    tiny["links"].append(["home", "nowhere", None])
    with pytest.raises(SystemExit, match="nowhere"):
        bp.build({"tiny": tiny}, built="x")


def test_unknown_ids_in_links_alias_and_in_are_errors(tiny):
    tiny["links"].append(["home", "nowhere", None])
    tiny["alias"]["Lost"] = "gone"
    tiny["places"]["ship"]["in"] = "harbour"
    tiny["links"].append(["home", "port", "no-route"])
    text = " ".join(errors(tiny))
    assert "nowhere" in text and "gone" in text and "harbour" in text and "no-route" in text


def test_a_link_labelled_with_a_town_is_an_error(tiny):
    tiny["links"].append(["home", "cave", "port"])
    assert any("port" in e for e in errors(tiny))


def test_two_top_level_places_on_one_spot_is_an_error(tiny):
    tiny["places"]["cave"]["at"] = [2, 2]
    assert any("[2, 2]" in e for e in errors(tiny))


def test_a_spot_outside_the_grid_is_an_error(tiny):
    tiny["places"]["cave"]["at"] = [4, 2]
    assert any("cave" in e and "grid" in e for e in errors(tiny))


def test_a_top_level_place_needs_a_spot_and_a_building_inside_one_has_none(tiny):
    del tiny["places"]["cave"]["at"]
    tiny["places"]["ship"]["at"] = [3, 0]
    text = " ".join(errors(tiny))
    assert "cave" in text and "ship" in text


def test_duplicate_and_reversed_links_are_errors(tiny):
    tiny["links"].append(["port", "road-1", "road-1"])
    assert any("twice" in e for e in errors(tiny))


def test_a_link_to_itself_is_an_error(tiny):
    tiny["links"].append(["home", "home", None])
    assert any("itself" in e for e in errors(tiny))


def test_a_place_cut_off_from_the_first_town_is_an_error(tiny):
    tiny["links"].remove(["sea-1", "cave", None])
    assert any("cave" in e and "reach" in e for e in errors(tiny))


def test_an_unknown_kind_is_an_error(tiny):
    tiny["places"]["cave"]["k"] = "volcano"
    assert any("volcano" in e for e in errors(tiny))


def test_a_url_off_bulbapedia_is_an_error(tiny):
    tiny["places"]["cave"]["url"] = "https://example.com/wiki/Cave"
    assert any("cave" in e and "url" in e for e in errors(tiny))


def test_a_name_both_aliased_and_skipped_is_an_error(tiny):
    tiny["skip"]["Road 1"] = "oops"
    assert any("Road 1" in e for e in errors(tiny))


def test_skipped_matches_a_name_and_its_floors_only():
    skip = {"Lost Cave": "Sevii"}
    assert bp.skipped("Lost Cave", skip) and bp.skipped("Lost Cave (room 1)", skip)
    assert not bp.skipped("Lost Cave Entrance", skip) and not bp.skipped("Road 1", skip)


def test_write_keeps_the_file_when_only_built_changed(tmp_path, tiny):
    path = tmp_path / "places.json"
    assert bp.write(bp.build({"tiny": tiny}, built="a"), str(path))
    assert not bp.write(bp.build({"tiny": tiny}, built="b"), str(path))
    assert json.loads(path.read_text())["built"] == "a"
    tiny["places"]["home"]["n"] = "Home Village"
    assert bp.write(bp.build({"tiny": tiny}, built="c"), str(path))
