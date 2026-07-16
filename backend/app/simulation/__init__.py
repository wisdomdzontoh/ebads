"""Discrete-event simulation package (docs/07-simulation.md).

The simulation is the project's evaluation instrument: it generates synthetic emergency
events and submits them through the *same* allocation code path as live operation
(``AllocationService.evaluate``), isolated per session over ``simulation_bed_state``. Every
run is reproducible under its recorded seed. See ``events`` (generation), ``distance_matrix``
(precomputed travel times), ``engine`` (the event loop), ``metrics`` (ATBP/FRR/MCEE/CM),
``service`` (session lifecycle), and ``runner`` (the batch grid).
"""
