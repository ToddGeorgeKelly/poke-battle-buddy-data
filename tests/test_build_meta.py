"""build_meta.py: meta.json's output, pinned byte for byte against a fake Smogon month."""
import json, os
import pytest
import build_meta
from fake_smogon import FakeSmogon, chaos, mon

EXPECTED = os.path.join(os.path.dirname(__file__), "fixtures", "meta_expected.json")


def month_2026_09():
    return {
        "gen9ou": chaos(5000, {
            "Garchomp": mon(0.31234, moves=("Earthquake", "", "Swords Dance", "Scale Shot", "Stealth Rock", "Spikes",
                                            "Fire Fang", "Iron Head", "Stone Edge", "Dragon Tail"),
                            checks={"Corviknight": (100, 0.7, 0.02), "Skarmory": (50, 0.9, 0.1), "Dondozo": (80, 0.6, 0.01)}),
            "Pikachu": mon(0.0151, tera=False, Spreads={}),
        }),
        "gen9ubers": chaos(800, {"Koraidon": mon(0.5)}),
        "gen9monotype": chaos(300, {"Garchomp": mon(0.2)}),
        "gen9vgc2026regf": chaos(1000, {"Incineroar": mon(0.6)}),
        "gen9vgc2026regg": chaos(3000, {"Miraidon": mon(0.4)}),
        "gen9vgc2026reggbo3": chaos(9000, {"Miraidon": mon(0.4)}),
        "gen9championsvgc2026regma": chaos(2000, {"Kingambit": mon(0.3)}),
        "gen8ou": chaos(9999, {"Dragapult": mon(0.4)}),
    }


@pytest.fixture
def smogon(monkeypatch, tmp_path):
    fake = FakeSmogon({"2026-08": {"gen9ou": chaos(1, {})}, "2026-09": month_2026_09()})
    monkeypatch.setattr(build_meta, "fetch", fake.fetch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["build_meta.py"])
    return fake


def test_meta_json_is_unchanged_byte_for_byte(smogon, tmp_path):
    build_meta.main()
    with open(tmp_path / "meta.json") as f, open(EXPECTED) as g:
        assert f.read() == g.read()


def test_meta_picks_singles_then_the_two_most_played_vgc_formats(smogon, tmp_path):
    build_meta.main()
    doc = json.load(open(tmp_path / "meta.json"))
    assert doc["month"] == "2026-09"
    assert [(f["id"], f["name"], f["cap"]) for f in doc["formats"]] == [
        ("gen9ou", "OU", "OU"), ("gen9ubers", "Ubers", "Uber"), ("gen9monotype", "Monotype", None),
        ("gen9vgc2026regg", "VGC 2026 Reg G", None), ("gen9championsvgc2026regma", "Champions VGC 2026 Reg M-A", None)]
    chomp = doc["formats"][0]["pokemon"]["Garchomp"]
    assert chomp["u"] == 31.2 and chomp["cc"] == ["Corviknight", "Dondozo", "Skarmory"]
    assert chomp["m"] == ["Earthquake", "Swords Dance", "Scale Shot", "Stealth Rock", "Spikes", "Fire Fang", "Iron Head",
                          "Stone Edge"]
