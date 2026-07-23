// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#include "fifo_chan/tx.h"

#include <stdint.h>
#include <xcore/assert.h>
#include <xcore/channel_streaming.h>

void fifo_chan_tx_init(fifo_chan_tx_t* tx, chanend_t chan, void* buf, size_t elem_size, uint8_t n_elems) {
	xassert(NULL != tx);
	xassert(NULL != buf);

	*tx = (fifo_chan_tx_t){
		.chan = chan,
		.buf = buf,
		.depth = n_elems,
		.elem_size = elem_size,
		.next = 0,
		.credits = n_elems,
	};

	s_chan_out_word(chan, (uint32_t)buf);
	s_chan_out_word(chan, elem_size);
}

