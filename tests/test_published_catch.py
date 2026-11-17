"""The catch.json about to be committed: known catch facts hold (the daily job runs this before committing)."""
import json, os, pathlib
import pytest
import build_catch as bc
import build_forms as bf

CATCH_JSON = pathlib.Path(os.environ.get("CATCH_JSON", pathlib.Path(__file__).parent.parent / "catch.json"))


FORMS_JSON = pathlib.Path(os.environ.get("FORMS_JSON", pathlib.Path(__file__).parent.parent / "forms.json"))


@pytest.fixture(scope="module")
def doc():
    return json.loads(CATCH_JSON.read_text())


@pytest.fixture(scope="module")
def forms():
    return json.loads(FORMS_JSON.read_text())


def test_shape_and_pinned_sources(doc):
    assert doc["schema"] == 1
    assert doc["sources"] == {"pokeapi": bf.POKEAPI, "pokedextracker": bf.TRACKER}
    assert set(doc["games"]) == {g for g in bf.GAMES if g != "home"}  # keys are written sorted
    assert set(doc["shiny"]) == {"games", "status"} and set(doc["shiny"]["games"]) == set(doc["games"])
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


# The shiny section (hand-written rules, locks and statuses)


def method(doc, game, id):
    return next(m for m in doc["shiny"]["games"][game]["methods"] if m["id"] == id)


def lock(doc, game, key):
    return doc["shiny"]["games"][game].get("locks", {}).get(key)


def test_gen_1_has_no_shinies(doc):
    assert doc["shiny"]["games"]["red-blue"] == {"shiny": False} == doc["shiny"]["games"]["yellow"]


def test_gen_4_masuda_is_5_rolls(doc):
    for game in ("diamond-pearl", "platinum", "heartgold-soulsilver"):
        m = method(doc, game, "masuda")
        assert doc["shiny"]["games"][game]["base"] == 8192 and m["rolls"] == 5
        assert round(bc.odds(8192, m["rolls"]), 1) == 1638.8


def test_legends_za_shiny_charm_is_3_extra_rolls(doc):
    za = doc["shiny"]["games"]["legends-za"]
    assert za["charm"]["extra"] == 3
    assert round(bc.odds(za["base"], method(doc, "legends-za", "wild")["charm_rolls"])) == 1024


def test_charm_only_eggs_are_2_rolls_in_gens_8_and_9_and_3_before(doc):
    for game in ("sword-shield", "brilliant-diamond-shining-pearl", "scarlet-violet"):
        assert method(doc, game, "eggs")["charm_rolls"] == 2, game
    for game in ("black-2-white-2", "x-y", "omega-ruby-alpha-sapphire", "sun-moon", "ultra-sun-ultra-moon"):
        assert method(doc, game, "eggs")["charm_rolls"] == 3, game


def test_unsettled_odds_are_flagged_approx(doc):
    assert method(doc, "x-y", "poke-radar")["approx"] is True
    assert method(doc, "ultra-sun-ultra-moon", "ultra-wormhole")["approx"] is True
    assert any(s.get("approx") for s in method(doc, "brilliant-diamond-shining-pearl", "grand-underground")["steps"])


def test_red_gyarados_is_always_shiny(doc):
    for game in ("gold-silver", "crystal", "heartgold-soulsilver"):
        assert lock(doc, game, "gyarados")["lock"] == "always", game


def test_snacksworth_legendaries_are_locked_in_scarlet_violet(doc):
    for key in ("lugia", "ho-oh", "kyurem", "necrozma"):
        assert lock(doc, "scarlet-violet", key)["lock"] == "never", key


def test_arceus_can_be_shiny_in_bdsp_with_legends_arceus_save_data(doc):
    arceus = lock(doc, "brilliant-diamond-shining-pearl", "arceus")
    assert arceus["lock"] == "open" and "Legends: Arceus" in arceus["needs"]
    assert lock(doc, "legends-arceus", "arceus")["lock"] == "never"


def test_shiny_statuses(doc):
    status = doc["shiny"]["status"]
    assert status["keldeo"]["status"] == "home-reward" and status["meloetta"]["status"] == "home-reward"
    assert status["victini"]["status"] == "never" and status["mew"]["status"] == "event"


def test_sword_shield_alola_gifts_are_left_out(doc):
    # PKHeX lists these as locked gifts, but no in-game source was found (user decision 2026-11-17).
    for key in ("rowlet", "litten", "popplio", "raichu-alola", "vulpix-alola", "exeggutor-alola"):
        assert lock(doc, "sword-shield", key) is None, key


def test_every_shiny_entry_resolves_and_ships_no_notes(doc, forms):
    known = set(doc["pk"]) | bc.form_keys(FORMS_JSON)
    for game, g in doc["shiny"]["games"].items():
        if g == {"shiny": False}:
            continue
        ids = [m["id"] for m in g["methods"]]
        assert g["best"] in ids and len(ids) == len(set(ids)) and g["base"] in (8192, 4096)
        for m in g["methods"]:
            assert m["plain"] and m["detail"] and m["name"]
            assert len([k for k in ("rolls", "one_in", "steps") if k in m]) == 1, (game, m["id"])
        for key, e in g.get("locks", {}).items():
            assert key in known, (game, key)
            assert e["lock"] in bc.LOCKS and e["encounter"]
        assert all(r["id"] and r["plain"] for r in g.get("rules", []))
    for key, e in doc["shiny"]["status"].items():
        assert key in known or key in forms["species"] or any(p.startswith(key + "-") for p in doc["pk"]), key
        assert e["status"] in bc.STATUSES and e["how"]
    text = json.dumps(doc["shiny"])
    assert '"note"' not in text and '"verified"' not in text


# The catch locks are the per-encounter source; forms.json's shiny lists must stay in step with them.

# Form-dex forms the catch files lock in a game that forms/shiny_locks.json doesn't list for it, with why.
NOT_IN_FORMS = {
    ("scarlet-violet", "growlithe-hisui"): "eggs can be shiny, so the form isn't locked in the game",
    ("scarlet-violet", "meowth-galar"): "eggs can be shiny, so the form isn't locked in the game",
    **{("sword-shield", k): "gap: ask the user before adding to forms/shiny_locks.json"
       for k in ("articuno-galar", "zapdos-galar", "moltres-galar")},
    **{("legends-arceus", k): "gap: ask the user before adding to forms/shiny_locks.json"
       for k in ("vulpix-alola", "giratina-origin", "tornadus-therian", "thundurus-therian", "landorus-therian")},
    **{(g, "zygarde-10"): "gap: ask the user before adding to forms/shiny_locks.json"
       for g in ("sun-moon", "ultra-sun-ultra-moon")},
}


def test_every_forms_lock_is_a_lock_in_the_catch_files(doc, forms):
    for key, games in forms["shiny"]["locked"].items():
        for game in games:
            assert (lock(doc, game, key) or {}).get("lock") == "never", (game, key)


def test_a_form_dex_form_locked_in_a_game_is_locked_in_forms_too(doc, forms):
    # Alternate forms only: forms.json doesn't list every per-game lock of a species' default form (Rayquaza in
    # OR / AS, say); the catch files do.
    tracked = {f["k"] for sp in forms["species"].values() for f in sp["forms"][1:]}
    missing = []
    for game, g in doc["shiny"]["games"].items():
        for key, e in g.get("locks", {}).items():
            in_forms = key in forms["shiny"]["never"] or game in forms["shiny"]["locked"].get(key, [])
            if e["lock"] == "never" and key in tracked and not in_forms and (game, key) not in NOT_IN_FORMS:
                missing.append((game, key))
    assert not missing
    for game, key in NOT_IN_FORMS:  # each allowed difference is still real
        assert lock(doc, game, key)["lock"] == "never" and game not in forms["shiny"]["locked"].get(key, [])
    # The gaps the shiny research found in forms/shiny_locks.json, now filled.
    assert "scarlet-violet" in forms["shiny"]["locked"]["meloetta-aria"]
    for key in ("keldeo-ordinary", "keldeo-resolute"):
        assert {"sword-shield", "legends-za"} <= set(forms["shiny"]["locked"][key])


def test_never_shiny_forms_are_never_shiny_anywhere(doc, forms):
    never = set(forms["shiny"]["never"])
    for game, g in doc["shiny"]["games"].items():
        for key, e in g.get("locks", {}).items():
            assert not (key in never and e["lock"] in bc.SHINY_ABLE), (game, key)


def test_never_shiny_species_match_forms_never_list(doc, forms):
    never = set(forms["shiny"]["never"])
    species_never = {k for k, e in doc["shiny"]["status"].items() if e["status"] == "never"}
    for s in species_never:  # every form of a never-shiny species is in forms.json's never list
        keys = [f["k"] for f in forms["species"][s]["forms"]] if s in forms["species"] else [s]
        assert set(keys) <= never, s
    for key in never:  # and a default form there belongs to a never-shiny species
        owner = next((s for s, sp in forms["species"].items() if key in [f["k"] for f in sp["forms"]]), key)
        default = owner not in forms["species"] or forms["species"][owner]["forms"][0]["k"] == key
        assert not default or owner in species_never, key
