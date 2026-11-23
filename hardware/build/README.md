# The one Vivado project

`maritime_a7.xpr` is the **sole canonical portable Xilinx project**. Open this
file directly to inspect RTL, run XSim, implement and view reports.

A fresh build or a GUI run generates `maritime_a7.runs/`, `maritime_a7.gen/`,
`maritime_a7.cache/`, `maritime_a7.srcs/`, `reports/` etc. in THIS folder.
Generated files are excluded from source ZIPs and Git.

Run the root `scripts/final_rebuild_and_reports.ps1` for a complete clean
XSim + synthesis + implementation + report archive. It archives generated
files, but not the one authoritative `.xpr`.

Do not duplicate or commit a second `.xpr` under a root-level `build/`.
