"""build_bbr.py: which Pokemon are rated and against what, the forms that share a rating, and bbr.json's shape."""
import json, re
import build_bbr


def ids(mons):
    return [m["id"] for m in mons]


# ---------------------------------------------------------------- field selection
def test_field_is_the_research_gen9_tiered_roster(tiny):
    mons = build_bbr.roster(tiny)
    field = [m["id"] for m in mons if m["field"]]
    # Tiered Gen 9 Pokemon ("(OU)" counts as OU); no National Dex tiers, no NFE / CAP / Gmax / battle-only forms.
    assert sorted(field) == ["alpha", "beta", "ditto", "palafin"]


def test_field_comes_first_then_every_other_showdown_pokemon(tiny):
    mons = build_bbr.roster(tiny)
    n = sum(m["field"] for m in mons)
    assert all(m["field"] for m in mons[:n])
    assert sorted(ids(mons[n:])) == ["delta", "deltamega", "gamma", "palafinhero"]


def test_gen9_pokemon_use_gen9_moves_and_others_every_gen(tiny):
    mons = {m["id"]: m for m in build_bbr.roster(tiny)}
    assert mons["alpha"]["moves"] == {"tackle"}             # Pursuit doesn't exist in Gen 9
    assert mons["delta"]["moves"] == {"tackle", "pursuit"}  # National Dex: moves from every generation
    assert mons["deltamega"]["moves"] == {"tackle", "pursuit"}


# ---------------------------------------------------------------- forms, unrated, output
def test_palafin_and_terapagos_get_their_battle_forms_rating():
    doc = build_bbr.make_doc({"palafin": 300, "palafinhero": 650, "terapagos": 400, "terapagosterastal": 610,
                              "pikachu": 200}, source="abc", built="2026-10-27T18:04:00Z")
    r = doc["ratings"]
    assert r["palafin"] == 650 and r["terapagos"] == 610
    assert r["palafinhero"] == 650 and r["terapagosterastal"] == 610 and r["pikachu"] == 200


def test_ditto_and_smeargle_are_listed_unrated_not_rated():
    doc = build_bbr.make_doc({"ditto": 213, "smeargle": 300, "pikachu": 200}, source="abc", built="2026-10-27T18:04:00Z")
    assert doc["unrated"] == ["ditto", "smeargle"]
    assert "ditto" not in doc["ratings"] and "smeargle" not in doc["ratings"]


def test_ratings_are_rounded_and_held_between_0_and_999():
    doc = build_bbr.make_doc({"a": -12.4, "b": 1040.0, "c": 419.6}, source="abc", built="2026-10-27T18:04:00Z")
    assert doc["ratings"] == {"a": 0, "b": 999, "c": 420}


def test_output_json_shape():
    doc = build_bbr.make_doc({"pikachu": 200.2}, source="abc123", built=build_bbr.built_now())
    doc = json.loads(build_bbr.to_json(doc))
    assert set(doc) == {"schema", "model", "source", "built", "ratings", "unrated"}
    assert doc["schema"] == 1 and doc["source"] == "abc123" and isinstance(doc["model"], str)
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", doc["built"])
    assert doc["ratings"] == {"pikachu": 200}


def test_built_timestamp_still_sorts_after_old_day_only_builds():
    # Old app versions compare `built` strings with > / >= against day-only dates like "2026-10-26".
    assert "2026-10-27T00:00:00Z" > "2026-10-27" > "2026-10-26"
    assert build_bbr.built_now() > "2026-10-26"
