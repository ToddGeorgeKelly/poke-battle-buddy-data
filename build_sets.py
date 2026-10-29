"""Builds sets.json: the most popular set of every Pokemon in each format, for the Pokedex's SET tab in Poke Battle Buddy.

meta.json keeps only the top 50 of the newest month. sets.json keeps every Pokemon that reached 1% usage in some month,
with the set from the newest such month and that month ("mo"). Each run merges the newest month over the previous file,
so a Pokemon missing this month keeps its last known set. Formats are the ones build_meta.py picks.

    python3 build_sets.py                     # merges in the newest month (does nothing if it's already in)
    python3 build_sets.py --backfill 2022-11  # one-time: merges every month from 2022-11 on, oldest first

Source: https://www.smogon.com/stats/ (official Smogon usage stats, the same 1500 rating cutoff as meta.json)
"""
import json, sys
import build_meta as meta

SCHEMA = 1        # bump if the app needs a new field layout
MIN_USAGE = 0.01  # a month counts for a Pokemon only at 1% usage or more (chaos usage is a fraction)


def month_sets(data, month):
    """Every Pokemon's set from one month's chaos stats (1% usage or more), tagged with that month."""
    return {mon: {"mo": month, **meta.set_of(v)} for mon, v in data["data"].items() if v["usage"] >= MIN_USAGE}


def load(path="sets.json"):
    """The previous sets.json, or an empty one."""
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"schema": SCHEMA, "month": "", "formats": []}


def merge(doc, gen, chosen, month, chaos_files):
    """Merges one month into doc. chaos_files: {format id: chaos JSON} for the chosen formats that month has.
    A Pokemon's set is replaced only by a month at least as new as its own; one missing this month keeps its old set."""
    old = {f["id"]: f["pokemon"] for f in doc["formats"]}
    formats = []
    for fid, cap in chosen:
        pokemon = dict(old.get(fid, {}))
        if fid in chaos_files:
            for mon, entry in month_sets(chaos_files[fid], month).items():
                if mon not in pokemon or entry["mo"] >= pokemon[mon]["mo"]:
                    pokemon[mon] = entry
        formats.append({"id": fid, "name": meta.format_name(fid, gen), "cap": cap, "pokemon": pokemon})
    return {"schema": SCHEMA, "month": max(doc["month"], month), "formats": formats}


def to_json(doc):
    return json.dumps(doc, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def chaos_files(month, chosen, listing):
    """This month's chaos stats for each chosen format it has (a format that didn't exist yet is skipped)."""
    return {fid: meta.fetch(f"{meta.STATS}/{month}/chaos/{fid}-1500.json")
            for fid, _ in chosen if f'href="{fid}-1500.json"' in listing}


def main(argv):
    month, listing = meta.newest_month()
    doc = load()
    if "--backfill" in argv:
        start = argv[argv.index("--backfill") + 1]
        months = [m for m in meta.posted_months() if start <= m <= month]
    elif doc["month"] >= month:
        print(f"sets.json already has {month}, nothing to do", file=sys.stderr)
        return
    else:
        months = [month]
    # Formats are picked from the newest month, as meta.json does; older months fill in whichever of them they have.
    gen, chosen = meta.chosen_formats(month, listing)
    for m in months:
        files = chaos_files(m, chosen, listing if m == month else meta.fetch(f"{meta.STATS}/{m}/chaos/", as_json=False))
        doc = merge(doc, gen, chosen, m, files)
        print(f"{m}: {', '.join(files) or 'no formats'}", file=sys.stderr)
    text = to_json(doc)
    with open("sets.json", "w") as f:
        f.write(text)
    sizes = ", ".join(f"{f['id']} {len(f['pokemon'])}" for f in doc["formats"])
    print(f"sets.json: {doc['month']}, {len(text) // 1024} KB, Pokemon per format: {sizes}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
