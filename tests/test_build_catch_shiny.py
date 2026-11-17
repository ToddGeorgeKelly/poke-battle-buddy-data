"""build_catch.py, part 2: the hand-written shiny rules, locks and statuses, checked and folded into catch.json."""
import pytest
import build_catch as bc
import fake_catch as fake
import fake_shiny


def build(shiny=None, games=fake.GAMES):
    return bc.build(bc.parse_pokeapi(fake.POKEAPI), bc.parse_tracker(fake.TRACKER), commits={}, built="",
                    games=games, shiny=fake_shiny.shiny() if shiny is None else shiny,
                    form_keys=fake_shiny.FORM_KEYS | fake_shiny.EXTRA_KEYS)


@pytest.fixture
def doc():
    return build()


def broken(edit):
    """The fake files with one edit made, built: the build should refuse them."""
    s = fake_shiny.shiny()
    edit(s)
    return lambda: build(s)


# Odds


def test_odds_from_rolls():
    assert round(bc.odds(8192, 5), 1) == 1638.8       # Gen 4 Masuda
    assert round(bc.odds(4096, 4), 1) == 1024.4       # Legends: Z-A with the Shiny Charm
    assert bc.odds(4096, 1) == pytest.approx(4096)


# The shipped section


def test_without_hand_written_files_shiny_is_empty():
    doc = bc.build(bc.parse_pokeapi(fake.POKEAPI), bc.parse_tracker(fake.TRACKER), commits={}, built="",
                   games=fake.GAMES)
    assert doc["shiny"] == {}


def test_every_game_has_rules_and_notes_and_checks_are_not_shipped(doc):
    games = doc["shiny"]["games"]
    assert list(games) == fake.GAMES
    assert games["red-blue"] == {"shiny": False}
    hgss = games["heartgold-soulsilver"]
    assert hgss["base"] == 8192 and hgss["best"] == "masuda"
    masuda = next(m for m in hgss["methods"] if m["id"] == "masuda")
    assert masuda == {"id": "masuda", "name": "Masuda Method", "plain": "p", "detail": "d", "rolls": 5}


def test_charm_ships_its_extra_rolls_and_how(doc):
    xy = doc["shiny"]["games"]["x-y"]
    assert xy["charm"] == {"extra": 2, "how": "Complete the National Pokedex."}
    assert "charm" not in doc["shiny"]["games"]["gold-silver"]


def test_fixed_odds_steps_and_approx_ship_as_written(doc):
    games = doc["shiny"]["games"]
    radar = games["x-y"]["methods"][1]
    assert radar["one_in"] == 100 and radar["approx"] is True
    dynamax = games["sword-shield"]["methods"][1]
    assert (dynamax["one_in"], dynamax["charm_one_in"]) == (300, 100)
    brilliant = games["sword-shield"]["methods"][0]
    assert brilliant["steps"][-1] == {"at": 500, "rolls": 7, "charm_rolls": 9}
    assert games["diamond-pearl"]["methods"][0]["steps"] == [{"at": 10, "one_in": 6200}, {"at": 40, "one_in": 200}]


def test_locks_and_rules_fold_into_their_game(doc):
    gs = doc["shiny"]["games"]["gold-silver"]
    assert gs["rules"] == [{"id": "trades", "plain": "In-game trades are never shiny."}]
    assert gs["locks"] == {"gyarados": {"lock": "always", "encounter": "Red Gyarados, Lake of Rage"}}
    hgss = doc["shiny"]["games"]["heartgold-soulsilver"]
    assert hgss["locks"]["pichu-spiky-eared"]["needs"] == "An event Pichu"
    assert "locks" not in doc["shiny"]["games"]["x-y"] and "rules" not in doc["shiny"]["games"]["x-y"]


def test_status_ships_status_and_how(doc):
    assert doc["shiny"]["status"] == {
        "celebi": {"status": "home-reward", "how": "A made-up HOME reward."},
        "mew": {"status": "event", "how": "Events and Pokemon GO only."},
        "pikachu-cosplay": {"status": "never", "how": "Never released shiny."}}


# Checks on the hand-written files


def test_a_missing_game_fails():
    with pytest.raises(ValueError, match="x-y"):
        broken(lambda s: s["rules"].pop("x-y"))()


def test_an_unknown_game_fails():
    with pytest.raises(ValueError, match="pokemon-stadium"):
        broken(lambda s: s["rules"].update({"pokemon-stadium": s["rules"]["x-y"]}))()
    with pytest.raises(ValueError, match="pokemon-stadium"):
        broken(lambda s: s["locks"].update({"pokemon-stadium": {}}))()


def test_an_unknown_pokemon_fails():
    with pytest.raises(ValueError, match="pikachuu"):
        broken(lambda s: s["locks"]["sword-shield"].update(pikachuu=s["locks"]["sword-shield"]["pikachu"]))()
    with pytest.raises(ValueError, match="mewtwoo"):
        broken(lambda s: s["status"].update(mewtwoo=s["status"]["mew"]))()


def test_a_species_name_resolves_for_status():
    s = fake_shiny.shiny()
    s["status"]["raichu"] = {"status": "go", "how": "h", "verified": "single", "note": "n"}
    assert build(s)["shiny"]["status"]["raichu"]["status"] == "go"


def test_rolls_that_dont_match_the_written_odds_fail():
    def edit(s):
        s["rules"]["heartgold-soulsilver"]["methods"][1]["odds"] = 2048  # the reroll-only count, not 5 rolls
    with pytest.raises(ValueError, match="masuda.*2048"):
        broken(edit)()

    def edit_step(s):
        s["rules"]["sword-shield"]["methods"][0]["steps"][1]["charm_odds"] = 400
    with pytest.raises(ValueError, match="brilliant"):
        broken(edit_step)()


@pytest.mark.parametrize("level", [None, "true", "datamined", True])
def test_verified_must_be_an_allowed_level(level):
    def edit(s):
        s["locks"]["gold-silver"]["gyarados"]["verified"] = level
    with pytest.raises(ValueError, match="verified"):
        broken(edit)()


@pytest.mark.parametrize("where", ["method", "lock", "rule", "status", "charm", "game"])
def test_every_entry_needs_a_note(where):
    def edit(s):
        {"method": lambda: s["rules"]["x-y"]["methods"][0],
         "lock": lambda: s["locks"]["sword-shield"]["pikachu"],
         "rule": lambda: s["locks"]["gold-silver"]["_rules"][0],
         "status": lambda: s["status"]["mew"],
         "charm": lambda: s["rules"]["x-y"]["charm"],
         "game": lambda: s["rules"]["red-blue"]}[where]().pop("note")
    with pytest.raises(ValueError, match="note"):
        broken(edit)()


def test_a_method_needs_plain_and_detail_lines():
    with pytest.raises(ValueError, match="plain"):
        broken(lambda s: s["rules"]["x-y"]["methods"][0].pop("plain"))()
    with pytest.raises(ValueError, match="detail"):
        broken(lambda s: s["rules"]["x-y"]["methods"][0].pop("detail"))()


def test_a_method_has_exactly_one_kind_of_odds():
    with pytest.raises(ValueError, match="one of"):
        broken(lambda s: s["rules"]["x-y"]["methods"][0].update(one_in=10))()
    with pytest.raises(ValueError, match="one of"):
        broken(lambda s: s["rules"]["x-y"]["methods"][0].pop("rolls"))()


def test_charm_odds_need_a_game_with_a_charm():
    with pytest.raises(ValueError, match="charm"):
        broken(lambda s: s["rules"]["heartgold-soulsilver"]["methods"][1].update(charm_rolls=7))()


def test_best_names_one_of_the_methods():
    with pytest.raises(ValueError, match="best"):
        broken(lambda s: s["rules"]["x-y"].update(best="chain-fishing"))()


def test_lock_and_status_values_are_checked():
    with pytest.raises(ValueError, match="sometimes"):
        broken(lambda s: s["locks"]["sword-shield"]["pikachu"].update(lock="sometimes"))()
    with pytest.raises(ValueError, match="rare"):
        broken(lambda s: s["status"]["mew"].update(status="rare"))()


def test_a_game_without_shinies_has_no_locks():
    with pytest.raises(ValueError, match="red-blue"):
        broken(lambda s: s["locks"].update({"red-blue": {"mew": dict(s["status"]["mew"], lock="never",
                                                                     encounter="e")}}))()


def test_a_never_shiny_status_cant_be_shiny_somewhere():
    def edit(s):
        s["status"]["pikachu"] = {"status": "never", "how": "h", "verified": "single", "note": "n"}
    with pytest.raises(ValueError, match="pikachu"):  # Sword / Shield's wild Pikachu can be shiny (partial lock)
        broken(edit)()
