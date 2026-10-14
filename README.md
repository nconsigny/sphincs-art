# sphincs-art

Unofficial fork of [sphincs.art](https://sphincs.art), Tom Wambsgans' leanSphincs proposal
([source](https://github.com/TomWambsgans/leanXMSS-leanSPHINCS-candidates/tree/main/site)), with one
addition: a **leanSphincs-23** column and the **One signer, leanSphincs-23** and **Threshold, leanSphincs-23** sections.

Live page: https://nconsigny.github.io/sphincs-art/

Everything else on the page — the proposal, the vanilla/spicy variants, the diagram, the threshold
section — is the original. The first commit is an unmodified copy of upstream; the later ones hold the changes.

## leanSphincs-23

Same scheme (one XMSS layer, WOTS+C, FORS with no root hash, hypertree pruning, BLAKE2s compressions),
retuned for lower lifetimes, few verification compressions and cheap threshold keys:

| | leanSphincs | leanSphincs-23 | leanSphincs-23, spicy |
|---|---|---|---|
| h | 26 | 25 | 24 |
| Few-time signature | FORS, k = 24, a = 10 | FORS, k = 17, a = 10 | WOTS forest (below) |
| WOTS+C | 64 chains of length 4, target sum 120 | 64 chains of length 4, target sum 128 | same |
| Lifetime (full / standard / Ledger) | 1.15B / 22M / 210K | 2^23 / 2^21 / 20K | 2^23 / 2^21 / 20K |
| Signature | 5,684 bytes | 4,436 bytes | 3,636 bytes |
| Verification | 373 compressions | 288 compressions | 224 compressions |

Verification: digest 2 + FORS 179 + WOTS+C 82 + path 25 (spicy: forest 116, path 24). The keygen budgets are
the proposal's (Ledger 60 s at 33K compressions/s, weak CPU 2 s at 128M/s, powerful CPU 16 s at 1B/s), so the
Ledger and standard signers keep subtrees of 2^13 and 2^20 leaves; Ledger signing may take up to 5 s.
Ledger signing is 65K compressions (2.0 s), estimated lifetimes 37.3K / 2.88M / 61.8M, full keygen 8.1 s.
The FORS set is not the one with the fewest compressions (272 is possible) but the one that keeps threshold
keys cheap: see below.

**Spicy.** As in the proposal's spicy variant, FORS is replaced by a two-level WOTS forest, here reshaped for
the lower lifetimes and a 5 s Ledger signing budget, traded for a smaller signature: 3 trees of height 4;
each leaf is H(R₀, R₁, R₂), the roots of three subtrees of height 5 over WOTS keys of 9 chains of length 3
that sign a codeword of digit sum 4. The 10-bit table holds all 414 such codewords, sorted as in the
proposal, the 196 most concentrated 3 times and the others twice. Per tree: 38 compressions, 46 values;
the digest is 171 bits, one call. WOTS+C is unchanged and the tree is one level lower (h = 24, full keygen
4.1 s); the Ledger and standard keygens are unchanged. Ledger signing is 144K compressions
(4.4 s), estimated lifetimes 59.0K / 3.03M / 24.7M.

**These lifetimes are estimates, not proved in Lean.** They use the cover estimate of the note
(section 3), and each tier clears its target by at least 25% under it (37.3K, 2.88M and 61.8M), since
the proved figures of the proposal sit 4–17% below that estimate.

## Threshold, leanSphincs-23

Same ceremony as the proposal's threshold mode (adapted from PRAWNS) and the same verifier, for the FORS
variant. Keygen has to hash every FORS secret inside an MPC; four changes cut that work:

- **No secret for the one-time keys.** Each WOTS+C key only signs its own FORS root, known at keygen, so its
  signature values come from a joint coin toss and that layer needs no MPC.
- **Sparse FORS.** Only about half of the FORS leaves get secrets; the others are random values with no known
  preimage. Signers grind the randomizer (about 2^30 hashes per signature) until the message picks real
  leaves. Half the MPC, unchanged verifier.
- **Balanced use.** The signing service logs every signature and grinds to an instance used fewer than a set
  number of times, so a kept subtree lasts about 1.8x longer.
- **Smaller FORS trees.** k = 17, a = 10: 17K leaves per instance instead of 53K with k = 13, a = 12.

For a 2-of-3 key lasting about 100K signatures, keygen traffic per operator drops from 2,964 GB to 223 GB.
Lifetimes are rated with a 25% margin under the cover estimate, with balanced use; traffic uses the
proposal's measured bytes per MPC leaf.

| Lifetime (signatures) | 7.7K (2^10) | 28.0K (2^12) | 112K (2^14) |
|---|---|---|---|
| 2-of-3 | 16 GB | 61 GB | 223 GB |
| 3-of-5 | 20 GB | 73 GB | 268 GB |
| 4-of-7 | 21 GB | 78 GB | 287 GB |

## Reproducing

```
python3 scripts/sweep_leansphincs_pruned.py --check-tom   # reproduces the proposal's 373 compressions
python3 scripts/sweep_leansphincs_pruned.py --lg-w 2      # the FORS search for the single-signer tiers
python3 scripts/option_a.py                               # FORS sets ranked by threshold cost; leanSphincs-23 is h=25 k=17 a=10
python3 scripts/sweep_leansphincs_forest.py --check-tom   # reproduces the spicy 307 compressions and lifetimes
python3 scripts/sweep_leansphincs_forest.py --ledger-sign-s 5   # the forest search behind the spicy column
```

Requires numpy and scipy. The cost model mirrors `scripts/scheme.py` of the upstream repository.

## License

The site is Tom Wambsgans' work, licensed under MIT OR Apache-2.0 (`LICENSE-MIT`, `LICENSE-APACHE`);
the changes in this fork are under the same terms.
