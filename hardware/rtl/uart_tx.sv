`timescale 1ns / 1ps
// 8N1 UART transmitter: pulse start only when busy==0.
module uart_tx #(parameter integer CLKS_PER_BIT = 868) (
  input logic clk,rst, input logic start,input logic [7:0] data,
  output logic tx, busy, done
);
  localparam integer CW=$clog2(CLKS_PER_BIT+1);
  logic [CW-1:0] ticks;
  logic [3:0] bitidx;
  logic [9:0] frame;
  always_ff @(posedge clk) begin
    if(rst) begin tx<=1;busy<=0;done<=0;ticks<=0;bitidx<=0;frame<=10'h3ff;end
    else begin
      done<=0;
      if(!busy) begin
        tx<=1;
        if(start) begin
          frame<={1'b1,data,1'b0};
          tx<=0;busy<=1;ticks<=CLKS_PER_BIT-1;bitidx<=0;
        end
      end else if(ticks==0) begin
        if(bitidx==9) begin tx<=1;busy<=0;done<=1;end
        else begin
          bitidx<=bitidx+1'b1;
          tx<=frame[bitidx+1'b1];
          ticks<=CLKS_PER_BIT-1;
        end
      end else ticks<=ticks-1'b1;
    end
  end
endmodule
