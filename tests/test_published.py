"""The bbr.json about to be committed: every gen is there and holds real ratings (the daily job runs this before committing)."""
import json, os, pathlib

BBR_JSON = pathlib.Path(os.environ.get("BBR_JSON", pathlib.Path(__file__).parent.parent / "bbr.json"))


def test_published_bbr_has_gen9_and_every_older_gen():
    doc = json.loads(BBR_JSON.read_text())
    assert doc["schema"] == 1
    assert len(doc["ratings"]) > 1000, "Gen 9 ratings look truncated"
    assert sorted(doc.get("gens", {})) == ["4", "5", "6", "7", "8"]
    for g, gen in doc["gens"].items():
        assert len(gen["ratings"]) > 300, f"Gen {g} ratings look truncated"
        assert all(0 <= v <= 999 for v in gen["ratings"].values())
