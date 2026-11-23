# Maritime FPGA FIR — UART Binary Protocol v1

**Status: documented; full UART/FIR RTL and local COM4 physical hardware smoke-test passed on 17 November 2026 (user-provided evidence). v0.6 GUI-to-hardware validation pending.**

UART 115200 baud, 8N1, independent from Xilinx JTAG, little-endian binary data, CRC16/CCITT-FALSE (init FFFF, poly 1021, nonreflected, no final xor). Standard test CRC: `123456789` => `0x29B1`. Only one host request may be outstanding; maximum 512 samples, signed 24-bit Q16.8. **v0.9 adds a second coefficient bank selected by the high bit of the Job ID.** Each input job resets FIR history (separate X and Y axes). Video frame data itself stays on the laptop.

## Request, command 0x01

| Field | Bytes | Content |
|---|---:|---|
| Sync | 2 | `A5 5A` |
| Version | 1 | `01` |
| Command | 1 | `01` (FIR batch) |
| Job ID | 1 | **0x00–0x7F = legacy 30 Hz motion FIR; 0x80–0xFF = 16 kHz speech-band audio FIR** (requires v0.9 bitstream) |
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
| Status | 1 | 0 success, 1 invalid header, 2 bad CRC, 3 invalid count, 4 receiver timeout, 5 UART framing error (invalid stop bit) |
| Count | 2 | N if status 0; otherwise 0 |
| Payload | 3×N | signed filtered output, same sample order |
| CRC | 2 | CRC-16, little-endian, **version through end of payload** |

Host must verify sync, version, reply command, matching ID, status, count and CRC. Stale/mismatched responses are hard failures. A bad request is never processed by the FIR. An incomplete valid-length request triggers a timeout/error response. Send batches sequentially, not concurrently.

## v0.9 audio extension (requires fresh bitstream)

The UART byte layout, CRC, command (`0x01`) and response (`0x81`) are unchanged. The **request Job ID high bit** selects the FIR bank:

- `job_id & 0x80 == 0`: original 17-tap camera-motion low-pass coefficients for 30 fps X/Y/roll.
- `job_id & 0x80 != 0`: new 17-tap **16 kHz** Hamming-window **3.2 kHz** low-pass speech-band coefficients. The host sends signed PCM16 samples shifted left 8 bits into signed 24-bit Q16.8. The returned Q16.8 samples are shifted right 8 bits to PCM16 after bit-exact verification.

Each job still resets the FIR state. **For longer offline audio**, the host must send 496 *new* samples per job plus eight original left-context and eight right-context samples, taking returned positions `16:16+n`. Every job is verified bit-for-bit against the full continuous Python reference. It is **not live audio streaming**: at 115200 baud the UART cannot support 16 kHz bidirectional PCM16 in real time. The v0.8.2 bitstream only contains the motion bank; its high job IDs do not filter audio correctly.

A new  audio mode will be required for future adaptive noise algorithms, spectrogram-based processing, or streaming control. Current v0.9 targets high-frequency hiss; it cannot selectively remove in-band speech and machinery noise.
