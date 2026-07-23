// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
///
/// implementation of rx, only functions which are unlikely to be timing
/// critical are here

#include "fifo_chan/rx.h"
#include "xcore/channel_streaming.h"

#include <stddef.h>
#include <xcore/assert.h>


void fifo_chan_rx_init(fifo_chan_rx_t* rx, chanend_t chan) {
	xassert(NULL != rx);

	void* buf = (void*)s_chan_in_word(chan);
	size_t elem_size = s_chan_in_word(chan);

	*rx = (fifo_chan_rx_t) {
		.chan = chan,
		.buffer = buf,
		.elem_size = elem_size
	};
}

