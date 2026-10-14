"""Idea A: load-balanced instance selection (signer keeps per-instance usage counts, grinds R until the
selected instance has load < R_cap). Security is then evaluated at a FIXED max load instead of
E_{r~Poisson}. Compare FORS parameter search (same cost model, tiers, margin) with the Poisson baseline."""
import math, sys
import os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import sweep_leansphincs_pruned as V

LEVEL, MARGIN = 127, 1.25
TARGET = {"ledger": 20_000, "standard": 2**21, "full": 2**23}
FILL = {"ledger": 0.8, "standard": 0.95, "full": 0.8}   # max fill of capacity R*2^b (bounds end-of-life grinding)

def fors_bits_fixed(r, a, k):
    """-log2 of cover probability with exactly r prior signatures on the instance."""
    if r == 0:
        return float('inf')
    p = -math.expm1(r * math.log1p(-2.0**-a))
    return -k * math.log2(p)

def cap(tier, b):
    lam = TARGET[tier] * MARGIN / 2**b
    R = max(1, math.ceil(lam / FILL[tier]))
    f = lam / R
    avg = (1 / f) * math.log(1 / (1 - f)) if f < 1 else float('inf')
    worst = 1 / (1 - f)
    return R, f, avg, worst

def tier_ok_bal(tier, h, b, a, k):
    R = cap(tier, b)[0]
    return (h - b) + fors_bits_fixed(R, a, k) >= LEVEL

WO = [x for x in V.wots_options(2**20) if x["lg_w"] == 2 and x["T"] == 128][0]

def costs(h, b, a, k, tier, balanced):
    rate, cache, _ = V.DEVICES[tier]
    digest = math.ceil((h + k * a) / 256) * V.MSG_BLOCK
    keygen = V.DERIVE + 2**b * (WO["leaf"] + V.NODE) + (h - b) * (V.DERIVE + V.NODE)
    grind = 2 ** (h - b) if b < h else 1
    if balanced:
        R, f, avg, worst = cap(tier, b)
        grind_avg, grind_worst = grind * avg, grind * worst
    else:
        grind_avg = grind_worst = (grind if b < h else 0)
    base = V.RND + digest + V.fors_sign(a, k) + WO["sign"] + V.tree_cost(b, cache // V.N, WO["leaf"])
    return dict(b=b, keygen_s=keygen / rate, sign_avg_s=(base + grind_avg) / rate, sign_worst_s=(base + grind_worst) / rate)

def search(balanced, ledger_cap_s, h_range=range(20, 29)):
    rows = []
    for h in h_range:
        for a in range(3, 17):
            for k in range(1, 90):
                verify = math.ceil((h + k * a) / 256) * V.MSG_BLOCK + k * a + V.comp(2 * k * V.N) + WO["verify"] + h
                if verify > 300:
                    break
                ok = {}
                for tier in ("full", "standard", "ledger"):
                    budget = V.DEVICES[tier][2]
                    cands = []
                    for b in range(1, h + 1):
                        c = costs(h, b, a, k, tier, balanced)
                        if c["keygen_s"] > budget:
                            continue
                        good = tier_ok_bal(tier, h, b, a, k) if balanced else V.tier_ok(TARGET[tier] * MARGIN, h, b, a, k)
                        if good:
                            cands.append(c)
                    if tier == "full":
                        cands = [c for c in cands if c["b"] == h]
                    if not cands:
                        break
                    ok[tier] = min(cands, key=lambda c: c["sign_worst_s"]) if tier == "ledger" else min(cands, key=lambda c: c["keygen_s"])
                if len(ok) < 3 or ok["ledger"]["sign_worst_s"] > ledger_cap_s:
                    continue
                size = 16 + k * (1 + a) * 16 + WO["size"] + h * 16
                rows.append(dict(h=h, a=a, k=k, verify=verify, size=size, **{f"{t}_{x}": ok[t][x] for t in ok for x in ok[t]}))
                break  # smallest k for this (h, a)
    rows.sort(key=lambda r: (r["verify"], r["size"]))
    return rows

if __name__ == "__main__":
    for cap_s in (2.2, 5.0):
        for balanced in (False, True):
            rows = search(balanced, cap_s)
            print(f"\n=== FORS, Ledger signing (worst) <= {cap_s} s, {'BALANCED loads' if balanced else 'Poisson (stateless)'} ===")
            for r in rows[:4]:
                print(f"  verify {r['verify']} size {r['size']} B  h={r['h']} k={r['k']} a={r['a']}  "
                      f"b_led={r['ledger_b']} led sign avg {r['ledger_sign_avg_s']:.2f}s worst {r['ledger_sign_worst_s']:.2f}s  b_std={r['standard_b']}")
    for t in ("ledger", "standard", "full"):
        b = {"ledger": 13, "standard": 20, "full": 24}[t]
        print(t, "cap R, fill, avg grind factor, worst factor:", tuple(round(x, 2) if isinstance(x, float) else x for x in cap(t, b)))
