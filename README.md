# sphincs-art

Unofficial fork of [sphincs.art](https://sphincs.art), Tom Wambsgans' leanSphincs proposal
([source](https://github.com/TomWambsgans/leanXMSS-leanSPHINCS-candidates/tree/main/site)), with one
two additions: a **leanSphincs-s** column with the **One signer, leanSphincs-s** and **Threshold, leanSphincs-s** sections, and a
**leanSphincs-f** column with its **One signer, leanSphincs-f** table (s = small, f = fast, as in SPHINCS+).

Live page: https://nconsigny.github.io/sphincs-art/

Everything else on the page — the proposal, the vanilla/spicy variants, the diagram, the threshold
section — is the original. The first commit is an unmodified copy of upstream; the later ones hold the changes.

## leanSphincs-s

Same scheme (one XMSS layer, WOTS+C, FORS with no root hash, hypertree pruning, BLAKE2s compressions),
retuned for lower lifetimes, the fewest verification compressions and the smallest signature:

| | leanSphincs | leanSphincs-s | leanSphincs-s, spicy |
|---|---|---|---|
| h | 26 | 26 | 26 |
| Few-time signature | FORS, k = 24, a = 10 | FORS, k = 13, a = 12 | WOTS forest (below) |
| WOTS+C | 64 chains of length 4, target sum 120 | 64 chains of length 4, target sum 128 | same |
| Lifetime, full tree | 2^30 (proved) | 2^26 (estimate) | 2^26 (estimate) |
| Lifetime targets (full / standard / Ledger) | 1.15B / 22M / 210K | 2^23 / 2^21 / 20K | at least leanSphincs-s's |
| Signature | 5,684 bytes | 4,164 bytes | 3,300 bytes |
| Verification, BLAKE2s | 373 compressions | 273 compressions | 240 compressions |
| Verification, Keccak-256 | 354 permutations | 259 permutations | 213 permutations |

Verification: digest 2 + FORS 163 + WOTS+C 82 + path 26 (spicy: forest 133, WOTS+C 79). The keygen budgets are
the proposal's (Ledger 60 s at 33K compressions/s, weak CPU about 1 s at 256M/s, powerful CPU 16 s at 1B/s), so the
Ledger and standard signers keep subtrees of 2^13 and 2^20 leaves; Ledger signing may take up to 5 s.
Ledger signing is 159K compressions (4.8 s), estimated lifetimes 43.7K / 3.05M / 108M (lowered by the proposal's proof gaps: 38.2K / 2.87M / 103M), full keygen 16 s.
The tree height is one level above the minimum: +1 compression doubles the full-tree lifetime, and the full
keygen uses the proposal's 16 s budget. The full tree gives 2^26 (estimate 1.08·10^8, 1.03·10^8 after the 4% proof gap).

**Spicy.** As in the proposal's spicy variant, FORS is replaced by a two-level WOTS forest, tuned to do for
leanSphincs-s what the proposal's spicy variant does for leanSphincs: a smaller signature and cheaper verification,
the same signing time, and lifetimes at least the vanilla ones, at the same h = 26 and keygen. 5 trees of height 5;
each leaf is H(R₀, R₁), the roots of two subtrees of height 3 over WOTS keys of 6 chains of length 6 that sign a
codeword of digit sum 6. The 9-bit table holds all 456 such codewords, sorted as in the proposal, the 56 most
concentrated twice. The digest is 171 bits, one call, and WOTS+C takes target sum 131. Against vanilla
leanSphincs-s: signature −21% (3,300 bytes), verification −18% (213 permutations, 240 compressions), Ledger
signing −3% (155K permutations, 27 s; 158K compressions, 4.8 s), estimated lifetimes 53.4K / 3.47M / 109M (lowered
by the proof gaps: 46.5K / 3.26M / 105M). The proposal gets −25% on both size and verification; leanSphincs-s
starts from a set already tuned for both, so the forest has less to gain. The shape is the knee of the
size/verification front of `scripts/spicy_search.py`.

**These lifetimes are estimates, not proved in Lean.** They use the cover estimate of the note
(section 3): the exact success probability of the cover attack, which for a plain FORS is a closed formula.
The proposal's Lean proofs land 4–17% below that estimate, because they must also bound adaptive forgers
and the WOTS+C neighbour route; we apply the proposal's measured gap at the same subtree size (4% for the
full tree, 6% at 2^20, 13% at 2^13). Each tier still clears its target (20K, 2^21, 2^23).

## leanSphincs-f

leanSphincs-s retuned for signing speed: the same scheme, keygen and tiers, with smaller FORS trees and a WOTS+C target
sum closer to the mean, within a verification budget of 290 Keccak-f permutations. It keeps leanSphincs-s's lifetime
floors (at least 20K signatures on the Ledger tier, at least 10^8 for the full tree).

| | leanSphincs-s | leanSphincs-f |
|---|---|---|
| h | 26 | 26 |
| FORS | k = 13, a = 12 | k = 20, a = 9 |
| WOTS+C | 64 chains of length 4, target sum 128 | 64 chains of length 4, target sum 122 |
| Signature | 4,164 bytes | 4,660 bytes |
| Verification, Keccak-256 | 259 permutations | 290 permutations |
| Verification, BLAKE2s | 273 compressions | 307 compressions |
| Signing, Keccak-256 (Ledger / weak CPU / powerful CPU) | 159K / 155K / 178K permutations | 38K / 35K / 57K permutations |
| Signing time, Keccak-256 | 27 s / 1.2 ms / 0.35 ms | 6.6 s / 0.27 ms / 0.11 ms |
| Lifetime (Ledger / standard / full, after the proof gaps) | 38.2K / 2.87M / 103M | 31.5K / 2.78M / 119M |

Verification, Keccak-256: digest 1 + FORS 180 + WOTS+C 83 + path 26 (BLAKE2s: digest 2 + FORS 191 + WOTS+C 88 + path 26).
Signing is 4.1x faster on the Ledger: FORS rebuilds 20 trees of 512 leaves instead of 13 of 4,096, and the counter
search takes about 1,570 tries instead of 14,700. It is the fastest-signing FORS set with 64 chains of length 4 at h = 26 under the 290-permutation
budget, the floors above and an unchanged keygen. In BLAKE2s, Ledger signing is 38K compressions (1.2 s). Lifetimes
are estimates, as for leanSphincs-s.

**Spicy leanSphincs-f.** The same forest construction: 7 trees of height 3; each leaf is H(R₀, R₁), the roots of
two subtrees of height 3 over WOTS keys of 6 chains of length 4 that sign a codeword of digit sum 4. The 7-bit
table holds the 108 most concentrated of the 120 codewords, the first 20 twice. The digest is 187 bits, one call,
and WOTS+C takes target sum 126. Against vanilla leanSphincs-f: signature −18% (3,812 bytes), verification −23%
(222 permutations, 256 compressions), the same signing (38K permutations, 6.6 s; 39K compressions, 1.2 s),
estimated lifetimes 40.2K / 3.15M / 124M (after the proof gaps: 35.0K / 2.96M / 119M). Verification, Keccak-256:
digest 1 + forest 119 + WOTS+C 76 + path 26 (BLAKE2s: digest 2 + forest 144 + WOTS+C 84 + path 26).

An on-chain Keccak-256 verifier, signers and test vectors are in
[nconsigny/SPHINCS-](https://github.com/nconsigny/SPHINCS-) (`src/keccak/LeanSphincs-FAsm.sol`, 44 K gas per verification).

## Keccak-256

The page follows the proposal's BLAKE2s / Keccak-256 switch. Keccak figures use the cost model of the proposal's
`keccak` branch (`scripts/keccak_model.py` reproduces its 354 and 267 permutations): one Keccak-f permutation per
136-byte block, and the WOTS+C encoding absorbs the few-time tops directly (no separate few-time key hash).
Same parameters for both hashes. Speeds: Ledger 5.8K permutations/s, weak CPU 128M/s, powerful CPU 512M/s, so
Keccak signing on a Ledger takes 27 s for leanSphincs-s (vanilla and spicy) and 6.6 s for leanSphincs-f, and Ledger keygen 5.5 min.

## Threshold, leanSphincs-s

Same ceremony as the proposal's threshold mode (adapted from PRAWNS) and the same verifier, for the FORS
variant. Keygen has to hash every FORS secret inside an MPC. leanSphincs-s is tuned for verification cost
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
python3 scripts/sweep_leansphincs_pruned.py --lg-w 2      # the FORS search; leanSphincs-s is its best set under 5 s, one level taller
python3 scripts/option_a.py                               # threshold cost of FORS sets with the three changes
python3 scripts/sweep_leansphincs_forest.py --check-tom   # reproduces the spicy 307 compressions and lifetimes
python3 scripts/keccak_model.py                          # Keccak-256 costs (the proposal's keccak branch model), incl. leanSphincs-f
python3 scripts/spicy_search.py s                          # the forest search behind spicy leanSphincs-s (f: spicy leanSphincs-f)
```

Requires numpy and scipy. The cost model mirrors `scripts/scheme.py` of the upstream repository.

## License

The site is Tom Wambsgans' work, licensed under MIT OR Apache-2.0 (`LICENSE-MIT`, `LICENSE-APACHE`);
the changes in this fork are under the same terms.
