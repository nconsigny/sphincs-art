# sphincs-art

Unofficial fork of [sphincs.art](https://sphincs.art), Tom Wambsgans' leanSphincs proposal
([source](https://github.com/TomWambsgans/leanXMSS-leanSPHINCS-candidates/tree/main/site)), with one
addition: a **This fork** column and a **One signer, this fork** table.

Live page: https://nconsigny.github.io/sphincs-art/

Everything else on the page — the proposal, the vanilla/spicy variants, the diagram, the threshold
section — is the original. The first commit is an unmodified copy of upstream; the second holds the changes.

## The added column

Same scheme (one XMSS layer, WOTS+C, FORS with no root hash, hypertree pruning, BLAKE2s compressions),
retuned for lower lifetimes and the fewest verification compressions:

| | leanSphincs | This fork |
|---|---|---|
| h, k, a | 26, 24, 10 | 24, 17, 10 |
| WOTS+C | 64 chains of length 4, target sum 120 | 64 chains of length 4, target sum 128 |
| Lifetime (full / standard / Ledger) | 1.15B / 22M / 210K | 2^23 / 2^21 / 20K |
| Signature | 5,684 bytes | 4,420 bytes |
| Verification | 373 compressions | 287 compressions |

Verification: digest 2 + FORS 179 + WOTS+C 82 + path 24. The device budgets are the proposal's
(Ledger keygen 60 s at 33K compressions/s, weak CPU 2 s at 128M/s, powerful CPU 16 s at 1B/s), so the
Ledger and standard signers keep subtrees of 2^13 and 2^20 leaves.

**These lifetimes are estimates, not proved in Lean.** They use the cover estimate of the note
(section 3), and each tier clears its target by at least 25% under it (34.9K, 2.67M and 30.9M), since
the proved figures of the proposal sit 4–17% below that estimate.

## Reproducing

```
python3 scripts/sweep_leansphincs_pruned.py --check-tom   # reproduces the proposal's 373 compressions
python3 scripts/sweep_leansphincs_pruned.py               # the search behind the added column (~20 s)
```

Requires numpy and scipy. The cost model mirrors `scripts/scheme.py` of the upstream repository.

## License

The site is Tom Wambsgans' work, licensed under MIT OR Apache-2.0 (`LICENSE-MIT`, `LICENSE-APACHE`);
the changes in this fork are under the same terms.
