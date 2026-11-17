"""Made-up hand-written shiny files for build_catch.py's tests, in the shape of catch/shiny_rules/<game>.json,
catch/shiny_locks/<game>.json and catch/shiny_status.json. The numbers are real; the wording is short on purpose."""
import copy

RULES = {
    "red-blue": {"shiny": False, "verified": "datamine", "note": "Gen 1 has no shiny Pokemon"},
    "gold-silver": {
        "base": 8192,
        "methods": [
            {"id": "wild", "name": "Any encounter", "plain": "Every Pokemon has a tiny shiny chance.",
             "detail": "Shininess comes from the DVs.", "rolls": 1, "odds": 8192,
             "verified": "datamine", "note": "pokecrystal CheckShininess"},
            {"id": "shiny-parent", "name": "Breed with a shiny parent", "plain": "Eggs from a shiny parent are often shiny.",
             "detail": "The egg copies some DVs from one parent.", "one_in": 64,
             "verified": "datamine", "note": "pokecrystal daycare.asm"}],
        "best": "shiny-parent"},
    "heartgold-soulsilver": {
        "base": 8192,
        "methods": [
            {"id": "wild", "name": "Any encounter", "plain": "p", "detail": "d", "rolls": 1,
             "verified": "datamine", "note": "n"},
            {"id": "masuda", "name": "Masuda Method", "plain": "p", "detail": "d", "rolls": 5, "odds": 1638.8,
             "verified": "datamine", "note": "pokeheartgold get_egg.c"}],
        "best": "masuda"},
    "diamond-pearl": {
        "base": 8192,
        "methods": [
            {"id": "poke-radar", "name": "Poke Radar", "plain": "p", "detail": "d",
             "steps": [{"at": 10, "one_in": 6200}, {"at": 40, "one_in": 200}],
             "verified": "datamine", "note": "pokeplatinum pokeradar.c"}],
        "best": "poke-radar"},
    "x-y": {
        "base": 4096,
        "charm": {"extra": 2, "how": "Complete the National Pokedex.", "verified": "multiple", "note": "n"},
        "methods": [
            {"id": "wild", "name": "Any encounter", "plain": "p", "detail": "d", "rolls": 1, "charm_rolls": 3,
             "charm_odds": 1365.7, "verified": "multiple", "note": "n"},
            {"id": "poke-radar", "name": "Poke Radar", "plain": "p", "detail": "d", "one_in": 100, "approx": True,
             "verified": "single", "note": "formula disputed: PokeStats and Serebii differ"}],
        "best": "poke-radar"},
    "sword-shield": {
        "base": 4096,
        "charm": {"extra": 2, "how": "Complete the Galar Pokedex.", "verified": "multiple", "note": "n"},
        "methods": [
            {"id": "brilliant", "name": "Brilliant Pokemon", "plain": "p", "detail": "d",
             "steps": [{"at": 0, "rolls": 2, "charm_rolls": 4}, {"at": 500, "rolls": 7, "charm_rolls": 9,
                                                                  "odds": 585.6, "charm_odds": 455.6}],
             "verified": "multiple", "note": "n"},
            {"id": "dynamax-adventure", "name": "Dynamax Adventures", "plain": "p", "detail": "d",
             "one_in": 300, "charm_one_in": 100, "verified": "datamine", "note": "n"}],
        "best": "dynamax-adventure"},
}

LOCKS = {
    "gold-silver": {
        "_rules": [{"id": "trades", "plain": "In-game trades are never shiny.", "verified": "datamine", "note": "n"}],
        "gyarados": {"lock": "always", "encounter": "Red Gyarados, Lake of Rage", "verified": "datamine", "note": "n"}},
    "heartgold-soulsilver": {
        "pichu-spiky-eared": {"lock": "never", "encounter": "Ilex Forest", "needs": "An event Pichu",
                              "verified": "datamine", "note": "n"}},
    "sword-shield": {
        "articuno-galar": {"lock": "never", "encounter": "Roaming, Crown Tundra", "verified": "datamine", "note": "n"},
        "pikachu": {"lock": "partial", "encounter": "Gift (Gigantamax) locked; wild ones can be shiny",
                    "verified": "datamine", "note": "n"}},
}

STATUS = {
    "mew": {"status": "event", "how": "Events and Pokemon GO only.", "verified": "single", "note": "n"},
    "celebi": {"status": "home-reward", "how": "A made-up HOME reward.", "verified": "multiple", "note": "n"},
    "pikachu-cosplay": {"status": "never", "how": "Never released shiny.", "verified": "multiple", "note": "n"},
}

# Keys forms.json has that catch.json's pk doesn't.
FORM_KEYS = {"pikachu-cosplay", "pichu-spiky-eared", "articuno-galar"}

# The fake PokeAPI has no Gyarados: add it to the keys the files may name.
EXTRA_KEYS = {"gyarados"}


def shiny():
    return {"rules": copy.deepcopy(RULES), "locks": copy.deepcopy(LOCKS), "status": copy.deepcopy(STATUS)}
