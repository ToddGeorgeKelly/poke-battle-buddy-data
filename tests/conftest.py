import copy, os, sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "bbr"))

# The research's Gen 9 data (the same Showdown export the research model was fitted and checked on).
RESEARCH_GEN9 = os.environ.get("BBR_RESEARCH_GEN9", "/tmp/bbr/gen/gen9.json")


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", help="also run the slow parity test (several minutes)")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: runs the battle simulation on the full Gen 9 field")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        return
    skip = pytest.mark.skip(reason="slow: run with --runslow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


def mon(num, name, types=("Normal",), stats=(80, 80, 80, 80, 80, 80), abilities=None, **extra):
    hp, at, de, sa, sd, sp = stats
    p = dict(num=num, name=name, types=list(types), baseStats=dict(hp=hp, atk=at, **{"def": de}, spa=sa, spd=sd, spe=sp),
             abilities=abilities or {"0": "Pressure"}, weightkg=50)
    p.update(extra)
    return p


TINY = dict(
    pokedex={
        "alpha": mon(1, "Alpha"),
        "beta": mon(2, "Beta", types=("Water",), stats=(90, 70, 80, 100, 80, 70)),
        "gamma": mon(3, "Gamma", types=("Fire",)),                       # in Gen 9, no tier (e.g. an NFE)
        "delta": mon(4, "Delta", types=("Grass",)),                      # not in Gen 9 (National Dex only)
        "deltamega": mon(4, "Delta-Mega", types=("Grass",), stats=(80, 120, 100, 80, 80, 100),
                         baseSpecies="Delta", forme="Mega", requiredItem="Deltite"),
        "palafin": mon(964, "Palafin", types=("Water",), stats=(100, 70, 72, 53, 62, 100)),
        "palafinhero": mon(964, "Palafin-Hero", types=("Water",), stats=(100, 160, 97, 106, 87, 100),
                           baseSpecies="Palafin", forme="Hero", battleOnly="Palafin"),
        "alphagmax": mon(1, "Alpha-Gmax", baseSpecies="Alpha", forme="Gmax"),
        "capmon": mon(-1, "Capmon"),
        "capreal": mon(5, "Capreal"),
        "ditto": mon(132, "Ditto", stats=(48, 48, 48, 48, 48, 48), abilities={"0": "Limber", "H": "Imposter"}),
    },
    formats={
        "alpha": {"tier": "OU"}, "beta": {"tier": "(OU)"}, "gamma": {"tier": "NFE"},
        "delta": {"isNonstandard": "Past", "tier": "Illegal", "natDexTier": "RU"},
        "deltamega": {"isNonstandard": "Past", "tier": "Illegal", "natDexTier": "OU"},
        "palafin": {"tier": "Uber"}, "palafinhero": {}, "alphagmax": {"isNonstandard": "Gigantamax", "tier": "Illegal"},
        "capmon": {"isNonstandard": "CAP", "tier": "CAP"}, "capreal": {"isNonstandard": "CAP", "tier": "CAP"},
        "ditto": {"tier": "PU"},
    },
    moves={"tackle": {"num": 33, "type": "Normal", "category": "Physical", "basePower": 40},
           "pursuit": {"num": 228, "type": "Dark", "category": "Physical", "basePower": 40, "isNonstandard": "Past"}},
    learnsets={"alpha": {"learnset": {"tackle": ["9L1"], "pursuit": ["7L1"]}},
               "delta": {"learnset": {"tackle": ["8L1"], "pursuit": ["7L1"]}}},
    abilities={}, typechart={},
)


@pytest.fixture
def tiny():
    return copy.deepcopy(TINY)
