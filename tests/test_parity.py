"""Parity with the research: on the research's Gen 9 field and data, production BBR equals the research recompute
(fixtures/research_gen9_ratings.json, made by the research's final model, BBR_RESEARCH.md part 3).

Slow (the battle simulation over the full field, a few minutes): `pytest --runslow tests/test_parity.py`."""
import json, os
import numpy as np, pytest
from conftest import RESEARCH_GEN9
import bbrlib, build_bbr

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.mark.slow
@pytest.mark.skipif(not os.path.exists(RESEARCH_GEN9), reason="needs the research's gen9.json")
def test_production_matches_research_on_gen9_field():
    ref = json.load(open(os.path.join(HERE, "fixtures", "research_gen9_ratings.json")))
    bbrlib.load_gendata(9, RESEARCH_GEN9)
    mons = [m for m in build_bbr.roster(bbrlib.gendata(9)) if m["field"]]  # the other rows don't change the field's
    got = dict(zip([m["id"] for m in mons], build_bbr.ratings(mons, build_bbr.duel_scores(mons, mons))))
    assert sorted(got) == sorted(ref)
    a, b = np.array([got[k] for k in ref]), np.array([ref[k] for k in ref])
    rank = lambda v: np.argsort(np.argsort(v))
    assert np.corrcoef(rank(a), rank(b))[0, 1] >= 0.999
    assert np.abs(a - b).max() <= 2
