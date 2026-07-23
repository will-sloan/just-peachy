// Copyright 2019-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
//
// CRC instruction used but checksum ignored
//
#include <xs1.h>

.section .text, "ax", @progbits

.globl spi_slave_initialise
.align 4
spi_slave_initialise:
  ENTSP_lu6 0
  ldap      r11, spi_sclk_port
  ldw       r0, r11[0]
  ldap      r11, spi_slave_ss_port
  ldw       r1, r11[0]
  ldap      r11, spi_mosi_port
  ldw       r3, r11[0]
  ldc       r2, XS1_CLKBLK_1
  setc      res[r0], XS1_SETC_INUSE_ON
  setc      res[r1], XS1_SETC_INUSE_ON
  setc      res[r1], XS1_SETC_INV_INVERT
  setc      res[r2], XS1_SETC_INUSE_ON
  setclk    res[r2], r0
  setrdy    res[r2], r1
  setc      res[r3], XS1_SETC_INUSE_ON
  setc      res[r3], XS1_SETC_BUF_BUFFERS
  setc      res[r3], XS1_SETC_RDY_STROBED
  setc      res[r3], XS1_SETC_MS_SLAVE
  ldc       r11, 32
  settw     res[r3], r11
  setclk    res[r3], r2
  ldap      r11, cs_low_too_early
  setv      res[r1], r11
  setc      res[r1], XS1_SETC_COND_EQ
  eeu       res[r1]
  eeu       res[r3]
  setc      res[r2], XS1_SETC_RUN_STARTR
  retsp     0
.align 4
spi_sclk_port:
.word XS1_PORT_1C
spi_mosi_port:
.word XS1_PORT_1D
spi_slave_ss_port:
.word XS1_PORT_1A

.globl spi_slave_transaction_receive
.align 4
spi_slave_transaction_receive:
  ENTSP_lu6 5
  stw       r4, sp[1]
  stw       r5, sp[2]
  stw       r6, sp[3]
  stw       r7, sp[4]
  ldap      r11, bitrev_poly
  ldw       r4, r11[0]
  ldap      r11, spi_slave_ss_port
  ldw       r7, r11[0]
  ldap      r11, spi_mosi_port
  ldw       r3, r11[0]
spi_slave_loop:
cs_low_too_early:
crc_checksum_fail:
  ldap      r11, spi_slave_data
  setv      res[r3], r11
  mkmsk     r5, 32
  ldc       r11, 0
  setd      res[r7], r11
  in        r11, res[r7]
  setc      res[r3], XS1_SETC_RUN_CLRBUF
  ldc       r11, 1
  setd      res[r7], r11
  in        r11, res[r7]
  ldc       r11, 0
  setd      res[r7], r11
  waiteu
spi_slave_data:
  in        r6, res[r3]
  crc32     r5, r6, r4
  stw       r6, r0[0]
  add       r0, r0, 4
  sub       r1, r1, 1
  bf        r1, spi_slave_done
  waiteu
spi_slave_done:
  ldw       r4, sp[1]
  ldw       r5, sp[2]
  ldw       r6, sp[3]
  ldw       r7, sp[4]
  retsp     5
.align 4
bitrev_poly:
.word 0xEDB88320
crc_disable_magic:
.word 0x0D15AB1E

.globl spi_slave_shutdown
.align 4
spi_slave_shutdown:
  ENTSP_lu6 0
  ldap      r11, spi_sclk_port
  ldw       r0, r11[0]
  ldap      r11, spi_slave_ss_port
  ldw       r1, r11[0]
  ldc       r2, XS1_CLKBLK_1
  ldap      r11, spi_mosi_port
  ldw       r3, r11[0]
  setc      res[r0], XS1_SETC_INUSE_OFF
  setc      res[r1], XS1_SETC_INUSE_OFF
  setc      res[r2], XS1_SETC_INUSE_OFF
  setc      res[r3], XS1_SETC_INUSE_OFF
  retsp     0
