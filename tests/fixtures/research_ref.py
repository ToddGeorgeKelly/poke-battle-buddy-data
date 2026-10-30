# How the research_gen<g>_ratings.json fixtures were made: the research's own Gen 9 reference script (research_ref.py)
# for any gen, the final model's ratings over that gen's research field. Run with the research working files in /tmp/bbr:
#   python3 tests/fixtures/research_ref.py /tmp/bbr tests/fixtures 4 5 6 7 8 9
import sys, pickle, json, os, numpy as np
sys.path.insert(0, sys.argv[1])
from baselines import bsr, app_effect
from features import utility_features
from addfeat import extra_features
from mech import mech_features
fw = pickle.load(open('/tmp/bbr/final_w.pkl', 'rb'))
print(fw)
for g in map(int, sys.argv[3:]):
    D = pickle.load(open('/tmp/bbr/duels_%s.pkl' % ('4_5_6' if g <= 6 else '7_8_9'), 'rb'))[g]
    mons, W = D['mons'], D['W']; n = len(mons)
    p = np.clip((W.sum(1) - .5) / (n - 1), 1e-3, 1 - 1e-3)
    f = dict(duel=np.log(p / (1 - p)))
    f.update(utility_features(g, mons)); f.update(extra_features(g, mons)); f.update(mech_features(g, mons))
    f['app_core'] = bsr(mons, T=2.5, effect=app_effect)
    zs = lambda v: (v - v.mean()) / v.std() if v.std() > 0 else v * 0
    s = np.column_stack([zs(f[k]) for k in fw['SEL']]) @ fw['w']
    r = (s - s.mean()) / s.std() * 120 + 420
    json.dump({m['id']: round(float(v), 2) for m, v in zip(mons, r)},
              open(os.path.join(sys.argv[2], f'research_gen{g}_ratings.json'), 'w'), indent=0, sort_keys=True)
    print(g, n, {m['name']: round(float(v)) for m, v in zip(mons, r) if m['id'] in ('garchomp', 'tyranitar', 'scizor', 'blissey')})
