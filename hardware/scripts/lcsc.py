"""BOM line -> JLCPCB/LCSC part mapping (phase B, plan Task 2).

Key: "<value>|<footprint>" exactly as the netlist holds them.  Each entry:
  {"lcsc": "C1234", "mpn": "...", "fallback": "C5678" or None, "note": "..."}
A fallback is pre-chosen for every line whose LCSC stock was under 200 when chosen.
fallback "GLOBAL" = JLCPCB global sourcing of the same part (still machine-placed).
Parts chosen 2026-11-13 against the JLCPCB parts API (see check_stock.py).
"""
from collections import defaultdict
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_netlist  # noqa: E402
from fpmap import in_bom  # noqa: E402

LCSC = {
    '1.2k|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C22765', "mpn": '0603WAF1201T5E', "fallback": None, "note": 'basic'},
    '10R|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C22859', "mpn": '0603WAF100JT5E', "fallback": None, "note": 'basic'},
    '10k|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C25804', "mpn": '0603WAF1002T5E', "fallback": None, "note": 'basic'},
    '100k|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C25803', "mpn": '0603WAF1003T5E', "fallback": None, "note": 'basic'},
    '133k|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C22870', "mpn": '0603WAF1333T5E', "fallback": None, "note": 'extended; fallback: same value from any 1 % 0603 maker'},
    '174k|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C22890', "mpn": '0603WAF1743T5E', "fallback": None, "note": 'extended'},
    '20.5k|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C22910', "mpn": '0603WAF2052T5E', "fallback": None, "note": 'extended'},
    '200k|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C25811', "mpn": '0603WAF2003T5E', "fallback": None, "note": 'basic'},
    '31.6k|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C25967', "mpn": '0603WAF3162T5E', "fallback": None, "note": 'extended'},
    '330|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C23138', "mpn": '0603WAF3300T5E', "fallback": None, "note": 'basic'},
    '33R|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C23140', "mpn": '0603WAF330JT5E', "fallback": None, "note": 'basic'},
    '348k|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C23006', "mpn": '0603WAF3483T5E', "fallback": None, "note": 'extended'},
    '4.7k|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C23162', "mpn": '0603WAF4701T5E', "fallback": None, "note": 'basic'},
    '43.2k|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C23053', "mpn": '0603WAF4322T5E', "fallback": None, "note": 'extended; quad ILIM, must stay inside 41.2-45.3 k'},
    '47k|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C25819', "mpn": '0603WAF4702T5E', "fallback": None, "note": 'basic'},
    '5.11k|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C23067', "mpn": '0603WAF5111T5E', "fallback": None, "note": 'extended; quad SNS scale'},
    '634k|Resistor_SMD:R_0603_1608Metric': {"lcsc": 'C65831', "mpn": '0603WAF6343T5E', "fallback": None, "note": 'extended'},
    '220|Resistor_SMD:R_1206_3216Metric': {"lcsc": 'C17957', "mpn": '1206W4F2200T5E', "fallback": None, "note": 'yellow series, 0.25 W'},
    '240k|Resistor_SMD:R_1206_3216Metric': {"lcsc": 'C18001', "mpn": '1206W4F2403T5E', "fallback": None, "note": '200 V 1206'},
    '30k|Resistor_SMD:R_1206_3216Metric': {"lcsc": 'C17999', "mpn": '1206W4F3002T5E', "fallback": None, "note": '200 V 1206'},
    '33m 1% 1W|Resistor_SMD:R_2512_6332Metric': {"lcsc": 'C2985721', "mpn": 'HoLLR2512-3W-33mR-1%', "fallback": 'C2903495', "note": 'R100, 3 W rated (>= 1 W)'},
    '100nF 100V|Capacitor_SMD:C_0805_2012Metric': {"lcsc": 'C28233', "mpn": 'CL21B104KCFNNNE', "fallback": 'C85866', "note": 'basic; VBAT/VBAT_B/VLOGIC_IN side, sees 50.6 V clamp'},
    '100nF 100V|Capacitor_SMD:C_0603_1608Metric': {"lcsc": 'C15725', "mpn": 'CL10B104KC8NNNC', "fallback": 'C77058', "note": 'C1 on VBAT_F, sees 50.6 V clamp'},
    '100nF|Capacitor_SMD:C_0603_1608Metric': {"lcsc": 'C14663', "mpn": 'CC0603KRX7R9BB104', "fallback": None, "note": 'basic, 50 V, logic rails'},
    '10nF 100V|Capacitor_SMD:C_0805_2012Metric': {"lcsc": 'C18741', "mpn": 'CL21B103KCANNNC', "fallback": None, "note": 'pod outputs'},
    '10nF|Capacitor_SMD:C_0603_1608Metric': {"lcsc": 'C57112', "mpn": '0603B103K500NT', "fallback": None, "note": 'basic'},
    '10uF|Capacitor_SMD:C_0603_1608Metric': {"lcsc": 'C19702', "mpn": 'CL10A106KP8NNNC', "fallback": None, "note": 'basic, 10 V, +3V3_ALW'},
    '1uF|Capacitor_SMD:C_0603_1608Metric': {"lcsc": 'C15849', "mpn": 'CL10A105KB8NNNC', "fallback": None, "note": 'basic, 50 V'},
    '1uF|Capacitor_SMD:C_1206_3216Metric': {"lcsc": 'C13832', "mpn": 'CL31B105KCHNNNE', "fallback": None, "note": '100 V, VBAT'},
    '2.2nF|Capacitor_SMD:C_0603_1608Metric': {"lcsc": 'C1604', "mpn": '0603B222K500NT', "fallback": None, "note": 'basic, 50 V'},
    '2.2uF|Capacitor_SMD:C_1206_3216Metric': {"lcsc": 'C170101', "mpn": 'CL31B225KCHSNNE', "fallback": None, "note": '100 V, VBAT/VLOGIC_IN'},
    '220nF|Capacitor_SMD:C_0603_1608Metric': {"lcsc": 'C107083', "mpn": 'CC0603KRX7R9BB224', "fallback": None, "note": '50 V; C63 on VCC10 (22 V zener, 23.3 V max)'},
    '220uF 63V|Capacitor_SMD:CP_Elec_10x10.5': {"lcsc": 'C56151978', "mpn": 'RVT1J221M1010', "fallback": 'C42393541', "note": 'Lelon V-chip 105 C; C68 pod ripple to be checked in the dissipation tally'},
    '22uF 63V|Capacitor_SMD:CP_Elec_6.3x7.7': {"lcsc": 'C72501', "mpn": 'RVT1J220M0607', "fallback": 'C57549', "note": 'C65, LTC4380 OUT bypass'},
    '22uF|Capacitor_SMD:C_0603_1608Metric': {"lcsc": 'C86295', "mpn": 'CL10A226MP8NUNE', "fallback": None, "note": '10 V X5R, buck outputs'},
    '39pF|Capacitor_SMD:C_0603_1608Metric': {"lcsc": 'C1666', "mpn": '0603CG390J500NT', "fallback": 'C107049', "note": 'C0G'},
    '47nF|Capacitor_SMD:C_0805_2012Metric': {"lcsc": 'C17074', "mpn": 'CL21B473KCFNNNE', "fallback": 'C107126', "note": '100 V, LTC4380 gate RC'},
    '680nF|Capacitor_SMD:C_0603_1608Metric': {"lcsc": 'C107067', "mpn": 'CC0603KRX7R7BB684', "fallback": None, "note": '16 V, LTC4380 TMR'},
    '68pF|Capacitor_SMD:C_0603_1608Metric': {"lcsc": 'C28262', "mpn": 'CL10C680JB8NNNC', "fallback": None, "note": 'C0G'},
    '1N4148|Diode_SMD:D_SOD-323': {"lcsc": 'C2128', "mpn": '1N4148WS', "fallback": None, "note": 'basic'},
    '22V|Diode_SMD:D_SOD-123': {"lcsc": 'C2108', "mpn": 'BZT52C22', "fallback": 'C131843', "note": 'D21 VCC10 clamp'},
    'BAT54|Diode_SMD:D_SOD-123': {"lcsc": 'C699107', "mpn": 'BAT54W', "fallback": 'C131469', "note": 'SOD-123 Schottky, SNS clamps'},
    'BZT52C5V6|Diode_SMD:D_SOD-123': {"lcsc": 'C2119', "mpn": 'BZT52C5V6', "fallback": 'C12770', "note": 'yellow clamps'},
    'MMSZ5245B|Diode_SMD:D_SOD-123': {"lcsc": 'C2126', "mpn": 'MMSZ5245B', "fallback": 'C129730', "note": '15 V, Q13 gate'},
    'SMBJ24A|Diode_SMD:D_SMB': {"lcsc": 'C123819', "mpn": 'SMBJ24A', "fallback": 'C87268', "note": 'unidirectional 600 W'},
    'Schottky 40V|Diode_SMD:D_SMA': {"lcsc": 'C2480', "mpn": 'SS14', "fallback": None, "note": 'basic, 40 V 1 A'},
    'PESD2CANFD24LT-Q|Package_TO_SOT_SMD:SOT-23': {"lcsc": 'C6952426', "mpn": 'PESD2CANFD24LT-QR', "fallback": 'C14486', "note": 'fallback SZ... NUP2105LT1G-family pinning must be re-checked before use'},
    '1.5uH|Inductor_SMD:L_Vishay_IHLP-4040': {"lcsc": 'C845071', "mpn": 'IHLP4040DZER1R5M01', "fallback": 'GLOBAL', "note": 'stock 320 at selection; fallback = JLCPCB global sourcing of the same part'},
    '7448031002|mccan:Wurth_WE-CMBNC_7448031002': {"lcsc": 'C1519839', "mpn": '7448031002', "fallback": 'GLOBAL', "note": 'THROUGH-HOLE: JLCPCB THT assembly (owner 2026-11-13); stock 11 at selection'},
    'ACT45B-510-2P-TL003|mccan:TDK_ACT45B': {"lcsc": 'C76584', "mpn": 'ACT45B-510-2P-TL003', "fallback": None, "note": 'CAN choke'},
    'MDA7030-220M|Inductor_SMD:L_KOHERelec_MDA7030': {"lcsc": 'C2847487', "mpn": 'MDA7030-220M', "fallback": 'C2847545', "note": 'replaces XAL7070-223ME (no stock); fallback MDA7050-220M needs a footprint change'},
    '74AHCT1G126GV|Package_TO_SOT_SMD:SOT-23-5': {"lcsc": 'C52140416', "mpn": '74AHCT1G126GV', "fallback": 'C842288', "note": 'fallback 74AHCT1G126W5-7 (Diodes SOT-25) -- re-check pinout before use'},
    'BTS7008-2EPA|Package_SO:Infineon_PG-TSDSO-14-22': {"lcsc": 'C534830', "mpn": 'BTS7008-2EPA', "fallback": None, "note": 'pod switch'},
    'ESP32-WROOM-32E-N8|RF_Module:ESP32-WROOM-32E': {"lcsc": 'C701342', "mpn": 'ESP32-WROOM-32E-N8', "fallback": None, "note": ''},
    'IPT007N06N|Package_TO_SOT_SMD:Infineon_PG-HSOF-8-1': {"lcsc": 'C122552', "mpn": 'IPT007N06N', "fallback": 'C531199', "note": 'replaces IPT008N06NM5LF (no stock); fallback IPT012N08N5 -- re-check SOA'},
    'LM5164DDA|Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.62x3.51mm': {"lcsc": 'C477928', "mpn": 'LM5164DDAR', "fallback": 'GLOBAL', "note": 'stock 323 at selection'},
    'LTC4380HMS-2|Package_SO:MSOP-10_3x3mm_P0.5mm': {"lcsc": 'C688451', "mpn": 'LTC4380HMS-2#PBF', "fallback": 'GLOBAL', "note": 'OWNER 2026-11-13: global-source the H grade (JLCPCB stock 3). I grade C688471 rated only to 85 C'},
    'MMBT3904|Package_TO_SOT_SMD:SOT-23': {"lcsc": 'C20526', "mpn": 'MMBT3904', "fallback": None, "note": 'basic'},
    'SQJ461EP|Package_SO:PowerPAK_SO-8L_Single': {"lcsc": 'C3279500', "mpn": 'SQJ461EP-T1_GE3', "fallback": None, "note": 'feed B FET'},
    'TJA1042T/3|Package_SO:SOIC-8_3.9x4.9mm_P1.27mm': {"lcsc": 'C132227', "mpn": 'TJA1042T/3/1J', "fallback": 'C2874888', "note": ''},
    'TPS4HC120AQDGQRQ1|mccan:TI_DGQ0028C': {"lcsc": 'C44545560', "mpn": 'TPS4HC120AQDGQRQ1', "fallback": None, "note": 'replaces TPS4H160BQPWPRQ1 (no stock), owner 2026-11-13'},
    'BOOT|Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A': {"lcsc": 'C318884', "mpn": 'TS-1187A-B-A-B', "fallback": None, "note": 'basic'},
    'EN/RESET|Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A': {"lcsc": 'C318884', "mpn": 'TS-1187A-B-A-B', "fallback": None, "note": 'basic'},
    'Prog/UART|Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical': {"lcsc": 'C492405', "mpn": 'PZ254V-11-06P', "fallback": None, "note": 'THROUGH-HOLE: assembled by JLCPCB (J2 decision: fitted, not DNP)'},
}


def bom_lines(netlist_path):
    """Non-DNP, in_bom() parts grouped by value + footprint, sorted by key."""
    nl = check_netlist.load(netlist_path)
    groups = defaultdict(list)
    for ref, p in nl.parts.items():
        if p.dnp or not in_bom(ref):
            continue
        groups["%s|%s" % (p.value, p.footprint)].append(ref)
    return sorted((k, sorted(v, key=lambda r: (r.rstrip("0123456789"), int("0" + r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ_")))))
                  for k, v in groups.items())
