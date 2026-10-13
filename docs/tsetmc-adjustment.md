# TSETMC reference-price adjustment

The API and formula are documented in the README and function docstrings.
The calculation is implemented independently in fima, without importing either
comparison package or making additional requests for adjustment events.

## Source inspection

Pinned sources inspected from the published wheels:

- [finpy-tse 1.2.10](https://pypi.org/project/finpy-tse/1.2.10/),
  `finpy_tse.Get_Price_History`;
  [source repository](https://github.com/ARahimiQuant/finpy-tse).
- [pytse-client 0.19.1](https://pypi.org/project/pytse-client/0.19.1/),
  `pytse_client.download.adjust_price` and history field mappings;
  [source repository](https://github.com/Glyphack/pytse-client).

Finpy's `Final` and pytse's unadjusted `adjClose` correspond to fima's official
`ClosePrice`. Finpy's `Close` and pytse's `close` correspond to `LastPrice`.
Column names alone do not establish adjustment status. Both implementations
use successive exchange-reference/previous-official-close ratios. Finpy
truncates adjusted values to integers; pytse rounds them to whole rials.
Fima retains floating-point precision.

Finpy substitutes previous closes for references of 0 or 1000 specifically
when stitching different market-history segments. This does not establish
that 1000 is invalid for a single instrument. Fima does not stitch instruments
or substitute missing references. It rejects instrument mixing and invalid
ratio inputs; a positive reference of 1000 is accepted.

## Bounded live comparison

Observed on 2026-10-13 for **فملی**, InsCode **35425587644337450**, with a shared
adjustment endpoint of **2026-10-12**. Requests were cached locally, used
10-second connection and 20-second read timeouts, one-second spacing and TLS
verification. Cached data and downloaded third-party sources are not committed.

The official
[daily endpoint](https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/35425587644337450/0)
returned HTTP 200 JSON without redirects: **4,673** observations from
2007-02-04 through 2026-10-12, with **367** zero-trade rows and no duplicate
dates. All closing/reference prices were positive. Zero-trade rows can have
zero first/minimum/maximum prices while their official close/reference carries
a valid level. Some reference changes occurred during zero-trade periods,
including consecutive changes on 2013-06-09 and 2013-06-10. Retaining these
rows in the chronological chain matched the independent traded-date results.
This is evidence for the sampled chain, not proof of session completeness
or economic classification for every instrument.

Both pinned packages' legacy endpoints returned 200 after HTTP-to-HTTPS 303
redirects. Their histories had **4,306** rows, omitting the **367** official
zero-trade rows. Comparisons used only matching instrument/date observations,
with the latest date aligned. The exact pinned functions were executed against
cached responses; finpy's identifier lookup was restricted to this one instrument.

| Comparison on 4,306 matching dates | Maximum official-close difference |
| --- | --- |
| Fima floating output vs finpy adjusted `Final` | < 1 rial |
| Fima truncated for comparison vs finpy | 0 |
| Fima floating output vs pytse adjusted `adjClose` | < 0.5 rial |
| Fima rounded for comparison vs pytse | 0 |
| Fima raw vs official unadjusted chart | 0 |
| Fima rounded vs official adjusted chart | 0 |

Both official charts returned HTTP 200 without redirects and contained 4,306
traded rows at the same endpoint:
[unadjusted](https://members.tsetmc.com/tsev2/chart/data/Financial.aspx?i=35425587644337450&t=ph&a=0),
[adjusted](https://members.tsetmc.com/tsev2/chart/data/Financial.aspx?i=35425587644337450&t=ph&a=1).
The chart's fifth field is last trade and its seventh field is official close;
the raw chart was checked against both corresponding daily fields before
comparing adjusted closes. These are snapshot comparisons, not permanent
availability or exact-match guarantees.

## Supporting events and limitations

### Zero opening fields on traded observations

During the 2026-10-13 investigation of Issue #36, the official daily history
for Shasta, InsCode 2400322364771558, returned a 2023-10-09 record with
`priceFirst=0`, 5,605 transactions, closing price 1,267, last trade 1,273,
minimum 1,244 and maximum 1,285. The legacy official history for the same
instrument/date supplied opening price 1,244; a subsequent daily response also
supplied 1,244. Responses varied in row coverage as well. These observations
show that a zero opening field is not evidence of zero trades or a genuine
zero execution price. The exact cause of the source discrepancy is unverified.

Fima preserves the supplied zero in both `FirstPrice` and `AdjustedFirstPrice`
without fetching or inferring a replacement. It does not use the opening price
in adjustment ratios, so this source value must not reject the entire chain.
Negative, missing and nonfinite opening values still fail validation. Closing
and used reference prices remain finite and positive; zero last/minimum/maximum
prices still require an explicit zero transaction count. The captured Shasta
record is covered by a mocked deterministic regression. Foolad's reported error
was reproduced in a ticker call, but subsequent responses passed; the offending
Foolad record was not captured, so its exact date is not established.

The official
[event endpoint](https://cdn.tsetmc.com/api/ClosingPrice/GetPriceAdjustList/35425587644337450)
returned 24 entries with null `corporateTypeCode`. Its two separate entries on
2011-07-05 describe before/after prices **15241 → 12991** and **12991 → 4911**.
Both were retained in the investigation, without deduplication or reliance on
response ordering. Their combined ratio agrees with that date's reference
discontinuity. The daily chain had 31 non-unit ratios, so the archive must not
be assumed complete or one-to-one with observations.

Reference gaps can reflect source corrections or other market behavior.
The helper cannot infer dividends, splits, rights or cash subscriptions from
those gaps, and does not certify investor total returns. Gaps in supplied dates
are linked as observations; callers remain responsible for data coverage.
Synthetic tests establish arithmetic and validation, not corporate-action
economics. Additional securities, market transitions and event-based economic
validation deserve separate work.
