"""Threshold keygen cost per route, for a threshold key that must last L signatures.
Routes: (T0) Tom's MPC keygen, stateless (Poisson); (T1) + balanced loads; (T2) + secret-free WOTS+C layer;
(T4) MPC-free multi-term FORS leaves (2-of-3 CNF, one subtree; t-of-n as C(n,t) t-of-t committee subtrees)."""
import math, sys
import os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import sweep_leansphincs_pruned as V
import balanced as B
LEVEL, MARGIN, FILL = 127, 1.25, 0.95
MEAS = {3: (1699, 5064), 5: (2039, 6078), 7: (2186, 6514)}   # Tom: bytes/operator per MPC FORS leaf, per 3-step WOTS chain
TN = {3: (2, 3), 5: (3, 5), 7: (4, 7)}

def life_poisson(h, b, a, k):
    return V.cover_lifetime(h, b, a, k) / MARGIN

def life_bal(h, b, a, k, slack_loss=0.0):
    R = 0
    while (h - b - slack_loss) + B.fors_bits_fixed(R + 1, a, k) >= LEVEL:
        R += 1
        if R > 10**6: break
    return FILL * R * 2**b / MARGIN

def min_b(life_fn, L, h):
    for b in range(0, h + 1):
        if life_fn(b) >= L:
            return b
    return None

def report(name, h, k, a, L=100_000):
    leaves = k * 2**a
    print(f"\n### {name}: h={h} k={k} a={a}  ({leaves:,} FORS leaves per instance)  -- threshold key for L={L:,} signatures")
    rows = []
    for label, fn, wots in (("T0 MPC, stateless", lambda b: life_poisson(h, b, a, k), True),
                            ("T1 MPC, balanced loads", lambda b: life_bal(h, b, a, k), True),
                            ("T2 MPC, balanced + secret-free WOTS+C", lambda b: life_bal(h, b, a, k), False)):
        b = min_b(fn, L, h)
        tr = {n: 2**b * (leaves * MEAS[n][0] + (64 * MEAS[n][1] if wots else 0)) for n in (3, 5, 7)}
        print(f"  {label:42s} b={b:2d} (life {fn(b):>9,.0f})  traffic/operator: 2-of-3 {tr[3]/1e9:6.1f} GB  3-of-5 {tr[5]/1e9:6.1f} GB  4-of-7 {tr[7]/1e9:6.1f} GB"
              f"  | {tr[3]/L/1e6:5.2f} MB/sig (2-of-3)")
    # T4: MPC-free. 2-of-3 CNF: one subtree; party 1 sends one 32-byte chaining value per leaf to the 2 others.
    b = min_b(lambda b: life_bal(h, b, a, k), L, h)
    bw = 2**b * leaves * 32 * 2
    print(f"  {'T4 MPC-free, 2-of-3 CNF (3 terms)':42s} b={b:2d}  bandwidth (sender) {bw/1e9:6.1f} GB, local hashing {2**b*leaves*2/1e9:.2f}G compr;"
          f"  verifier +{k} compr, signature +{32*k} B")
    for n in (3, 5, 7):
        t, _ = TN[n]
        com = math.comb(n, t)
        loss = math.log2(com)
        b = min_b(lambda b: life_bal(h, b, a, k, slack_loss=loss), L, h - math.ceil(loss))
        per_member_committees = math.comb(n - 1, t - 1)
        bw = per_member_committees * 2**b * leaves * 32   # each member forwards one chaining value per leaf per committee
        print(f"  {'T4 MPC-free, '+str(t)+'-of-'+str(n)+' as '+str(com)+' committees':42s} b={b:2d}  bandwidth/member {bw/1e9:6.1f} GB;"
              f"  verifier +{(t-1)*k} compr, signature +{16*(t-1)*k} B")

if __name__ == "__main__":
    report("Tom leanSphincs (FORS)", 26, 24, 10)
    report("leanSphincs-23 FORS live (5 s)", 25, 13, 12)
    report("leanSphincs-23 FORS balanced (2.2 s)", 23, 15, 10)
    report("leanSphincs-23 FORS balanced (5 s)", 23, 12, 12)
