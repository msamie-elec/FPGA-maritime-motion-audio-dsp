`timescale 1ns / 1ps
// Request: A5 5A version=01 command=01 job_id countLE16 payload(3*n) CRCLE16.
// CRC covers version through last payload byte, excludes the two sync bytes.
// enable held low while job active; error response is emitted on invalid packet.
module uart_packet_rx #(
  parameter integer CLKS_PER_BIT=868,
  parameter integer TIMEOUT_CYCLES=100000000
)(
 input logic clk,rst,enable,input logic serial_in,
 output logic wr_en, output logic [8:0] wr_addr,
 output logic signed [23:0] wr_data,
 output logic packet_done, output logic [7:0] job_id,
 output logic [15:0] count,output logic [7:0] status
);
`include "crc16_ccitt.svh"
 localparam [7:0] ST_OK=0,ST_HEADER=1,ST_CRC=2,ST_COUNT=3,ST_TIMEOUT=4,ST_FRAMING=5;
 localparam integer TW=$clog2(TIMEOUT_CYCLES+1);
 logic [7:0] uart_data; logic uart_valid,uart_frame_error;
 uart_rx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_uart_rx(.clk(clk),.rst(rst),.rx(serial_in),
  .data(uart_data),.valid(uart_valid),.framing_error(uart_frame_error));
 typedef enum logic[2:0] {SYNC0,SYNC1,HEADER,PAYLOAD,CRC_LOW,CRC_HIGH} state_t;
 state_t state;
 logic [2:0] hdr_index;
 logic [1:0] byte_index;
 logic [8:0] sample_index;
 logic [23:0] sample_assemble;
 logic [7:0] rx_crc_low;
 logic [15:0] crc;
 logic [7:0] version,command;
 logic [TW-1:0] idle_cycles;
 always_ff @(posedge clk) begin
  if(rst || !enable) begin
   state<=SYNC0;hdr_index<=0;byte_index<=0;sample_index<=0;
   sample_assemble<=0;rx_crc_low<=0;crc<=16'hffff;version<=0;command<=0;
   wr_en<=0;wr_addr<=0;wr_data<=0;packet_done<=0;job_id<=0;count<=0;status<=ST_OK;idle_cycles<=0;
  end else begin
   wr_en<=0;packet_done<=0;
   if(state!=SYNC0 && state!=SYNC1 && !uart_valid) begin
     if(idle_cycles==TIMEOUT_CYCLES-1) begin
      packet_done<=1;status<=ST_TIMEOUT;state<=SYNC0;idle_cycles<=0;
     end else idle_cycles<=idle_cycles+1'b1;
   end
   // A malformed UART stop bit must not leave a partially accepted packet alive.
   // Only report a framing error once a packet has progressed beyond the sync bytes.
   // During sync search, discard the malformed byte and return to the sync hunt.
   if(uart_frame_error) begin
    idle_cycles<=0;
    if(state!=SYNC0 && state!=SYNC1) begin
      packet_done<=1;status<=ST_FRAMING;
    end
    state<=SYNC0;
   end else if(uart_valid) begin
    idle_cycles<=0;
    case(state)
     SYNC0: if(uart_data==8'ha5) state<=SYNC1;
     SYNC1: begin
      if(uart_data==8'h5a) begin state<=HEADER;hdr_index<=0;crc<=16'hffff;count<=0;end
      else if(uart_data!=8'ha5) state<=SYNC0;
     end
     HEADER: begin
      crc<=crc16_next(crc,uart_data);
      case(hdr_index)
       0: version<=uart_data;
       1: command<=uart_data;
       2: job_id<=uart_data;
       3: count[7:0]<=uart_data;
       4: begin
        count[15:8]<=uart_data;
        if(version!=8'h01 || command!=8'h01) begin packet_done<=1;status<=ST_HEADER;state<=SYNC0;end
        else if(({uart_data,count[7:0]}>16'd512)||({uart_data,count[7:0]}==16'd0)) begin
          packet_done<=1;status<=ST_COUNT;state<=SYNC0;
        end else begin
         state<=PAYLOAD;byte_index<=0;sample_index<=0;
        end
       end
      endcase
      hdr_index<=hdr_index+1'b1;
     end
     PAYLOAD: begin
      crc<=crc16_next(crc,uart_data);
      case(byte_index)
       0: begin sample_assemble[7:0]<=uart_data;byte_index<=1;end
       1: begin sample_assemble[15:8]<=uart_data;byte_index<=2;end
       2: begin
        wr_data<=$signed({uart_data,sample_assemble[15:0]});wr_addr<=sample_index;
        wr_en<=1;byte_index<=0;
        if({7'd0,sample_index}+16'd1==count) state<=CRC_LOW;
        else sample_index<=sample_index+1'b1;
       end
      endcase
     end
     CRC_LOW: begin rx_crc_low<=uart_data;state<=CRC_HIGH;end
     CRC_HIGH: begin
      packet_done<=1;status<=({uart_data,rx_crc_low}==crc)?ST_OK:ST_CRC;
      state<=SYNC0;
     end
     default:state<=SYNC0;
    endcase
   end
  end
 end
endmodule
