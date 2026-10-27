// Exports Pokemon Showdown's current data (a checkout's data/*.ts) as one JSON file for build_bbr.py.
//   node bbr/export_showdown.mjs path/to/pokemon-showdown/data gen9.json
import fs from 'node:fs';
import path from 'node:path';
const [dir, out] = process.argv.slice(2);
const files = {pokedex: ['pokedex.ts', 'Pokedex'], formats: ['formats-data.ts', 'FormatsData'], moves: ['moves.ts', 'Moves'],
  abilities: ['abilities.ts', 'Abilities'], typechart: ['typechart.ts', 'TypeChart'], learnsets: ['learnsets.ts', 'Learnsets']};
const result = {};
for (const [key, [file, name]] of Object.entries(files)) {
  const mod = await import(path.resolve(dir, file));
  // Functions (move and ability effects) become `true`, so "has a basePowerCallback" survives.
  result[key] = JSON.parse(JSON.stringify(mod[name], (k, v) => typeof v === 'function' ? true : v));
}
fs.writeFileSync(out, JSON.stringify(result));
console.error(`wrote ${out}`);
