# Cropstar

Farm management for regenerative agriculture. This glossary fixes the words used in code,
UI and conversation. Area terms follow the Austrian AMA / INVEKOS standard; German is the
primary UI language, English names are used in code and the English UI.

## Organisation

**Farm** (de: _Betrieb_):
The agricultural holding that owns all farm data — fields, plots, tasks. Every piece of
farm data belongs to exactly one Farm, never to a User directly.
_Avoid_: Account, Tenant, Organisation, Hof

**User** (de: _Benutzer_):
A person who can sign in. A User has no farm data of their own; access comes only through
Memberships.
_Avoid_: Account, Farmer (a Farmer is a role in the real world, not an identity)

**Membership** (de: _Mitgliedschaft_):
The link between one User and one Farm, carrying exactly one Role. A User can be a member
of several Farms, a Farm has several members.

**Role** (de: _Rolle_):
What a member may do on a Farm: **Admin** (de: _Admin_), **Worker** (de: _Mitarbeiter_)
or **Advisor** (de: _Berater_).

**Instance Operator** (de: _Instanz-Betreiber_):
Whoever runs a Cropstar installation. Configures the instance; is not a Role on any Farm.
_Avoid_: Admin (that is a Role on a Farm), Superuser

## Areas

**Harvest Year** (de: _Erntejahr_):
The year in which a Plot's main crop is harvested; identical to the AMA application year
(_Antragsjahr_). Every Field, Plot and Operation belongs to exactly one Harvest Year,
regardless of the calendar date of the work.
_Avoid_: Season, Wirtschaftsjahr, Kalenderjahr

**Locked Harvest Year** (de: _gesperrtes Erntejahr_):
A Harvest Year an Admin has closed; nothing that refers to it can be changed until an
Admin unlocks it.

**Field** (de: _Feldstück_):
A contiguous area of land as declared to AMA / INVEKOS for one Harvest Year. The same
ground in another year is a different Field; continuity across years is spatial, not by
number.
_Avoid_: Parcel, Plot (a Plot is a part of a Field), Acker

**Plot** (de: _Schlag_):
A part of a Field carrying one crop in one Harvest Year, as declared to AMA / INVEKOS. The
Plot is the unit the simulation model works on.
_Avoid_: Field (a Field contains Plots), Parzelle, Teilfläche

**Land Use** (de: _Nutzungsart_):
What a Field or Plot is declared to AMA as used for: broad for a Field (arable land,
grassland), specific for a Plot (winter rye, green fallow). Identified by its AMA code.
_Avoid_: Crop, Kultur (fallow and grassland are not crops)

**Land Use Category** (de: _Nutzungskategorie_):
The broad group a Plot's Land Use belongs to, such as cereals, legumes, fallow or
grassland, following the European crop taxonomy HCAT.
_Avoid_: Crop group, Fruchtart

**Declared Area** (de: _beantragte Fläche_):
The area of a Field or Plot as declared to AMA. Cropstar shows it as declared and never
recomputes it from the geometry.
_Avoid_: Size, Fläche (unqualified)

## Work

**Task** (de: _Aufgabe_):
Any piece of work on a Farm that someone intends to do or has done. It may refer to any
number of Fields and Plots, or to none; if it refers to any, they all share one Harvest
Year. A Task recorded after the fact is created as Done.
_Avoid_: Todo, Job, Auftrag

**Status** (de: _Status_):
**Open** (de: _offen_), **Done** (de: _erledigt_) or **Discarded** (de: _verworfen_).
Discarding is reversible; deleting is not, and a deleted Task leaves no trace. A Task
with Operations takes its Status from them: Open while any Operation is Open.

**Operation Type** (de: _Maßnahmen-Typ_):
One entry of the list of kinds of work the model and reports understand, e.g. tillage,
sowing, fertilisation, harvest. The list is the same for every Farm. A Task with an
Operation Type refers to Plots only, at least one.

**Operation** (de: _Maßnahme_):
The Plot-specific part of a Task that has an Operation Type: one Operation per Plot,
each with its own Status, Planned Details and Actual Details.
_Avoid_: Management event, Measure, Activity

**Planned Details** (de: _Plan-Details_):
What an Operation is intended to apply, e.g. amount and date. Entered once on the Task
and adjustable per Operation.

**Actual Details** (de: _Ist-Details_):
What an Operation really applied. Recorded when the Operation is Done, defaulting to the
Planned Details. Only Actual Details count as having happened.

**Operation Log** (de: _Maßnahmenprotokoll_):
All Done Operations of one Plot, in date order.
_Avoid_: Field record, Schlagkartei
