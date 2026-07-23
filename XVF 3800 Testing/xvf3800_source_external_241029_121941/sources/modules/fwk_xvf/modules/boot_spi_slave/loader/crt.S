// Copyright 2019-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#include <xs1.h>
#include "header.h"

// XS1_RAM_BASE + XS1_RAM_SIZE
// - 4 * ((XS1_DBG_BUFFER_WORDS + 1 + _cmdline_buffer_stackwords) $A 2)
#define STACK_256B 0x7FB

.section .crt, "ax", @progbits

.globl _start

// assume this is RAM start
_start:
.text
  bu        minimal_crt
#ifdef TEST
#include "test_header.S"
#endif
.align HEADER_MAX_BYTES
minimal_crt:
// allocate some stack space so we can call an XC function
// also initialise DP and CP so XC can load constants
// allocate thread local timer, turn on default clock block, set vector base
  ldap      r11, minimal_stack
  set       sp, r11
  ldap      r11, _dp
  set       dp, r11
  ldap      r11, _cp
  set       cp, r11
  getr      r9, XS1_RES_TYPE_TIMER
  ldaw      r10, dp[__timers]
  get       r11, id
  stw       r9, r10[r11]
  ldc       r11, XS1_CLKBLK_REF
  setc      res[r11], XS1_SETC_INUSE_ON
  setc      res[r11], XS1_SETC_RUN_STARTR
  ldc       r11, XS1_PS_RAM_BASE
  get       r11, ps[r11]
  ldc       r10, XS1_PS_VECTOR_BASE
  set       ps[r10], r11
  bu        main
.align 16
.skip STACK_256B
.align 16
minimal_stack:
.word 0
