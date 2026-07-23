// Copyright 2019-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#ifndef __is_simulation_h__
#define __is_simulation_h__

#include <xs1.h>

// simulation check that doesn't rely on system calls
inline int is_simulation_badfood_in_ram(void)
{
  int x;
  asm("ldw %0, %1[0]" : "=r"(x) : "r"(XS1_RAM_BASE + XS1_RAM_SIZE - 10000));
  return (x == 0xBADDF00D);
}

#endif
