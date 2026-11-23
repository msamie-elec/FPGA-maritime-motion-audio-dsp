# FPGA die-temperature evidence — Vivado XADC

**Current evidence, 23 November 2026:** **36 operator-provided XADC snapshots**, 
31.6–32.4°C, latest 32.2°C at 14:30:17 GMT. 14 idle (mean 31.871°C), 
20 post-processing (mean 32.065°C), plus two earlier `soak_end` labels which
**do not** imply a confirmed soak workload. The 20 post-processing readings
were made after, not continuously during, GUI processing. 
See `evidence/xadc_2026-11-23/README.md` and the original archived CSV.

Vivado's 0.071 W is a **post-route vectorless power estimate**. The XADC is
actual silicon die temperature measured through JTAG, not board input power,
room temperature or an automatically collected 15-minute heat-soak trace.

**Caution:** Running XADC Tcl queries concurrently with the active Windows GUI
UART/video processing previously coincided with a stalled GUI job. Avoid
concurrent JTAG monitoring until the interaction is independently tested;
read immediately after processing instead, with the GUI idle.

## Capture one actual measurement (Arty A7-35T)

1. Connect and power the board. Open **Vivado Hardware Manager → Open Target → Auto Connect**.
2. Program the tested bitstream if the FPGA has lost its configuration.
3. Open Vivado's **Tcl Console**. Change directory to the **extracted project root**. The following path is only an example; replace it with yours:

```tcl
cd {C:/path/to/FPGA_Maritime_AV_RevF}
set ::env(MARITIME_PHASE) idle
source hardware/vivado/sample_xadc_snapshot.tcl
```

The script queries `get_hw_sysmons` and the `TEMPERATURE` property. A valid
measurement prints `XADC_SNAPSHOT idle die_temperature_c=...`, and appends one row
to `evidence/final_validation/xadc_snapshots.csv` with the local timestamp,
operator-labelled phase and die temperature in degrees Celsius. If no XADC is
available or the value cannot be read, the script fails **without inserting a
fabricated reading**.

4. In the desktop GUI open **Summary Report → Refresh evidence**. The "Die temp
(XADC)" tile displays the latest recorded reading, and the detailed report
lists every imported reading with its phase and timestamp.

If you want temperature **under a workload**, record a new idle reading and
then a separate `during_workload` or `after_workload` reading by setting
`::env(MARITIME_PHASE)` accordingly before sourcing again. Run only one program
that owns COM4 at a time; a serial console or another Python client should not
open COM4 while a UART test runs. **XADC Hardware Manager connections themselves
are not a serial COM4 temperature monitor.**

## Interpretation and limits

- These readings are **FPGA silicon die temperature**, not ambient room
  temperature and not total Arty board power.
- Log ambient temperature and power configuration separately if needed.
- An idle snapshot taken now **cannot** establish what the device temperature
  was during the already completed 15-minute soak. Meaningful idle-vs-workload
  comparison needs readings captured at those conditions.
- There is no controlled hot/cold temperature-chamber qualification here.
- The summary distinguishes the measured reading from Vivado's vectorless
  power estimate; if the CSV does not exist it displays **NOT MEASURED**.

## Actual 23 November operator-supplied data

The complete 36-row unmodified CSV is included in the engineering ZIP at
`evidence/final_validation/xadc_snapshots.csv` and, for source-safe GitHub
readers, in `evidence/xadc_2026-11-23/xadc_snapshots.csv`. The GUI prefers
locally recorded snapshots if present, otherwise uses these **labelled
archived** snapshots. No live sensor reading is inferred from simply opening
the GUI. The highest observed discrete reading was 32.4°C, not necessarily
the peak temperature under continuous activity.
