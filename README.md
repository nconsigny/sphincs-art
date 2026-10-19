# sphincs-art

Unofficial fork of [sphincs.art](https://sphincs.art), Tom Wambsgans' leanSphincs proposal
([source](https://github.com/TomWambsgans/leanXMSS-leanSPHINCS-candidates/tree/main/site)), with one
addition: a **leanSphincs-S** column and the **One signer, leanSphincs-S** and **Threshold, leanSphincs-S** sections.

Live page: https://nconsigny.github.io/sphincs-art/

Everything else on the page — the proposal, the vanilla/spicy variants, the diagram, the threshold
section — is the original. The first commit is an unmodified copy of upstream; the later ones hold the changes.

## leanSphincs-S

Same scheme (one XMSS layer, WOTS+C, FORS with no root hash, hypertree pruning, BLAKE2s compressions),
retuned for lower lifetimes, the fewest verification compressions and the smallest signature:

| | leanSphincs | leanSphincs-S | leanSphincs-S, spicy |
|---|---|---|---|
| h | 26 | 26 | 25 |
| Few-time signature | FORS, k = 24, a = 10 | FORS, k = 13, a = 12 | WOTS forest (below) |
| WOTS+C | 64 chains of length 4, target sum 120 | 64 chains of length 4, target sum 128 | same |
| Lifetime, full tree | 2^30 (proved) | 2^26 (estimate) | 2^25 (estimate) |
| Lifetime targets (full / standard / Ledger) | 1.15B / 22M / 210K | 2^23 / 2^21 / 20K | 2^23 / 2^21 / 20K |
| Signature | 5,684 bytes | 4,164 bytes | 3,652 bytes |
| Verification, BLAKE2s | 373 compressions | 273 compressions | 225 compressions |
| Verification, Keccak-256 | 354 permutations | 259 permutations | 201 permutations |

Verification: digest 2 + FORS 163 + WOTS+C 82 + path 26 (spicy: forest 116, path 25). The keygen budgets are
the proposal's (Ledger 60 s at 33K compressions/s, weak CPU about 1 s at 256M/s, powerful CPU 16 s at 1B/s), so the
Ledger and standard signers keep subtrees of 2^13 and 2^20 leaves; Ledger signing may take up to 5 s.
Ledger signing is 159K compressions (4.8 s), estimated lifetimes 43.7K / 3.05M / 108M (lowered by the proposal's proof gaps: 38.2K / 2.87M / 103M), full keygen 16 s.
The tree height is one level above the minimum: +1 compression doubles the full-tree lifetime, and the full
keygen uses the proposal's 16 s budget. The full tree gives 2^26 (estimate 1.08·10^8, 1.03·10^8 after the 4% proof gap).

**Spicy.** As in the proposal's spicy variant, FORS is replaced by a two-level WOTS forest, here reshaped for
the lower lifetimes and a 5 s Ledger signing budget, traded for a smaller signature: 3 trees of height 4;
each leaf is H(R₀, R₁, R₂), the roots of three subtrees of height 5 over WOTS keys of 9 chains of length 3
that sign a codeword of digit sum 4. The 10-bit table holds all 414 such codewords, sorted as in the
proposal, the 196 most concentrated 3 times and the others twice. Per tree: 38 compressions, 46 values;
the digest is 171 bits, one call. WOTS+C is unchanged and the tree is one level lower (h = 25, full keygen
8.1 s); the Ledger and standard keygens are unchanged. Ledger signing is 146K compressions
(4.4 s), estimated lifetimes 66.0K / 3.51M / 49.5M (lowered by the proof gaps: 56.4K / 3.20M / 47.6M); the full tree gives 2^25.

**These lifetimes are estimates, not proved in Lean.** They use the cover estimate of the note
(section 3): the exact success probability of the cover attack, which for a plain FORS is a closed formula.
The proposal's Lean proofs land 4–17% below that estimate, because they must also bound adaptive forgers
and the WOTS+C neighbour route; we apply the proposal's measured gap at the same subtree size (4% for the
full tree, 6% at 2^20, 13% at 2^13). Each tier still clears its target (20K, 2^21, 2^23).

## Keccak-256

The page follows the proposal's BLAKE2s / Keccak-256 switch. Keccak figures use the cost model of the proposal's
`keccak` branch (`scripts/keccak_model.py` reproduces its 354 and 267 permutations): one Keccak-f permutation per
136-byte block, and the WOTS+C encoding absorbs the few-time tops directly (no separate few-time key hash).
Same parameters for both hashes. Speeds: Ledger 5.8K permutations/s, weak CPU 128M/s, powerful CPU 512M/s, so
Keccak signing on a Ledger takes 27 s (FORS) or 24 s (forest), and Ledger keygen 5.5 min.

## Threshold, leanSphincs-S

Same ceremony as the proposal's threshold mode (adapted from PRAWNS) and the same verifier, for the FORS
variant. Keygen has to hash every FORS secret inside an MPC. leanSphincs-S is tuned for verification cost
and signature size, so its FORS supports fewer signatures per instance and its threshold keys cost more than
the proposal's. Three changes cut the MPC:

- **No secret for the one-time keys.** Each WOTS+C key only signs its own FORS root, known at keygen, so its
  signature values come from a joint coin toss and that layer needs no MPC.
- **Sparse FORS.** Only about 40% of the FORS leaves get secrets; the others are random values with no known
  preimage. Signers grind the randomizer (about 2^30 hashes per signature) until the message picks real
  leaves. About 2.5x less MPC, unchanged verifier.
- **Balanced use.** The signing service logs every signature and grinds to an instance used fewer than a set
  number of times, so a kept subtree lasts about 1.5x longer.

For a 2-of-3 key lasting about 100K signatures, keygen traffic per operator drops from 2,975 GB to 568 GB.
Applied to the proposal's own set, the same changes cut its traffic by about a third (2-of-3 with 2^12 kept
instances: 172 GB to 108 GB); the page shows these figures in green next to the original threshold table.
Lifetimes are the cover estimate with balanced use, lowered by the proposal's proof gap at the same subtree size; traffic uses the
proposal's measured bytes per MPC leaf.

| Lifetime (signatures) | 9.1K (2^10) | 30.1K (2^12) | 109K (2^14) |
|---|---|---|---|
| 2-of-3 | 44 GB | 158 GB | 568 GB |
| 3-of-5 | 53 GB | 189 GB | 681 GB |
| 4-of-7 | 57 GB | 203 GB | 730 GB |

## Reproducing

```
python3 scripts/sweep_leansphincs_pruned.py --check-tom   # reproduces the proposal's 373 compressions
python3 scripts/sweep_leansphincs_pruned.py --lg-w 2      # the FORS search; leanSphincs-S is its best set under 5 s, one level taller
python3 scripts/option_a.py                               # threshold cost of FORS sets with the three changes
python3 scripts/sweep_leansphincs_forest.py --check-tom   # reproduces the spicy 307 compressions and lifetimes
python3 scripts/keccak_model.py                          # Keccak-256 costs (the proposal's keccak branch model)
python3 scripts/sweep_leansphincs_forest.py --ledger-sign-s 5   # the forest search behind the spicy column
```

Requires numpy and scipy. The cost model mirrors `scripts/scheme.py` of the upstream repository.

## License

The site is Tom Wambsgans' work, licensed under MIT OR Apache-2.0 (`LICENSE-MIT`, `LICENSE-APACHE`);
the changes in this fork are under the same terms.
