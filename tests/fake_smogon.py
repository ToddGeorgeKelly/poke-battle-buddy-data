"""A tiny stand-in for smogon.com/stats (and Showdown's pokedex.json), so tests never touch the network."""
import re

STATS = "https://www.smogon.com/stats"
POKEDEX = "https://play.pokemonshowdown.com/data/pokedex.json"


def mon(usage, moves=("Earthquake", "Swords Dance"), checks=None, tera=True, **extra):
    """One Pokemon's chaos entry. checks: {name: (n, p, d)}, written as a dict like newer months unless old_checks."""
    v = {"usage": usage, "Abilities": {"Rough Skin": 900, "Sand Veil": 100}, "Items": {"Choice Scarf": 3, "Leftovers": 5},
         "Moves": {m: 10 - i for i, m in enumerate(moves)}, "Spreads": {"Jolly:0/252/0/0/4/252": 7, "Adamant:252/252/0/0/4/0": 2},
         "Teammates": {"Gholdengo": 2.0, "Great Tusk": 1.0},
         "Checks and Counters": {k: {"n": n, "p": p, "d": d} for k, (n, p, d) in (checks or {}).items()}}
    if tera:
        v["Tera Types"] = {"Steel": 5, "Fire": 9}
    v.update(extra)
    return v


def old_checks(v):
    """Older months store each check as a list [n, p, d]."""
    v["Checks and Counters"] = {k: [c["n"], c["p"], c["d"]] for k, c in v["Checks and Counters"].items()}
    return v


def chaos(battles, mons):
    return {"info": {"number of battles": battles, "cutoff": 1500}, "data": mons}


class FakeSmogon:
    """months: {"2026-09": {"gen9ou": chaos(...), ...}}. Records every URL fetched in .urls."""

    def __init__(self, months, pokedex=None):
        self.months = months
        self.pokedex = pokedex or {"garchomp": {"num": 445, "name": "Garchomp", "tier": "OU", "natDexTier": "OU"},
                                   "pikachu": {"num": 25, "name": "Pikachu", "tier": "PU", "doublesTier": "DUU"},
                                   "capmon": {"num": -1, "name": "Capmon", "tier": "CAP"}}
        self.urls = []

    def fetch(self, url, as_json=True, tries=4):
        self.urls.append(url)
        if url == POKEDEX:
            return self.pokedex
        if url == f"{STATS}/":
            return "".join(f'<a href="{m}/">{m}/</a>\n' for m in sorted(self.months))
        match = re.fullmatch(rf"{STATS}/(\d{{4}}-\d\d)/chaos/(.*)", url)
        if match and match.group(1) in self.months:
            month, name = match.groups()
            if name == "":
                return "".join(f'<a href="{f}-{c}.json">{f}-{c}.json</a>\n' for f in sorted(self.months[month])
                               for c in (0, 1500, 1695))
            fid = name.removesuffix("-1500.json")
            if fid in self.months[month]:
                return self.months[month][fid]
        raise AssertionError(f"unexpected URL {url}")

    def chaos_fetches(self):
        """The (month, format) of every chaos file downloaded, in order."""
        return [m.groups() for u in self.urls if (m := re.fullmatch(rf"{STATS}/(.*)/chaos/(.+)-1500\.json", u))]
