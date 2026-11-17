"""build_breeding.py: each species' breeding facts, each game's egg moves and who learns them, and the Showdown check."""
import json
import pytest
import build_breeding as bb
import fake_breeding as fake


@pytest.fixture
def api():
    return bb.parse_pokeapi({
        "pokemon_species": fake.POKEMON_SPECIES, "evolution_chains": fake.EVOLUTION_CHAINS, "items": fake.ITEMS,
        "egg_groups": fake.EGG_GROUPS, "pokemon_egg_groups": fake.POKEMON_EGG_GROUPS, "pokemon": fake.POKEMON,
        "moves": fake.MOVES, "version_groups": fake.VERSION_GROUPS, "pokemon_move_methods": fake.POKEMON_MOVE_METHODS,
        "pokemon_moves": fake.POKEMON_MOVES})


@pytest.fixture
def species(api):
    return bb.species_table(api)


@pytest.fixture
def showdown():
    return {"scarlet-violet": bb.parse_showdown_egg_moves(fake.SHOWDOWN_GEN9, 9),
            "brilliant-diamond-shining-pearl": bb.parse_showdown_egg_moves(fake.SHOWDOWN_BDSP, 8)}


def build(api, showdown, allowed=frozenset(), **kw):
    """The fake sources agree, so no disagreement is allowed (the real list in bb.ALLOWED is for the real sources)."""
    return bb.build(api, showdown, commits={"pokeapi": "abc", "showdown": "def"}, built="2026-11-16T00:00:00Z",
                    games=fake.GAMES, allowed=allowed, **kw)


# Each species' breeding facts


def test_egg_groups_gender_ratio_and_hatch_cycles(species):
    assert species["pikachu"]["eg"] == ["ground", "fairy"]
    assert species["pikachu"]["g"] == 4 and species["pikachu"]["h"] == 10
    assert species["snorlax"]["eg"] == ["monster"] and species["snorlax"]["g"] == 1 and species["snorlax"]["h"] == 40


def test_genderless_species_have_gender_rate_minus_one_and_ditto_is_in_the_ditto_group(species):
    assert species["magnemite"]["g"] == -1 and species["ditto"]["g"] == -1
    assert species["ditto"]["eg"] == ["ditto"]


def test_babies_are_flagged_and_only_incense_babies_name_their_incense(species):
    assert species["pichu"]["b"] is True and "i" not in species["pichu"]
    assert species["munchlax"]["b"] is True and species["munchlax"]["i"] == "full-incense"
    assert species["azurill"]["i"] == "sea-incense"
    assert "b" not in species["pikachu"] and "i" not in species["snorlax"]


def test_a_baby_that_cant_breed_lists_the_evolutions_to_breed_instead(species):
    assert species["pichu"]["eg"] == ["no-eggs"]
    assert species["pichu"]["bp"] == ["pikachu", "raichu"]
    assert species["munchlax"]["bp"] == ["snorlax"]
    assert species["azurill"]["bp"] == ["marill", "azumarill"]


def test_an_evolved_species_eggs_hatch_into_its_first_stage(species):
    assert species["raichu"]["o"] == "pichu" and species["pikachu"]["o"] == "pichu"
    assert species["meowstic"]["o"] == "espurr"
    assert "o" not in species["espurr"] and "o" not in species["pichu"]  # its own eggs, or none


def test_without_incense_the_egg_hatches_into_the_stage_after_the_baby(species):
    assert "o" not in species["snorlax"] and "o" not in species["marill"]  # Snorlax eggs hatch Snorlax
    assert species["azumarill"]["o"] == "marill"


def test_manaphys_eggs_hatch_into_phione(species):
    assert species["manaphy"]["o"] == "phione" and "o" not in species["phione"]


def test_nidoran_f_and_illumise_eggs_can_also_hatch_into_the_other_gender_line(species):
    assert species["nidoran-f"]["ao"] == ["nidoran-m"] and "o" not in species["nidoran-f"]
    assert species["illumise"]["ao"] == ["volbeat"]
    assert "ao" not in species["nidoran-m"] and "ao" not in species["volbeat"]


# Each game's egg moves and who learns them


def test_games_without_breeding_have_no_egg_moves(api, showdown):
    games = build(api, showdown)["games"]
    assert games["red-blue"] == {"gen": 1, "br": False}
    assert games["legends-arceus"] == {"gen": 8, "br": False}


def test_a_breeding_game_lists_each_egg_move_with_who_learns_it_and_how(api):
    em = bb.learners(api, ["scarlet-violet", "the-teal-mask"])
    assert em["sweet-kiss"] == {"e": ["pikachu", "pichu", "pichu-spiky-eared"]}  # in PokeAPI's Pokemon order
    assert em["wish"] == {"e": ["pikachu", "pichu", "pichu-spiky-eared"], "l": ["raichu"]}
    assert em["belly-drum"] == {"e": ["marill"], "l": ["azumarill"]}
    assert em["charm"] == {"e": ["munchlax", "meowstic-male", "meowstic-female"], "m": ["snorlax"]}


def test_only_egg_moves_are_listed_and_the_dlc_version_groups_count(api):
    em = bb.learners(api, ["scarlet-violet", "the-teal-mask"])
    assert "thunderbolt" not in em and "volt-tackle" not in em   # a TM move only, and Light Ball's Volt Tackle
    assert em["surf"] == {"e": ["marill"], "m": ["marill"]}       # from The Teal Mask


def test_egg_moves_of_pokemon_that_cant_breed_or_hatch_are_left_out(api):
    em = bb.learners(api, ["scarlet-violet"])
    assert "extreme-speed" not in em                                 # Entei: Undiscovered and not a baby
    assert em["sweet-kiss"]["e"] == ["pikachu", "pichu", "pichu-spiky-eared"]  # Pichu hatches: a baby


def test_tutor_moves_are_listed_and_other_games_moves_dont_count(api):
    assert bb.learners(api, ["crystal"]) == {"sweet-kiss": {"e": ["pichu"], "t": ["pikachu"]}}  # not Ice Punch
    assert bb.learners(api, ["gold-silver"]) == {"sweet-kiss": {"e": ["pichu"]}}


def test_games_carry_their_generation_and_breeding_rules(api, showdown):
    games = build(api, showdown)["games"]
    assert games["gold-silver"]["gen"] == 2 and games["gold-silver"]["r"] == ["father", "tm"]
    assert games["crystal"]["r"] == ["father", "tm", "tutor"]
    assert games["scarlet-violet"]["r"] == ["mirror-herb"]
    assert "r" not in games["brilliant-diamond-shining-pearl"]


def test_learners_are_indexes_into_the_pokemon_list(api, showdown):
    doc = build(api, showdown)
    pk = doc["pk"]
    charm = doc["games"]["scarlet-violet"]["em"]["charm"]
    assert [pk[i] for i in charm["e"]] == ["munchlax", "meowstic-male", "meowstic-female"]
    assert [pk[i] for i in charm["m"]] == ["snorlax"]
    assert pk == sorted(pk, key=lambda n: bb.pokemon_order(api, n)) and len(pk) == len(set(pk))
    assert "ditto" not in pk                                   # learns none of the egg moves


def test_shape_sources_and_species(api, showdown):
    doc = build(api, showdown)
    assert doc["schema"] == 1 and doc["sources"] == {"pokeapi": "abc", "showdown": "def"}
    assert doc["built"] == "2026-11-16T00:00:00Z"
    assert set(doc) == {"schema", "built", "sources", "species", "games", "pk"}
    assert doc["species"]["munchlax"]["i"] == "full-incense"


# The Showdown check (Scarlet / Violet against Gen 9, BDSP against the gen8bdsp mod)


def test_showdown_egg_moves_are_read_for_one_generation(showdown):
    assert showdown["scarlet-violet"]["pichu"] == {"sweetkiss", "wish"}
    assert "snorlax" not in showdown["scarlet-violet"]                # 8E only
    assert showdown["brilliant-diamond-shining-pearl"] == {"munchlax": {"charm"}}


def test_agreeing_sources_pass_and_showdown_only_pokemon_are_skipped(api, showdown):
    assert bb.disagreements(api, showdown, fake.GAMES) == []                       # syclar (CAP) isn't in PokeAPI


def test_a_form_showdown_files_under_its_species_is_compared_with_the_species(api, showdown):
    found = bb.disagreements(api, showdown, fake.GAMES)
    assert not [d for d in found if d[1] == "pichu-spiky-eared"]     # same egg moves as Showdown's pichu
    showdown["scarlet-violet"]["pichu"].add("charm")
    found = bb.disagreements(api, showdown, fake.GAMES)
    assert ("scarlet-violet", "pichu-spiky-eared", "charm", "showdown") in found


def test_showdown_pokemon_that_arent_in_the_game_are_skipped(api, showdown):
    assert not [d for d in bb.disagreements(api, showdown, fake.GAMES) if d[1] == "eevee-starter"]  # Let's Go only


def test_a_disagreement_fails_the_build(api, showdown):
    showdown["scarlet-violet"]["pichu"].discard("wish")
    showdown["brilliant-diamond-shining-pearl"]["munchlax"].add("tackle")
    found = bb.disagreements(api, showdown, fake.GAMES)
    assert ("scarlet-violet", "pichu", "wish", "pokeapi") in found
    assert ("brilliant-diamond-shining-pearl", "munchlax", "tackle", "showdown") in found
    with pytest.raises(ValueError, match="pichu"):
        build(api, showdown)


def test_a_first_stage_with_egg_moves_showdown_lacks_is_a_disagreement(api, showdown):
    del showdown["scarlet-violet"]["pichu"], showdown["scarlet-violet"]["marill"]
    found = bb.disagreements(api, showdown, fake.GAMES)
    assert ("scarlet-violet", "pichu", "wish", "pokeapi") in found
    assert not [d for d in found if d[1] == "marill"]                  # evolves from Azurill: Showdown may skip it


def test_an_allowed_disagreement_passes_and_a_stale_allowance_fails(api, showdown):
    showdown["scarlet-violet"]["pichu"].discard("wish")
    allowed = {("scarlet-violet", "pichu", "wish", "pokeapi"), ("scarlet-violet", "pichu-spiky-eared", "wish", "pokeapi")}
    assert build(api, showdown, allowed=allowed)["games"]["scarlet-violet"]["br"] is True
    showdown["scarlet-violet"]["pichu"].add("wish")
    with pytest.raises(ValueError, match="no longer"):
        build(api, showdown, allowed=allowed)


# Writing the file


def test_rewrites_only_when_something_besides_built_changed(api, showdown, tmp_path):
    path = tmp_path / "breeding.json"
    doc = build(api, showdown)
    assert bb.write(doc, path) is True
    assert bb.write({**doc, "built": "2026-11-17T00:00:00Z"}, path) is False
    assert json.loads(path.read_text())["built"] == "2026-11-16T00:00:00Z"
    doc["species"]["pichu"]["h"] = 5
    assert bb.write(doc, path) is True
