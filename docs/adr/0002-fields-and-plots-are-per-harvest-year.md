---
status: accepted
---

# Fields and Plots are per-Harvest-Year snapshots of the AMA application

A Field (Feldstück) and a Plot (Schlag) each belong to exactly one Harvest Year, which is
the AMA application year. The same ground in another year is a different Field or Plot.
Continuity across years ("what grew here in 2024?") is resolved spatially, not by number.
We considered permanent Fields with yearly Plots. We rejected it because AMA does not keep
field numbers stable: the farmer picks and can change them, and the public `fs_kennung` is
reissued every release. An import would therefore have to guess identity that AMA itself
does not guarantee.

## Consequences

- An Operation belongs to the Harvest Year of its Plot, not to the calendar year of its
  date. For example, sowing winter wheat in October 2026 belongs to Harvest Year 2027.
  This means a Plot may have to exist in Cropstar before AMA knows it; how such Plots are
  reconciled with a later import is decided in the import slice.
- Locking a Harvest Year freezes everything that refers to it.
