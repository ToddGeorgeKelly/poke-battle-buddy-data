"""build_sets.py: every Pokemon's most popular set per format, each with the month it came from, merged month over month."""
import json
import pytest
import build_meta, build_sets
from fake_smogon import FakeSmogon, chaos, mon, old_checks


@pytest.fixture
def run(monkeypatch, tmp_path):
    """run(months, *args) runs build_sets against a fake Smogon and returns (sets.json as a dict, the fake)."""
    monkeypatch.chdir(tmp_path)

    def run(months, *args):
        fake = FakeSmogon(months)
        monkeypatch.setattr(build_meta, "fetch", fake.fetch)
        build_sets.main(list(args))
        return json.load(open(tmp_path / "sets.json")), fake
    return run


def formats(doc):
    return {f["id"]: f for f in doc["formats"]}


def test_file_shape_and_each_entry_carries_its_month(run):
    doc, _ = run({"2026-09": {"gen9ou": chaos(500, {"Garchomp": mon(0.3, checks={"Skarmory": (5, 0.8, 0.01)})}),
                              "gen9vgc2026regg": chaos(100, {"Miraidon": mon(0.5)})}})
    assert set(doc) == {"schema", "month", "formats"}
    assert doc["schema"] == 1 and doc["month"] == "2026-09"
    assert [(f["id"], f["name"], f["cap"]) for f in doc["formats"]] == [("gen9ou", "OU", "OU"),
                                                                       ("gen9vgc2026regg", "VGC 2026 Reg G", None)]
    assert formats(doc)["gen9ou"]["pokemon"] == {"Garchomp": {
        "mo": "2026-09", "u": 30.0, "a": ["Rough Skin", "Sand Veil"], "i": ["Leftovers", "Choice Scarf"],
        "m": ["Earthquake", "Swords Dance"], "t": ["Fire", "Steel"], "s": "Jolly:0/252/0/0/4/252",
        "tm": ["Gholdengo", "Great Tusk"], "cc": ["Skarmory"]}}


def test_a_month_counts_only_at_one_percent_usage(run):
    doc, _ = run({"2026-09": {"gen9ou": chaos(500, {"Garchomp": mon(0.3), "Edge": mon(0.01), "Under": mon(0.0099)})}})
    assert sorted(formats(doc)["gen9ou"]["pokemon"]) == ["Edge", "Garchomp"]


AUG = {"gen9ou": chaos(500, {"Garchomp": mon(0.3, moves=("Spikes",)), "Gone": mon(0.05), "Dipped": mon(0.04)})}
SEP = {"gen9ou": chaos(500, {"Garchomp": mon(0.2, moves=("Earthquake",)), "Dipped": mon(0.005)})}


def test_a_newer_month_replaces_and_missing_pokemon_keep_their_last_set(run):
    run({"2026-08": AUG})
    doc, _ = run({"2026-08": AUG, "2026-09": SEP})
    ou = formats(doc)["gen9ou"]["pokemon"]
    assert doc["month"] == "2026-09"
    assert (ou["Garchomp"]["mo"], ou["Garchomp"]["m"], ou["Garchomp"]["u"]) == ("2026-09", ["Earthquake"], 20.0)
    assert (ou["Gone"]["mo"], ou["Gone"]["u"]) == ("2026-08", 5.0)      # not in September at all
    assert (ou["Dipped"]["mo"], ou["Dipped"]["u"]) == ("2026-08", 4.0)  # under 1% in September


def test_the_daily_run_downloads_nothing_more_when_the_month_is_already_in(run, tmp_path):
    run({"2026-09": SEP})
    before = (tmp_path / "sets.json").read_text()
    _, fake = run({"2026-09": SEP})
    assert fake.chaos_fetches() == []
    assert (tmp_path / "sets.json").read_text() == before


def test_backfill_walks_oldest_first_so_newer_months_win(run):
    months = {"2026-07": {"gen9ou": chaos(500, {"Garchomp": mon(0.3, moves=("Outrage",)), "July": mon(0.2)})},
              "2026-08": AUG, "2026-09": SEP}
    doc, fake = run(months, "--backfill", "2026-08")
    ou = formats(doc)["gen9ou"]["pokemon"]
    assert fake.chaos_fetches() == [("2026-08", "gen9ou"), ("2026-09", "gen9ou")]
    assert "July" not in ou                                   # before the backfill's first month
    assert (ou["Garchomp"]["mo"], ou["Garchomp"]["m"]) == ("2026-09", ["Earthquake"])
    assert ou["Gone"]["mo"] == ou["Dipped"]["mo"] == "2026-08"
    assert doc["month"] == "2026-09"


def test_backfill_never_overwrites_a_newer_set_already_in_the_file(run):
    run({"2026-08": AUG, "2026-09": SEP})
    doc, _ = run({"2026-07": {"gen9ou": chaos(500, {"Garchomp": mon(0.3, moves=("Outrage",))})}, "2026-08": AUG},
                 "--backfill", "2026-07")
    chomp = formats(doc)["gen9ou"]["pokemon"]["Garchomp"]
    assert (chomp["mo"], chomp["m"]) == ("2026-09", ["Earthquake"])
    assert doc["month"] == "2026-09"


def test_backfill_skips_formats_a_month_does_not_have_and_reads_old_checks_lists(run):
    old = old_checks(mon(0.4, tera=False, checks={"Skarmory": (5, 0.8, 0.01), "Dondozo": (5, 0.9, 0.1)}))
    months = {"2026-08": {"gen9ou": chaos(500, {"Garchomp": old})},
              "2026-09": {"gen9ou": chaos(500, {"Kingambit": mon(0.3)}),
                          "gen9vgc2026regg": chaos(100, {"Miraidon": mon(0.5)})}}
    doc, fake = run(months, "--backfill", "2026-08")
    assert ("2026-08", "gen9vgc2026regg") not in fake.chaos_fetches()
    f = formats(doc)
    assert list(f["gen9vgc2026regg"]["pokemon"]) == ["Miraidon"]
    chomp = f["gen9ou"]["pokemon"]["Garchomp"]
    assert (chomp["mo"], chomp["t"], chomp["cc"]) == ("2026-08", [], ["Skarmory", "Dondozo"])
