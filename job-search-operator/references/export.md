# Export Application Materials

Use the workspace contract. Set `SKILL_ROOT` to the directory containing
`SKILL.md`; use its resolved `PROFILE`, `APPLICATIONS`, `APPLICATION`, and
`PIPELINE` paths. Export only on the user's explicit request. Use the
application Markdown as the source and preserve the canonical profile as the
authority for all candidate claims.

## Set a safe output path

Resolve `WORKSPACE` before calculating any output path. Write only beneath the
approved resolved root `"$WORKSPACE/exports"`, in
`"$WORKSPACE/exports/<company-role-slug>/"`. Require `exports` and every
existing output component to be non-symlinked and contained beneath resolved
`WORKSPACE`; reject rather than follow a symlinked `exports` or slug component.

Form `<company-role-slug>` from the company and target role: lowercase;
transliterate or strip to ASCII where possible; replace each run outside
`[a-z0-9]` with one `-`; then trim `-`. Reject an empty slug, control
characters, path separators, `..`, absolute paths, or any other unsafe path
component. Use only this validated slug as the output directory. Before writing
and again after creating directories, resolve the final artifact targets and
assert that both remain beneath the resolved `"$WORKSPACE/exports"` directory.

Preserve existing files. Overwrite a file only after the user explicitly
approves that exact resolved path. Use workspace-relative paths in records.

## Validate and prepare

Run the application validator before export and resolve every error:

```sh
python3 "$SKILL_ROOT/scripts/validate_application.py" "$APPLICATION" "$PROFILE" \
  --applications-dir "$APPLICATIONS"
```

Create clean, separate Markdown source for the resume and cover letter. Remove
internal scores, assessments, notes, instructions, and unresolved content. Do
not export until the validator passes. If a requested fact is unsupported or
unresolved, stop that document and ask for the information needed to make it
truthful.

## Create DOCX files

Require both a DOCX-creation capability and a plain-text-extraction capability
before producing files. If either capability is unavailable, keep the clean
Markdown and report the export as blocked or unverified; do not produce a
DOCX or substitute a PDF.

Use the available capabilities to create separate resume and cover-letter DOCX
files in the approved output directory. Derive a safe, readable candidate name
from the canonical profile and use candidate-company-role leaf names:
`[Candidate-Name]-[Company]-[Role]-Resume.docx` and
`[Candidate-Name]-[Company]-[Role]-Cover-Letter.docx`. Derive the Candidate,
Company, and Role placeholders from the canonical profile and application; the
bracketed form is a generic template, not a hardcoded candidate identity.
Normalize every dynamic component into a safe filename component and preserve
the validated output directory rules above.

Use a conventional font, standard headings, body contact details, and a
single-column layout. Exclude tables, text boxes, sidebars, icons, images,
charts, headers, footers, comments, tracked changes, and hidden content.

After creation, extract plain text from each DOCX and check reading order,
contact fields, headings, dates, titles, and candidate claims against the
validated Markdown and profile. Correct any mismatch, then record the export
date and workspace-relative file paths in the application's log. In the
pipeline Notes field, write `Exported YYYY-MM-DD: relative/[Candidate-Name]-
[Company]-[Role]-Resume.docx; relative/[Candidate-Name]-[Company]-[Role]-
Cover-Letter.docx`. Never set or change `Date applied` for an export.
Record a submission date and submitted status only after the user confirms
actual submission; never treat file generation as submission.
