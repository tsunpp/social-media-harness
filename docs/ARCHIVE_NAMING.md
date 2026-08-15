# Human-readable archive naming

The canonical archive ID remains `SMmmddyyyyNN`. It is the immutable identity used for date allocation, lookup, verification, references, and OpenClaw handoff.

New archive directory names use `SMmmddyyyyNN--content-slug`, for example `SM0813202601--vape-liquid-diamond-b`.

The content slug:

- is derived from the approved final story subject;
- contains 2-5 lowercase English/alphanumeric keywords separated by hyphens;
- may end in `a` or `b` when the variant is content-distinguishing;
- describes content only;
- never contains mutable status words such as `ready`, `approved`, `pending`, or `published`.

Every index and new manifest records `archive_id`, `archive_name`, and `content_slug` separately. Historical immutable directories are not renamed; their readable names live in the canonical index. Runtime lookup supports both legacy ID-only directories and new readable directories.
