# Feature Spec: `hosting_provider_review`

## Source metadata

- **Feature:** `hosting_provider_review` — Review hosting, tunnel, and Gemini provider terms (`operations`).
- **Status at planning:** `not_started`; depends on accepted `backend_ask_endpoint` and `backend_campaign_validity`.
- **Source behavior:** Record current, source-linked choices for API hosting, managed tunnel, private artifact delivery, and gated Gemini generation, including terms, privacy, reliability, and cost.
- **Feature-list verification:** A dated decision record compares the owned-server/tunnel path with a managed-host fallback using current official provider materials and states the selected path and blockers.
- **Feature-list note:** Gemini generation is planned for the pilot but remains gated off until exact model terms, privacy/data flows, limits, and qualified review are documented and approved. Selecting a model or tier is deliberately unresolved.

## Goal and boundaries

Choose whether an owned server can reliably host the private API through a managed tunnel. If it cannot, select a managed API host using current official documentation. The review must not rely on MasterPlanV3's historical assumptions or make unverified claims about provider terms.

**In scope:** provider and service identity for hosting, managed tunnel, and private build delivery; current official terms, privacy/data processing, region, access control, TLS, logs/retention, support, limits, incident notice, cost, reliability prerequisites, and exit/rollback path; a written go/no-go decision by the project owner.

**Non-goals:** deployment implementation, provider account creation, activating Gemini before its review gate, user research, or a legal compliance certification. Qualified privacy/legal review is tracked in `pilot_privacy_readiness`.

## Job story

When choosing where the pilot API runs and how it is reachable, I want a current evidence-based provider decision, so questions and service availability are not exposed to an unreviewed infrastructure provider.

## Acceptance scenarios

### Owned server meets pilot requirements

Given an owned server and managed tunnel candidate, when the project owner completes the review, then the record lists tested capacity/availability requirements, official terms and data handling, known costs/limits, operational prerequisites, and a clear go/no-go.

### Owned server is not viable

Given the owned server cannot meet the documented readiness bar, when the comparison is completed, then the record names the evaluated managed-host alternative and its official sources, or leaves hosting blocked if evidence is inadequate.

### Terms change

Given a provider's material privacy, terms, or pricing change, when the owner revisits the decision, then the current record is re-reviewed before the affected service continues for the pilot.

### No AI-provider implication

Given the selected infrastructure, when the record describes data flow, then it states that the current API uses extractive answers and does not call Gemini until the review gate is passed.

## Technical approach

Create a dated decision record with a small comparison matrix and direct official links for the host, tunnel, artifact-delivery, and Gemini options, accessed date, exact relevant sections, data-flow notes, cost assumptions, operational requirements, decision owner, review trigger, and unresolved blockers. Do not copy legal text at length or infer legal compliance. If a provider cannot be selected with official evidence, keep the affected pilot path blocked and list the missing evidence. Record Gemini model ID/revision, tier, regions, prompts/responses processing, retention, human review, limits, pricing assumptions, and an explicit disabled-by-default gate. Do not send real user data during evaluation until the qualified review approves it.

## Expected file changes

- `docs/specs/hosting_provider_review.md` and appendix — decision contract and evidence template.
- `docs/risks-and-open-questions.md` — resolved hosting direction or precise remaining blocker.
- `README.md`/`backend/README.md` only if a later approved provider decision changes operator instructions.

## Visual design impact

None.

## Durable documentation impact

- `ARCHITECTURE.md`: update only after the chosen hosting boundary is implemented.
- `CONSTRAINTS.md`: preserve Gemini disabled-by-default until reviewed and enforce data minimization and verifier invariants.
- `AGENTS.md`: not needed.
- `docs/risks-and-open-questions.md`: update the hosting/tunnel decision and review trigger.

## Focused verification

<!-- verify:start -->
```sh
git diff --check
```
<!-- verify:end -->

## Appendix

See [`hosting_provider_review.appendix.md`](hosting_provider_review.appendix.md).

## Decision and evidence — 2026-10-27

**Decision owner:** the project owner. **Status:** a dated direction for the private pilot, not a
pilot release approval. **Go/no-go: GO only to continue preparation; NO-GO for exposing the API to
any real user or for enabling Gemini.** Every bracketed key below resolves to a direct official URL,
page/section, and access date in the appendix source table; all sources were accessed on 2026-10-27.

### Outcome

| Path | Outcome on 2026-10-27 |
|---|---|
| Owned server | **Not approved / blocked.** The repository contains no evidence for hardware, connectivity, power/backup, maintenance window, capacity, or recovery. Cloudflare's documented baseline recommends two dedicated hosts per location, not one server. |
| Managed tunnel | **Cloudflare Tunnel conditionally selected as transport** for the API path, only after the owned-server attestation passes. A tunnel does not authenticate the API. |
| Managed-host fallback | **Fly.io is the only fallback evaluated; not approved.** It has no free tier, its DPA text was not retrievable, and its public privacy statement says information is stored/processed in the United States while Machines may run in `fra`. |
| Private artifact delivery | **Cloudflare R2 presigned URLs selected as the candidate** for private APK/Desktop installer links. They are bearer tokens with a 1 second–7 day lifetime and cannot use a custom domain. |
| Gemini generation | **Disabled by default; exact model/tier deliberately unresolved.** Spain is an EU Member State [EU-SPAIN], and the EEA Agreement brings the EU Member States into the EEA [EEA-AGREEMENT], so any API client made available to pilot users must use Paid, not Free [GEM-TERMS]. No Gemini call exists in the current API. |

This is not a finding that any provider is legally compliant, secure for farm data, or inexpensive.
It records what the current official material says and what still has to be proven.

### Why the owned-server path stays blocked

The owner must attest each row before this path can be reconsidered. None of these facts can be
derived from the repository, and this review did not inspect a physical server.

| Readiness field | Evidence available now | Pass condition |
|---|---|---|
| Hardware | None | Exact model, CPU, RAM, disk, NIC, age, and spare capacity recorded. |
| Connectivity | None | At least one working ISP measured; redundant connectivity or an accepted single-link risk recorded; outbound TCP 7844 verified. |
| Power and backup | None | UPS/generator behavior, graceful shutdown, and tested restore of the API and corpus recorded. |
| Maintenance window | None | Named window, owner coverage, and user-visible notice plan recorded. |
| Capacity | None | Measured retrieval/response latency and concurrency headroom for the pilot, not a guess. |
| Recovery | None | Backup location, restore steps, restore drill date, and maximum acceptable downtime recorded. |

Cloudflare's published baseline recommendations are a `cloudflared` replica on **two dedicated hosts per
location**, each with at least 4 GB RAM, 4 CPU cores, and 50,000 ports [CF-SYS]. The overview states
that each tunnel keeps four long-lived connections to two Cloudflare data centers, and that additional
`cloudflared` replicas provide more availability [CF-TUNNEL]; the former protects the Cloudflare leg,
not a single home server losing power or connectivity. A one-host setup can be a development trial,
but it cannot be presented as the documented baseline.

### Selected path and its conditions

The API path is **owned server + Cloudflare Tunnel**, conditional on all of the following:

1. The owner completes the six-row attestation above and accepts any single-link/single-host risk in
   writing; a second host is added where the documented baseline is claimed.
2. The API gets its own authentication, per-client rate limiting, request-size limits, and an
   explicit authorization decision before any public hostname is routed to it. The current OpenAPI
   contract declares no security scheme [REPO-OPENAPI], and `ask_api.py` has no authentication
   dependency [REPO-ASK].
3. TLS is terminated at Cloudflare with an edge certificate; Universal SSL covers the apex and
   first-level subdomains on a full setup [CF-TLS]. The origin is reached through the tunnel; no
   inbound port is opened. The hostname requires a domain on Cloudflare and a Cloudflare account
   [CF-START].
4. Application and provider logs are configured to exclude question text, land context, and stable
   identifiers. The backend currently contains no application logging calls [REPO-ASK], but default
   ASGI/uvicorn access logs, reverse-proxy logs, and tunnel/provider logs are not configured or
   reviewed by this feature and must not be assumed silent.
5. Current terms, data flow, retention, support, and cost are re-checked at account/domain creation;
   this record is not a purchase approval.
6. The qualified privacy/legal review in `pilot_privacy_readiness` passes before real-user questions
   transit the service.
7. An incident runbook, status/notice channel, rollback procedure, and cost owner are recorded.

If the owner cannot attest the server or provide the controls, the path remains blocked; Fly.io is
not a default substitute because it has its own unresolved DPA, residency, backup, and cost issues.

### Data flow, logs, and retention

Current behavior: `/ask` returns extractive answers from the reviewed local corpus and makes no
hosted-model or network call [REPO-README]. It requires an explicit `MANIJERO_ACTIVE_CAMPAIGN`
[REPO-README][REPO-ASK]. A question carries the person's text plus the minimal land context
(opaque local ids and only the attributes the question needs); land names, notes, and area are
excluded by the accepted context contract. The current API is unauthenticated [REPO-OPENAPI].

When hosted, the intended flow is: client → TLS → Cloudflare edge/tunnel → origin FastAPI. Cloudflare
therefore processes Customer Content in transit and Customer Logs such as IP addresses; its DPA
Annex 1 names both categories and describes retention until termination or until processing is no
longer necessary [CF-DPA]. The privacy policy gives purpose-based retention criteria and no fixed
period for Customer Logs [CF-PRIV]. Cloudflare's Logpull documentation says HTTP request logs are
not retained by default, and Logpull itself is Enterprise-only [CF-RETAIN][CF-LOGPULL]; this record
therefore does not assume a free/Pro request-log audit trail. Cloudflare may use Network Data to
provide, maintain, develop, and improve its services and may inspect traffic and logs for service or
network security [CF-TOS].

Fly.io's public logging documentation says app logs are the process's stdout, Grafana search retains
them for 7 days, and Fly Log Shipper can export them [FLY-LOG]. Its sub-processor page states that
AI vendors do not receive volume contents or request bodies, but support/abuse work can process
account metadata, ticket text, and platform log lines including whatever the app writes to stdout
[FLY-SUB]. Its privacy statement says application data is processed on the customer's instructions
and is stored/processed in the United States [FLY-PRIV]. The DPA text itself was not retrieved, so
Fly's processor deletion/return timing is unverified.

R2 carries build artifacts only, not user questions. Presigned URLs embed the signature and act as
bearer tokens until expiry; anyone with the link can perform the signed operation [CF-R2URL]. R2
access logging and audit retention were not reviewed here, so links must be short-lived, scoped to
one object, and never placed in a public bucket.

Gemini is off. If its gate ever passes, only the minimum question text and approved retrieved
passages may be sent, with no land names/notes or stable identifiers, on a Paid project. Paid use
does not improve Google's products, but prompts and responses are still logged for abuse/legal
purposes and may be stored transiently or cached in any country where Google or its agents maintain
facilities [GEM-TERMS]. Abuse monitoring retains prompts, context, and output for 55 days
[GEM-ABUSE]. Logging is on by default for Generate Content calls in projects created on or after
2026-10-26, with a 55-day default adjustable to 7/14/28/55 days; shared datasets have no set
retention and are governed by Unpaid-Service terms [GEM-LOGS].

Human review is also part of the data flow. When prompts or model outputs are flagged by safety
filters and abuse detection, authorized Google employees may assess the flagged content, and such
data can be accessed for human review only through Google's internal governance assessment and review
platform; it is used solely for policy enforcement and not to train or fine-tune models beyond that
purpose [GEM-ABUSE]. If logs are optionally shared as datasets for model improvement, human reviewers
may read, annotate, and process those API inputs and outputs, with identifying links removed before
reviewer access [GEM-LOGS]. This record notes those possibilities; it does not approve them for farm
questions.

**Gemini unresolved fields (2026-10-27).** Every field below is deliberately unselected or
unreviewed; none is an approval to enable generation.

| Field | Status on 2026-10-27 |
|---|---|
| Model ID/revision | Unselected. `gemini-3.8-flash` appears only as a pricing example [GEM-PRICE]; no model or revision is chosen. |
| Tier | Paid is required for API clients in the EEA/Switzerland/UK [GEM-TERMS]; the exact tier is unselected. |
| Regions | Spain is listed on Google's official available-regions page [GEM-REGIONS]; serving-region routing and any regional processing guarantee were not reviewed. |
| Quotas and limits | Not reviewed; no rate, token, or concurrency limit was established. |
| Retention | Abuse monitoring keeps prompts/context/output for 55 days [GEM-ABUSE]; project logs default to 55 days and are configurable to 7/14/28/55 days [GEM-LOGS]; shared datasets have no set retention [GEM-LOGS]. |
| Human review | Authorized Google employees may review flagged prompts/outputs for abuse enforcement [GEM-ABUSE]; shared-dataset inputs/outputs may be read, annotated, and processed by human reviewers [GEM-LOGS]. |
| Pricing assumptions | List-price example only (see Cost assumptions); no quote, measured usage, or spend cap exists. |
| Disabled-by-default gate | The provider call is absent and the key is unset. Enabling requires a passed `pilot_privacy_readiness` review, a resolved model/tier/region/limit record, and an explicit owner go decision. |

**Owner decisions (2026-10-31).** Recorded by the owner while choosing a tier; the decision was then
postponed, so none of this enables Gemini or selects a revision.

- **Postponed in favour of local generation.** No spending for now: answer drafting is tried first
  with a local open-weight model (`local_generation_provider`), developed and measured on the
  owner's Mac. Paid Gemini is reconsidered for production only if local generation is not enough.
  This supersedes MasterPlanV3 decision D3 (Gemini Flash on the free tier).
- **Free vs paid.** The free tier may be used only for development with synthetic data; any pilot
  user requires Paid services, as the EEA rule above already states.
- **Platform.** Development on the Gemini Developer API (AI Studio); pilot on Vertex AI's EU
  multi-region endpoint, which keeps ML processing in the EU. Vertex retention settings and model
  availability in that endpoint are unverified.
- **Model.** The cheapest suitable model (Flash-Lite family); no model or revision is fixed. Google
  list prices checked on 2026-10-30: Gemini 3.5 Flash-Lite $0.30 input / $2.50 output and Gemini
  3.1 Flash-Lite $0.25 / $1.50 per 1M tokens, paid Standard.
- **Not decided.** Service tier, usage-tier limits, the limits record values, and the spend cap.

### Terms, support, and incident notice

- **Cloudflare terms.** The Self-Serve Subscription Agreement lets Cloudflare change prices with 30
  days' notice [CF-TOS §4.2], suspend or terminate access at any time for any reason [CF-TOS §8],
  provide Free Services without liability [CF-TOS §2.6], and disclaim warranties [CF-TOS §11].
  Material revisions are notified, and Free Services may require renewed consent [CF-TOS §14]. The
  DPA provides delete-or-return on termination [CF-DPA §3.1(i)], 30 days' notice of new
  sub-processors with a 10-day objection window [CF-DPA §4.4], and SCCs for restricted transfers
  [CF-DPA §6.2].
- **Cloudflare support.** Free and pay-as-you-go plans have no SLA; Free plans cannot open technical
  support cases (billing/account/registrar only); support is in English; the status page is the
  documented incident channel [CF-SUPPORT]. A pilot that needs a response commitment must budget for
  a paid plan or accept best-effort community support.
- **Fly.io terms.** Fly.io is not obligated to back up Customer Data [FLY-TOS §4.1]; the Customer
  Data licence includes improving the Fly.io Services [FLY-TOS §2 "Customer Data"]; the service is
  provided as-is [FLY-TOS §5]; Customer Data is returned on termination [FLY-TOS §9 "Effect of
  Termination"]; material changes are effective 30 days after posting for existing customers
  [FLY-TOS §12]. The privacy statement says
  data is stored/processed in the US and material privacy changes get at least 30 days' notice
  [FLY-PRIV].
- **Fly.io support.** Community support is free; email and the Support Portal require a paid
  Standard/Premium/Enterprise package or a legacy Launch/Scale plan; the status page is the
  platform-wide channel [FLY-SUPPORT]. The reviewed pages do not state a response SLA.
- **Gemini terms.** The Additional Terms require users to be 18+, restrict API clients from being
  directed to under-18 users, require Paid Services for API clients in the EEA/Switzerland/UK
  [GEM-TERMS], allow price changes effective 30 days after posting, and disclaim that the services
  are experimental and not a substitute for legal or professional advice [GEM-TERMS].

### Cost assumptions

These are list-price assumptions as of 2026-10-27, not quotes or forecasts. No account, domain,
invoice, or measured usage exists.

| Item | Assumption | Source |
|---|---|---|
| Cloudflare Tunnel | Available on all plans [CF-TUNNEL]. A single tunnel is included at no extra cost, so this review assumes $0.00 for one tunnel; the $4.50/additional-tunnel price above 1,000 tunnels is Tunnels-for-Platforms capacity pricing and does not apply here. | [CF-TUNNEL]; capacity pricing note [CF-PLAT] |
| Domain | Cloudflare Registrar charges registry and ICANN fees at cost, not zero; registration and renewal still cost money. | [CF-REG] |
| Cloudflare plan | A Free plan is possible but has no SLA and no support case; Business or higher shows a 100% uptime SLA, and any paid plan is an additional cost not quoted here. | [CF-SUPPORT][CF-PLANS] |
| R2 | 10 GB-month storage, 1M Class A, and 10M Class B operations free each month; then $0.015/GB-month Standard storage, $4.50/M Class A, $0.36/M Class B; egress is free. | [CF-R2PRICE] |
| Fly.io compute | No free tier. `shared-cpu-1x` 256 MB $2.19/30 days; 512 MB $3.69; 1 GB $6.70 in `iad`/`ewr`; 1 GB `fra` $7.73. | [FLY-PRICE] |
| Fly.io extras | Egress $0.02/GB in Europe; volume $0.15/GB-month; first 10 single-hostname certificates free, then $0.10/month; support $29/month Standard or $199/month Premium. | [FLY-PRICE] |
| Gemini | Example only, not a selection: `gemini-3.8-flash` Paid Standard is $0.75 input/$3.75 output per 1M tokens through 2026-12-31, then $1.50/$7.50 from 2027-01-01. | [GEM-PRICE] |

Excluded from every row: taxes, domain renewals, paid support, incident labor, monitoring, backups,
and the cost of a second host. No zero-cost claim is made for the pilot.

### Reliability prerequisites

1. Owned server: UPS/graceful shutdown, redundant connectivity or an accepted single-link risk,
   disk-health monitoring, backups with a dated restore drill, and physical security.
2. Tunnel: two `cloudflared` replicas on separate hosts where HA is claimed; outbound 7844 verified;
   tunnel credentials stored as secrets; health/alerting on connector loss; configuration backed up.
3. Application: health endpoint checked externally, bounded request size and concurrency, rate
   limiting, authentication, and graceful degradation when the corpus or campaign is unavailable.
4. Fly.io fallback: external monitoring must restart unhealthy Machines because Fly health checks
   route around them but do not restart them [FLY-HEALTH]; backups are the customer's duty
   [FLY-TOS §4.1]; only 7 days of searchable logs are available without export [FLY-LOG].
5. Provider outage/incident: status pages are the notice channel; Cloudflare Free/pay-as-you-go has
   no SLA [CF-SUPPORT]; a pilot support plan is an explicit decision, not an assumption.
6. Cost: usage and error rates are measured; a spend cap/alert exists before traffic.

### Exit and rollback

- Keep the API portable and the tunnel/origin configuration in versioned files. Moving the hostname
  means changing DNS and tunnel routes, not rewriting the application.
- Preserve the reviewed corpus and a tested backup outside the chosen host. Fly.io explicitly does
  not back up Customer Data [FLY-TOS §4.1].
- Export or delete R2 objects and revoke presigned links by deleting the objects or rotating
  credentials; a presigned link cannot be individually revoked before expiry [CF-R2URL].
- On Cloudflare termination, request delete-or-return under the DPA [CF-DPA §3.1(i)]; on Fly.io,
  request return of Customer Data under the ToS [FLY-TOS §9 "Effect of Termination"]. Fly's DPA
  deletion timing remains unverified.
- Disable Gemini by keeping the provider call absent and the key unset; no runtime flag is the only
  gate.
- No rollback, migration, or restore has been exercised because no deployment exists.

### Unresolved blockers

1. Owner attestation for all six readiness fields; no server evidence exists.
2. No application authentication, authorization, or rate limiting on the current API.
3. No deployed environment, domain, TLS setup, or runtime smoke test.
4. No measured capacity, latency, or cost data for the pilot.
5. Cloudflare Free/pay-as-you-go has no SLA and no technical support case; this review did not
   establish a free/Pro request-log audit trail, and the documented Logpull path is Enterprise-only.
6. Fly.io DPA text was not retrieved; US storage/processing vs a `fra` Machine is unresolved; backup
   is explicitly not Fly's obligation.
7. The qualified privacy/legal review (`pilot_privacy_readiness`) has not passed.
8. Exact Gemini model/tier is unselected; Paid is mandatory for EEA users; abuse/log retention is 55
   days by default, flagged content and shared datasets may receive human review, and transient
   storage may occur in any Google facility. Regions, quotas/limits, and serving-region routing remain
   unresolved (see "Gemini unresolved fields").
9. APK signing/notarization, installer trust, and distribution are not implemented; a presigned R2
   link does not solve install friction or trust.
10. Incident runbook, on-call coverage, support plan, and user notice text are not defined.

### Re-review trigger

Re-review this decision before any real-user pilot; before enabling Gemini; on any material change
to provider terms, privacy policy, sub-processors, regions, limits, or pricing; after a provider
security incident or extended outage; if the host, domain, region, or data flow changes; if the
owner attestation fails or a second host is unavailable; and at least every 90 days while preparation
continues (next by 2027-01-25). The Gemini price change on 2027-01-01 is a concrete re-check date, and
the Cloudflare/Fly 30-day notice windows set how much warning a change gives
[GEM-PRICE][CF-TOS §4.2][FLY-TOS §12].

### Residual risk and honesty limits

This record proves only that the cited pages said the cited things on 2026-10-27. It does not prove
that the pilot is legally compliant, that any provider is safe for personal data, that the owned
server exists or is reliable, that the tunnel has been installed, that costs will stay at list
price, or that a provider will not change terms. No account, domain, server, deployment, load test,
restore drill, or provider incident exercise was performed. No real user data was used. The current
API remains extractive and unauthenticated, and no Gemini call exists.
