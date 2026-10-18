# Final fix wave report

Gates: generators run twice in order (symlib, power_input, rails, mcu_can, outputs, root); second pass md5-identical.
ERC: 0 errors, 0 warnings. check_netlist.py: PASS deleted, feed_b, rails, mcu, outputs, harness, boot_safety. verify_fpmap.py: 144 verified, 0 failures, exit 0.

- I1: R33 10k -> 47k (gen_mcu_can.py:298, note, README, check_netlist `outputs` check, gen_outputs note). 47k || 33.3k = 19.5k -> 2.66 V vs VIH 2.0 V. Netlist: /DIAG_EN_Q = R30.2 R33.1 U11.14 U12.14 U13.14; R33 value 47k.
- I2: NT1.2 moved GND -> GND_IN. The geometry lives in layout_power_input.py (read as data by gen_power_input.py): removed #PWR07, added a wire and a local GND_IN label at NT1 pin 2; roster entry "GND(feed B)" removed, NT1.2 added to GND_IN. Why: keeps feed A's and feed B's return current from bypassing L2's return winding (DC common-mode imbalance). check_netlist chk_nt1 asserts one pin GND_B, one GND_IN, and no part other than NT1 touches GND_B and a ground net. README, notes_power_input.py, harness.md updated. Netlist: GND_B = C66.2 D25.2 J9.2 NT1.1 R108.2; GND_IN has 13 members incl. NT1.2; GND has L2.3 and no NT1.
- I3: NT1 footprint -> NetTie:NetTie-2_SMD_Pad2.0mm (exists in NetTie.pretty; verified in netlist). harness.md, README, sheet notes now state per-feed protection (other feed disconnected, or whole harness reversed); one feed reversed with the other connected faults via NT1 until the harness fuse clears. Bring-up line added.
- M1: 100 k min / 175 typ / 250 max; 47k || 100k = 32.0k -> 2.88 V (quadpins.py, gen_outputs.py note, part-selection.md).
- M2: GPIO15 text corrected (README, gen_mcu_can note); bring-up line with optional 10k pull-up on MCU side of R32 (not added).
- M3: bring-up line only (espefuse set_flash_voltage 3.3V is irreversible, owner's decision, not run).
- M5: gen_outputs.py note: tau = 65 us, wait >= 400 us after any DIAG_SEL or DIAG_EN change (also in bring-up checklist).
- M6: quadpins.py and part-selection.md: 0.08 A is steady current, inrush unmeasured (spec 9.2).
- M7: part-selection.md tiebreak row and spec 4.4: off-state open-load needs an external pull-up (Table 7-2 note 1, p.22), absent here; only on-state CS resolves lamp-out. Also removed "open-load detection in silicon" from spec 4.4's first claim.
- M8: C66 value "100nF 100V"; chk_c66 and the table now require it. Netlist: C66 = 100nF 100V.
- M10: README.md:4-5 point at the 2026-10-17 spec and 2026-10-18 phase-A plan; spec 6 item 3 -> "current limit, then thermal latch-off (THER high)".

Notes: no phase-A bring-up checklist existed (hardware/docs/bring-up.md is plan3), so the lines were added as "Phase-A bring-up checklist (additions)" in hardware/README.md. The plan file still names NetTie 0.5mm and GND for NT1 (plan history, untouched).
