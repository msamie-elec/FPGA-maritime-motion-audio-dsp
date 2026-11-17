`timescale 1ns / 1ps
// SPDX-License-Identifier: MIT
// 17-tap signed fixed-point motion FIR (build-time coefficient ROM).
// Signed input/output: 24-bit Q16.8. Signed coeff: 16-bit Q1.15.
// One 24x16 multiplier, 48-bit accumulator, 2 cycles per tap.
// Truncation: arithmetic >>15; clamp to signed 24-bit output.
// Each accepted sample advances the 17-entry history exactly once.
// State reset (rst=1) cancels pending output and clears all history.
module fir_sequential (
    input  logic                     clk,
    input  logic                     rst,
    input  logic signed [23:0]       in_data,
    input  logic                     in_valid,
    output logic                     in_ready,
    output logic signed [23:0]       out_data,
    output logic                     out_valid
);
    localparam integer TAPS = 17;
    typedef enum logic [1:0] { IDLE=2'd0, MULTIPLY=2'd1, ACCUMULATE=2'd2, FINISH=2'd3 } state_t;
    state_t state;

    logic signed [23:0] sample_history [0:TAPS-1];
    logic [4:0] tap_idx;
    logic signed [39:0] product_reg;
    logic signed [47:0] accumulator;
    logic signed [47:0] scaled;
    integer i;

    // Generated constant-coefficient function. Packed 16-bit signed values.
`include "fir_coefficients.svh"

    assign in_ready = (state == IDLE) && !rst;
    assign scaled = accumulator >>> 15;

    always_ff @(posedge clk) begin
        if (rst) begin
            state       <= IDLE;
            tap_idx     <= 5'd0;
            product_reg <= '0;
            accumulator <= '0;
            out_data    <= '0;
            out_valid   <= 1'b0;
            for (i=0; i<TAPS; i=i+1)
                sample_history[i] <= '0;
        end else begin
            out_valid <= 1'b0;
            case (state)
                IDLE: begin
                    if (in_valid) begin
                        for (i=TAPS-1; i>0; i=i-1)
                            sample_history[i] <= sample_history[i-1];
                        sample_history[0] <= in_data;
                        tap_idx <= 5'd0;
                        accumulator <= '0;
                        state <= MULTIPLY;
                    end
                end
                MULTIPLY: begin
                    // A single signed multiplication is time-multiplexed across taps.
                    // Registered product isolates multiplier from MAC carry chain.
                    product_reg <= $signed(sample_history[tap_idx]) * $signed(coeff_at(tap_idx));
                    state <= ACCUMULATE;
                end
                ACCUMULATE: begin
                    accumulator <= accumulator + {{8{product_reg[39]}}, product_reg};
                    if (tap_idx == TAPS-1)
                        state <= FINISH;
                    else begin
                        tap_idx <= tap_idx + 5'd1;
                        state <= MULTIPLY;
                    end
                end
                FINISH: begin
                    // Saturate *after* arithmetic right shift. The coefficient
                    // list has DC gain exactly 1.0000 in Q1.15 integer terms.
                    if (scaled > 48'sd8388607)
                        out_data <= 24'sh7fffff;
                    else if (scaled < -48'sd8388608)
                        out_data <= 24'sh800000;
                    else
                        out_data <= scaled[23:0];
                    out_valid <= 1'b1;
                    state <= IDLE;
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
