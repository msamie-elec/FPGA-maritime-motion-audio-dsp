`timescale 1ns / 1ps
// Standalone self-checking test for synchronous BTN0 reset synchroniser.
module tb_reset_sync;
  logic clk = 0;
  always #5 clk = ~clk;
  logic button_reset = 0;
  wire rst;
  reset_sync dut(.clk(clk), .button_reset(button_reset), .rst(rst));

  task automatic tick(input logic expected);
    begin
      @(posedge clk);
      #1;
      if (rst !== expected)
        $fatal(1, "reset_sync expected %b got %b at t=%0t", expected, rst, $time);
    end
  endtask
  initial begin
    #1;
    if (rst !== 1'b1) $fatal(1,"Power-on reset not asserted by INIT");
    // With button initially released, reset exits after three rising edges.
    tick(1); tick(1); tick(0);
    // Changing the button between clock edges must NOT update rst async.
    @(negedge clk); #1 button_reset = 1;
    #1 if (rst !== 1'b0) $fatal(1,"Asynchronous reset assertion detected");
    tick(0); tick(0); tick(1);
    repeat (2) tick(1);
    @(negedge clk); #1 button_reset = 0;
    #1 if (rst !== 1'b1) $fatal(1,"Asynchronous reset release detected");
    tick(1); tick(1); tick(0);
    // A pulse shorter than a clock period between consecutive edges is ignored.
    @(negedge clk); #1 button_reset = 1;
    #2 button_reset = 0;
    #1 if (rst !== 1'b0) $fatal(1,"Short glitch changed reset");
    repeat (4) tick(0);
    // Second genuine press exercises repeated operation.
    @(negedge clk); #1 button_reset = 1;
    tick(0); tick(0); tick(1);
    @(negedge clk); #1 button_reset = 0;
    tick(1); tick(1); tick(0);
    $display("MARITIME_RESET_SYNC_REGRESSION_PASS");
    $finish;
  end
endmodule
