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
- Manual cloud updater and its reusable Pages deployment succeeded: https://github.com/xhq52465840/overseas-opportunity-radar/actions/runs/43843890527
- Actual source status: success, incremental, 3 public requests, 24 cache hits, 50 recent cards, 2 new projects/profiles; total 12,592 projects and 795 profile sources. This was not a full directory recrawl.
- Export version consistency deployment also succeeded: https://github.com/xhq52465840/overseas-opportunity-radar/actions/runs/43843851646
- Scheduled GitHub execution is best effort and upstream failure must be read separately from workflow success.
- Rolling-year launch/payment filters deployed successfully: https://github.com/xhq52465840/overseas-opportunity-radar/actions/runs/43844797790
- Verified 2026-11-16 18:01 Asia/Shanghai (UTC+8): HTTPS homepage has all four date filters; live JavaScript matches tested code; live index contains 12,592 projects, metadata shows 795 profiles and 25 prior official-content checks, first detail chunk has 100 records, and source status is success/incremental/3 requests.
- Existing explicit public launch statements support only 4 strict recent-paid records, plus 316 recent-founded paid candidates awaiting launch evidence. Launch statements are product/founder self-reports, not independent date audits. The complete pool is retained.
- Latest safety audit: 1,856 data files/archive members, zero unresolved common credential/unsafe URL/markup findings. This is not a reputation audit of every external website. Python: 28 tests passed; frontend: 26 assertions passed.
- Replacement sanitized ZIP has 12,592 records; CRC and JSON count/version verified, and public ZIP/JSONL byte checksums match local audited files. ZIP SHA256: 078ed3b9601bd35202a422b00667755f47afd749e518ae0bf159ecb99ebd5271
- Downloads: https://raw.githubusercontent.com/xhq52465840/overseas-opportunity-radar/main/data/trustmrr-data.zip and https://raw.githubusercontent.com/xhq52465840/overseas-opportunity-radar/main/data/projects.jsonl
- Automated tests and live HTTP/data checks are complete; no real-browser visual QA is claimed.

Repository: https://github.com/xhq52465840/overseas-opportunity-radar
Actions: https://github.com/xhq52465840/overseas-opportunity-radar/actions
