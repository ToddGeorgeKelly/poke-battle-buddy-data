"""Slow, opt-in (pytest --runslow): our hand-written shiny locks against PKHeX's encounter tables.

PKHeX (GPL-3, https://github.com/kwsch/PKHeX) is only a check here. Its source is downloaded at a pinned commit into a
fresh temp folder as untrusted data, read as plain text (never run or imported), and never shipped or committed.
The comparison is per game and per species: which species PKHeX's gift / static tables mark `Shiny.Never` (or leave
at a template's Never default) or `Shiny.Always`, against our `never` / `partial` and `always` locks. In-game trades
are left out (our files cover them with a `trades` rule), except trades marked Always. Differences we accept are in
ACCEPTED with the reason; anything else fails the test with a report.
"""
import collections, re
import pytest
import build_catch as bc
import build_forms as bf

PKHEX = "6c9583883c7551ac74a4b74180cead249d4277b8"   # kwsch/PKHeX master, 2026-11-16
DATA = "PKHeX.Core/Legality/Encounters/Data"

# PKHeX's encounter files and the app games each covers.
FILES = {
    "Gen2/Encounters2.cs": ["gold-silver", "crystal"],
    "Gen3/Encounters3RSE.cs": ["ruby-sapphire", "emerald"],
    "Gen3/Encounters3FRLG.cs": ["firered-leafgreen"],
    "Gen4/Encounters4DPPt.cs": ["diamond-pearl", "platinum"],
    "Gen4/Encounters4HGSS.cs": ["heartgold-soulsilver"],
    "Gen5/Encounters5BW.cs": ["black-white"],
    "Gen5/Encounters5B2W2.cs": ["black-2-white-2"],
    "Gen6/Encounters6XY.cs": ["x-y"],
    "Gen6/Encounters6AO.cs": ["omega-ruby-alpha-sapphire"],
    "Gen7/Encounters7SM.cs": ["sun-moon"],
    "Gen7/Encounters7USUM.cs": ["ultra-sun-ultra-moon"],
    "Gen7/Encounters7GG.cs": ["lets-go-pikachu-lets-go-eevee"],
    "Gen8/Encounters8.cs": ["sword-shield"],
    "Gen8/Encounters8b.cs": ["brilliant-diamond-shining-pearl"],
    "Gen8/Encounters8a.cs": ["legends-arceus"],
    "Gen9/Encounters9.cs": ["scarlet-violet"],
    "Gen9/Encounters9a.cs": ["legends-za"],
}

# Templates whose Shiny field defaults to Never (EncounterStatic8a: "Everything is shiny locked anyway").
DEFAULT_NEVER = {"EncounterStatic8a", "EncounterStatic9a", "EncounterGift9a", "EncounterTrade9", "EncounterTrade9a"}

# Accepted differences: (PKHeX file, direction, species) -> why. "pkhex" = PKHeX locks it and we don't; "ours" = we
# lock it and PKHeX's text doesn't; "always-pkhex" / "always-ours" the same for forced shinies.
SWSH_ALOLA = "PKHeX lists it as a locked Sword / Shield gift, but no in-game source was found; left out (user " \
             "decision 2026-11-17)"
ODD_EGG = "Crystal's Odd Egg: our files give it as the odd-egg method (14% shiny), not as per-baby locks"
ACCEPTED = {
    **{("Gen8/Encounters8.cs", "pkhex", s): SWSH_ALOLA for s in
       ("rowlet", "litten", "popplio", "raichu", "sandshrew", "vulpix", "meowth", "exeggutor", "marowak", "diglett")},
    **{("Gen2/Encounters2.cs", d, s): ODD_EGG for d in ("pkhex", "always-pkhex") for s in
       ("pichu", "cleffa", "igglybuff", "tyrogue", "smoochum", "elekid", "magby")},
    **{("Gen4/Encounters4HGSS.cs", "ours", s): "a gift with a fixed PID (research: datamine); PKHeX stores the PID, "
       "not a Shiny flag" for s in ("spearow", "shuckle")},
    ("Gen8/Encounters8.cs", "ours", "urshifu"): "evolved from the locked Kubfu; PKHeX has no Urshifu encounter",
    **{("Gen9/Encounters9a.cs", "ours", s): "a wild-slot or scripted lock (Anubis via Dexerto); PKHeX's wild data is "
       "binary, so it isn't in the text" for s in ("mareep", "electrike", "fletchling")},
}

DECL = re.compile(r"static readonly (\w+)(\[\])? (\w+)\s*=", re.M)
ENTRY = re.compile(r"(?:new\s*\(((?:[^()]|\([^()]*\))*)\)|(\w+)\s+with)\s*(\{(?:[^{}]|\{[^{}]*\})*\})?", re.S)


def strip_comments(text):
    return re.sub(r"//[^\n]*", "", text)


def field(body, name):
    m = re.search(rf"\b{name}\s*=\s*(?:Shiny\.)?(\w+)", body or "")
    return m.group(1) if m else None


def parse(text):
    """[(kind, species, shiny)] for every gift / static / trade entry in one PKHeX encounter file. shiny is
    "Never", "Always", "Random"... or None (PKHeX's default for that template)."""
    text = strip_comments(text)
    decls = list(DECL.finditer(text))
    templates, out = {}, []
    for i, d in enumerate(decls):
        kind, is_array, name = d.groups()
        body = text[d.end():decls[i + 1].start() if i + 1 < len(decls) else len(text)]
        if not re.search(r"Static|Gift|Trade", kind):
            continue
        default = "Never" if kind in DEFAULT_NEVER else None
        if not is_array:
            m = ENTRY.search(body)
            if m:
                templates[name] = (species_of(m, kind), field(m.group(3), "Shiny") or default)
            continue
        if not body.lstrip().startswith("["):
            continue  # a table read from a binary resource
        for m in ENTRY.finditer(body[:body.find("];") + 1] if "];" in body else body):
            args, base, fields = m.groups()
            if base:
                if base not in templates:
                    continue
                species, shiny = templates[base]
                species = int(field(fields, "Species") or species or 0)
                out.append((kind, species, field(fields, "Shiny") or shiny))
            else:
                species = species_of(m, kind)
                if species:
                    out.append((kind, species, field(fields, "Shiny") or default))
    return out


def species_of(m, kind):
    args, _, fields = m.groups()
    s = field(fields, "Species")
    if s:
        return int(s)
    ints = [int(a) for a in re.findall(r"(?<![\w.])(\d+)(?![\w.])", args or "")]
    if "Trade" in kind:
        return ints[1] if len(ints) > 1 else None  # new(TradeNames, <name index>, <version>, species, level)
    return ints[0] if ints else None


def pkhex_sets(entries):
    never, always = set(), set()
    for kind, species, shiny in entries:
        if shiny == "Always":
            always.add(species)
        elif shiny == "Never" and "Trade" not in kind:
            never.add(species)
    return never, always


def test_parse_reads_species_and_shiny_from_the_entry_styles_pkhex_uses():
    text = """
    private static readonly EncounterStatic6 BaseCosplay = new(ORAS) { Species = 025, Form = 6, Shiny = Shiny.Never };
    internal static readonly EncounterStatic6[] Encounter =
    [
        new(130, 30, GSC) { Location = 038, Shiny = Shiny.Always, IVs = new(0, 14, 10, 10, 10, 10) }, // Gyarados
        new(HGSS)
        {
            Species = 172,
            Shiny = Shiny.Never,
        },
        BaseCosplay with {Form = 1, Moves = new(098, 486)},
      //new() { Species = 896, Shiny = Never }, // commented out
        new(SV) { Species = 0906, Shiny = Never, Level = 05 },
    ];
    internal static readonly EncounterStatic8a[] StaticLA =
    [
        new(077,000,15    ) { Location = 014, Shiny = Always}, // Ponyta*
        new(483,000,65) { Location = 1 },
    ];
    internal static readonly EncounterTrade9[] TradeGift_SV =
    [
        new(TradeNames, 26, SV, 0522, 20) { ID32 = 1, Shiny = Always },
        new(TradeNames, 27, SV, 0100, 20) { ID32 = 2 },
    ];
    internal static readonly EncounterArea9[] Slots = EncounterArea9.GetAreas(Get("wild_paldea", "sv"u8), SV);
    """
    got = parse(text)
    assert ("EncounterStatic6", 130, "Always") in got and ("EncounterStatic6", 172, "Never") in got
    assert ("EncounterStatic6", 25, "Never") in got and ("EncounterStatic6", 906, "Never") in got
    assert not any(s == 896 for _, s, _ in got)
    assert ("EncounterStatic8a", 77, "Always") in got and ("EncounterStatic8a", 483, "Never") in got
    assert ("EncounterTrade9", 522, "Always") in got and ("EncounterTrade9", 100, "Never") in got
    assert pkhex_sets(got) == ({172, 25, 906, 483}, {130, 77, 522})


def our_sets(shiny, games, species_id):
    never, always = set(), set()
    for game in games:
        for key, e in shiny["locks"].get(game, {}).items():
            if key == "_rules":
                continue
            (always if e["lock"] == "always" else never if e["lock"] in ("never", "partial") else set()).add(
                species_id[key])
    return never, always


def shiny_keys():
    return [[k for k in entries if k != "_rules"] for entries in bc.load_shiny()["locks"].values()]


@pytest.mark.slow
def test_our_shiny_locks_match_pkhex(tmp_path_factory):
    folder = tmp_path_factory.mktemp("pkhex")  # a new, empty folder for the untrusted download
    shiny = bc.load_shiny()
    rows = bf.rows(bf.raw("PokeAPI/pokeapi", bf.POKEAPI, "data/v2/csv/pokemon.csv"))
    species_rows = bf.rows(bf.raw("PokeAPI/pokeapi", bf.POKEAPI, "data/v2/csv/pokemon_species.csv"))
    name = {int(r["id"]): r["identifier"] for r in species_rows}
    of = {r["identifier"]: name[int(r["species_id"])] for r in rows}  # Pokemon name -> species name
    number = {v: k for k, v in name.items()}
    species_id = collections.defaultdict(lambda: None)
    species_id.update({k: number[bc.species_of(k, of)] for g in shiny_keys() for k in g})
    report, unexpected = [], []
    for path, games in FILES.items():
        target = folder / path.replace("/", "_")
        target.write_bytes(bf.raw("kwsch/PKHeX", PKHEX, f"{DATA}/{path}").encode())
        theirs_never, theirs_always = pkhex_sets(parse(target.read_text(encoding="utf-8", errors="replace")))
        ours_never, ours_always = our_sets(shiny, games, species_id)
        diffs = [("pkhex", theirs_never - ours_never), ("ours", ours_never - theirs_never),
                 ("always-pkhex", theirs_always - ours_always), ("always-ours", ours_always - theirs_always)]
        for direction, ids in diffs:
            for s in sorted(ids):
                key = (path, direction, name[s])
                reason = ACCEPTED.get(key)
                report.append(f"{path} {direction} {name[s]}: {reason or 'NOT ACCEPTED'}")
                if not reason:
                    unexpected.append(key)
    print("\n".join(report))
    stale = sorted(set(ACCEPTED) - {(p, d, n) for p, d, n in
                                    (tuple(r.split(": ")[0].split(" ")) for r in report)})
    assert not unexpected and not stale, f"unexpected: {unexpected}; accepted but no longer different: {stale}"
