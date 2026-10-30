"""Parity with the research: on the research's data for each gen (4-9), production BBR of that gen's field equals the
research recompute (fixtures/research_gen<g>_ratings.json, made by fixtures/research_ref.py from the research's final
model and its saved battle matrices, BBR_RESEARCH.md part 3).

Slow (the battle simulation over each full field, 1-5 minutes per gen): `pytest --runslow tests/test_parity.py`."""
import json, os
import numpy as np, pytest
from conftest import RESEARCH_GEN
import bbrlib, build_bbr

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.mark.slow
@pytest.mark.parametrize("g", [9, *build_bbr.OLDER_GENS])
def test_production_matches_research_on_each_gens_field(g):
    path = os.path.join(RESEARCH_GEN, f"gen{g}.json")
    if not os.path.exists(path):
        pytest.skip(f"needs the research's gen{g}.json")
    ref = json.load(open(os.path.join(HERE, "fixtures", f"research_gen{g}_ratings.json")))
    bbrlib.load_gendata(g, path)
    mons = [m for m in build_bbr.roster(bbrlib.gendata(g), g) if m["field"]]  # the other rows don't change the field's
    got = dict(zip([m["id"] for m in mons], build_bbr.ratings(mons, build_bbr.duel_scores(mons, mons, g), g)))
    assert sorted(got) == sorted(ref)
    a, b = np.array([got[k] for k in ref]), np.array([ref[k] for k in ref])
    rank = lambda v: np.argsort(np.argsort(v))
    assert np.corrcoef(rank(a), rank(b))[0, 1] >= 0.999
    assert np.abs(a - b).max() <= 0.05  # 0.006 or less in every gen: the fixtures are rounded to 0.01
