`timescale 1ns / 1ps
// Arty A7-35T physical top, 100 MHz oscillator, USB-UART, reset button, LEDs.
// Full video remains on the host: FPGA processes fixed-point motion samples.
module arty_a7_maritime_top #(
 parameter integer CLKS_PER_BIT=868,
 parameter integer RX_TIMEOUT_CYCLES=100000000
)(
 input logic CLK100MHZ,
 input logic btn_reset,
 input logic uart_rxd_in,
 output logic uart_txd_out,
 output logic [3:0] led
);
 wire rst;
 reset_sync u_reset_sync(.clk(CLK100MHZ),.button_reset(btn_reset),.rst(rst));
 wire [8:0] rx_wr_addr,job_rd_addr,tx_rd_addr,result_wr_addr;
 wire signed [23:0] rx_wr_data,job_rd_data,result_wr_data,tx_rd_data;
 wire rx_wr_en,result_wr_en;
 wire rx_packet_done,job_done,job_busy,tx_done,tx_busy;
 wire [7:0] rx_job_id,rx_status;
 wire [15:0] rx_count;
 logic [7:0] active_job,active_status;
 logic [15:0] active_count;
 logic error_latched;
 typedef enum logic[2:0] {WAIT_REQ,START_JOB,WAIT_JOB,REPLY_GAP,START_RESP,WAIT_RESP} top_state_t;
 top_state_t state;
 localparam integer TURNAROUND_CYCLES=2*CLKS_PER_BIT;
 logic [$clog2(TURNAROUND_CYCLES+1)-1:0] reply_gap;

 uart_packet_rx #(.CLKS_PER_BIT(CLKS_PER_BIT),.TIMEOUT_CYCLES(RX_TIMEOUT_CYCLES)) u_packet_rx (
   .clk(CLK100MHZ),.rst(rst),.enable(state==WAIT_REQ),.serial_in(uart_rxd_in),
   .wr_en(rx_wr_en),.wr_addr(rx_wr_addr),.wr_data(rx_wr_data),
   .packet_done(rx_packet_done),.job_id(rx_job_id),.count(rx_count),.status(rx_status));
 sample_buffer u_input_ram(.clk(CLK100MHZ),.wr_en(rx_wr_en),.wr_addr(rx_wr_addr),
   .wr_data(rx_wr_data),.rd_addr(job_rd_addr),.rd_data(job_rd_data));
 fir_job_controller u_fir_job(.clk(CLK100MHZ),.rst(rst),.start(state==START_JOB),
   .count(active_count),.input_rd_addr(job_rd_addr),.input_rd_data(job_rd_data),
   .result_wr_en(result_wr_en),.result_wr_addr(result_wr_addr),
   .result_wr_data(result_wr_data),.done(job_done),.busy(job_busy));
 sample_buffer u_result_ram(.clk(CLK100MHZ),.wr_en(result_wr_en),.wr_addr(result_wr_addr),
   .wr_data(result_wr_data),.rd_addr(tx_rd_addr),.rd_data(tx_rd_data));
 uart_packet_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_packet_tx(
   .clk(CLK100MHZ),.rst(rst),.start(state==START_RESP),
   .job_id(active_job),.status(active_status),.requested_count(active_count),
   .rd_addr(tx_rd_addr),.rd_data(tx_rd_data),.serial_out(uart_txd_out),.busy(tx_busy),.done(tx_done));

 assign led[0]=(state==WAIT_REQ);
 assign led[1]=job_busy;
 assign led[2]=tx_busy;
 assign led[3]=error_latched;
 always_ff @(posedge CLK100MHZ)begin
   if(rst)begin state<=WAIT_REQ;active_job<=0;active_count<=0;active_status<=0;error_latched<=0;reply_gap<=0;end
   else case(state)
    WAIT_REQ: if(rx_packet_done)begin
      active_job<=rx_job_id;active_count<=rx_count;active_status<=rx_status;
      error_latched<=(rx_status!=0);
      if(rx_status==0) state<=START_JOB;
      else begin reply_gap<=TURNAROUND_CYCLES-1;state<=REPLY_GAP;end
    end
    START_JOB:state<=WAIT_JOB;
    WAIT_JOB:if(job_done)begin reply_gap<=TURNAROUND_CYCLES-1;state<=REPLY_GAP;end
    REPLY_GAP:if(reply_gap==0)state<=START_RESP;else reply_gap<=reply_gap-1'b1;
    START_RESP:state<=WAIT_RESP;
    WAIT_RESP:if(tx_done)state<=WAIT_REQ;
    default:state<=WAIT_REQ;
   endcase
 end
endmodule
