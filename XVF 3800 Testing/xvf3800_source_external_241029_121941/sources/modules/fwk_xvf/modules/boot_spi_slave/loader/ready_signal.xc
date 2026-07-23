// Copyright 2019-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#include <xs1.h>
#include "stringify.h"

out port p_ready = XS1_PORT_1G;

void ready_signal_initialise(void)
{
  asm("setc res[%0], " STRINGIFY(XS1_SETC_INUSE_ON) :: "r"(p_ready));
  asm("setclk res[%0], %1" :: "r"(p_ready), "r"(XS1_CLKBLK_REF));
}

void ready_signal_shutdown(void)
{
  asm("setc res[%0], " STRINGIFY(XS1_SETC_INUSE_OFF) :: "r"(p_ready));
}

void ready_signal_output(int value)
{
  p_ready <: value;
}
