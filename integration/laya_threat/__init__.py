"""EP-225 (D-202): opponent damage threat for the laya renderer v9.

v7 text with (1) the assumed foe set's spread made consistent with its item and attack category before every damage
calculation, and (2) worst plausible incoming damage on switch options and the active Pokemon. Lives outside
`integration/laya_imitation`, which stays byte-identical while EP-224 runs; laya_imitation's damage path is reused by
replacing `features._opp_spec` only while a v9 render runs (`spreads.patched`).
"""
