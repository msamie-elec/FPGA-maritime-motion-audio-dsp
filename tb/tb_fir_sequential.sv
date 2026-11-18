`timescale 1ns/1ps
// Self-checking vector replay against independently generated Python values.
// Run simulator from repository root so tests/vectors paths resolve.
module tb_fir_sequential;
    logic clk=0;
    always #5 clk=~clk;   // 100 MHz
    logic rst=1;
    logic signed [23:0] in_data=0;
    logic in_valid=0;
    wire in_ready;
    wire signed [23:0] out_data;
    wire out_valid;
    logic [23:0] test_input [0:511];
    logic [23:0] test_expected [0:511];
    int tests_run=0;
    int samples_checked=0;
    int failures=0;

    fir_sequential dut (
        .clk(clk),.rst(rst),.in_data(in_data),.in_valid(in_valid),
        .in_ready(in_ready),.out_data(out_data),.out_valid(out_valid)
    );

    task automatic do_reset;
    begin
        @(negedge clk); rst=1'b1; in_valid=1'b0;
        repeat (3) @(negedge clk);
        rst=1'b0;
        #1; // Allow combinational in_ready to settle after reset deassertion.
        if (!in_ready) $fatal(1,"Core not ready after reset");
    end
    endtask

    task automatic send_and_check(input logic signed [23:0] sample,
                                  input logic signed [23:0] expected,
                                  input string title, input int idx);
        integer clocks;
    begin
        @(negedge clk);
        clocks=0;
        while (!in_ready) begin
            @(negedge clk);
            clocks++;
            if (clocks>100) $fatal(1,"Input readiness timeout %s %0d",title,idx);
        end
        in_data=sample;
        in_valid=1'b1;
        @(negedge clk);
        in_valid=1'b0;
        clocks=0;
        while (!out_valid) begin
            @(negedge clk);
            clocks++;
            if (clocks>100) $fatal(1,"Output validity timeout %s %0d",title,idx);
        end
        if (out_data !== expected) begin
            $display("FAIL %s[%0d]: in=%0d expected=%0d got=%0d",title,idx,$signed(sample),$signed(expected),$signed(out_data));
            failures++;
            if (failures>=8) $fatal(1,"Too many numerical errors");
        end
        samples_checked++;
    end
    endtask

    task automatic run_case(input string title,input int len);
        string in_file;
        string out_file;
        integer j;
    begin
        in_file={"tests/vectors/",title,"_input.mem"};
        out_file={"tests/vectors/",title,"_expected.mem"};
        // Clear any old contents to avoid silent tests of uninitialised memory.
        for (j=0;j<512;j++) begin
            test_input[j]=24'hx;
            test_expected[j]=24'hx;
        end
        $readmemh(in_file,test_input);
        $readmemh(out_file,test_expected);
        do_reset();
        for (j=0;j<len;j++) begin
            if (^test_input[j] === 1'bx || ^test_expected[j] === 1'bx)
                $fatal(1,"Missing vector %s[%0d]",title,j);
            send_and_check(test_input[j],test_expected[j],title,j);
        end
        tests_run++;
        $display("PASS case=%s samples=%0d",title,len);
    end
    endtask

    initial begin
        do_reset();
        run_case("impulse",96);
        run_case("dc",96);
        run_case("negative_dc",96);
        run_case("ramp",128);
        run_case("random",512);
        run_case("extremes",128);
        run_case("zeros",64);
        run_case("shake",256);

        // Test reset cancellation: no stale result after aborted mid-job.
        do_reset();
        @(negedge clk);
        in_data=24'sd65536; in_valid=1'b1;
        @(negedge clk); in_valid=1'b0;
        repeat (7) @(negedge clk);
        rst=1'b1;
        repeat (3) @(negedge clk);
        rst=1'b0;
        repeat (5) begin
            @(negedge clk);
            if(out_valid) $fatal(1,"Output leaked after reset");
        end
        send_and_check(24'sd0,24'sd0,"reset_cancellation",0);
        $display("PASS reset_cancellation");
        if (failures != 0) $fatal(1,"FIR verification FAILED %0d mismatches",failures);
        $display("FIR_RTL_REGRESSION_PASS tests=%0d samples=%0d",tests_run+1,samples_checked);
        $finish;
    end
endmodule
