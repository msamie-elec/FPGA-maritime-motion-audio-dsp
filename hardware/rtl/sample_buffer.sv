`timescale 1ns / 1ps
// Synchronous-read RAM. One write and one read address per cycle.
module sample_buffer #(parameter integer ADDR_BITS=9)(
 input logic clk,input logic wr_en,input logic [ADDR_BITS-1:0] wr_addr,
 input logic signed [23:0] wr_data,
 input logic [ADDR_BITS-1:0] rd_addr,
 output logic signed [23:0] rd_data
);
  (* ram_style = "block" *) logic signed [23:0] mem [0:(1<<ADDR_BITS)-1];
  always_ff @(posedge clk) begin
    if(wr_en) mem[wr_addr]<=wr_data;
    rd_data<=mem[rd_addr];
  end
endmodule
