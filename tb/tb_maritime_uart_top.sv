`timescale 1ns / 1ps
// Complete serialized UART->BRAM->FIR->BRAM->UART regression.
// Simulation uses CLKS_PER_BIT=16 for speed, hardware still defaults 868.
module tb_maritime_uart_top;
  localparam integer CPB=16;
  logic clk=0;always #5 clk=~clk;
  logic btn_reset=1,uart_rxd_in=1;
  wire uart_txd_out;wire[3:0] led;
  arty_a7_maritime_top #(.CLKS_PER_BIT(CPB),.RX_TIMEOUT_CYCLES(100000)) dut(
    .CLK100MHZ(clk),.btn_reset(btn_reset),.uart_rxd_in(uart_rxd_in),.uart_txd_out(uart_txd_out),.led(led));
  integer tests=0;
  reg [15:0] crc_req;
  reg [7:0] frame_byte;
  reg [15:0] crc_resp;
  integer j;
  integer sent_count;
  reg [7:0] headers[0:7];
  reg [23:0] payload_word;
  reg [7:0] lo,hi;
`include "crc16_ccitt.svh"
`include "audio_coefficients.svh"
  task automatic send_byte(input [7:0] data);
    integer b;
    begin
      @(negedge clk); uart_rxd_in=0;repeat(CPB)@(negedge clk);
      for(b=0;b<8;b=b+1)begin uart_rxd_in=data[b];repeat(CPB)@(negedge clk);end
      uart_rxd_in=1;repeat(CPB)@(negedge clk);
    end
  endtask
  task automatic send_body_byte(input [7:0] data);
   begin send_byte(data);crc_req=crc16_next(crc_req,data);end
  endtask
  task automatic send_packet(input [7:0] job,input integer count,input bit make_bad_crc,input bit impulse);
    integer k;reg [23:0] datum;
    begin
      crc_req=16'hffff;
      send_byte(8'ha5);send_byte(8'h5a);
      send_body_byte(8'h01);send_body_byte(8'h01);send_body_byte(job);
      send_body_byte(count[7:0]);send_body_byte(count[15:8]);
      for(k=0;k<count;k=k+1)begin
        datum=(impulse && k==0)?24'd32768:24'd0;
        send_body_byte(datum[7:0]);send_body_byte(datum[15:8]);send_body_byte(datum[23:16]);
      end
      if(make_bad_crc) crc_req=crc_req^16'h0001;
      send_byte(crc_req[7:0]);send_byte(crc_req[15:8]);
    end
  endtask
  task automatic recv_byte(output [7:0] data);
    integer cycles,b;
    begin
      cycles=0;
      while(uart_txd_out!==1'b0) begin
        @(negedge clk);cycles=cycles+1;
        if(cycles>100000) $fatal(1,"UART response start timeout");
      end
      repeat(CPB/2)@(negedge clk);
      if(uart_txd_out!==1'b0)$fatal(1,"Bad UART start bit");
      for(b=0;b<8;b=b+1)begin
        repeat(CPB)@(negedge clk);data[b]=uart_txd_out;
      end
      repeat(CPB)@(negedge clk);
      if(uart_txd_out!==1'b1)$fatal(1,"Bad UART stop bit");
    end
  endtask
  task automatic recv_checked(input[7:0] expect_job,input[7:0] expect_status,input integer exp_n,input bit impulse);
    integer i;reg[7:0] b;reg[7:0] crc_l,crc_h;reg [23:0] value;
    integer signed expected;
    begin
      crc_resp=16'hffff;
      for(i=0;i<8;i=i+1)begin
        recv_byte(b);headers[i]=b;
        if(i>=2) crc_resp=crc16_next(crc_resp,b);
      end
      if(headers[0]!==8'ha5||headers[1]!==8'h5a||headers[2]!==8'h01||headers[3]!==8'h81)
        $fatal(1,"Bad response prefix");
      if(headers[4]!==expect_job||headers[5]!==expect_status)
        $fatal(1,"Wrong job or status: job=%d status=%d",headers[4],headers[5]);
      if({headers[7],headers[6]}!==exp_n)
        $fatal(1,"Wrong response count: received=%d expected=%d",{headers[7],headers[6]},exp_n);
      for(i=0;i<exp_n;i=i+1)begin
        recv_byte(b);value[7:0]=b;crc_resp=crc16_next(crc_resp,b);
        recv_byte(b);value[15:8]=b;crc_resp=crc16_next(crc_resp,b);
        recv_byte(b);value[23:16]=b;crc_resp=crc16_next(crc_resp,b);
        if(impulse && expect_job[7]) begin
          if(i<17) expected=audio_coeff_at(i[4:0]);
          else expected=0;
        end else if(impulse)
          case(i)
            0:expected=-95;
            1:expected=-90;
            2:expected=0;
            3:expected=399;
            4:expected=1282;
            5:expected=2617;
            default:expected=0;
          endcase
        else expected=0;
        if($signed(value)!==expected) $fatal(1,"FIR sample %0d: got %0d expected %0d",i,$signed(value),expected);
      end
      recv_byte(crc_l);recv_byte(crc_h);
      if({crc_h,crc_l}!==crc_resp)
        $fatal(1,"Response CRC mismatch: got %h expected %h",{crc_h,crc_l},crc_resp);
      tests=tests+1;
      $display("PASS UART_JOB=%0d status=%0d returned_samples=%0d",expect_job,expect_status,exp_n);
    end
  endtask
  initial begin
   repeat(10) @(negedge clk);btn_reset=0;
   repeat(16) @(negedge clk);
   // first job should process a true impulse (not just return uploaded bytes).
   send_packet(8'h31,6,0,1);recv_checked(8'h31,0,6,1);
   // bad CRC must be rejected with count=0, no stale result data.
   send_packet(8'h32,4,1,0);recv_checked(8'h32,2,0,0);
   // a new valid job proves recoverability and FIR history reset.
   send_packet(8'h33,4,0,0);recv_checked(8'h33,0,4,0);
   // Audio-mode job: high job ID bit selects the independent speech FIR bank.
   send_packet(8'h81,6,0,1);recv_checked(8'h81,0,6,1);
   // Switching back must restore the original motion coefficient bank.
   send_packet(8'h34,6,0,1);recv_checked(8'h34,0,6,1);
   $display("MARITIME_UART_FIR_REGRESSION_PASS jobs=%0d",tests);
   $finish;
  end
endmodule
