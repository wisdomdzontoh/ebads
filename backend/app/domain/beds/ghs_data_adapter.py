"""``GHSDataAdapter`` — reference adapter over Ghana Health Service facility data.

(docs/01 §5, built.)

``[IMPL]`` Ghana Health Service publishes no live bed-occupancy feed the prototype can poll
(the "GHS data" this project actually has is the static Greater Accra facility registry in
``backend/data/ga_facilities.csv``, loaded once by the seed script into the same
``bed_count`` table ``ManualAdapter`` reads). There is exactly one live registry in this
system, so a "second, differently-sourced" adapter would either sit on invented
infrastructure (a fake external feed no doc describes) or, as here, be a structurally
independent implementation over the data that exists. What FR2/NFR9 need proved is
*substitutability* — that the allocation engine works unchanged against any conforming
``BedDataSource`` — and a second class satisfying the same interface, registrable via
``facility.active_data_source``, proves exactly that without inventing behaviour. Connecting
a real GHS feed later is then "override ``fetch``/``reserve``/``release`` in this class (or
add a fourth adapter)", not a change to allocation code.

Subclasses ``ManualAdapter`` rather than reimplementing identical logic — the two are
byte-for-byte the same over the same store today; only ``name()`` differs.
"""

from __future__ import annotations

from app.domain.beds.manual_adapter import ManualAdapter


class GHSDataAdapter(ManualAdapter):
    """Reference adapter proving interface substitutability (docs/01 §5); same store as manual."""

    def name(self) -> str:
        return "ghs_data"
