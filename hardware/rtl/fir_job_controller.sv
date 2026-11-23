`timescale 1ns / 1ps
// Batch processing: reset FIR history for each independent X or Y job.
// Input RAM read is synchronous. Output RAM written on valid output.
module fir_job_controller(
 input logic clk,rst,start,audio_mode,input logic [15:0] count,
 output logic [8:0] input_rd_addr,input logic signed [23:0] input_rd_data,
 output logic result_wr_en,output logic [8:0] result_wr_addr,
 output logic signed [23:0] result_wr_data,
 output logic done,output logic busy
);
 typedef enum logic[2:0] {IDLE,CLEAR,FETCH,WAIT_RAM,SEND,WAIT_FIR,COMPLETE} state_t;
 state_t state;
 logic signed [23:0] fir_out;
 logic fir_out_valid,fir_in_ready;
 logic fir_reset, fir_in_valid;
 logic [8:0] sample_idx;
 assign fir_reset=rst||(state==CLEAR);
 assign fir_in_valid=(state==SEND);
 assign input_rd_addr=sample_idx;
 assign busy=(state!=IDLE);
 fir_sequential u_fir(.clk(clk),.rst(fir_reset),.audio_mode(audio_mode),.in_data(input_rd_data),
   .in_valid(fir_in_valid),.in_ready(fir_in_ready),.out_data(fir_out),.out_valid(fir_out_valid));
 always_ff @(posedge clk) begin
  if(rst) begin
   state<=IDLE;sample_idx<=0;result_wr_en<=0;
   result_wr_addr<=0;result_wr_data<=0;done<=0;
  end else begin
   done<=0;result_wr_en<=0;
   case(state)
    IDLE: if(start) begin sample_idx<=0;state<=CLEAR;end
    CLEAR: state<=FETCH;
    FETCH: state<=WAIT_RAM;
    WAIT_RAM: state<=SEND;
    SEND: if(fir_in_ready) state<=WAIT_FIR;
    WAIT_FIR: if(fir_out_valid) begin
      result_wr_en<=1;result_wr_addr<=sample_idx;result_wr_data<=fir_out;
      if({7'd0,sample_idx}+16'd1==count) state<=COMPLETE;
      else begin sample_idx<=sample_idx+1'b1;state<=FETCH;end
    end
    COMPLETE: begin done<=1;state<=IDLE;end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
