`timescale 1ns / 1ps
// Active-high, asynchronous assert and synchronised deassert.
module reset_sync(input logic clk, input logic button_reset, output logic rst);
  (* ASYNC_REG = "TRUE" *) logic [2:0] stages = 3'b111;
  always_ff @(posedge clk or posedge button_reset) begin
    if (button_reset) stages <= 3'b111;
    else stages <= {stages[1:0], 1'b0};
  end
  assign rst = stages[2];
endmodule
