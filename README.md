# sphincs-art

Unofficial fork of [sphincs.art](https://sphincs.art), Tom Wambsgans' leanSphincs proposal
([source](https://github.com/TomWambsgans/leanXMSS-leanSPHINCS-candidates/tree/main/site)), with one
addition: a **leanSphincs-23** column and a **One signer, leanSphincs-23** table.

Live page: https://nconsigny.github.io/sphincs-art/

Everything else on the page — the proposal, the vanilla/spicy variants, the diagram, the threshold
section — is the original. The first commit is an unmodified copy of upstream; the later ones hold the changes.

## leanSphincs-23

Same scheme (one XMSS layer, WOTS+C, FORS with no root hash, hypertree pruning, BLAKE2s compressions),
retuned for lower lifetimes and the fewest verification compressions:

| | leanSphincs | leanSphincs-23 | leanSphincs-23, spicy |
|---|---|---|---|
| h | 26 | 24 | 24 |
| Few-time signature | FORS, k = 24, a = 10 | FORS, k = 17, a = 10 | WOTS forest (below) |
| WOTS+C | 64 chains of length 4, target sum 120 | 64 chains of length 4, target sum 128 | same |
| Lifetime (full / standard / Ledger) | 1.15B / 22M / 210K | 2^23 / 2^21 / 20K | 2^23 / 2^21 / 20K |
| Signature | 5,684 bytes | 4,420 bytes | 4,180 bytes |
| Verification | 373 compressions | 287 compressions | 227 compressions |

Verification: digest 2 + FORS 179 (spicy: forest 119) + WOTS+C 82 + path 24. The device budgets are the proposal's
(Ledger keygen 60 s at 33K compressions/s, weak CPU 2 s at 128M/s, powerful CPU 16 s at 1B/s), so the
Ledger and standard signers keep subtrees of 2^13 and 2^20 leaves.

**Spicy.** As in the proposal's spicy variant, FORS is replaced by a two-level WOTS forest, here reshaped for
the lower lifetimes: 4 trees of height 4; each leaf is H(R₀, R₁, R₂), the roots of three subtrees of height 3
over WOTS keys of 10 chains of length 3 that sign a codeword of digit sum 3. The 8-bit table holds all 210
such codewords, sorted as in the proposal, the 46 most concentrated twice. Per tree: 29 compressions,
43 values; the digest is 172 bits, one call. Keygen and WOTS+C are unchanged; Ledger signing is 64K
compressions (1.9 s), estimated lifetimes 46.3K / 2.99M / 30.0M.

**These lifetimes are estimates, not proved in Lean.** They use the cover estimate of the note
(section 3), and each tier clears its target by at least 25% under it (34.9K, 2.67M and 30.9M), since
the proved figures of the proposal sit 4–17% below that estimate.

## Reproducing

```
python3 scripts/sweep_leansphincs_pruned.py --check-tom   # reproduces the proposal's 373 compressions
python3 scripts/sweep_leansphincs_pruned.py               # the search behind the added column (~20 s)
python3 scripts/sweep_leansphincs_forest.py --check-tom   # reproduces the spicy 307 compressions and lifetimes
python3 scripts/sweep_leansphincs_forest.py               # the forest search behind the spicy column (~45 s)
```

Requires numpy and scipy. The cost model mirrors `scripts/scheme.py` of the upstream repository.

## License

The site is Tom Wambsgans' work, licensed under MIT OR Apache-2.0 (`LICENSE-MIT`, `LICENSE-APACHE`);
the changes in this fork are under the same terms.
