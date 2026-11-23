`timescale 1ns / 1ps
// SPDX-License-Identifier: MIT
// BTN0 is a human-operated, active-high ASYNCHRONOUS input.
// All three stages are plain clocked flip-flops: there is NO asynchronous
// set/reset control pin that can propagate to a RAMB18 enable or address.
// ASYNC_REG and SHREG_EXTRACT=NO preserve physical metastability filtering.
// Artix-7 flip-flop INIT=1 initializes the system into reset after FPGA
// configuration. Reset assertion and release each need 3 rising edges.
// A sub-clock button pulse is not guaranteed to be detected (by design).
module reset_sync (
    input  logic clk,
    input  logic button_reset,
    output logic rst
);
    (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO" *)
    logic [2:0] stages = 3'b111;
    always_ff @(posedge clk) begin
        stages <= {stages[1:0], button_reset};
    end
    assign rst = stages[2];
endmodule
