// Copyright 2019-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#ifndef __ready_signal_h__
#define __ready_signal_h__

void ready_signal_initialise(void);

void ready_signal_output(int value);

void ready_signal_shutdown(void);

#endif
