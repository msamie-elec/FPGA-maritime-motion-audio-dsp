// CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflect/xorout.
function automatic [15:0] crc16_next(input [15:0] prior,input [7:0] byte_in);
  reg [15:0] c;
  integer j;
  begin
    c=prior ^ {byte_in,8'h00};
    for(j=0;j<8;j=j+1)
      if(c[15]) c=(c<<1)^16'h1021;
      else c=(c<<1);
    crc16_next=c;
  end
endfunction
