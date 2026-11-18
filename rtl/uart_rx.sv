`timescale 1ns / 1ps
// 8N1 UART receiver with two-stage synchronizer. One-cycle byte strobe.
module uart_rx #(parameter integer CLKS_PER_BIT = 868) (
  input logic clk, rst, input logic rx,
  output logic [7:0] data, output logic valid,
  output logic framing_error
);
  localparam integer CW=$clog2(CLKS_PER_BIT+1);
  typedef enum logic[1:0] {IDLE, START, BITS, STOP} state_t;
  state_t state;
  (* ASYNC_REG = "TRUE" *) logic rx_meta,rx_sync;
  logic [CW-1:0] ticks;
  logic [2:0] bitidx;
  logic [7:0] shift;
  always_ff @(posedge clk) begin
    rx_meta <= rx;
    rx_sync <= rx_meta;
    if (rst) begin
      state<=IDLE; ticks<=0; bitidx<=0; shift<=0;
      data<=0;valid<=0;framing_error<=0;
    end else begin
      valid<=0; framing_error<=0;
      case(state)
        IDLE: if (!rx_sync) begin ticks<=CLKS_PER_BIT/2;state<=START;end
        START: if (ticks==0) begin
          if(!rx_sync) begin ticks<=CLKS_PER_BIT-1;bitidx<=0;state<=BITS;end
          else state<=IDLE;
        end else ticks<=ticks-1'b1;
        BITS: if(ticks==0) begin
          shift[bitidx]<=rx_sync; ticks<=CLKS_PER_BIT-1;
          if(bitidx==7) state<=STOP;
          else bitidx<=bitidx+1'b1;
        end else ticks<=ticks-1'b1;
        STOP: if(ticks==0) begin
          if(rx_sync) begin data<=shift;valid<=1;end
          else framing_error<=1;
          state<=IDLE;
        end else ticks<=ticks-1'b1;
      endcase
    end
  end
endmodule
