# Optional unread CDSE backup cache

S2-T41 and proposed decision 0066 define this custodian-only path. Ordinary
`./eii build-public` excludes the source, even with the pair present. Only the
lead-shell `./eii build-public --cdse-backup` form selects it. Missing/blank/partial
credentials omit it successfully. A full pair still omits it with
`provider_contract_pending`: documentation reading does not activate acquisition.
No cache, credential proof, account query or processing request was made here.

`scripts/cdse_key.py` alone names the environment pair. The injected transport
rejects redirects, unlisted hosts and unbudgeted attempts, holds tokens only in
memory and redacts refusal text. It opens no socket. `REVIEWED_ENDPOINTS` remains
empty pending the lead's admission and operational evidence. `wire.py` records
the documented endpoint identities separately; it does not admit those hosts.

## Official pages read for P24

Maker: OpenAI; model: GPT-6-based Codex. Read date for every row: 2026-11-20.
Publisher for D1 through D14: Copernicus Data Space Ecosystem. Publisher for D15:
European Commission (the notice's own heading). SHA-256 is of the fetched body
bytes before text extraction, not of a quotation. Only read-only GETs to these
publishers were used. Embedded scripts, examples and sign-in links were not run.
The API reference wrapper points to the OpenAPI file in D10; no external renderer
was fetched. D15 was fetched and hashed in memory and read with the PDF reader;
the local `pdftotext` attempt failed because the executable is unavailable.

| Id | Official page and section read | Fetched-body SHA-256 |
|---|---|---|
| D1 | https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html — OAuth2 Endpoints, token examples, reuse | 5937bfc87fc59c0b203e3b8adb02dc813674af311cf85c091c55b64a565919c5 |
| D2 | https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Process.html — Processing API introduction | 68205adf2594433afc214b832826db317478cd310601fa831021a69389e8a328 |
| D3 | https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S2L2A.html — filtering, bands, units, SCL, scenes | a01f7c062b8a9a37af7dbe80681038616260901d418aed4da71a3631beeb8a47 |
| D4 | https://documentation.dataspace.copernicus.eu/Quotas.html — Copernicus General Users, Sentinel Hub column, reset | 3ccd0caa52c52d634ad4936bd23fc4dcf81a09fb97972f6dcfde5f1bf39a1c50 |
| D5 | https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/ProcessingUnit.html — General data processing, querying, factors, minima | c29db04f60570b587bc4ffbe4a44f36d96ce76a385eb5ae19c87bc77674eedbc |
| D6 | https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/RateLimiting.html — policy and response headers | 9c74709a6cf6865dab43de35987933d0b78ef787fb59aad1f1637e4b11bcbb7a |
| D7 | https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/UserGuides/Metadata.html — TILE metadata and userdata.json | c3594e88823175e3fb3978bf0a12c7d4117bfb4721cdbd7eed310d44f4196640 |
| D8 | https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Evalscript/Functions.html — setup, samples/scenes, AUTO, updateOutputMetadata | 9dc11bae656f2f2593b66d971412dfa116aa43efbdbca77169d31e6873e09e72 |
| D9 | https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/UserGuides/Transparency.html — alpha and no-data | dac33d3f616bbe3ec828eea709ee64f4dbbbf9a09054db55eb607c34d5a66e50 |
| D10 | https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/ApiReference/openapi.v1.yaml — server, /process/v1, ProcessRequest, TimeRange and bounds/output schemas | d958128dc59ee2b2ca469113827fdd6014b83a8107d95cc577ec7ffb3a557b9f |
| D11 | https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Process/Crs.html — UTM northern hemisphere | 04114a8c74d2f60a0aff36d17cfe06a55ed7b9aa81ecb37ff540dae6e89445d0 |
| D12 | https://dataspace.copernicus.eu/terms-and-conditions — Data supply, Copyrights, Availability, Use | f2e349a7955c49aa72fe8de0fca9800468a70958e7033bb980c428b29047faae |
| D13 | https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/ApiReference.html — wrapper's spec-url | e140c37534f6920ac6bc5a597928ff9b8fc7d4244a185b4a8ccd02d3078528a4 |
| D14 | https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Process/Examples/S2L2A.html — true colour, metadata and multiple outputs | db2a959e6750f6adcd00ada46a78b3d288075b1ef6194c27695a555c1c28715c |
| D15 | https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice — source notices on both pages | fa2955ff48a1d82e77fc7296d63681670ecdb9d2811a0505ae60d0683b62fa64 |

## Exact words used and the resulting contract

D1: "Do not fetch a new token for each API request you make." Its token endpoint
is `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token`.
The request example uses `POST`, `application/x-www-form-urlencoded`,
`grant_type=client_credentials`, `client_id` and `client_secret` in the body.
D10's Process example uses `Authorization: Bearer <your_access_token>` and
`Content-Type: application/json` at `https://sh.dataspace.copernicus.eu/process/v1`.
No endpoint was contacted by this reading.

D3: "Use sentinel-2-l2a (previously S2L2A) as the value of the input.data.type
parameter in your API requests." The `leastCC` row says "pixel is selected from
tile with the least cloud coverage metadata" and warns that the per-tile figure
"is only an estimate". This establishes ordering, never cloud-free coverage.
The documented SCL categories supply the local exclusion policy for no-data,
defective pixels, shadows, unclassified/low-probability clouds, medium/high
clouds and cirrus. That policy is application-owned, not a publisher guarantee.

D8: "When mosaicking is SIMPLE:" — "scenes object is empty." Its TILE section
states "The length of scenes.tiles array is always the same as the length of
the samples array." The date property "represents the date the tile was
acquired." D7 demonstrates `outputMetadata.userData` and `userdata.json`.
The fixed TILE script selects the first unmasked sample in the requested order
and records dates only when its pixels contribute, rather than dumping every
candidate date. Node executes it against invented samples in the tests.

D9: "No-data pixels are marked by the value 0 in the dataMask band."
"Output file formats which support transparency are PNG and TIFF."
D8 defines AUTO values in the interval from zero to one, stretched to uint8;
D14's example applies factor 2.5 to B04/B03/B02. The code requests a four-channel
AUTO TIFF and a JSON userdata response in the same uncompressed tar response.
It decodes regular members in memory, validates raster size, type, georeference,
alpha and dates, and never extracts archive paths. A malformed/absent/out-of-window
contribution date or invalid raster refuses promotion. Coverage stays `partial`.
No claim of complete or cloud-free coverage is inferred from ordering.

D10: "The request image width. Must be an integer between 1 and 2500."
The height description has the same range. Its TimeRange description states:
"Both the start and end of a time interval are inclusive and can be equal."
The internal contract stays half-open. For second-precision UTC inputs, the
wire builder subtracts one second from its exclusive end; fractional inputs
are refused. D11 lists UTM north codes from 32601 through 32660 and requires
`input.bounds.properties.crs` to use the documented CRS URL. The owner-targeted
metric tiles retain their tested edge dimensions; no real Qatar frame was read.

The `cdse-process.v1` metadata records SCL/dataMask as auxiliary bands. Its
sanitized request hash covers the complete canonical JSON, including the fixed
script. The older `cdse-cache.v1` fixture metadata remains a separate internal
contract, with no claim that its invented responses came from this provider.
The old `pending.v1` Process envelope is refused. No separate metadata endpoint
is asserted; `Session.metadata` refuses before send, even with a reserved slot.

D4 says the monthly quotas "reset on the first day of every month". The General
Users table's Sentinel Hub column states requests/month `10 000`, PU/month
`10 000`, requests/minute `300` and PU/minute `300`. These are published ceilings,
not this account's remaining capacity. D5 defines the base image as
"an output (image) size of 512 x 512 pixels," with "3 collection input bands,"
and "one data sample per pixel (see sample),". Its Process minimum is
"0.005 PU for Process API and OGC API,"; the area-factor minimum is `0.01`.
"An exception is requesting dataMask which is not counted, unless it is the only
band included." "The multiplication factor equals the number of data samples
per pixel." SCL therefore adds a counted band; dataMask does not add another.
`documented_units` computes these unrounded factors exactly as rational numbers.
The tests exercise both area/request minima, sample/band factors and an invented
plan below/above the recorded nominal ceiling. The old CostModel remains an
explicit invented linear fixture, not the verified billing formula.
`bulk_budget` takes its counted input bands from the same `INPUT_BANDS` tuple
that builds the wire script, and requires a positive, explicit `tile_samples`
upper bound from its caller for every Process attempt, including reserved retries.
No default of one sample is inferred from TILE mosaicking. The lead still must
establish that bound before a live plan can be admitted.

D6: "To conform to the rate limiter, all rate limiting policies have to be
satisfied." A response of HTTP 429 stops the session; no automatic retry is
introduced. The minute limits do not establish an implemented pacing mechanism.
The fetched pages do not state a billing quantum or general rounding rule.
`BILLING_QUANTUM` remains null; no rounding quantum is inferred from rounded
examples. The upper number of TILE samples, metadata/token quota charges,
remaining account amounts, reserve selection and pacing still require lead
resolution before any bulk run. The fixed script alone establishes none of them.

## Imagery notice, interface terms and attribution

D12's title is "Terms and Conditions of the Copernicus Data Space Ecosystem".
It treats Sentinel data separately from other portal contents and directs the
reader to D15 for the data legal notice. Its restrictions on other portal
contents and the availability caveat are not an imagery CC BY grant. The
registry's `provider_terms` and `commit_allowed: false` stay in force.

D15 gives the unmodified-data source wording "Copernicus Sentinel data [Year]"
and the adapted-data wording "Contains modified Copernicus Sentinel data [Year]".
The transform here requires the adapted-data wording when displayed, with its
actual contributing year and notice link. Whether the interface needs additional
service-specific credit beyond these data notices is still pending: D12 requires
an appropriate credit for portal material but supplies no complete
Sentinel-Hub-specific display line. The later display owner must resolve that
field; no display or credit rendering is delivered by S2-T41.

## Remaining operational evidence

`cache.py` reuses `sidecar_for`, `commit_pair` and immutable snapshots. Roots stay
`data/public_cache` only; no imagery enters an analytical table, release, freeze,
product asset or serving route. Default gates and the guided story need no cache.
The registry's pending publisher/URL fields and the empty live allow-list are
retained until the lead reviews activation; the readings above do not silently
admit a host or change a registry row. Its current sidecar terms records remain
pending; this documentation is not a live receipt.

S2-T41 acceptance boxes three, four and five stay open: explicit live command
wiring/admission, reviewed real frame and response mapping, and a complete free
bulk budget have not been proved. Independent maker review, the lead's private
balance check, reserve/pacing selection and live proof remain required. No owner
narrowing or completed task criterion is inferred from an offline fixture.
