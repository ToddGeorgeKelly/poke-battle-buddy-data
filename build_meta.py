"""Builds meta.json: a trimmed snapshot of Smogon's monthly usage stats plus Showdown tiers, for Poke Battle Buddy.

Runs by itself every day from .github/workflows/update.yml. It finds the newest month Smogon has posted, the newest
generation, and the most-played VGC/Champions formats, so new months, regulations and generations show up without
anyone editing this file. Smogon posts once a month, so most days nothing changes and nothing is committed.

    python3 build_meta.py                 # writes meta.json
    python3 build_meta.py --swift FILE    # also writes the app's built-in fallback (MetaDataTable.swift)

Sources: https://www.smogon.com/stats/ (official Smogon usage stats)
         https://play.pokemonshowdown.com/data/pokedex.json (tiers; Pokemon Showdown, MIT license)
"""
import json, re, sys, time, urllib.error, urllib.request

STATS = "https://www.smogon.com/stats"
TOP = 50           # Pokemon kept per format
DOUBLES_PICKS = 2  # most-played VGC/Champions formats to include
SCHEMA = 1         # bump if the app needs a new field layout


def fetch(url, as_json=True, tries=4):
    """Downloads a URL, retrying a few times since Smogon's server sometimes answers with a temporary error (5xx)."""
    request = urllib.request.Request(url, headers={"User-Agent": "PokeBattleBuddy-data-builder"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read()
            return json.loads(body) if as_json else body.decode()
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == tries - 1 or (isinstance(error, urllib.error.HTTPError) and error.code < 500):
                raise
            time.sleep(10 * (attempt + 1))


def newest_month():
    months = sorted(set(re.findall(r'href="(\d{4}-\d{2})/"', fetch(f"{STATS}/", as_json=False))))
    for month in reversed(months):
        listing = fetch(f"{STATS}/{month}/chaos/", as_json=False)
        if re.search(r'href="gen\d+ou-1500\.json"', listing):
            return month, listing
    raise SystemExit("No month with chaos stats found")


def format_name(fid, gen):
    """Readable name: gen9ou -> OU, gen9championsvgc2026regmc -> Champions VGC 2026 Reg M-C."""
    fixed = {"ou": "OU", "ubers": "Ubers", "uu": "UU", "ru": "RU", "nu": "NU", "pu": "PU", "monotype": "Monotype",
             "nationaldex": "National Dex OU", "doublesou": "Doubles OU", "championsou": "Champions OU"}
    rest = fid[len(f"gen{gen}"):]
    if rest in fixed:
        return fixed[rest]
    match = re.fullmatch(r"(champions)?(vgc|bss)(\d{4})?(?:reg(\w+?))?(bo3)?", rest)
    if match:
        champions, kind, year, reg, bo3 = match.groups()
        parts = ["Champions"] if champions else []
        parts.append(kind.upper())
        if year:
            parts.append(year)
        if reg:
            parts.append("Reg " + "-".join(reg.upper()))
        if bo3:
            parts.append("Bo3")
        return " ".join(parts)
    return fid


def top(d, n):
    return [k for k, _ in sorted(d.items(), key=lambda kv: -kv[1])[:n]]


def main():
    month, listing = newest_month()
    gen = max(int(g) for g in re.findall(r'href="gen(\d+)ou-1500\.json"', listing))
    available = set(re.findall(r'href="(gen\d+[a-z0-9]+)-1500\.json"', listing))

    singles = [("ou", "OU"), ("ubers", "Uber"), ("uu", "UU"), ("ru", "RU"), ("nu", "NU"), ("pu", "PU"),
               ("monotype", None), ("nationaldex", None), ("doublesou", None), ("championsou", None)]
    chosen = [(f"gen{gen}{s}", cap) for s, cap in singles if f"gen{gen}{s}" in available]

    # VGC/Champions formats change names with each regulation, so pick the most-played ones this month.
    doubles = [f for f in available if f.startswith(f"gen{gen}") and re.search(r"vgc", f) and not f.endswith("bo3")]
    battles = {}
    for fid in doubles:
        battles[fid] = fetch(f"{STATS}/{month}/chaos/{fid}-1500.json")["info"]["number of battles"]
    chosen += [(fid, None) for fid in sorted(doubles, key=lambda f: -battles[f])[:DOUBLES_PICKS]]

    formats = []
    for fid, cap in chosen:
        data = fetch(f"{STATS}/{month}/chaos/{fid}-1500.json")
        mons = sorted(data["data"].items(), key=lambda kv: -kv[1]["usage"])[:TOP]
        pokemon = {}
        for mon, v in mons:
            checks = sorted(v.get("Checks and Counters", {}).items(), key=lambda kv: -(kv[1]["p"] - 4 * kv[1]["d"]))
            pokemon[mon] = {
                "u": round(v["usage"] * 100, 1),
                "a": top(v.get("Abilities", {}), 2),
                "i": top(v.get("Items", {}), 3),
                "m": [m for m in top(v.get("Moves", {}), 9) if m][:8],
                "t": top(v.get("Tera Types", {}), 2),
                "s": top(v.get("Spreads", {}), 1)[0] if v.get("Spreads") else "",
                "tm": top(v.get("Teammates", {}), 8),
                "cc": [c for c, _ in checks[:6]],
            }
        formats.append({"id": fid, "name": format_name(fid, gen), "cap": cap,
                        "battles": data["info"]["number of battles"], "pokemon": pokemon})
        print(f"{fid}: {len(pokemon)} Pokemon, {data['info']['number of battles']} battles", file=sys.stderr)

    tiers = {}
    for v in fetch("https://play.pokemonshowdown.com/data/pokedex.json").values():
        t = {short: v[key] for key, short in (("tier", "s"), ("doublesTier", "d"), ("natDexTier", "n")) if v.get(key)}
        if t and v.get("num", 0) > 0:
            tiers[v["name"]] = t

    table = {"schema": SCHEMA, "month": month, "formats": formats, "tiers": tiers}
    text = json.dumps(table, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
    with open("meta.json", "w") as f:
        f.write(text)
    print(f"meta.json: {month}, {len(formats)} formats, {len(text) // 1024} KB", file=sys.stderr)

    if "--swift" in sys.argv:
        path = sys.argv[sys.argv.index("--swift") + 1]
        assert '"##' not in text
        with open(path, "w") as f:
            f.write(f'''//
//  MetaDataTable.swift
//  PokeBattleBuddy
//
//  GENERATED FILE, don't edit by hand. The built-in fallback copy of the usage stats ({month}).
//  The app downloads a newer copy each day from https://github.com/ToddGeorgeKelly/poke-battle-buddy-data
//  (Smogon usage stats, https://www.smogon.com/stats/, plus Showdown tiers). Refresh with that repo's
//  build_meta.py --swift before an app release.
//  Per Pokemon: u = usage %, a = abilities, i = items, m = moves, t = Tera types, s = top spread
//  (Nature:HP/Atk/Def/SpA/SpD/Spe EVs), tm = common teammates, cc = top checks and counters. IDs are Showdown IDs.
//

let metaDataJSON = ##"{text}"##
''')


if __name__ == "__main__":
    main()
