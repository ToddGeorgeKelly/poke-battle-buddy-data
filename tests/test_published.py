"""The bbr.json about to be committed: every gen is there and holds real ratings (the daily job runs this before committing)."""
import json, os, pathlib

BBR_JSON = pathlib.Path(os.environ.get("BBR_JSON", pathlib.Path(__file__).parent.parent / "bbr.json"))


def test_published_bbr_has_gen9_and_every_older_gen():
    doc = json.loads(BBR_JSON.read_text())
    assert doc["schema"] == 1
    assert len(doc["ratings"]) > 1000, "Gen 9 ratings look truncated"
    # Gens 1-3 are there when the export had Showdown's mods for them; Gens 4-8 always.
    assert {"4", "5", "6", "7", "8"} <= set(doc.get("gens", {})) <= {"1", "2", "3", "4", "5", "6", "7", "8"}
    fewest = {"1": 140, "2": 240, "3": 360}  # Gen 1 has 151 Pokemon, Gen 2 251, Gen 3 386
    for g, gen in doc["gens"].items():
        assert len(gen["ratings"]) > fewest.get(g, 300), f"Gen {g} ratings look truncated"
        assert all(0 <= v <= 999 for v in gen["ratings"].values())
