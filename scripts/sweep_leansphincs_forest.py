#!/usr/bin/env python3
"""
leanSphincs-23, spicy: replace FORS by a two-level WOTS forest (leanSPHINCS.pdf section 3) and search
the forest shape for the fewest verification compressions, keeping everything else of leanSphincs-23
(one XMSS layer, WOTS+C with 64 chains of length 4 and target sum 128, the same keygen) and its tiers:

    full      powerful CPU     whole tree of 2^h leaves       lifetime >= 2^23
    standard  weak CPU         pruned subtree of 2^b_std      lifetime >= 2^21
    ledger    Ledger Nano S+   pruned subtree of 2^b_led      lifetime >= 20,000

Forest shape, generalising Tom's (F=8, th=4, m=2, s=3, WOTS 6 chains of length 5, digit sum 5,
256-entry table of 214 codewords):

    F trees of height th; each leaf hashes the top nodes of m subtrees of height s over WOTS keys;
    a WOTS key has c chains of length w and signs a codeword d in {0..w-1}^c with sum(d) = D, read from
    a table of 2^tau entries: the codewords sorted by decreasing sum(d_i^2) then lexicographically,
    entry t is codeword number t mod M. No tree or subtree has a root hash.

Security is the cover estimate of section 3: with f_t the probability that t random table entries
cover a random entry (componentwise max),

    cover(r) = ( sum_u Bin(r, 2^-th)(u) [ sum_t Bin(u, 2^-s)(t) f_t ]^m )^F
    lifetime(b) = largest N with 2^127 * 2^(b - h) * E_{r ~ Poisson(N / 2^b)}[cover(r)] <= 1

Costs follow Tom's scripts/scheme.py (64-byte compressions, 32-byte prefix on every call).
"""

import argparse
import itertools
import math
from functools import lru_cache

import numpy as np
from scipy.special import gammaln
from scipy.stats import binom

import sweep_leansphincs_pruned as V

N, LEVEL = V.N, V.LEVEL
comp, DERIVE, STEP, NODE = V.comp, V.DERIVE, V.STEP, V.NODE
R_MAX = 96          # Poisson loads per instance considered (lambda <= ~4 in every tier)
T_MAX = 64          # f_t computed up to here, f_t := 1 beyond (conservative)
WOTSC_T = 128       # leanSphincs-23's WOTS+C


# ---------------------------------------------------------------- codeword tables
@lru_cache(maxsize=None)
def codewords(c, w, D):
    words = [x for x in itertools.product(range(w), repeat=c) if sum(x) == D]
    words.sort(key=lambda x: (-sum(d * d for d in x), x))
    return tuple(words)


@lru_cache(maxsize=None)
def f_tab(c, w, D, tau, M):
    """f[t] = P(a uniform table entry is covered by the componentwise max of t uniform entries)."""
    words = codewords(c, w, D)
    E = 2**tau
    K = np.zeros((w,) * c)
    base, extra = divmod(E, M)
    for i, x in enumerate(words[:M]):
        K[x] += base + (1 if i < extra else 0)
    for ax in range(c):                         # K(m) = #entries <= m
        K = np.cumsum(K, axis=ax)
    DK = K.copy()                               # Möbius difference towards larger m on every axis
    for ax in range(c):
        shifted = np.zeros_like(DK)
        sl_dst = [slice(None)] * c
        sl_src = [slice(None)] * c
        sl_dst[ax], sl_src[ax] = slice(0, w - 1), slice(1, w)
        shifted[tuple(sl_dst)] = DK[tuple(sl_src)]
        DK = DK - shifted
    P, W = (K / E).ravel(), (DK / E).ravel()
    keep = W != 0
    P, W = P[keep], W[keep]
    out = np.empty(T_MAX + 1)
    pw = np.ones_like(P)
    for t in range(T_MAX + 1):
        out[t] = float(np.dot(pw, W))
        pw = pw * P
    return np.clip(out, 0.0, 1.0)


# ---------------------------------------------------------------- per-tree cover
_U = np.arange(R_MAX + 1)
_BIN = {}


def bin_matrix(p):
    """B[n, k] = Bin(n, p)(k) for n, k <= R_MAX."""
    if p not in _BIN:
        _BIN[p] = binom.pmf(_U[None, :], _U[:, None], p)
    return _BIN[p]


def g_sub(f, s):
    """g[u] = P(one subtree covered | u prior signatures at its leaf)."""
    ft = np.ones(R_MAX + 1)
    ft[: T_MAX + 1] = f
    return bin_matrix(2.0**-s) @ ft


def log_q_tree(g, th, m):
    """ln P(one tree covered | r prior signatures at the instance), r = 0..R_MAX."""
    q = bin_matrix(2.0**-th) @ (g**m)
    with np.errstate(divide="ignore"):
        return np.log(q)


_LOGFACT = gammaln(_U + 1.0)


def tier_bits(log_q, F, n_sigs, h, b):
    """(h - b) - log2 E_{r ~ Poisson(n/2^b)}[q(r)^F]."""
    lam = n_sigs / 2**b
    t = -lam + _U * math.log(lam) - _LOGFACT + F * log_q
    mx = t.max()
    return (h - b) - (mx + math.log(np.exp(t - mx).sum())) / math.log(2)


def forest_lifetime(log_q, F, h, b):
    lo, hi = 1, 2 ** (b + 8)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if tier_bits(log_q, F, mid, h, b) >= LEVEL else (lo, mid)
    return lo


# ---------------------------------------------------------------- costs
def forest_costs(F, th, m, s, c, w, D, tau):
    lh = comp(c * N)
    wots_key = -(-c // 2) * DERIVE + c * (w - 1) * STEP + lh
    leaf_hash = comp(2 * m * N)
    per_tree_verify = m * (D * STEP + lh + (s - 1) * NODE) + leaf_hash + (th - 1) * NODE
    per_tree_values = m * (c + s) + th
    subtree = 2**s * wots_key + (2**s - 2) * NODE
    per_tree_sign = 2**th * (m * subtree + leaf_hash) + (2**th - 2) * NODE
    key = comp(2 * F * N)
    return dict(verify=F * per_tree_verify + key, values=F * per_tree_values,
                sign=F * per_tree_sign + key, bits=F * (th + m * (s + tau)),
                per_tree_verify=per_tree_verify, per_tree_values=per_tree_values)


@lru_cache(maxsize=None)
def wotsc(T=WOTSC_T):
    return [x for x in V.wots_options(2**20) if x["lg_w"] == 2 and x["T"] == T][0]


@lru_cache(maxsize=None)
def tier_fixed(h, name, b):
    """Keygen and the signing work outside the forest (randomizer, grinding, WOTS+C, auth path)."""
    wo = wotsc()
    rate, cache, _ = V.DEVICES[name]
    keygen = DERIVE + 2**b * (wo["leaf"] + NODE) + (h - b) * (DERIVE + NODE)
    grind = 2 ** (h - b) if b < h else 0
    return keygen, V.RND + grind + wo["sign"] + V.tree_cost(b, cache // N, wo["leaf"]), rate


def digest_cost(h, bits):
    return math.ceil((h + bits) / 256) * V.MSG_BLOCK


def scheme_costs(h, fc, b_led=13, b_std=20):
    wo = wotsc()
    digest = digest_cost(h, fc["bits"])
    verify = digest + fc["verify"] + wo["verify"] + h * NODE
    size = N + fc["values"] * N + wo["size"] + h * N
    tiers = {}
    for name, b in (("ledger", b_led), ("standard", b_std), ("full", h)):
        keygen, fixed, rate = tier_fixed(h, name, b)
        sign = fixed + digest + fc["sign"]
        tiers[name] = dict(b=b, keygen=keygen, keygen_s=keygen / rate, sign=sign, sign_s=sign / rate)
    return dict(verify=verify, size=size, digest=digest, wots_verify=wo["verify"], tiers=tiers)


# ---------------------------------------------------------------- checks against Tom's spicy variant
def check_tom():
    f = f_tab(6, 5, 5, 8, 214)
    print("f(1..6) =", " ".join(f"{x:.6f}" for x in f[1:7]), "(FOREST.md: 0.005188 0.067847 0.172139 0.280345 0.376068 0.456117)")
    lq = log_q_tree(g_sub(f, 3), 4, 2)
    for b, want in ((26, 1.43966e9), (20, 2.85120e7), (13, 2.89047e5), (8, 1.07843e4)):
        print(f"b={b}: cover lifetime {forest_lifetime(lq, 8, 26, b):.6g} (FOREST.md {want:.6g})")
    fc = forest_costs(8, 4, 2, 3, 6, 5, 5, 8)
    wo = [x for x in V.wots_options(2**20) if x["lg_w"] == 2 and x["T"] == 120][0]
    digest = math.ceil((26 + fc["bits"]) / 256) * V.MSG_BLOCK
    print(f"verify {digest + fc['verify'] + wo['verify'] + 26} (paper 307), size {N + fc['values'] * N + wo['size'] + 26 * N} "
          f"(paper 4276), forest signing {fc['sign']} (paper ~61K), digest bits {26 + fc['bits']} (paper 234)")


# ---------------------------------------------------------------- search
def wots_shapes(args):
    for c in range(2, args.c_max + 1):
        for w in range(2, args.w_max + 1):
            if w**c > args.grid_max:
                continue
            for D in range(1, min(args.d_max, c * (w - 1)) + 1):
                n_cw = len(codewords(c, w, D))
                for tau in range(4, args.tau_max + 1):
                    E = 2**tau
                    if n_cw < E // 4:
                        continue
                    top = min(n_cw, E)
                    Ms = sorted({top} | {round(x * E) for x in args.m_fracs if round(x * E) < top and round(x * E) >= 8})
                    for M in Ms:
                        yield c, w, D, tau, M


def search(args):
    targets = {k: v * args.margin for k, v in V.TARGETS.items()}
    wo = wotsc()
    rows, best_v = [], args.verify_cap
    shapes = list(wots_shapes(args))
    print(f"{len(shapes)} WOTS/table shapes")
    for (c, w, D, tau, M) in shapes:
        for s in range(1, args.s_max + 1):
            for th in range(1, args.th_max + 1):
                for m in (1, 2, 3):
                    lq = None
                    for h in range(args.h_min, args.h_max + 1):
                        if V.DEVICES["full"][2] < tier_fixed(h, "full", h)[0] / V.DEVICES["full"][0]:
                            continue
                        led_fixed, led_rate = tier_fixed(h, "ledger", 13)[1:]
                        # verification, size and signing all grow with F: the first F that is secure is the one
                        for F in range(1, args.f_max + 1):
                            fc = forest_costs(F, th, m, s, c, w, D, tau)
                            if h + fc["bits"] > 512:
                                break
                            digest = digest_cost(h, fc["bits"])
                            verify = digest + fc["verify"] + wo["verify"] + h * NODE
                            if verify > best_v + args.slack:
                                break
                            if (led_fixed + digest + fc["sign"]) / led_rate > args.ledger_sign_s:
                                break
                            if lq is None:
                                lq = log_q_tree(g_sub(f_tab(c, w, D, tau, M), s), th, m)
                            if not (tier_bits(lq, F, targets["full"], h, h) >= LEVEL and
                                    tier_bits(lq, F, targets["standard"], h, 20) >= LEVEL and
                                    tier_bits(lq, F, targets["ledger"], h, 13) >= LEVEL):
                                continue
                            best_v = min(best_v, verify)
                            rows.append(dict(F=F, th=th, m=m, s=s, c=c, w=w, D=D, tau=tau, M=M, h=h, fc=fc,
                                             sc=scheme_costs(h, fc)))
                            break
    return [r for r in rows if r["sc"]["verify"] <= best_v + args.slack]


def describe(r):
    fc, sc = r["fc"], r["sc"]
    lq = log_q_tree(g_sub(f_tab(r["c"], r["w"], r["D"], r["tau"], r["M"]), r["s"]), r["th"], r["m"])
    life = {name: forest_lifetime(lq, r["F"], r["h"], t["b"]) for name, t in sc["tiers"].items()}
    return life


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check-tom", action="store_true")
    ap.add_argument("--margin", type=float, default=1.25)
    ap.add_argument("--h-min", type=int, default=24)
    ap.add_argument("--h-max", type=int, default=24)
    ap.add_argument("--f-max", type=int, default=16)
    ap.add_argument("--th-max", type=int, default=6)
    ap.add_argument("--s-max", type=int, default=5)
    ap.add_argument("--c-max", type=int, default=10)
    ap.add_argument("--w-max", type=int, default=7)
    ap.add_argument("--d-max", type=int, default=10)
    ap.add_argument("--tau-max", type=int, default=10)
    ap.add_argument("--grid-max", type=int, default=400_000, help="max w^c for the f_t computation")
    ap.add_argument("--m-fracs", type=float, nargs="*", default=[0.7, 0.8, 0.84, 0.9])
    ap.add_argument("--ledger-sign-s", type=float, default=2.2)
    ap.add_argument("--verify-cap", type=int, default=290)
    ap.add_argument("--slack", type=int, default=6, help="keep sets within this many compressions of the best")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()
    if args.check_tom:
        check_tom()
        return
    rows = search(args)
    rows.sort(key=lambda r: (r["sc"]["verify"], r["sc"]["size"], r["sc"]["tiers"]["ledger"]["sign"]))
    print(f"{len(rows)} sets within {args.slack} of the best; top {args.top}:")
    for r in rows[: args.top]:
        fc, sc, t = r["fc"], r["sc"], r["sc"]["tiers"]
        print(f"verify {sc['verify']:3d}  size {sc['size']:5d} B | F={r['F']:2d} th={r['th']} m={r['m']} s={r['s']} "
              f"WOTS c={r['c']} w={r['w']} D={r['D']} table 2^{r['tau']}/{r['M']} h={r['h']} | "
              f"per tree {fc['per_tree_verify']} compr / {fc['per_tree_values']} values, bits {r['h'] + fc['bits']}, "
              f"forest sign {fc['sign']}, ledger sign {t['ledger']['sign_s']:.2f} s")


if __name__ == "__main__":
    main()
