---
status: accepted
---

# Area Uploads assign declared areas to existing ones; nothing is guessed or copied

An Area Upload for a Harvest Year that already has Fields and Plots asks the Admin, for
every declared area, whether it is the same piece of land as an existing one or new,
without history. Areas that are unchanged or covered at least 90 % by exactly one existing
area are prefilled, and the Admin can change them. Everything else starts undecided, with
overlapping existing areas listed first, and the upload cannot be applied until every
area is decided. Within one Harvest Year an assignment is 1:1. The existing Field or Plot
is updated in place, so its Tasks and Operations stay with the land even if AMA
renumbered it or moved it to another Field. Existing areas nobody is assigned to are
removed. If Tasks or Operations refer to such an area, the upload is refused.

This settles the open point in ADR 0002. AMA numbers are not stable, so we do not match by
number. Matching by geometry alone (an IoU threshold) still guesses at splits, merges and
redrawn boundaries, and a wrong guess silently moves recorded work onto different ground.
We rejected copying or inheriting Operations when a Plot is split or merged: an Operation
happened once, on one piece of land.

## Consequences

- Splitting or merging a Plot that already has Operations within the same Harvest Year is
  blocked; the Admin first moves that work to a remaining Plot or deletes it.
- The reconciliation does not assume both sides belong to the same Harvest Year. Starting
  a new Harvest Year from the previous one (M4) will reuse it to record **confirmed
  links** between Plots of consecutive years ("Plot z comes from x and y"). Area shares
  are computed from geometry, not stored, which is why amounts in Operation details are
  per hectare.
