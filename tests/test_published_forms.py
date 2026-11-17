"""The forms.json about to be committed: the form dex's known facts hold (the daily job runs this before committing)."""
import json, os, pathlib
import pytest

FORMS_JSON = pathlib.Path(os.environ.get("FORMS_JSON", pathlib.Path(__file__).parent.parent / "forms.json"))


@pytest.fixture(scope="module")
def doc():
    return json.loads(FORMS_JSON.read_text())


@pytest.fixture(scope="module")
def forms(doc):
    return {f["k"]: f for s in doc["species"].values() for f in s["forms"]}


def keys(doc, species):
    return [f["k"] for f in doc["species"][species]["forms"]]


def test_shape_and_pinned_sources(doc):
    assert doc["schema"] == 1
    assert set(doc["sources"]) == {"pokeapi", "sprites", "pokedextracker", "showdown"}
    assert set(doc["gender"]) == {"n", "m", "f"} and set(doc["shiny"]) == {"never", "locked"}


def test_every_key_is_used_once(doc):
    all_keys = [f["k"] for s in doc["species"].values() for f in s["forms"]]
    assert len(all_keys) == len(set(all_keys))


def test_vivillon_has_20_patterns_with_fancy_and_poke_ball_as_events(doc, forms):
    assert len(keys(doc, "vivillon")) == 20
    assert forms["vivillon-fancy"]["ev"] and forms["vivillon-poke-ball"]["ev"]
    assert "vivillon-poke-ball" in doc["shiny"]["never"]


def test_unown_28_furfrou_10_alcremie_63_with_both_sprites(doc, forms):
    assert len(keys(doc, "unown")) == 28 and len(keys(doc, "furfrou")) == 10
    alcremie = doc["species"]["alcremie"]["forms"]
    assert len(alcremie) == 63
    assert all("s" in f for f in alcremie) and all("p" in f for f in alcremie[1:])


def test_no_megas_gigantamax_totems_primals_or_battle_only_forms(forms):
    for part in ("-mega", "-gmax", "-totem", "-primal", "-eternamax", "-meteor"):
        assert not [k for k in forms if part in k], part
    for k in ("aegislash-blade", "castform-sunny", "darmanitan-zen", "darmanitan-galar-zen", "mimikyu-busted",
              "cherrim-sunshine", "wishiwashi-school", "morpeko-hangry", "eiscue-noice", "palafin-hero",
              "zygarde-complete", "koraidon-limited-build", "miraidon-drive-mode", "necrozma-ultra", "zacian-crowned"):
        assert k not in forms


def test_spinda_has_no_form_marks(doc):
    assert "spinda" not in doc["species"]


def test_alolan_raichu_is_transfer_only_in_scarlet_violet(forms):
    assert "scarlet-violet" in forms["raichu-alola"]["t"]
    assert "scarlet-violet" not in forms["raichu-alola"]["c"]


def test_102_species_have_a_visible_gender_difference(doc):
    assert sum(1 for s in doc["species"].values() if s.get("gd")) == 102
    assert "pikachu" not in doc["gender"]["n"] and "unown" in doc["gender"]["n"]


def test_caps_and_partner_forms_are_never_shiny(doc):
    caps = [f"pikachu-{c}-cap" for c in ("hoenn", "sinnoh", "unova", "kalos", "alola")]
    assert set(caps) | {"pikachu-starter", "eevee-starter"} <= set(doc["shiny"]["never"])


def test_caps_with_an_obtainable_shiny_get_shiny_marks(doc):
    # Shiny Original and World Cap came out in Pokémon GO; Partner Cap can be shiny in US / UM.
    shiny_caps = {f"pikachu-{c}-cap" for c in ("original", "partner", "world")}
    assert not shiny_caps & set(doc["shiny"]["never"])


def test_event_forms_are_flagged(forms):
    for k in ("pikachu-cosplay", "pikachu-starter", "eevee-starter", "magearna-original", "zarude-dada",
              "pichu-spiky-eared", "floette-eternal", "keldeo-resolute", "pikachu-world-cap"):
        assert forms[k].get("ev"), k


def test_other_kept_forms_are_there(forms):
    for k in ("ursaluna-bloodmoon", "gimmighoul-roaming", "sinistea-antique", "polteageist-antique",
              "poltchageist-artisan", "sinistcha-masterpiece", "ogerpon-wellspring-mask", "rotom-wash",
              "kyurem-black", "calyrex-shadow", "minior-violet"):
        assert k in forms, k
    assert forms["rotom-wash"]["r"] and forms["ursaluna-bloodmoon"]["r"]


def test_look_alike_forms_are_hidden(forms):
    for k in ("scatterbug-polar", "spewpa-fancy", "mothim-trash", "arceus-fire", "silvally-water", "genesect-douse",
              "xerneas-active"):
        assert forms[k]["h"], k
    assert "pyroar-female" not in forms and "arceus-unknown" not in forms
