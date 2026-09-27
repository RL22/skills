# Workspace Contract

Set `SKILL_ROOT` to the directory containing `SKILL.md`. Read
`~/.config/job-search-operator/config.yaml`; require `workspace`,
`candidate_profile`, `application_directory`, `network_file`, `positioning_file`,
and `pipeline_file`. Resolve each relative path against `workspace`; retain
absolute paths. Define operational paths from those resolved config values:

```sh
SKILL_ROOT=/absolute/path/to/job-search-operator
WORKSPACE=<resolved workspace>
PROFILE=<resolved candidate_profile>
APPLICATIONS=<resolved application_directory>
NETWORK=<resolved network_file>
POSITIONING=<resolved positioning_file>
PIPELINE=<resolved pipeline_file>
APPLICATION="$APPLICATIONS/company-target-role.md"
```

After resolving the workspace, load only state required by the selected route:
`PROFILE` for candidate facts or claims, `PIPELINE` and the matching
application record for opportunity work, `NETWORK` for relationship or contact
work, and `POSITIONING` for positioning work or an external signal. The profile
is the canonical source for contact details, held titles, dates, education,
tools, and verified stories when it is loaded. Setup and config recovery may
run without an existing config, profile, or pipeline.

If configuration or workspace is unavailable, ask for the known workspace. If
the user chooses a new one, run the safe initializer against the explicit path:

```sh
python3 "$SKILL_ROOT/scripts/initialize_workspace.py" "$WORKSPACE"
```

After it succeeds, create the config only if it does not exist. Use this exact
schema, replacing only `/chosen/workspace` with the selected absolute path:

```yaml
workspace: /chosen/workspace
candidate_profile: CAREER_FACTS.md
application_directory: applications
network_file: NETWORK.md
positioning_file: POSITIONING_LOG.md
pipeline_file: README.md
```

Do not make the initializer write outside its target workspace. Do not guess a
workspace or overwrite a config or workspace file; the initializer creates only
missing files and preserves existing content.

## Application records

Use one application Markdown file per company and target role. Search existing
application metadata, the application directory, and pipeline for that identity
first. Name a new record with a lowercase-hyphenated company-role slug, such as
`acme-senior-product-manager.md`; update the existing match and never duplicate
it. Preserve user edits and make the smallest targeted change.

## Required records of work

For opportunity work, after meaningful research, evaluation, drafting, or a
decision, update the application log and pipeline with date, action,
status/result, and one next action. After outreach, update the network record.
For standalone network-only work, update only the network record. After an
external signal changes an audience, claim, or message, update the positioning
log. Do not log hypothetical work as completed.

Write claim provenance in the application’s `Sources and Evidence` table:
`user-provided`, `sourced`, or `inference`, plus source URLs and access dates.
Mark nonessential facts unknown and continue; ask only when an unknown blocks a
truthful, actionable result.
