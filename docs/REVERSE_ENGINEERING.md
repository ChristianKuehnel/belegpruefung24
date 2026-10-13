# Portal24 Interface Research

Record only verified, sanitized information here. Never store authenticated HAR captures, cookies, bearer tokens, real account identifiers, private URLs, addresses, personal data, or transaction payloads.

## Sources and Existing Libraries
- **No public API documentation** exists for Portal24 (checked portal24.com, immoware24.de, support.immoware24.de). No OpenAPI/Swagger description is published.
- **No existing Python client** on PyPI or GitHub (searched 2026-10-13; all GitHub hits for "portal24" are unrelated projects).
- Portal24 is the tenant/owner portal of the Immoware24 property-management SaaS (vendor admin app: REMS, a separate product).
- Vendor marketing confirms Portal24 features: documents, ETV (owner meetings), UVI (consumption info), online forms/tickets, digital signature, Belegprüfung (voucher review).

## Authentication (verified 2026-10-13, public page + live login)
- Login page: `GET {base}/user/auth/login`; also `/user/auth/activate`, `/user/auth/register`, `/user/auth/reset-password`.
- Login form: `POST /user/auth/login?today=` (the empty `?today=` param is part of the form action) with URL-encoded fields `email`, `password`, `type` (hidden 32-char per-page token scraped from the GET response), `submit` ("Login").
- **Live-verified success behavior:** the POST returns `302` to the post-login landing page (`/portal/object/show`); failure re-renders the login page (optionally with an error message in an `alert-danger` div).
- Session is a cookie (PHP-style; cookie name observed: `PHPSESSID`). Session persists across client restarts when the cookie is replayed.
- No MFA/CAPTCHA observed on this tenant portal (would appear after the credential POST if enabled).
- HTML attribute values on the login page are HTML-entity-encoded (`&#x2F;` = `/`); parsers must unescape.
- Language switch: `GET /user/language/switch/de_DE` | `/user/language/switch/en_US`.

## Application Architecture (verified 2026-10-13)
- Server-rendered PHP (Zend-style) pages + jQuery 2.x / Bootstrap 3.3.6 / DataTables 1.10.22 / Select2 / Dropzone 5.1.1. **Not** a SPA — business endpoints are server-injected per page (`data-url`, paginator hrefs, inline scripts). One React island: POM meetings (`/portal/pom/meeting/{id}`, data not in HTML).
- App version marker: `?_=3.26.0` on `/dist/*` assets (bundle built 2026-09-21).
- Per-page globals: `window.ErrorLog = {userId, mandator, locale, errorLogFrontendUrl}` and `var globalUserInformation = { v1: { user, dataSource, ds, uid, role } }` (role e.g. `owner`).
- JSON polling endpoints (server-injected): `GET /portal/api/get-notifications`, `GET /portal/api/get-open-invites`.
- Pagination is uniform: `.paginator > ul.pagination[title="start - end / total / pageCount"]`, page param `?page=N` (1-based). Page sizes observed: 24 (documents), 10 (notifications).

## Confirmed Read-Only Endpoints (verified live 2026-10-13)
| Purpose | URL pattern |
|---|---|
| Login page / credential login | `GET/POST /user/auth/login` (see above) |
| Dashboard (redirects to object view) | `GET /portal/dashboard` → `/portal/object/show` |
| Object (property) view + object/rent-unit switcher columns | `GET /portal/object/show` |
| Object pinboard tabs | `GET /portal/object/show/0/0` (aktuell), `/portal/object/show/0/1` (Archiv) |
| Resolutions collection | `GET /portal/object/resolution` |
| Meetings (React island, no SSR data) | `GET /portal/pom`, `/portal/pom/meeting/{id}` |
| Rent-unit payments ("beschlossene Zahlungen", incl. SEPA pre-notification) | `GET /portal/rent-unit/payments` |
| Payment validity history | `GET /portal/rent-unit/details` |
| Allocation properties (Umlageeigenschaften) | `GET /portal/rent-unit/properties` |
| Consumption info (UVI) | `GET /portal/rent-unit/consumptions` |
| Document list (all categories) | `GET /dms/document/list/-1?page=N` |
| Document list (one category) | `GET /dms/document/list/{categoryId}?page=N` |
| **Document binary download** | `GET /dms/document/download/{id}` (original bytes, e.g. PDF) |
| Document detail view | `GET /dms/document/show/{id}` — **side effect: marks document read; avoid in sync** |
| Category table (flat, no IDs) | `GET /dms/category/list` |
| Tags | `GET /dms/tag/list` |
| Filter reset | `GET /dms/document/reset-filter` |
| Tickets | `GET /communicator/ticket/list`, `/communicator/ticket/show/{id}` |
| Ticket attachment download | `GET /communicator/ticket/download-attachment/{ticket}/{attachment}` |
| Online forms | `GET /communicator/form/list`, `/communicator/form/show/{id}` |
| Notifications | `GET /messenger/notification/list?page=N` |
| Global statistics | `GET /portal/dashboard/global-object-statistics` |

### Document list row schema (verified)
Table `#selectTable`, columns: Status (`neu`/`gelesen`), Name (full name in `td[title]`), Größe (human size), Freigabe (release datetime `dd.mm.yyyy, hh:mm:ss`), Heruntergeladen (download datetime, empty if never), Kategorie (leaf category name text), Aktionen (show + download links). Document ID carried by the row checkbox `value` and the `/dms/document/(show|download)/{id}` hrefs. 24 rows per page.

### Category tree (verified)
The document list page embeds the full category tree as inline `DmsCategory` builder scripts:
`currentCategory = new DmsCategory().setId(N).setName('...').setCount(N);` with `currentCategory.addChild(new DmsCategory()...)` for children. Parent category lists **include** their children's documents (parent count includes child counts); child categories must be enumerated separately and results deduplicated by document id.

### Object / rent-unit enumeration (verified)
`/portal/object/show` contains switcher columns: `div#objectSearchTarget` (objects, href `/application/essential/switch-object/{id}/{base64(returnPath)}`) and `div#rucrSearchTarget` (rent units, href `/application/essential/switch-rent-unit-contact-relation/{id}/{base64}`). Name in link text, address/meta in `span.text-xs`. **These switch links are state-changing (change the session's active context) and must only be parsed, never followed.**

## State-Changing Endpoints (verified — must NEVER be called)
- `GET /application/essential/switch-object/{id}/{b64}` — switches active object (session state).
- `GET /application/essential/switch-rent-unit-contact-relation/{id}/{b64}` — switches active rent unit.
- `GET /user/auth/switch-data-source/{id}` — switches active data source.
- `GET /dms/category/link/{id}/-1` — bulk-assigns selected documents to a category.
- `GET /dms/document/select-list-item/{id}`, `deselect-list-item/{id}`, `select-all/{id}`, `deselect-all`, `select-multiple-list-items/{ids}`, `deselect-multiple-list-items/{ids}`, `select-this-list-items/{ids}` — selection state.
- `GET /dms/document/show/{id}` — marks document as read (review state).
- `POST /portal/object/mark-pin-board-entry-read` — marks pinboard entries read.
- `GET /messenger/notification/jump/{id}` / mark-as-seen variants — notification read state.
- `GET /communicator/ticket/revoke-attachment/{t}/{a}` — revokes an attachment.
- All `POST` filter forms on list pages (mutate session filter state).

> Lesson learned (2026-10-13): an early discovery crawl followed some `switch-*` GET links, which changed the session's active object context. The client's link filter now blocks all patterns above; the switch state is a reversible UI context (next login re-selects the usual object), but no such endpoints are called by the shipped client.

## Document Hierarchy (verified)
Server hierarchy: **data source (management company) → category tree (nested) → document**. Documents are listed at data-source level with an optional object filter (radio `currentObject`: `includeAllObjects`/`filterCurrentObject`, default include-all). The document list does **not** expose a per-document object id, so the mirror maps documents under the category tree, not under individual properties. Objects/rent-units are mirrored as metadata.

## Structured Accounting Data (verified)
- **No machine-readable transaction feed exists** in this tenant portal. There are no booking/ledger endpoints; "Online-Belegprüfung" is implemented as **DMS documents in the "Belegprüfung" category** (monthly voucher bundles `MM.YYYY_<street>.pdf`, plus accounting extracts such as "Buchungen gruppiert nach Konten: Einnahmen/Ausgaben", "Bankkonto-Abrechnung", "Rücklagenkonto").
- Annual statements live in the "Jahresabrechnung" category tree (children "Rücklage", "Sonderumlage").
- The closest structured data is the rent-unit payments table (monthly house-money lines + SEPA pre-notification block) on `/portal/rent-unit/payments` — display-only, non-paginated.
- Therefore: transaction "exports" are (a) the mirrored PDFs and (b) client-generated CSV/JSON of the Belegprüfung *document records* (metadata), clearly labeled as client-generated, not native server exports.

## Limitations and Open Questions
- Meeting (POM) data is rendered client-side by a React bundle; no SSR data was found. Meeting minutes are available as documents in "Protokolle"/"Versammlung" categories.
- Whether `Heruntergeladen` timestamps or per-document read state are used server-side for anything beyond display is unknown (read state is mutated by `/dms/document/show/{id}`, which the client avoids).
- Session lifetime/refresh behavior not measured (cookie accepted across multiple hours of testing).
- Behavior with multiple objects/rent-units is inferred from the switcher markup (one entry per accessible object); only single-object accounts were tested.
- The `?today=` cache-buster param and `PHPSESSID` name may vary between tenants/versions.
