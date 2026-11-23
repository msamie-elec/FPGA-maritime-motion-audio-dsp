`timescale 1ns / 1ps
// Response: A5 5A 01 81 job status countLE16 payload(3*n) CRCLE16.
// CRC covers byte indices 2..(header+payload-1), CRC bytes excluded.
module uart_packet_tx #(parameter integer CLKS_PER_BIT=868)(
 input logic clk,rst,start,input logic [7:0] job_id,status,
 input logic [15:0] requested_count,
 output logic [8:0] rd_addr,input logic signed [23:0] rd_data,
 output logic serial_out,output logic busy,output logic done
);
`include "crc16_ccitt.svh"
 typedef enum logic[2:0] {IDLE,PREP,SEND,WAIT_TX,ADVANCE,FINISHED} state_t;
 state_t state;
 logic [15:0] output_count,byte_idx,total_bytes;
 logic [15:0] crc;
 logic [8:0] sample_addr;
 logic [1:0] sample_byte_sel;
 logic [7:0] current_byte;
 logic uart_busy,uart_done,uart_start;
 logic [7:0] uart_byte;
 uart_tx #(.CLKS_PER_BIT(CLKS_PER_BIT)) u_uart_tx(.clk(clk),.rst(rst),
  .start(uart_start),.data(uart_byte),.tx(serial_out),.busy(uart_busy),.done(uart_done));
 assign rd_addr = sample_addr;
 assign busy=(state!=IDLE);
 always_comb begin
   case(byte_idx)
    0:current_byte=8'ha5;
    1:current_byte=8'h5a;
    2:current_byte=8'h01;
    3:current_byte=8'h81;
    4:current_byte=job_id;
    5:current_byte=status;
    6:current_byte=output_count[7:0];
    7:current_byte=output_count[15:8];
    default: begin
      if(byte_idx < 16'd8+16'd3*output_count)
        case (sample_byte_sel)
         0:current_byte=rd_data[7:0];
         1:current_byte=rd_data[15:8];
         default:current_byte=rd_data[23:16];
        endcase
      else if (byte_idx==16'd8+16'd3*output_count) current_byte=crc[7:0];
      else current_byte=crc[15:8];
    end
   endcase
 end
 always_ff @(posedge clk) begin
  if(rst)begin
    state<=IDLE;output_count<=0;byte_idx<=0;total_bytes<=0;crc<=16'hffff;
    uart_byte<=0;uart_start<=0;done<=0;sample_addr<=0;sample_byte_sel<=0;
  end else begin
   uart_start<=0;done<=0;
   case(state)
    IDLE: if(start)begin
      output_count<=(status==0)?requested_count:16'd0;
      total_bytes<=16'd10+((status==0)?(16'd3*requested_count):16'd0);
      byte_idx<=0;crc<=16'hffff;sample_addr<=0;sample_byte_sel<=0;state<=PREP;
    end
    PREP: state<=SEND; // synchronous BRAM read data stable by next cycle
    SEND: if(!uart_busy)begin
      uart_byte<=current_byte;uart_start<=1;
      if(byte_idx>=2 && byte_idx<(total_bytes-2)) crc<=crc16_next(crc,current_byte);
      state<=WAIT_TX;
    end
    WAIT_TX: if(uart_done)state<=ADVANCE;
    ADVANCE: if(byte_idx==total_bytes-1)state<=FINISHED;
             else begin
               if(byte_idx>=16'd8 && byte_idx<(16'd8+16'd3*output_count)) begin
                 if(sample_byte_sel==2) begin sample_byte_sel<=0;sample_addr<=sample_addr+1'b1;end
                 else sample_byte_sel<=sample_byte_sel+1'b1;
               end
               byte_idx<=byte_idx+1'b1;state<=PREP;
             end
    FINISHED: begin done<=1;state<=IDLE;end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
