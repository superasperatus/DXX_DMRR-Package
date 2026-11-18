# 02 - Saved collection output

The study archive is kept in this folder, separate from any new collection runs:

- [raw](raw): original response attempts and exclusion notes.
- [input_manifest.json](input_manifest.json): package-relative paths, source
  details, and checksums for all 41 included CSVs.

The archive manifest also covers [collection stimuli](../01_collection/stimuli)
and [paper references](../00_documentation/references). Those are inputs, not
collection output.

Do not edit the archived CSVs. Processing verifies their hashes before analysis.
Optional new calls create separate timestamped folders under the Git-ignored
`new_runs` directory. Each contains `collection_config.json`, `stimuli.csv`,
and its own response files. Process these runs separately from the archive.

To process the archive, select `--input 02_output`. To process a new run,
select its individual folder, not the `new_runs` parent. No archive-manifest
editing is needed for new runs.

Next: [03_processing](../03_processing/README.md).
