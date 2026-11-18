# Maritime FPGA FIR — UART Binary Protocol v1

**Status: documented; full UART/FIR RTL and local COM4 physical hardware smoke-test passed on 17 November 2026 (user-provided evidence). v0.6 GUI-to-hardware validation pending.**

UART 115200 baud, 8N1, independent from Xilinx JTAG, little-endian binary data, CRC16/CCITT-FALSE (init FFFF, poly 1021, nonreflected, no final xor). Standard test CRC: `123456789` => `0x29B1`. Only one host request may be outstanding; maximum 512 samples, signed 24-bit Q16.8. Each input job resets FIR history (separate X and Y axes). Video frame data itself stays on the laptop.

## Request, command 0x01

| Field | Bytes | Content |
|---|---:|---|
| Sync | 2 | `A5 5A` |
| Version | 1 | `01` |
| Command | 1 | `01` (FIR batch) |
| Job ID | 1 | caller byte 0..255 |
| Count | 2 | N, unsigned little-endian, 1..512 |
| Payload | 3×N | signed 24-bit samples, little-endian, two's complement |
| CRC | 2 | CRC-16, little-endian, **version through end of payload** |

## Response, command 0x81

| Field | Bytes | Content |
|---|---:|---|
| Sync | 2 | `A5 5A` |
| Version | 1 | `01` |
| Command | 1 | `81` (FIR response) |
| Job ID | 1 | returned request ID |
| Status | 1 | 0 success, 1 invalid header, 2 bad CRC, 3 invalid count, 4 receiver timeout |
| Count | 2 | N if status 0; otherwise 0 |
| Payload | 3×N | signed filtered output, same sample order |
| CRC | 2 | CRC-16, little-endian, **version through end of payload** |

Host must verify sync, version, reply command, matching ID, status, count and CRC. Stale/mismatched responses are hard failures. A bad request is never processed by the FIR. An incomplete valid-length request triggers a timeout/error response. Send batches sequentially, not concurrently.

## Audio future compatibility

Current core resets history for each packet. That is suitable for separately padded X/Y video trajectories but **not** for continuous audio chunks. Preserved history/stream flags must be implemented as an explicit future version; do not suggest continuous chunk handling works yet.
