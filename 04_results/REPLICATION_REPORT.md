# Offline reproduction report

The analyses below are reproduced from archived commercial/API-model responses.
This report is generated from the included data; no new model responses
are collected.

## Table 6: commercial models

**36/36 reference cells match at the paper's displayed precision.**
Continuous values allow half a unit of rounding; counts must match exactly.

| model_id | n_items | mean_abs_Bcorr | mean_AR | mean_RVI_gap | mean_abs_PBI | significant_items |
| --- | --- | --- | --- | --- | --- | --- |
| Llama-3.3-70B-Instruct | 200 | 0.925 | 0.043 | 0.028 | 0.060 | 191 |
| Phi-4 | 200 | 0.838 | 0.142 | 0.047 | 0.057 | 180 |
| gpt-4.1 | 196 | 0.858 | 0.137 | 0.036 | 0.037 | 178 |
| gpt-4.1-mini | 196 | 0.863 | 0.124 | 0.028 | 0.036 | 176 |
| gpt-4o | 196 | 0.795 | 0.201 | 0.036 | 0.027 | 167 |
| o4-mini | 196 | 0.904 | 0.086 | 0.029 | 0.012 | 187 |

Archived attempts: 122,859. Selected valid responses:
119,000. Complete-pair analysis:
118,400. See [quality](tables/data_quality.csv) and
[exclusions](tables/excluded_items.csv).

## Table 11: original temperature check

**7/24 reference cells match.**
[The comparison table](tables/table11_comparison.csv) reports every difference.
The available archive does not recover every manuscript value under the
complete-pair rules.
The later temperature-v2 archive is separate; o4-mini is not a verified
temperature contrast.

## Resampling and limits

Bootstrap: 1000 draws. Trial precision: 300 draws at
5, 10, and 25 trials per condition. Seed: 42.
These are provided as additional analyses, not reproductions of the article's
supplementary tables.
Directional consistency alone is not evidence of stereotyping.
Undefined exclusive-volatility values remain missing, not zero.

Run [03_processing/main.py](../03_processing/main.py) with `--input 02_output` from the package root.
See [methodology](../00_documentation/METHODOLOGY.md) and [output map](../00_documentation/OUTPUT_MAP.md).
