# 01 - Collection inputs and optional collection

This directory contains the study stimuli and an optional collector. To reproduce the
archived results, skip collection and use the responses already in
[02_output](../02_output/README.md).

All stimulus inputs are in [stimuli](stimuli):

- [pool_final_200.csv](stimuli/pool_final_200.csv): the main 200-item pool, used
  by default.
- [robustness_prompt_subsample.csv](stimuli/robustness_prompt_subsample.csv):
  the fixed 20-item prompt-robustness subset.
- [robustness_temp10_subsample.csv](stimuli/robustness_temp10_subsample.csv):
  the fixed 40-item temperature subset.

Questions and options come from these CSVs; [prompts.py](prompts.py) adds fixed
instructions. Use `--pool` to select another stimulus CSV. Offline processing
reads the same pools without importing or executing collection code.

From the package root, print a plan without network calls or output writes:

```powershell
python 01_collection\main.py --dry-run --model gpt-4.1 --items 1 --trials 1
```

To collect new responses, configure [config.py](config.py), supply credentials
through environment variables, and explicitly pass `--execute`. All endpoints
are blank by default. Check provider access, model availability, and costs
before enabling live calls.

Each live invocation creates a distinct timestamped folder under
`02_output/new_runs` by default, after endpoint validation:

```text
run_<UTC timestamp>_<unique suffix>/
    collection_config.json      Selected items, models, trial target, parameters
    stimuli.csv                 Byte-for-byte snapshot of the supplied pool
    raw_<model>_commercial.csv   Every successful and failed attempt
```

The collector prints the run location and a command for
[processing](../03_processing/README.md). Select that individual run folder;
processing never substitutes the archived responses.

Use `--output` to name a folder yourself. Reusing an existing run folder with
matching settings resumes missing successful slots. A changed or missing pool
snapshot is rejected. Archives, stimuli, and paper references cannot be used as
collection destinations.

Custom pools must include the complete [stimulus schema](../00_documentation/CODEBOOK.md):
item ID, source, bias category, question, both options, and `ab_flipped`.
If you change the prompts, preserve the corresponding source code alongside
the new data so that readers can recover the wording used.
