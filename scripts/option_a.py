"""Option A: standard verifier, cheaper threshold MPC keygen.
Single-signer tiers: stateless (Poisson cover estimate, margin 1.25, Ledger signing <= 5 s), as on the site.
Threshold key (2-of-3, L signatures): the signing service keeps a usage log (balanced loads, fill 0.95),
secret-free WOTS+C layer (no MPC), sparse FORS with total grinding budget 2^G per threshold signature.
MPC traffic per operator uses Tom's measured bytes per FORS leaf."""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import sweep_leansphincs_pruned as V
import balanced as B
import threshold as T

L, G = 100_000, 30
WO = B.WO

def threshold_cost(h, k, a, n=3, L=L, G=G, sparse=True, balanced=True):
    life = (lambda b: T.life_bal(h, b, a, k)) if balanced else (lambda b: T.life_poisson(h, b, a, k))
    b = T.min_b(life, L, h)
    if b is None:
        return None
    g = G - (h - b)
    rho = min(1.0, 2 ** (-g / k)) if (sparse and g > 0) else 1.0
    leaves = 2**b * k * 2**a * rho
    return dict(b=b, rho=rho, life=life(b), mpc=leaves * T.MEAS[n][0], public=2**b * k * 2**a * 16)

def single_ok(h, k, a):
    for tier, b in (("full", h), ("standard", 20), ("ledger", 13)):
        if not V.tier_ok(V.TARGETS[tier] * 1.25, h, b, a, k):
            return False
    return True

if __name__ == "__main__":
    rows = []
    for h in range(22, 28):
        for a in range(4, 15):
            for k in range(1, 80):
                verify = math.ceil((h + k * a) / 256) * V.MSG_BLOCK + k * a + V.comp(2 * k * V.N) + WO["verify"] + h
                if verify > 340:
                    break
                if not single_ok(h, k, a):
                    continue
                led = B.costs(h, 13, a, k, "ledger", False)
                if led["sign_worst_s"] > 5.0:
                    break
                tc = threshold_cost(h, k, a)
                if tc is None:
                    break
                size = 16 + k * (1 + a) * 16 + WO["size"] + h * 16
                rows.append(dict(h=h, k=k, a=a, verify=verify, size=size, led=led["sign_worst_s"], **tc))
                break
    rows.sort(key=lambda r: (r["verify"], r["mpc"]))
    print(f"{'verify':>6} {'size':>6} {'h':>3} {'k':>3} {'a':>3} {'led s':>6} | thr b  rho   MPC 2-of-3 (L=100K)")
    best = None
    for r in rows:
        if best is None or r["mpc"] < best:
            best = r["mpc"]
            print(f"{r['verify']:6d} {r['size']:6d} {r['h']:3d} {r['k']:3d} {r['a']:3d} {r['led']:6.2f} | {r['b']:5d} {r['rho']:.2f} {r['mpc']/1e9:9.1f} GB")
    live = threshold_cost(25, 13, 12, sparse=False, balanced=False)
    livea = threshold_cost(25, 13, 12)
    tom = threshold_cost(26, 24, 10, sparse=False, balanced=False)
    toma = threshold_cost(26, 24, 10)
    print(f"\nlive FORS set (h=25 k=13 a=12): plain MPC {live['mpc']/1e9:.0f} GB (b={live['b']}), with Option A {livea['mpc']/1e9:.0f} GB (b={livea['b']}, rho={livea['rho']:.2f})")
    print(f"Tom (h=26 k=24 a=10): plain MPC {tom['mpc']/1e9:.0f} GB (b={tom['b']}), with Option A {toma['mpc']/1e9:.0f} GB (b={toma['b']}, rho={toma['rho']:.2f})")
