"""The breeding.json about to be committed: known breeding facts hold (the daily job runs this before committing)."""
import json, os, pathlib
import pytest

BREEDING_JSON = pathlib.Path(os.environ.get("BREEDING_JSON",
                                            pathlib.Path(__file__).parent.parent / "breeding.json"))


@pytest.fixture(scope="module")
def doc():
    return json.loads(BREEDING_JSON.read_text())


def egg_movers(doc, game, move):
    return [doc["pk"][i] for i in doc["games"][game]["em"][move]["e"]]


def test_shape_and_pinned_sources(doc):
    assert doc["schema"] == 1
    assert set(doc["sources"]) == {"pokeapi", "showdown"}
    assert len(doc["species"]) >= 1025 and len(doc["pk"]) == len(set(doc["pk"]))


def test_babies_and_their_incense(doc):
    sp = doc["species"]
    assert sp["pichu"]["b"] and "i" not in sp["pichu"] and sp["pichu"]["bp"] == ["pikachu", "raichu"]
    assert sp["munchlax"]["i"] == "full-incense" and sp["azurill"]["i"] == "sea-incense"
    assert sp["wynaut"]["i"] == "lax-incense" and sp["happiny"]["i"] == "luck-incense"
    assert sum(1 for s in sp.values() if "i" in s) == 9


def test_egg_groups_and_what_eggs_hatch_into(doc):
    sp = doc["species"]
    assert sp["ditto"]["eg"] == ["ditto"] and sp["entei"]["eg"] == ["no-eggs"]
    assert sp["raichu"]["o"] == "pichu" and "o" not in sp["snorlax"]
    assert sp["manaphy"]["o"] == "phione" and sp["nidoran-f"]["ao"] == ["nidoran-m"]


def test_games_without_breeding(doc):
    no = {g for g, v in doc["games"].items() if not v["br"]}
    assert no == {"red-blue", "yellow", "lets-go-pikachu-lets-go-eevee", "legends-arceus", "legends-za"}
    assert all("em" not in doc["games"][g] for g in no)


def test_breeding_games_have_egg_moves_and_rules(doc):
    games = doc["games"]
    assert "reversal" in [m for m in games["gold-silver"]["em"]] and "pichu" in egg_movers(doc, "crystal", "reversal")
    assert "charmander" in egg_movers(doc, "scarlet-violet", "belly-drum")
    assert games["crystal"]["r"] == ["father", "tm", "tutor"] and games["scarlet-violet"]["r"] == ["mirror-herb"]
    assert all(len(v["em"]) > 100 for v in games.values() if v["br"])


def test_legendaries_have_no_egg_moves(doc):
    entei = doc["pk"].index("entei") if "entei" in doc["pk"] else None
    for v in doc["games"].values():
        for how in v.get("em", {}).values():
            assert entei not in how.get("e", [])
