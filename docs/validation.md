# Validation record

Verified on Python 3.9.10 and Node.js 22.23.1.

- 15 automated tests passed: deterministic replay, duplicate removal, citation integrity, same-service correlation, stale/future change exclusion, threshold validation, timezone validation, healthy-window behavior, all three scenarios, report output, HTTP assets, SQLite persistence, invalid routes/scenarios, and cross-origin write rejection.
- JavaScript syntax check passed with `node --check web/app.js`.
- Browser verification passed for scenario replay, finding display, citation navigation to the correct raw audit record, and Markdown report download.
- The dashboard was visually inspected at the available browser viewport. A full-page preview is supplied alongside the project.

Reproduce automated checks from the project directory:

```sh
python3 -m unittest discover -s tests -v
node --check web/app.js
```

No cloud services or external APIs were used. This does not validate live GCP ingestion, production security, distributed behavior, or cloud-scale capacity.
