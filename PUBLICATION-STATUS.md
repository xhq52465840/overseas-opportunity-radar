# Security and publication status

Initial publication was rejected by GitHub push protection because an upstream Website field contained a possible credential. The rejected content is not being resubmitted.

## Security preparation complete
- All 12,590 project records are retained; unsafe credential-like fields/URLs are omitted with redaction markers.
- Every public fact string, URL, raw evidence file, JSONL/Markdown output and ZIP member was checked. The final audit found zero unresolved issues; no matched value was printed, validated or used.
- URL schemes, userinfo, credential-like query/fragment parameters and unsafe markup are checked at export boundaries. The UI uses DOM creation/textContent, not HTML injection.
- The updater, all exporters and CI have the same safety boundary. GitHub protection remains unchanged; no allow-secret URL or alternate transport is used.
- Only unpublished local history was cleaned. Original private historical files must not be redistributed.

## Live publication verification
- Sanitized initial commit: af61736d0df85b012bb5c009b05b2f0b36b2e923; normal protected push accepted.
- First Pages deployment succeeded: https://github.com/xhq52465840/overseas-opportunity-radar/actions/runs/43843309336
- Verified 2026-11-16 17:51 Asia/Shanghai (UTC+8): HTTPS homepage, index, metadata, first detail chunk and annotations all returned 200. Index contains 12,590 projects; coverage records 793 profiles and 25 prior official-content checks.
- Live site: https://xhq52465840.github.io/overseas-opportunity-radar/
- GitHub secret scanning and secret-scanning push protection are enabled. No protection was bypassed or disabled; no rejected commit was republished.
- Follow-up export check caught an embedded metadata version not updated after redaction. The exporter now synchronizes all fact hashes, with an offline regression test; no project facts were removed.
- Manual cloud updater validation is still pending at this revision. Scheduled GitHub execution is best effort and upstream failure must be read separately from workflow success.
- Automated tests and live HTTP/data checks are complete; no real-browser visual QA is claimed.

Repository: https://github.com/xhq52465840/overseas-opportunity-radar
Actions: https://github.com/xhq52465840/overseas-opportunity-radar/actions
