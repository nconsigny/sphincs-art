"""Tom's Keccak-256 cost model (branch keccak, scripts/scheme.py): one Keccak-f permutation per 136-byte block,
(32 + l) // 136 + 1 per call; no FTS key hash, the WOTS+C encoding absorbs the FTS tops then the 4-byte counter."""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..')); sys.path.insert(0, HERE)
import sweep_leansphincs_pruned as V
N, RATE = 16, 136
comp = lambda l: (32 + l) // RATE + 1
DERIVE, STEP, NODE, MSG, RND = comp(32), comp(N), comp(2 * N), comp(32 + N), comp(64)
SPEED = {"ledger": 5.8e3, "standard": 128e6, "full": 512e6}
CACHE = {"ledger": 16 * 2**10, "standard": 2**20, "full": 16 * 2**20}
v, q = 64, 4
def merged(tops):
    fixed = 32 + tops
    return comp(tops + 4), fixed // RATE, (fixed % RATE + 4) // RATE + 1
def alpha(T): return V.n_sum(v, q, T) / q**v
def wots(T, tops):
    enc, fx, tr = merged(tops)
    return enc + (v * (q - 1) - T) * STEP + comp(v * N), fx + tr / alpha(T) + v // 2 * DERIVE + T * STEP
LEAF = v // 2 * DERIVE + v * (q - 1) * STEP + comp(v * N)
def tiers(h, fts_sign, wsign, digest):
    out = {}
    for name, b in (("ledger", 13), ("standard", 20), ("full", h)):
        keygen = DERIVE + 2**b * (LEAF + NODE) + (h - b) * (DERIVE + NODE)
        grind = 2 ** (h - b) * MSG if b < h else 0
        sign = RND + digest + grind + fts_sign + wsign + V.tree_cost(b, CACHE[name] // N, LEAF)
        out[name] = (keygen, keygen / SPEED[name], sign, sign / SPEED[name])
    return out
def fors(h, k, a, T):
    digest = math.ceil((h + k * a) / 256) * MSG
    wv, ws = wots(T, 2 * k * N)
    return digest + k * (STEP + (a - 1) * NODE) + wv + h * NODE, tiers(h, k * (2**a // 2 * DERIVE + 2**a * STEP + (2**a - 2) * NODE), ws, digest)
def forest(h, F, th, m, s, c, w, D, bits, T):
    lh = comp(c * N); wk = -(-c // 2) * DERIVE + c * (w - 1) * STEP + lh; leaf_hash = comp(2 * m * N)
    per_tree = m * (D * STEP + lh + (s - 1) * NODE) + leaf_hash + (th - 1) * NODE
    sign = F * (2**th * (m * (2**s * wk + (2**s - 2) * NODE) + leaf_hash) + (2**th - 2) * NODE)
    digest = math.ceil((h + bits) / 256) * MSG
    wv, ws = wots(T, 2 * F * N)
    return digest + F * per_tree + wv + h * NODE, tiers(h, sign, ws, digest)
if __name__ == "__main__":
    for name, (vv, t) in (("Tom FORS (check 354)", fors(26, 24, 10, 120)),
                          ("Tom forest (check 267)", forest(26, 8, 4, 2, 3, 6, 5, 5, 208, 123)),
                          ("leanSphincs-S FORS h=26 k=13 a=12 T=128", fors(26, 13, 12, 128)),
                          ("leanSphincs-S forest h=25 T=128", forest(25, 3, 4, 3, 5, 9, 3, 4, 147, 128))):
        print(f"{name}: verify {vv} permutations")
        for tier, (kg, kgs, sg, sgs) in t.items():
            print(f"   {tier:8s} keygen {kg:,} ({kgs:.3g} s)  sign {sg:,.0f} ({sgs*1e3:.4g} ms)")
    print("BLAKE2s weak CPU at 256M/s: FORS keygen 253,755,405 ->", 253755405/256e6, "s; sign 155,742 ->", 155742/256e6*1e3, "ms; forest sign 146,877 ->", 146877/256e6*1e3, "ms")
