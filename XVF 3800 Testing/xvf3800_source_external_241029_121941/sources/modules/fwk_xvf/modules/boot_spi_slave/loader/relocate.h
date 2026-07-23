// Copyright 2019-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#ifndef __relocate_h__
#define __relocate_h__

#define RELOCATE(to, from, nwords) \
  for (int i = 0; i < nwords; i++) { \
    ((unsigned*)(to))[i] = ((unsigned*)(from))[i]; \
  } \
  { int dp, cp, sp; \
    int ram_end = XS1_RAM_BASE + XS1_RAM_SIZE; \
    asm("ldaw %0, dp[0]" : "=r"(dp)); \
    asm("set dp, %0" :: "r"(dp + (to) - (from))); /* adjust DP */ \
    asm("ldaw r11, cp[0]\nmov %0, r11" : "=r"(cp) :: "r11"); \
    asm("set cp, %0" :: "r"(cp + (to) - (from))); /* adjust CP */ \
    asm("ldaw %0, sp[0]" : "=r"(sp)); \
    asm("set sp, %0" :: "r"(sp + (to) - (from))); /* adjust SP */ \
    if (cp + (to) - (from) > ram_end || dp + (to) - (from) > ram_end) \
      __builtin_trap(); /* check that we haven't gone past RAM end */ \
  }

#endif
