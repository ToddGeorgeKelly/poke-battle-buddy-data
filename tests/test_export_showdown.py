"""bbr/export_showdown.mjs: one JSON per generation, each gen's mods applied over the next gen's data
(the research's load.mjs). Runs node on a tiny fake Showdown data/ folder."""
import json, os, shutil, subprocess
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE = {
    "pokedex.ts": "export const Pokedex = {a: {num: 1, name: 'A', types: ['Fairy']}, b: {num: 2, name: 'B'}};",
    "formats-data.ts": "export const FormatsData = {a: {tier: 'OU'}, b: {tier: 'UU'}};",
    "moves.ts": "export const Moves = {tackle: {num: 33, basePower: 40, basePowerCallback() { return 1; }}};",
    "abilities.ts": "export const Abilities = {pressure: {rating: 2.5}};",
    "typechart.ts": "export const TypeChart = {fairy: {damageTaken: {}}, normal: {damageTaken: {}}};",
    "learnsets.ts": "export const Learnsets = {a: {learnset: {tackle: ['9L1']}}};",
}
MODS = {
    # Gen 8: A is Normal there (inherit merges over Gen 9's entry), its own tiers replace Gen 9's.
    "gen8/pokedex.ts": "export const Pokedex = {a: {inherit: true, types: ['Normal']}};",
    "gen8/formats-data.ts": "export const FormatsData = {a: {tier: 'UU'}};",
    # Gen 5: Tackle is 50 power; no inherit means the entry is replaced outright.
    "gen5/moves.ts": "export const Moves = {tackle: {num: 33, basePower: 50}};",
}


@pytest.fixture
def showdown(tmp_path):
    if not shutil.which("node"):
        pytest.skip("needs node")
    data = tmp_path / "data"
    for name, text in {**BASE, **{"mods/" + k: v for k, v in MODS.items()}}.items():
        (data / name).parent.mkdir(parents=True, exist_ok=True)
        (data / name).write_text(text)
    out = tmp_path / "gen"
    subprocess.run(["node", os.path.join(ROOT, "bbr", "export_showdown.mjs"), str(data), str(out)], check=True,
                   capture_output=True)
    return {g: json.load(open(out / f"gen{g}.json")) for g in range(4, 10)}


def test_writes_gens_4_to_9_with_every_table(showdown):
    for g, d in showdown.items():
        assert set(d) == {"pokedex", "formats", "moves", "abilities", "typechart", "learnsets"}, g


def test_gen9_is_showdowns_current_data_with_functions_as_true(showdown):
    assert showdown[9]["pokedex"]["a"]["types"] == ["Fairy"]
    assert showdown[9]["moves"]["tackle"] == {"num": 33, "basePower": 40, "basePowerCallback": True}


def test_each_gen_applies_its_mods_over_the_next_gen(showdown):
    a8 = showdown[8]["pokedex"]["a"]
    assert a8 == {"num": 1, "name": "A", "types": ["Normal"]}           # inherit: merged, flag dropped
    assert showdown[4]["pokedex"]["a"]["types"] == ["Normal"]           # carried down to older gens
    assert showdown[8]["formats"] == {"a": {"tier": "UU"}}              # tiers replaced, not merged
    assert showdown[7]["formats"] == {"a": {"tier": "UU"}}
    assert showdown[6]["moves"]["tackle"]["basePower"] == 40
    assert showdown[5]["moves"]["tackle"] == {"num": 33, "basePower": 50}  # replaced, callback gone
    assert showdown[4]["moves"]["tackle"]["basePower"] == 50
