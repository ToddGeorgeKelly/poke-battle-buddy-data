// Exports Pokemon Showdown's current data (a checkout's data/*.ts and data/mods/gen4-8/*.ts) as one JSON file per
// generation, gen4.json ... gen9.json, for build_bbr.py.
//   node bbr/export_showdown.mjs path/to/pokemon-showdown/data gen
// Same as the research's load.mjs: Gen 9 is data/ itself; each older gen applies its mod over the next newer gen
// (entries with `inherit` are merged into the newer entry, others replace it; a mod's formats-data replaces the tiers
// outright, so a Pokemon without an entry there isn't in that gen).
import fs from 'node:fs';
import path from 'node:path';
const [dir, out] = process.argv.slice(2);
const files = {pokedex: ['pokedex.ts', 'Pokedex'], formats: ['formats-data.ts', 'FormatsData'], moves: ['moves.ts', 'Moves'],
  abilities: ['abilities.ts', 'Abilities'], typechart: ['typechart.ts', 'TypeChart'], learnsets: ['learnsets.ts', 'Learnsets']};

async function load(file, name) {
  const p = path.resolve(dir, file);
  return fs.existsSync(p) ? (await import(p))[name] : null;
}

function merge(parent, mod) {
  const result = {...parent};
  for (const [k, v] of Object.entries(mod || {})) {
    if (v && v.inherit) { result[k] = {...(parent[k] || {}), ...v}; delete result[k].inherit; }
    else result[k] = v;
  }
  return result;
}

// Functions (move and ability effects) become `true`, so "has a basePowerCallback" survives.
const strip = (t) => JSON.parse(JSON.stringify(t, (k, v) => typeof v === 'function' ? true : v));

function write(g, cur) {
  fs.writeFileSync(path.join(out, `gen${g}.json`), JSON.stringify(Object.fromEntries(
    Object.entries(cur).map(([k, v]) => [k, strip(v)]))));
}

fs.mkdirSync(out, {recursive: true});
let cur = {};
for (const [key, [file, name]] of Object.entries(files)) cur[key] = await load(file, name);
write(9, cur);
for (let g = 8; g >= 4; g--) {
  const next = {};
  for (const [key, [file, name]] of Object.entries(files)) {
    const mod = await load(`mods/gen${g}/${file}`, name);
    next[key] = key === 'formats' ? (mod || cur[key]) : merge(cur[key], mod);
  }
  cur = next;
  write(g, cur);
}
console.error(`wrote ${out}/gen4.json ... gen9.json`);
