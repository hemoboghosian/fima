# Security maintenance

## External HTML and Soup Sieve

CVE-2026-126190 affects Soup Sieve versions below 4.0. Python 3.10 resolves
Soup Sieve 2.10; patched releases require Python >=3.11.5. fima preserves Python
3.10 support and mitigates the vulnerable matching path at the application
level. This does **not** patch the installed dependency or suppress its alerts.

Provider markup is external input. CSS expressions are internal constants or
are constructed from internal grid names, not user-supplied CSS. The affected
descendant chains are:

| Module | Chains |
| --- | --- |
| IFB | page-size div/select; panel heading/label; payment and financing table/pager row |
| Funds | thead/header; tbody/row; tfoot/pager/next link |
| KILID | trend container/table; thead/header; tbody/row |
| _ifb_market_values | market-value container/table |

`_html` matches each simple component locally and carries ancestor-prefix
matches forward in document order. Each tag is evaluated once per component;
it does not repeatedly backtrack through ancestors. Matching scope, first/all
results, order and uniqueness follow the original CSS behavior. No arbitrary
page-size/depth limit or financial-data truncation is introduced. Existing
missing/ambiguous-section and pagination checks still apply.

All remaining CSS calls in CBI, TGJU, IFB, Funds, KILID, `_ifb_reports`,
`_ifb_yields` and `_ifb_market_values` use single compound selectors or the
direct-child combinator. KILID's private `_one` takes internal selectors only.
Future changes must not pass descendant chains or untrusted selector strings
to Soup Sieve on Python 3.10. Upstream selector-compilation advisories remain
in the compatible dependency, but fima exposes no public CSS-selector input.

A bounded reproduction of IFB's missing-container lookup on Soup Sieve 2.10
performed 5,150 / 20,300 / 80,600 selector checks for 100 / 200 / 400 nested
tables. The deterministic regression counts operations rather than timing.
Normal provider fixtures, financial values, ambiguity errors, history and
pagination are tested separately. This mitigation does not promise bounded
resource use for every operation on arbitrary hostile HTML.

Reference: [upstream advisory](https://github.com/facelessuser/soupsieve/security/advisories/GHSA-mmhr-3c5m-f64f).
