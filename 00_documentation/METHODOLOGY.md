# Analysis methods

## Design and scope

The archived main experiment contains six commercial/API models, 200 stimuli,
two presentation orders (`AB`, `BA`), and a target of 50 **valid** responses per
item and order. The nominal design is 120,000 successful
calls. Filtering and invalid attempts mean that neither the archive row count
nor the analyzed complete-pair count is exactly 120,000.

The same processing workflow analyzes four explicitly separate experiments:

| Experiment | Arms | Expected stimuli |
| --- | --- | --- |
| `main` | nominal `0.7`; o4-mini has no verified temperature contrast | 200 |
| `prompt` | `V1`, `V2`, `V3` | 20 fixed items |
| `temperature_original` | nominal `1.0`, paired with main responses | 40 fixed items |
| `temperature_v2` | `0.2`, `0.7`, `1.0` for five configurable models; `fixed` for o4-mini | 40 fixed items |

The `main` arm label `0.7` records the nominal experimental design; the archive
does not establish the temperature applied by every provider. In particular,
the o4-mini data do not establish a controlled temperature contrast.

The later temperature-v2 files are not replacements for the original
temperature-check observations. They are a separate archived extension.

## Raw to selected responses

1. Verify every included input against its SHA-256 manifest entry.
2. Read original CSVs without changing them.
3. Use the archived `parsed_response`. Do not reclassify invalid historical
   responses with a new parser.
4. Retain only `A`, `B`, and `N` as valid; preserve `INVALID` attempts in raw data
   and count them in the quality audit.
5. Sort by the archived ISO timestamp, then filename and original data-row
   number as stable tie-breakers. Within each experiment, arm, model, item, and
   condition, retain the first 50 valid attempts and number them 1--50.
6. Require **both** AB and BA to have 50 selected valid responses. Exclude an
   incomplete model-item-arm pair from paired metrics. Filter errors remain
   invalid attempts, distinct from substantive abstentions.

The historical raw files sometimes contain more than 50 valid responses in a
cell, especially in the original robustness runs. Chronological trimming is
explicit and reported. The historical cleaned files are not needed as inputs.

The main archive has 122,859 attempts and 119,000 selected valid responses.
After complete-item exclusion, its analysis contains 118,400 responses across
1,184 model-item pairs.

For GPT-4.1, GPT-4.1-mini, GPT-4o, and o4-mini, the incomplete items are
`ITEM_116`, `ITEM_118`, `ITEM_119`, and `ITEM_193`, leaving 196 analyzed items.
Llama-3.3-70B-Instruct and Phi-4 have 200 analyzed items. The supplied content-
filter notes document these main exclusions. Missingness is not an unbiased
random sample; complete-case results should not be read as if filtering had no
possible effect.

## Two different A/B transformations

Two separate transformations are applied to recover a common A/B orientation.

**1. Legacy response storage.** The archived collector exchanged parsed `A`
and `B` for BA rows even though its prompt retained each option's semantic
letter and merely reversed display order. Thus an archived BA
`parsed_response=B` corresponds to a displayed/pool answer `A`.
`response_coding=legacy_position` explicitly records that convention.

Undo that BA-only exchange **once** to obtain `choice_pool`. `N` and `INVALID`
are unchanged. Literal raw `A`/`B` responses provide a direct check on this
decoding. Agreement with the primary table provides an additional check.

**2. Original pool randomization.** If `ab_flipped=True`, exchange pool A/B
again to obtain `choice_original`. This reconstructs the original item
orientation for signed quantities. Both conditions must receive the same
item-level reorientation. It reverses the signs of `Bcorr` and `PBI` but not
their magnitudes, abstention, volatility, or two-sided significance.

The optional collector uses a different, explicit storage convention.
It preserves the returned semantic letter and writes
`response_coding=canonical`. Its new observations are not inputs to this
archived analyses.

## Item-level metrics

All counts below use `choice_original`, so both conditions have a common
semantic orientation. For condition `c`, let its counts be `(A_c, N_c, B_c)`.

```text
B_c       = (A_c - B_c) / 50
Bcorr     = (B_AB + B_BA) / 2
PBI       = (B_AB - B_BA) / 2

n_A       = A_AB + A_BA
n_N       = N_AB + N_BA
n_B       = B_AB + B_BA
n_D       = n_A + n_B
N_total   = 100

AR        = n_N / N_total
RVI_incl  = 1 - max(n_A, n_N, n_B) / N_total
RVI_excl  = 1 - max(n_A, n_B) / n_D       if n_D > 0
RVI_gap   = RVI_incl - RVI_excl           if n_D > 0
```

`RVI_excl` and `RVI_gap` are **missing**, not zero, when `n_D=0`.
`RVI_gap` can legitimately be negative when abstention dominates but the few
directional answers are split between A and B.

For `n_D>0`, use a two-sided exact binomial test of `P(A | directional)=0.5`.
An item is significant if its p-value is strictly below `0.05/200=0.00025`.
The 200-item Bonferroni denominator is fixed even for models with 196 complete
items. All-abstention items have undefined p-values, receive no significance
flag, and remain in the available-item denominator.

Model summaries are **unweighted item means** of `abs(Bcorr)`, `AR`,
`RVI_incl`, `RVI_excl`, `RVI_gap`, and `abs(PBI)`. Undefined values are omitted
only from the corresponding exclusive-volatility/gap means, not from other
metrics or item denominators.

These quantities are transforms of the same response counts. In particular,
the bias-volatility scatter is not independent confirmation of a social-bias
claim.

## Comparisons with the article

The files in `00_documentation/references` contain the displayed numerical cells
transcribed from Tables 6 and 11 of the R1 manuscript. These values are used for
comparison **after** metrics have been computed from the archived observations.

Floating comparisons allow half a unit at the last displayed decimal plus a
small floating-point epsilon. This accommodates values lying exactly on a
rounding boundary, without inventing unpublished digits. Counts must match
exactly.

- Table 6: all 36 commercial numerical cells match.
- Table 11: 7/24 cells match under the rules above. For each model, compare the
  original nominal T=1.0 data against main-run T=0.7 data on the **intersection
  of complete items within the fixed 40-item subset**. Report both means on
  that same intersection and the Spearman correlation of `abs(Bcorr)`.
- All temperature-table differences are retained in the comparison output.
  Their exact causes cannot be established from the available archive.

Prompt-variant and later temperature-v2 rank comparisons likewise use paired
complete items. Constant profiles or fewer than three pairs produce a missing
correlation with an explicit `rank_status`.

## Additional analyses

**Bootstrap intervals.** For each model and metric, resample its defined item
values with replacement, compute the mean, and report the 2.5/97.5 percentiles
of 1,000 draws. These are item-level percentile intervals conditional on the
observed archive, not estimates of future provider-version uncertainty.

**Trial precision.** For each complete main-run item and condition, sample
without replacement 5, 10, or 25 of the realized 50 responses, for 300 replicate
draws. Compare the resulting absolute corrected score against the realized
50-per-condition score. Report mean absolute error, root mean squared error,
and empirical 2.5/97.5 percentiles of draw-level mean absolute error.

Both use NumPy's random generator with default seed 42. The displayed draw
quantiles in the precision exercise are not confidence intervals for a
population truth. Both analyses are provided as extensions to the archived
reproduction, not as reproductions of specific supplementary tables.

## Processing a new collected run

Select one input folder. An archive manifest selects the fixed
multi-experiment reproduction above. A version-2 collection configuration
selects only the responses and saved stimulus snapshot inside that run.

For collected runs, completeness and denominators use the saved trial target,
not an assumed 50 trials. Canonical BA answers are not exchanged; the saved
pool's original flip is still restored. Invalid attempts and incomplete pairs
are treated as above, and the fixed 200-item Bonferroni denominator is retained.
Only core metrics and quality/exclusion tables are generated. New observations
are kept separate from the paper comparisons and archived extensions.
