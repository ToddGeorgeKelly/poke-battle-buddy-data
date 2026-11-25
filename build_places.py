"""Builds places.json: each region's places (towns, routes, caves, buildings), which connects to which, a rough grid
spot for each, and which catch.json place names belong to which place. The app draws its own schematic region map
from it and lights the places a Pokemon is found.

    python3 build_places.py   # reads places/<region>.json, checks it, writes places.json

Hand-written, one file per region (places/kanto.json). Facts only: places, connections and grid spots come from
written route descriptions ("Route 1 runs north from Pallet Town to Viridian City") and the app's own mockup, never
from a map image or a game's data. Each place links to its Bulbapedia page; nothing from Bulbapedia is bundled.
The `skip` list (catch.json names that belong to no place on this map) isn't shipped.
"""
import collections, datetime, json, os, sys
import build_forms as bf

SCHEMA = 1
KINDS = {"town", "route", "sea", "cave", "building", "area"}
ROUTES = {"route", "sea"}
WIKI = "https://bulbapedia.bulbagarden.net/wiki/"
SHIPPED = ("name", "grid", "games", "places", "links", "alias")


def skipped(name, skip):
    """Whether a catch.json name is on the skip list: the name itself, or one of its floors or areas ("Lost Cave
    (room 1)")."""
    return any(name == s or name.startswith(s + " (") for s in skip)


def check(rid, region):
    """Everything wrong with one region's table, as messages (empty when it's good)."""
    out = []
    places = region["places"]
    cols, rows = region["grid"]
    spots = {}
    for i, p in places.items():
        if p.get("k") not in KINDS:
            out.append(f"{rid}: {i} has unknown kind {p.get('k')}")
        if not p.get("n"):
            out.append(f"{rid}: {i} has no name")
        if not str(p.get("url", "")).startswith(WIKI):
            out.append(f"{rid}: {i} url isn't a Bulbapedia wiki page: {p.get('url')}")
        if "in" in p:
            if p["in"] not in places:
                out.append(f"{rid}: {i} is in unknown place {p['in']}")
            if "at" in p:
                out.append(f"{rid}: {i} is inside {p['in']}, so it has no spot of its own")
            continue
        if "at" not in p:
            out.append(f"{rid}: {i} has no spot")
            continue
        x, y = p["at"]
        if not (0 <= x < cols and 0 <= y < rows):
            out.append(f"{rid}: {i} at {p['at']} is outside the grid {region['grid']}")
        if tuple(p["at"]) in spots:
            out.append(f"{rid}: {i} and {spots[tuple(p['at'])]} share the spot {p['at']}")
        spots[tuple(p["at"])] = i
    seen = set()
    graph = collections.defaultdict(set)
    for a, b, r in region["links"]:
        for end in (a, b):
            if end not in places:
                out.append(f"{rid}: link {a}-{b} goes to unknown place {end}")
            elif "in" in places[end]:
                out.append(f"{rid}: link {a}-{b} goes to {end}, which is inside {places[end]['in']}")
        if r is not None and places.get(r, {}).get("k") not in ROUTES:
            out.append(f"{rid}: link {a}-{b} is labelled {r}, which isn't a route")
        if a == b:
            out.append(f"{rid}: {a} links to itself")
        if frozenset((a, b)) in seen:
            out.append(f"{rid}: {a}-{b} is linked twice")
        seen.add(frozenset((a, b)))
        graph[a].add(b)
        graph[b].add(a)
    start = next(iter(places))
    reached, todo = {start}, [start]
    while todo:
        for n in graph[todo.pop()] - reached:
            reached.add(n)
            todo.append(n)
    for i, p in places.items():
        if "in" not in p and i not in reached:
            out.append(f"{rid}: can't reach {i} from {start}")
    for name, i in region["alias"].items():
        if i not in places:
            out.append(f"{rid}: alias {name!r} points at unknown place {i}")
        if skipped(name, region.get("skip", {})):
            out.append(f"{rid}: {name!r} is both aliased and skipped")
    return out


def build(regions, built):
    """places.json from the region tables (fails on any error)."""
    problems = [e for rid, r in regions.items() for e in check(rid, r)]
    if problems:
        raise SystemExit("\n".join(problems))
    return {"schema": SCHEMA, "built": built,
            "regions": {rid: {k: r[k] for k in SHIPPED} for rid, r in regions.items()}}


def load(root=None):
    """The hand-written region tables under places/: {region id: table}."""
    root = root or os.path.join(os.path.dirname(os.path.abspath(__file__)), "places")
    out = {}
    for f in sorted(os.listdir(root)):
        if f.endswith(".json"):
            with open(os.path.join(root, f)) as fh:
                out[f[:-5]] = json.load(fh)
    return out


def write(doc, path="places.json"):
    """Writes places.json unless only the built time would change. Returns whether it wrote."""
    return bf.write(doc, path)


def main(argv):
    doc = build(load(), built=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    wrote = write(doc)
    for rid, r in doc["regions"].items():
        print(f"places.json: {'written' if wrote else 'unchanged'}; {rid}: {len(r['places'])} places, "
              f"{len(r['links'])} links, {len(r['alias'])} aliases", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
