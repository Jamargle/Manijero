# `hosting_provider_review` Appendix

## Repository research

- `backend/README.md` documents local FastAPI `/health` and `/ask`; no deployment container or host is configured.
- Android/desktop endpoints are currently local development URLs; campaign configuration is explicit.
- MasterPlanV3's own-server/Cloudflare proposal is archived and explicitly not current evidence.

## Implementation plan and tasks

1. Inspect the actual server's owner, connectivity, maintenance window, capacity, power/backup, and recovery capability.
2. Identify one managed-tunnel candidate, a managed-host fallback, and a private artifact-delivery option; read current official terms, privacy/data processing, availability, cost, limits, and exit documentation for each.
3. Map request data, access logs, service logs, and retention for each candidate; include that no hosted LLM is used.
4. Record the owner's selection, review date, source links, unresolved issues, and conditions that trigger re-review.

## Verification plan

- Confirm every provider claim links to a current official source and records an access date.
- Check the decision does not claim legal compliance or zero cost without evidence.
- `git diff --check` is the focused documentation check.

## Evidence to capture

- Server readiness notes, provider comparison, official-source links/access dates, and signed owner decision.

## Feature evidence

### Status and method

Documentation-only review completed on **2026-10-27**. No provider account, domain, server
inspection, deployment, load test, backup/restore drill, or real-user question was used. Each
provider statement below is a dated reading of a public official page fetched over HTTPS on that
date; the exact page and section are in the source table. "Not verified" means the reviewed pages
did not establish the fact and this review did not test it.

### Option comparison matrix

| Requirement | Owned server + Cloudflare Tunnel | Fly.io fallback | Cloudflare R2 (artifacts) | Gemini (generation) |
|---|---|---|---|---|
| Role assessed | Cloudflare Tunnel conditionally selected as transport; owned server blocked | Managed-host fallback | Private artifact delivery candidate | Gated future generation |
| Terms retrieved | Self-Serve Agreement last updated 2025-09-12; DPA v6.4 effective 2026-04-03 [CF-TOS][CF-DPA] | ToS effective 2026-04-29; privacy statement effective 2026-10-24; **DPA text not retrieved** [FLY-TOS][FLY-PRIV] | Same Cloudflare terms and DPA [CF-TOS][CF-DPA] | Additional Terms effective 2026-03-23 [GEM-TERMS] |
| Data location | Owner premises; physical location and security unknown | Public statement says servers are in the United States; `fra` Machines are priced for Frankfurt [FLY-PRIV][FLY-PRICE] | Cloudflare network; storage location and access logs **not verified** | Spain is listed on Google's available-regions page [GEM-REGIONS]; logs may be stored transiently or cached in any country with Google facilities [GEM-TERMS]; serving-region routing **not reviewed** |
| Encryption in transit | TLS at Cloudflare edge with Universal SSL; outbound-only tunnel, no public origin IP [CF-TLS][CF-TUNNEL][CF-START] | Fly TLS termination **not verified in this review** | HTTPS S3 API endpoint; presigned URL is the authorization [CF-R2URL] | HTTPS API; not exercised |
| Access control | Current API declares no security scheme and has no auth dependency; must be built [REPO-OPENAPI][REPO-ASK] | Same application gap; host does not add auth | Presigned bearer URL, expiry 1 second–7 days, cannot use a custom domain [CF-R2URL] | API key plus Paid-tier gate; no call exists |
| Logs and retention | HTTP request logs not retained by default; Logpull retention needs enabling and is Enterprise-only; Customer Logs have no fixed period [CF-RETAIN][CF-LOGPULL][CF-PRIV] | App logs are stdout; Grafana search keeps 7 days; support/abuse staff can process platform log lines including stdout [FLY-LOG][FLY-SUB] | R2 access logging **not verified** | Abuse monitoring keeps prompts/context/output 55 days and flagged content may be human-reviewed [GEM-ABUSE]; project logs default to 55 days for projects created on/after 2026-10-26, and shared datasets may be read/annotated by human reviewers [GEM-LOGS] |
| Support and SLA | Free and pay-as-you-go have no SLA; Free can only open billing/account/registrar cases; support in English [CF-SUPPORT] | Community support free; email/portal needs a paid package or legacy plan; no SLA found on reviewed pages [FLY-SUPPORT] | Same Cloudflare support model [CF-SUPPORT] | Google support terms **not reviewed** |
| Limits | Tunnel available on all plans [CF-TUNNEL]; the 1,000-tunnel allowance and $4.50/additional tunnel are Tunnels-for-Platforms capacity pricing, irrelevant to one pilot tunnel [CF-PLAT]; baseline recommends two hosts per location [CF-SYS] | Machine sizes and regional prices published; no free tier [FLY-PRICE] | 10 GB-month + 1M Class A + 10M Class B free monthly [CF-R2PRICE] | Quotas/limits **not reviewed**; exact model/revision and tier unselected; Paid required for EEA API clients [GEM-TERMS] |
| Cost at pilot scale | One tunnel $0; domain and any paid plan are non-zero [CF-TUNNEL][CF-REG][CF-SUPPORT] | 1 GB `fra` Machine $7.73/30 days plus volume and egress [FLY-PRICE] | Free tier likely covers a few builds; $0.015/GB-month after [CF-R2PRICE] | Example only: `gemini-3.8-flash` $0.75 input/$3.75 output per 1M through 2026-12-31; $1.50/$7.50 from 2027-01-01 [GEM-PRICE] |
| Exit | DNS and tunnel routes portable; DPA delete-or-return [CF-DPA §3.1(i)] | Customer Data returned on termination [FLY-TOS §9 "Effect of Termination"]; backup is not Fly's obligation [FLY-TOS §4.1] | Delete objects or rotate credentials; a presigned link cannot be revoked individually before expiry [CF-R2URL] | Keep the call absent and the key unset; there is no runtime flag gate |
| Verdict | **Conditional, blocked on owner attestation and API controls** | **Not approved** | **Candidate** | **Disabled by default** |

### Source table

All sources accessed **2026-10-27**. Repository sources are local files reviewed on the same date.

| ID | Official source (direct URL) | Exact section or location | Accessed |
|---|---|---|---|
| CF-TUNNEL | https://developers.cloudflare.com/tunnel/ | "Overview": outbound-only connections, "Each tunnel maintains four long-lived connections to two Cloudflare data centers", available on all plans | 2026-10-27 |
| CF-SYS | https://developers.cloudflare.com/tunnel/platform/system-requirements/ | "Baseline recommendations": two dedicated hosts per location, 4 GB RAM, 4 CPU cores, 50,000 ports per host | 2026-10-27 |
| CF-START | https://developers.cloudflare.com/tunnel/get-started/ | "Prerequisites": Cloudflare account, domain on Cloudflare, server/VM, outbound port 7844 | 2026-10-27 |
| CF-TLS | https://developers.cloudflare.com/ssl/edge-certificates/ | "Overview": Universal SSL provides automatic, free edge certificates for the apex domain and first-level subdomains, provisioned automatically on full setups | 2026-10-27 |
| CF-PLAT | https://developers.cloudflare.com/tunnel/features/tunnels-for-platforms/ | "Pricing" (Tunnels for Platforms): first 1,000 tunnels in every account included; $4.50 per additional tunnel per month; inactive tunnels count toward the limit | 2026-10-27 |
| CF-TOS | https://www.cloudflare.com/terms/ | "Cloudflare Self-Serve Subscription Agreement", Last Updated September 12, 2025: §2.5 Customer Content and Network Data, §2.6 Free & Trial Services, §4.2 Price Changes, §8 Termination of Use, §11 Disclaimers, §14 Changes to this Agreement | 2026-10-27 |
| CF-DPA | https://www.cloudflare.com/cloudflare-customer-dpa/ | Version 6.4, effective April 3, 2026: §3.1(i) delete-or-return, §4.4 sub-processor notice and objection, §6.2 standard contractual clauses, Annex 1 categories and retention period | 2026-10-27 |
| CF-PRIV | https://www.cloudflare.com/privacypolicy/ | Effective November 4, 2025: §11 Data Retention | 2026-10-27 |
| CF-RETAIN | https://developers.cloudflare.com/logs/logpull/enabling-log-retention/ | "Enabling log retention": HTTP request logs are not retained by default; retention must be enabled and can be turned off | 2026-10-27 |
| CF-LOGPULL | https://developers.cloudflare.com/logs/logpull/ | "Overview": Logpull is available to Enterprise plan customers; described as a legacy feature | 2026-10-27 |
| CF-LOGPULL-BASICS | https://developers.cloudflare.com/logs/logpull/understanding-the-basics/ | "Data retention period": queries start 1 minute in the past and go back at least 3 days and up to 7 days; Logpush recommended for longer durations | 2026-10-27 |
| CF-SUPPORT | https://developers.cloudflare.com/support/contacting-cloudflare-support/ | "Submit a support case" (Free users: billing, account, registrar only); "Service Level Agreements and Objectives" (pay-as-you-go and Free: no SLAs); "Supported languages" (English) | 2026-10-27 |
| CF-PLANS | https://www.cloudflare.com/plans/ | Plan comparison, "Uptime SLA" row: Free and Pro have no value; Business and Contract show 100% | 2026-10-27 |
| CF-REG | https://www.cloudflare.com/domains/ | "At cost": registration, transfer, and renewal prices at or below registry and ICANN charges | 2026-10-27 |
| CF-R2URL | https://developers.cloudflare.com/r2/api/s3/presigned-urls/ | "Expiry": 1 second to 7 days (604,800 seconds); "Custom domains": S3 API domain only, not custom domains | 2026-10-27 |
| CF-R2PRICE | https://developers.cloudflare.com/r2/pricing/ | "R2 pricing" table (Standard): $0.015/GB-month, $4.50/M Class A, $0.36/M Class B, egress free; "Free tier": 10 GB-month, 1M Class A, 10M Class B | 2026-10-27 |
| FLY-TOS | https://fly.io/legal/terms-of-service/ | Effective April 29, 2026: §2 "Customer Data" licence, §4.1 Customer Warranty (no backup obligation), §5 Disclaimer, §9 "Effect of Termination" (return of Customer Data), §12 Agreement Updates | 2026-10-27 |
| FLY-PRIV | https://fly.io/legal/privacy-policy/ | Effective October 24, 2026: application data processor/controller split; servers in the United States; "Changes to our Privacy Statement" (at least 30 days' notice) | 2026-10-27 |
| FLY-SUB | https://fly.io/legal/sub-processors/ | "AI vendors": no volume contents or request bodies sent to AI vendors; support/abuse can process account metadata, ticket text, and platform log lines including stdout; "Changes": DPA §6.3, 30-day listing, 10-day objection | 2026-10-27 |
| FLY-LOG | https://docs.fly.io/monitoring/logging-overview | "Logging overview": app logs are process stdout; "Search logs": Grafana retains logs for 7 days; "Export logs": Fly Log Shipper | 2026-10-27 |
| FLY-PRICE | https://docs.fly.io/about/pricing | "What you pay for" (256 MB $2.19, 512 MB $3.69, 1 GB $6.70, 1 GB `fra` $7.73, volume $0.15/GB-month, egress $0.02/GB Europe, support $29/$199); "Is there a free tier? No" | 2026-10-27 |
| FLY-SUPPORT | https://docs.fly.io/about/support | "Fly.io status" (status page); "Community forum" (everyone); "Email support" (Standard/Premium/Enterprise or legacy plans) | 2026-10-27 |
| FLY-HEALTH | https://docs.fly.io/reference/health-checks | "Important": failing health checks can stop request routing but Machines do not restart or stop automatically | 2026-10-27 |
| GEM-TERMS | https://ai.google.dev/gemini-api/terms | Effective March 23, 2026: "Age Requirements" (18+); "Use Restrictions" (Paid required for API clients in EEA/Switzerland/UK); "Paid Services" → "How Google Uses Your Data" (no product improvement; prompts/responses logged for abuse/legal; transient storage anywhere Google facilities); "Payment Terms" (price changes effective 30 days after posting); "Disclaimers" (experimental) | 2026-10-27 |
| GEM-ABUSE | https://ai.google.dev/gemini-api/docs/usage-policies | "Abuse monitoring" → "How We Handle Data": prompts, contextual information, and output retained fifty-five (55) days for abuse prevention and required legal/regulatory disclosure; "How We Investigate Potential Issues": authorized Google employees may assess flagged prompts/outputs through an internal governance assessment and review platform, solely for policy enforcement, and not to train or fine-tune models except for policy enforcement | 2026-10-27 |
| GEM-REGIONS | https://ai.google.dev/gemini-api/docs/available-regions | "Available regions": Spain is listed among the available regions for Google AI Studio and the Gemini API | 2026-10-27 |
| GEM-LOGS | https://ai.google.dev/gemini-api/docs/logs-policy | "Data logging and sharing": logging on by default for Generate Content API calls in projects created on or after 2026-10-26; "How we use your data": 55-day default maximum, configurable to 7/14/28/55 days; datasets have no set retention and use Unpaid-Service terms; shared data may be read, annotated, and processed by human reviewers with identifying links removed before reviewer access | 2026-10-27 |
| GEM-PRICE | https://ai.google.dev/gemini-api/docs/pricing | "gemini-3.8-flash", Paid Tier Standard: input $0.75 and output $3.75 per 1M through December 31, 2026; $1.50/$7.50 from January 1, 2027 | 2026-10-27 |
| EU-SPAIN | https://european-union.europa.eu/principles-countries-history/eu-countries/spain_en | "Spain – EU country": Spain is an EU country | 2026-10-27 |
| EEA-AGREEMENT | https://www.efta.int/about-efta/legal-documents/eea-legal-texts | "EEA & Relations with the EU": the EEA Agreement brings together the EU Member States and Iceland, Liechtenstein, and Norway | 2026-10-27 |
| REPO-OPENAPI | `contracts/openapi.yaml` | No `security` requirement and no `securitySchemes`; `/ask` request/response schema and campaign error description | 2026-10-27 |
| REPO-ASK | `backend/app/ask_api.py` | Router dependencies are configuration/corpus providers, not authentication; `MANIJERO_ACTIVE_CAMPAIGN` read from the environment; no application logging calls in `backend/app` | 2026-10-27 |
| REPO-README | `backend/README.md` (local repository file) | `/health`, extractive `/ask`, no hosted model or network call; campaign requirement | 2026-10-27 |

### Data flow, logs, and retention worksheet

| Stage | Data seen | Documented handling | What remains unverified |
|---|---|---|---|
| Client → Cloudflare edge | Question text, minimal land context, IP address, request metadata over TLS [CF-TLS] | Cloudflare Customer Content and Customer Logs are processed under the DPA; Annex 1 names both and states retention until termination or until processing is no longer necessary [CF-DPA]; privacy §11 gives purpose-based criteria and no fixed period [CF-PRIV] | Whether any free-plan analytics or security product retains request content, and for how long |
| Cloudflare edge request logs | HTTP request metadata | Request logs are not retained by default and retention must be enabled [CF-RETAIN]; the Logpull query window starts 1 minute in the past and goes back at least 3 days and up to 7 days [CF-LOGPULL-BASICS]; Logpull itself is Enterprise-only [CF-LOGPULL] | Whether the pilot's plan produces any other request-log product or export |
| Tunnel connector | Origin traffic and connector health | Tunnel is outbound-only; no public origin IP is required [CF-TUNNEL]; connector prerequisites include outbound 7844 [CF-START] | Connector log location, content, and retention were not documented on the reviewed pages |
| Origin FastAPI | Question text and minimal land context in memory | Backend contains no application logging calls; `/ask` is extractive and makes no hosted-model or network call [REPO-ASK][REPO-README] | Default Uvicorn/ASGI access-log configuration, reverse-proxy logs, and process-manager logs were not reviewed or configured |
| R2 artifact delivery | APK and macOS installer bytes; presigned URL | Presigned URL authorizes anyone holding it for the signed operation until expiry, 1 second–7 days; S3 API domain only; no custom domain [CF-R2URL] | R2 access logging, audit retention, and object-lock/versioning settings were not reviewed |
| Gemini (disabled) | Would be minimum question text and approved passages only | Paid Services do not use prompts/responses for product improvement but log them for abuse/legal purposes and may store transiently in any Google facility [GEM-TERMS]; abuse logs are kept 55 days and flagged content may be human-reviewed by authorized Google employees [GEM-ABUSE]; project logs default to 55 days (7/14/28/55), shared datasets have no set retention and may be read/annotated by human reviewers [GEM-LOGS]; Spain is listed as an available region [GEM-REGIONS] | Exact model/revision and tier, quota/limit values, serving-region routing, dataset policy, and the qualified privacy review |

Question text and land context are the only user content expected to transit the API; the accepted
context contract excludes land names, notes, and area. Artifacts carry no user data. No log-retention
setting has been applied to any environment, because no environment exists.

### Owner attestation status

| Field | Evidence supplied on 2026-10-27 |
|---|---|
| Hardware | None. No model, CPU, RAM, disk, NIC, age, or spare capacity recorded. |
| Connectivity | None. No ISP measurement, redundancy statement, or outbound 7844 test. |
| Power and backup | None. No UPS, generator, shutdown, or restore evidence. |
| Maintenance window | None. No window, coverage, or notice plan. |
| Capacity | None. No measured latency or concurrency headroom. |
| Recovery | None. No backup location, restore steps, drill date, or downtime target. |

Cloudflare's documented baseline is two `cloudflared` replicas on two dedicated hosts per location
[CF-SYS]. A single owned server is therefore a development trial, not the documented baseline.

### Cost worksheet

List prices only; no invoice, quote, discount, or measured usage exists.

| Item | Arithmetic | Monthly assumption |
|---|---|---|
| Cloudflare Tunnel | 1 pilot tunnel; available on all plans [CF-TUNNEL] | $0.00; Tunnels-for-Platforms $4.50/additional tunnel above the first 1,000 [CF-PLAT] does not apply |
| Domain | Registrar sells at cost; registry/ICANN charges still apply | Non-zero, amount depends on extension [CF-REG] |
| Cloudflare plan | Free possible, but no SLA and no technical case; paid plan not quoted | $0.00 on Free, plus accepted support risk [CF-SUPPORT][CF-PLANS] |
| R2 storage | Two artifacts plus an assumed 12 retained builds at ≤0.7 GB each, under 10 GB-month | $0.00 within free tier [CF-R2PRICE] |
| R2 operations | Assumed small-pilot downloads, under 10M Class B/month | $0.00 within free tier [CF-R2PRICE] |
| Fly.io fallback compute | 1 × `shared-cpu-1x` 1 GB in `fra` | $7.73 per 30 days [FLY-PRICE] |
| Fly.io fallback volume | 10 GB provisioned | $1.50 [FLY-PRICE] |
| Fly.io fallback egress | 10 GB Europe | $0.20 [FLY-PRICE] |
| Fly.io fallback subtotal | Compute + volume + egress | **$9.43 per 30 days**, before support and backups [FLY-PRICE] |
| Fly.io paid support | Optional | $29 Standard or $199 Premium per month [FLY-PRICE] |
| Gemini | Not selected and not called | Formula only: input tokens/1M × $0.75 + output tokens/1M × $3.75 through 2026-12-31; double from 2027-01-01 [GEM-PRICE] |

Excluded everywhere: taxes, domain renewals, paid Cloudflare plan, incident labor, monitoring,
backups, a second host, and 31-day months. No zero-cost claim is made.

### Verification performed

- `./scripts/init.sh --feature hosting_provider_review` — exit 0 on the post-repair rerun. It ran
  `git diff --check` with no output.
- `./scripts/init.sh --fast` — exit 0, "All 9 offline checks passed. / Fast tier passed." Details:
  `:shared:jvmTest` reported `BUILD SUCCESSFUL`; contract examples validated 2 request and 3 response
  examples; the backend suite reported `636 passed, 1 warning in 7.34s` (Python 3.14.5, pytest 8.4.2);
  `knowledge/source_catalog.json` validated as `source-catalog-v1` with 4 sources checked as of
  2026-10-13; the retrieval, generation, abstention, clarification, and land-safety evaluators all
  passed their synthetic fixtures.
- Exact-section source re-check on 2026-10-27 (post-repair): each URL below returned HTTP 200 and the
  named section was read directly.
  - `GEM-ABUSE` "How We Investigate Potential Issues": authorized Google employees may assess flagged
    prompts/outputs via an internal governance assessment and review platform, solely for policy
    enforcement, not to train or fine-tune models except for policy enforcement.
  - `GEM-LOGS` "How we use your data": 55-day default maximum, configurable to 7/14/28/55 days;
    datasets have no set retention; shared data may be read, annotated, and processed by human
    reviewers with identifying links removed.
  - `GEM-REGIONS` "Available regions": Spain is listed.
  - `CF-RETAIN` "Enabling log retention": HTTP request logs are not retained by default; retention
    must be enabled and can be turned off.
  - `CF-LOGPULL-BASICS` "Data retention period": queries start 1 minute in the past and go back at
    least 3 days and up to 7 days.
  - `CF-TUNNEL` "Overview": "Available on all plans".
  - `CF-PLAT` "Pricing": $4.50 per additional tunnel per month above the first 1,000 included
    tunnels (Tunnels for Platforms).
- Manual source checks earlier on 2026-10-27: every provider URL in the source table returned HTTP
  200; redirects were followed to the final URL recorded above. Cloudflare Registrar now resolves to
  `https://www.cloudflare.com/domains/`.
- Repository checks: `contracts/openapi.yaml` contains no `security` scheme; `backend/app/ask_api.py`
  has no authentication dependency and `backend/app` has no logging calls.
- **Not run:** any deployment, TLS handshake against a real hostname, tunnel installation, Fly.io
  Machine, R2 upload/download, presigned-link expiry test, Gemini call, load test, restore drill,
  or provider incident exercise.

### Limitations

- The owned server was not inspected; all six readiness fields remain unsupplied. The owner did not
  sign a separate acceptance artifact; this record is the written direction and remains subject to
  every stated pre-pilot condition.
- Fly.io's DPA text could not be retrieved, so its deletion/return timing, sub-processor list
  commitments beyond the public page, and transfer mechanism remain unverified. Only Fly.io was
  evaluated as the managed-host fallback; no other managed host was assessed.
- Only Cloudflare R2 was evaluated for artifact delivery; no alternative provider's terms were
  assessed.
- No legal or privacy compliance conclusion is made; `pilot_privacy_readiness` owns that review.
- Prices are list prices read on one date and can change with 30 days' notice [CF-TOS §4.2]
  [GEM-TERMS "Payment Terms"], or for Fly.io under §12 [FLY-TOS §12].
- The current API is unauthenticated and has no rate limit; provider selection does not fix that.

### Independent acceptance

Accepted on 2026-10-27 after one repair round; the validator re-ran both tiers and re-fetched the
load-bearing official sections. See the
[acceptance record](../validations/hosting_provider_review.md). No deployment, provider account,
Gemini call, or real-user data was involved.

## Validator checklist

- [x] The owned-server path is assessed rather than assumed available.
- [x] A fallback is evaluated or hosting remains explicitly blocked.
- [x] Provider data handling, limits, and costs are supported by current official sources.
- [x] No hosted LLM is described as currently used; Gemini remains disabled by default.
- [x] The record states its limits and re-review trigger.
