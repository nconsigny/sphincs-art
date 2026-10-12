#!/usr/bin/env python3
"""
leanSphincs-style search (single XMSS layer, WOTS+C + FORS, hypertree pruning) for three device tiers
that share ONE parameter set and differ only in how much of the tree the signer builds:

    full      powerful CPU     whole tree of 2^h leaves       lifetime >= 2^23
    standard  weak CPU         pruned subtree of 2^b_std      lifetime >= 2^21
    ledger    Ledger Nano S+   pruned subtree of 2^b_led      lifetime >= 20,000

Objective: fewest verification compressions. Ties: smaller signature, faster Ledger signing.

Cost model copied from TomWambsgans/leanXMSS-leanSPHINCS-candidates scripts/scheme.py: BLAKE2s-style
compressions, every call hashes P (16 B) || address (16 B) || input, max(1, ceil(len / 64)) per call;
FORS trees have no root hash; one derivation yields two secrets; a pruned signer grinds R at one
compression per try. Security is the "cover" estimate of leanSPHINCS.pdf section 3:

    lifetime(b) = largest N with  2^127 * 2^(b - h) * E_{r ~ Poisson(N / 2^b)}[(1 - (1 - 2^-a)^r)^k] <= 1

Tom's Lean-proved lifetimes are 4-17% below this estimate (worse at small b), so by default each
tier must clear MARGIN * target under the estimate.
"""

import argparse
import math
from functools import lru_cache

import numpy as np
from scipy.special import gammaln

N = 16
PREFIX = 32
LEVEL = 127


def comp(input_bytes):
    return max(1, math.ceil((PREFIX + input_bytes) / 64))


DERIVE, STEP, NODE, ENC = comp(32), comp(N), comp(2 * N), comp(N + 4)
RND, MSG_BLOCK = comp(64), comp(32 + N)

DEVICES = {  # compressions per second, signer cache (bytes), keygen budget (s)
    "full": (1e9, 16 * 2**20, 16.0),
    "standard": (128e6, 2**20, 2.0),
    "ledger": (33e3, 16 * 2**10, 61.0),  # Tom's b=13 keygen is 1.98M = 60.1 s
}
TARGETS = {"full": 2**23, "standard": 2**21, "ledger": 20_000}


# ---------------------------------------------------------------- FORS cover bound
@lru_cache(maxsize=None)
def fors_bits(n_sigs, b, a, k):
    """-log2 E_{r~Poisson(n_sigs/2^b)}[(1-(1-2^-a)^r)^k]: forging at a random one of 2^b instances."""
    lam = n_sigs / 2**b
    if lam > 2 ** (a - 1):  # every leaf of every tree is half-covered: hopeless for k <= 64
        return 0.0
    hi = int(lam + 60 * math.sqrt(lam) + 400)
    r = np.arange(1, hi + 1, dtype=np.float64)
    log_pmf = -lam + r * math.log(lam) - gammaln(r + 1)
    log_cover = k * np.log(-np.expm1(r * math.log1p(-(2.0**-a))))
    t = log_pmf + log_cover
    m = t.max()
    return -(m + math.log(np.exp(t - m).sum())) / math.log(2)


def tier_ok(n_sigs, h, b, a, k):
    return (h - b) + fors_bits(n_sigs, b, a, k) >= LEVEL


def cover_lifetime(h, b, a, k):
    lo, hi = 1, 2 ** (b + a)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if tier_ok(mid, h, b, a, k) else (lo, mid)
    return lo


# ---------------------------------------------------------------- WOTS+C
def n_sum(v, q, s):
    poly = [1]
    for _ in range(v):
        new = [0] * (len(poly) + q - 1)
        for i, c in enumerate(poly):
            for d in range(q):
                new[i + d] += c
        poly = new
    return poly[s] if 0 <= s < len(poly) else 0


def wots_options(max_grind):
    """Per lg_w, the T values that are Pareto-optimal in (verify steps, expected counters)."""
    out = []
    for lg_w in (1, 2, 3, 4):
        v, q = -(-128 // lg_w), 2**lg_w
        top = v * (q - 1)
        pk = comp(v * N)
        leaf = -(-v // 2) * DERIVE + top * STEP + pk
        for T in range(top + 1):
            cnt = n_sum(v, q, T)
            if cnt == 0:
                continue
            tries = q**v / cnt
            if tries > max_grind or T < top // 2:
                continue
            out.append(dict(lg_w=lg_w, w=q, v=v, T=T, tries=tries,
                            verify=ENC + (top - T) * STEP + pk,
                            sign=ENC * tries + -(-v // 2) * DERIVE + T * STEP,
                            leaf=leaf, size=v * N + 4))
    return out


# ---------------------------------------------------------------- signer costs
def tree_cost(height, cache_nodes, leaf):
    """scheme.py: per-signature auth-path work given a node cache."""
    if 2 ** (height + 1) - 1 <= cache_nodes:
        return 0
    best = 2**height * leaf + (2**height - 1) * NODE
    for c in range(1, height + 1):
        below = 2**c * leaf + (2**c - 1) * NODE
        if 2 ** (height - c + 1) - 1 <= cache_nodes:
            best = min(best, below)
        if 2 ** (height - c) <= cache_nodes:
            best = min(best, below + (2 ** (height - c) - 1) * NODE)
    return best


def fors_sign(a, k):
    return k * (2**a // 2 * DERIVE + 2**a * STEP + (2**a - 2) * NODE) + comp(2 * k * N)


def tier_costs(h, b, a, k, wots, device):
    rate, cache, _ = DEVICES[device]
    leaf = wots["leaf"]
    digest = math.ceil((h + k * a) / 256) * MSG_BLOCK
    keygen = DERIVE + 2**b * (leaf + NODE) + (h - b) * (DERIVE + NODE)
    grind = 2 ** (h - b) if b < h else 0
    sign = RND + digest + grind + fors_sign(a, k) + wots["sign"] + tree_cost(b, cache // N, leaf)
    return dict(b=b, keygen=keygen, keygen_s=keygen / rate, sign=sign, sign_s=sign / rate, grind=grind)


def pick_b(h, a, k, wots, device, margin):
    """Smallest-keygen subtree for standard; fastest-signing subtree within the keygen budget for ledger."""
    target = TARGETS[device] * margin
    budget = DEVICES[device][2]
    cands = []
    for b in range(1, h + 1):
        if not tier_ok(target, h, b, a, k):
            continue
        c = tier_costs(h, b, a, k, wots, device)
        if c["keygen_s"] <= budget:
            cands.append(c)
    if not cands:
        return None
    key = (lambda c: c["sign"]) if device == "ledger" else (lambda c: c["keygen"])
    return min(cands, key=key)


def search(args):
    wopts = wots_options(args.max_wots_grind)
    if args.lg_w:
        wopts = [w for w in wopts if w["lg_w"] in args.lg_w]
    rows = []
    for h in range(args.h_min, args.h_max + 1):
        for a in range(3, 17):
            k_first = None
            for k in range(1, 65):
                # FORS only gets stronger with k; past the first feasible k, more trees only cost more
                # (a couple more are kept: a smaller pruned subtree can sometimes sign faster)
                if k_first is not None and k > k_first + 2:
                    break
                if not tier_ok(TARGETS["full"] * args.margin, h, h, a, k):
                    continue
                fors_v = k * (STEP + (a - 1) * NODE) + comp(2 * k * N)
                digest = math.ceil((h + k * a) / 256) * MSG_BLOCK
                for wo in wopts:
                    full = tier_costs(h, h, a, k, wo, "full")
                    if full["keygen_s"] > DEVICES["full"][2]:
                        continue
                    std = pick_b(h, a, k, wo, "standard", args.margin)
                    led = pick_b(h, a, k, wo, "ledger", args.margin)
                    if std is None or led is None:
                        continue
                    rows.append(dict(
                        h=h, a=a, k=k, **{f"w_{x}": wo[x] for x in ("lg_w", "w", "v", "T", "tries")},
                        verify=digest + fors_v + wo["verify"] + h * NODE,
                        size=N + k * (1 + a) * N + wo["size"] + h * N,
                        full=full, std=std, led=led))
                    if k_first is None:
                        k_first = k
    return rows


def pareto(rows, keys):
    rows = sorted(rows, key=lambda r: tuple(keys_of(r, keys)))
    front, best = [], None
    for r in rows:
        ks = keys_of(r, keys)
        if best is None or ks[1] < best:
            front.append(r)
            best = ks[1]
    return front


def keys_of(r, keys):
    return [eval(k, {}, {"r": r}) for k in keys]


def fmt(x):
    for dv, u in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if x >= dv * 0.9995:
            return f"{x / dv:.3g}{u}"
    return f"{x:.0f}"


def show(r, margin):
    h, a, k = r["h"], r["a"], r["k"]
    lifes = {t: cover_lifetime(h, r[t2]["b"], a, k) for t, t2 in (("full", "full"), ("standard", "std"), ("ledger", "led"))}
    print(f"h={h:2d} a={a:2d} k={k:2d}  WOTS+C w={r['w_w']} v={r['w_v']} T={r['w_T']} (~{r['w_tries']:.0f} counters)"
          f"  | verify {r['verify']} compr, sig {r['size']} B")
    for name, key in (("full", "full"), ("standard", "std"), ("ledger", "led")):
        c = r[key]
        print(f"    {name:8s} b={c['b']:2d}  lifetime {fmt(lifes[name]):>6} (target {fmt(TARGETS[name])}, "
              f"x{lifes[name] / TARGETS[name]:.2f})  keygen {fmt(c['keygen']):>6} = {c['keygen_s']:.3g} s"
              f"  sign {fmt(c['sign']):>5} = {c['sign_s'] * 1e3:.3g} ms (grind {fmt(c['grind'])})")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--margin", type=float, default=1.25, help="required cover lifetime / target")
    ap.add_argument("--h-min", type=int, default=10)
    ap.add_argument("--h-max", type=int, default=26)
    ap.add_argument("--lg-w", type=int, nargs="*", help="restrict WOTS+C chain length to 2^lg_w")
    ap.add_argument("--max-wots-grind", type=float, default=2**14, help="max expected WOTS+C counters")
    ap.add_argument("--ledger-sign-s", type=float, nargs="*", default=[1.0, 2.2, 3.0, 5.0])
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--check-tom", action="store_true", help="reproduce Tom's h=26 a=10 k=24 numbers")
    args = ap.parse_args()

    if args.check_tom:
        for b, want in ((26, 1.20e9), (20, 2.37e7), (13, 2.42e5), (8, 9.0e3)):
            print(f"b={b}: cover lifetime {cover_lifetime(26, b, 10, 24):.4g} (paper {want:.3g})")
        wo = [w for w in wots_options(2**20) if w["lg_w"] == 2 and w["T"] == 120][0]
        digest = math.ceil((26 + 240) / 256) * MSG_BLOCK
        v = digest + 24 * (STEP + 9 * NODE) + comp(2 * 24 * N) + wo["verify"] + 26 * NODE
        print(f"verify {v} (paper 373); WOTS leaf {wo['leaf'] + NODE} (paper ~242); "
              f"ledger b=13: {tier_costs(26, 13, 10, 24, wo, 'ledger')}")
        return

    rows = search(args)
    print(f"{len(rows)} feasible (h, a, k, WOTS+C) sets; margin x{args.margin}, {LEVEL}-bit cover estimate\n")
    for cap in args.ledger_sign_s:
        ok = [r for r in rows if r["led"]["sign_s"] <= cap]
        ok.sort(key=lambda r: (r["verify"], r["size"], r["led"]["sign"]))
        print(f"=== Ledger signing <= {cap:g} s: best {min(args.top, len(ok))} by verification ===")
        for r in ok[: args.top]:
            show(r, args.margin)
        print()

    print("=== Pareto front: verification compressions vs Ledger signing time ===")
    for r in pareto(rows, ['r["verify"]', 'r["led"]["sign"]']):
        print(f"  verify {r['verify']:4d}  ledger sign {r['led']['sign_s']:5.2f} s  sig {r['size']:5d} B  "
              f"h={r['h']} a={r['a']} k={r['k']} w={r['w_w']} T={r['w_T']} b_led={r['led']['b']} b_std={r['std']['b']}")
    print("\n=== Pareto front: verification compressions vs signature size ===")
    for r in pareto(rows, ['r["verify"]', 'r["size"]']):
        print(f"  verify {r['verify']:4d}  sig {r['size']:5d} B  ledger sign {r['led']['sign_s']:5.2f} s  "
              f"h={r['h']} a={r['a']} k={r['k']} w={r['w_w']} T={r['w_T']} b_led={r['led']['b']} b_std={r['std']['b']}")


if __name__ == "__main__":
    main()
