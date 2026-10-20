#!/usr/bin/env python3
"""Spicy (WOTS-forest) versions of leanSphincs-s and -f at h = 26, Keccak-256 costs (sphincs-art keccak_model.forest),
cover-estimate lifetimes (sweep_leansphincs_forest). Tom's spicy vs vanilla: verify -25%, size -25%, signing ~same,
lifetime >= vanilla. Floors per variant are its vanilla's estimated lifetimes (Light, Standard, Full).

Usage: spicy_search.py {s,f} [--sign-slack 1.05] [--floor vanilla|min]. Prints the Pareto front (signature size vs
verification) of the forest shapes that keep the lifetimes and Ledger signing within the slack. The page uses
the knee of each front: s: F=5 th=5 m=2 s=3 c=6 w=6 D=6 tau=9 M=456 T=131; f: F=7 th=3 m=2 s=3 c=6 w=4 D=4
tau=7 M=108 T=126. Takes about 30-60 minutes per variant."""
import os, sys, json, math, argparse, functools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import keccak_model as K, sweep_leansphincs_forest as S, sweep_leansphincs_pruned as V
K.alpha = functools.lru_cache(maxsize=None)(K.alpha)
N, H = 16, 26
VAN = {"s": dict(verify=259, size=4164, sign=159007, life={13: 43715, 20: 3053279, 26: 108170220}),
       "f": dict(verify=290, size=4660, sign=38364,  life={13: 36206, 20: 2954691, 26: 123602647})}
ap = argparse.ArgumentParser(); ap.add_argument("variant"); ap.add_argument("--sign-slack", type=float, default=1.05)
ap.add_argument("--floor", choices=["vanilla", "min"], default="vanilla")
a = ap.parse_args(); van = VAN[a.variant]
floors = van["life"] if a.floor == "vanilla" else {13: 20000/0.87, 20: 2**21/0.94, 26: 1e8/0.96}
sign_cap = van["sign"] * a.sign_slack
args = argparse.Namespace(c_max=10, w_max=7, d_max=10, tau_max=10, grid_max=400_000, m_fracs=[0.7, 0.8, 0.84, 0.9])
shapes = list(S.wots_shapes(args)); print(len(shapes), "table shapes", flush=True)
rows = []
for i, (c, w, D, tau, M) in enumerate(shapes):
    f = S.f_tab(c, w, D, tau, M)
    for s in range(1, 6):
        g = S.g_sub(f, s)
        for th in range(1, 7):
            for m in (1, 2, 3):
                lq = S.log_q_tree(g, th, m)
                for F in range(1, 17):
                    bits = F * (th + m * (s + tau))
                    if H + bits > 512: break
                    size = N + F * (m * (c + s) + th) * N + 4 + 64 * N + H * N
                    if size > van["size"]: break
                    if not all(S.tier_bits(lq, F, floors[b], H, b) >= S.LEVEL for b in (13, 20, 26)): continue
                    best = None
                    for T in range(90, 150):
                        v, t = K.forest(H, F, th, m, s, c, w, D, bits, T)
                        if t["ledger"][2] > sign_cap: continue
                        if best is None or v < best[0]: best = (v, T, t)
                    if best:
                        v, T, t = best
                        rows.append(dict(F=F, th=th, m=m, s=s, c=c, w=w, D=D, tau=tau, M=M, T=T, bits=bits, verify=v, size=size,
                                         sign={k: round(x[2]) for k, x in t.items()}, ledger_s=round(t["ledger"][3], 1)))
                    break
    if i % 200 == 0: print(f"{i}/{len(shapes)} shapes, {len(rows)} feasible", flush=True)
print(len(rows), "feasible")
front, best = [], None
for r in sorted(rows, key=lambda r: (r["size"], r["verify"])):
    if best is None or r["verify"] < best: best = r["verify"]; front.append(r)
print(f"vanilla {a.variant}: verify {van['verify']} size {van['size']} ledger sign {van['sign']}")
for r in front: print(f"  verify {r['verify']} ({r['verify']/van['verify']-1:+.0%})  size {r['size']} ({r['size']/van['size']-1:+.0%})  sign {r['sign']} ({r['ledger_s']} s)  F={r['F']} th={r['th']} m={r['m']} s={r['s']} c={r['c']} w={r['w']} D={r['D']} tau={r['tau']} M={r['M']} T={r['T']}")
