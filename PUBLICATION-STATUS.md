# Security and publication status

Initial publication was rejected by GitHub push protection because an upstream Website field contained a possible credential. The rejected content is not being resubmitted.

## Security preparation complete
- All 12,590 project records are retained; unsafe credential-like fields/URLs are omitted with redaction markers.
- Every public fact string, URL, raw evidence file, JSONL/Markdown output and ZIP member was checked. The final audit found zero unresolved issues; no matched value was printed, validated or used.
- URL schemes, userinfo, credential-like query/fragment parameters and unsafe markup are checked at export boundaries. The UI uses DOM creation/textContent, not HTML injection.
- The updater, all exporters and CI have the same safety boundary. GitHub protection remains unchanged; no allow-secret URL or alternate transport is used.
- Only unpublished local history was cleaned. Original private historical files must not be redistributed.

## Live publication verification
The next step is a normal protected push of the sanitized initial commit and Pages deployment. Until a successful deploy and HTTPS/data checks are recorded, this document does not claim the site is live.

Repository: https://github.com/xhq52465840/overseas-opportunity-radar
Actions: https://github.com/xhq52465840/overseas-opportunity-radar/actions
