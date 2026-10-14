# sphincs-art

Unofficial fork of [sphincs.art](https://sphincs.art), Tom Wambsgans' leanSphincs proposal
([source](https://github.com/TomWambsgans/leanXMSS-leanSPHINCS-candidates/tree/main/site)), with one
addition: a **leanSphincs-23** column and the **One signer, leanSphincs-23** and **Threshold, leanSphincs-23** sections.

Live page: https://nconsigny.github.io/sphincs-art/

Everything else on the page — the proposal, the vanilla/spicy variants, the diagram, the threshold
section — is the original. The first commit is an unmodified copy of upstream; the later ones hold the changes.

## leanSphincs-23

Same scheme (one XMSS layer, WOTS+C, FORS with no root hash, hypertree pruning, BLAKE2s compressions),
retuned for lower lifetimes, the fewest verification compressions and the smallest signature:

| | leanSphincs | leanSphincs-23 | leanSphincs-23, spicy |
|---|---|---|---|
| h | 26 | 25 | 24 |
| Few-time signature | FORS, k = 24, a = 10 | FORS, k = 13, a = 12 | WOTS forest (below) |
| WOTS+C | 64 chains of length 4, target sum 120 | 64 chains of length 4, target sum 128 | same |
| Lifetime (full / standard / Ledger) | 1.15B / 22M / 210K | 2^23 / 2^21 / 20K | 2^23 / 2^21 / 20K |
| Signature | 5,684 bytes | 4,148 bytes | 3,636 bytes |
| Verification | 373 compressions | 272 compressions | 224 compressions |

Verification: digest 2 + FORS 163 + WOTS+C 82 + path 25 (spicy: forest 116, path 24). The keygen budgets are
the proposal's (Ledger 60 s at 33K compressions/s, weak CPU 2 s at 128M/s, powerful CPU 16 s at 1B/s), so the
Ledger and standard signers keep subtrees of 2^13 and 2^20 leaves; Ledger signing may take up to 5 s.
Ledger signing is 155K compressions (4.7 s), estimated lifetimes 40.2K / 2.78M / 54.0M, full keygen 8.1 s.

**Spicy.** As in the proposal's spicy variant, FORS is replaced by a two-level WOTS forest, here reshaped for
the lower lifetimes and a 5 s Ledger signing budget, traded for a smaller signature: 3 trees of height 4;
each leaf is H(R₀, R₁, R₂), the roots of three subtrees of height 5 over WOTS keys of 9 chains of length 3
that sign a codeword of digit sum 4. The 10-bit table holds all 414 such codewords, sorted as in the
proposal, the 196 most concentrated 3 times and the others twice. Per tree: 38 compressions, 46 values;
the digest is 171 bits, one call. WOTS+C is unchanged and the tree is one level lower (h = 24, full keygen
4.1 s); the Ledger and standard keygens are unchanged. Ledger signing is 144K compressions
(4.4 s), estimated lifetimes 59.0K / 3.03M / 24.7M.

**These lifetimes are estimates, not proved in Lean.** They use the cover estimate of the note
(section 3), and each tier clears its target by at least 25% under it (40.2K, 2.78M and 54.0M), since
the proved figures of the proposal sit 4–17% below that estimate.

## Threshold, leanSphincs-23

Same ceremony as the proposal's threshold mode (adapted from PRAWNS) and the same verifier, for the FORS
variant. Keygen has to hash every FORS secret inside an MPC. leanSphincs-23 is tuned for verification cost
and signature size, so its FORS supports fewer signatures per instance and its threshold keys cost more than
the proposal's. Three changes cut the MPC:

- **No secret for the one-time keys.** Each WOTS+C key only signs its own FORS root, known at keygen, so its
  signature values come from a joint coin toss and that layer needs no MPC.
- **Sparse FORS.** Only about 40% of the FORS leaves get secrets; the others are random values with no known
  preimage. Signers grind the randomizer (about 2^30 hashes per signature) until the message picks real
  leaves. About 2.5x less MPC, unchanged verifier.
- **Balanced use.** The signing service logs every signature and grinds to an instance used fewer than a set
  number of times, so a kept subtree lasts about 1.7x longer.

For a 2-of-3 key lasting about 100K signatures, keygen traffic per operator drops from 2,975 GB to 538 GB.
Applied to the proposal's own set, the same changes cut its traffic by about a third (2-of-3 with 2^12 kept
instances: 172 GB to 108 GB); the page shows these figures in green next to the original threshold table.
Lifetimes are rated with a 25% margin under the cover estimate, with balanced use; traffic uses the
proposal's measured bytes per MPC leaf.

| Lifetime (signatures) | 7.7K (2^10) | 28.0K (2^12) | 99.6K (2^14) |
|---|---|---|---|
| 2-of-3 | 42 GB | 150 GB | 538 GB |
| 3-of-5 | 50 GB | 180 GB | 646 GB |
| 4-of-7 | 54 GB | 193 GB | 693 GB |

## Reproducing

```
python3 scripts/sweep_leansphincs_pruned.py --check-tom   # reproduces the proposal's 373 compressions
python3 scripts/sweep_leansphincs_pruned.py --lg-w 2      # the FORS search; leanSphincs-23 is the best set under 5 s
python3 scripts/option_a.py                               # threshold cost of FORS sets with the three changes
python3 scripts/sweep_leansphincs_forest.py --check-tom   # reproduces the spicy 307 compressions and lifetimes
python3 scripts/sweep_leansphincs_forest.py --ledger-sign-s 5   # the forest search behind the spicy column
```

Requires numpy and scipy. The cost model mirrors `scripts/scheme.py` of the upstream repository.

## License

The site is Tom Wambsgans' work, licensed under MIT OR Apache-2.0 (`LICENSE-MIT`, `LICENSE-APACHE`);
the changes in this fork are under the same terms.
