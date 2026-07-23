// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// Receiver side of the fifo_chan
///
/// example:
/// @code
/// // create an rx fifo and wait on tx for initialisation data.
///	fifo_chan_rx_t rx;
///	fifo_chan_rx_init(&rx, chan); // chan initialised elsewhere
///
///	// get a buffer and use it, you must know what type to expect
///	int* buf = fifo_chan_rx_receive(&rx);
///	if(NULL != buf) printf("%d\n", *buf);
///
///	// release buffer, must be done before receiving the next
///	fifo_chan_rx_done(&rx);
/// @endcode

#include <xcore/channel_streaming.h>
#include <xcore/assert.h>
#include <xcore/chanend.h>
#include <xcore/select.h>
#include <stddef.h>
#include <stdbool.h>
#include "timing_debug_defs.h"

/// rx notification val. the value doesn't matter as the only thing sent
/// back to tx is byte-wise notifications and the fifo is unidirectional
#define RX_NOTI_VAL 0


// from s_chan_non_blocking.xc, profiling showed that implementing
// this in xc gives fifo_chan_rx_flush a 2x speed up (from 115 ticks to 55 ticks).
extern int chan_non_blocking_flush(chanend_t c);

// also from s_chan_non_blocking.xc. desciption can be found there
extern int chan_non_blocking_receive(chanend_t c, unsigned char *data);


/// rx state
typedef struct {
	/// pointer to buffer that is sent from tx during init
	void* buffer;

	/// Size of each element in the array
	size_t elem_size;

	/// Channel for communicating with tx
	chanend_t chan;

	/// true when buf is "out" of the chan but not done
	bool buf_out;
} fifo_chan_rx_t;

/// initialise rx, blocks until tx has sent starting buffer and size over
/// chan. rx must not be NULL
void fifo_chan_rx_init(fifo_chan_rx_t* rx, chanend_t chan);

/// Mark the last received buffer as done. This gives the sender back 1 credit so it can use This
/// buffer again. Could block if the tx fifo depth is greater than 8 and tx is not servicing the 
/// channel
STATIC_INLINE void fifo_chan_rx_done(fifo_chan_rx_t* rx) {
	xassert(NULL != rx);
	xassert(rx->buf_out);

	rx->buf_out = false;
	s_chan_out_byte(rx->chan, RX_NOTI_VAL);
}



/// Flush the channel of input and send a notification to sender
/// for each skipped buffer.
/// @warning This will flood the channel with rx notifications
/// @return true if there was data to be flushed
STATIC_INLINE bool fifo_chan_rx_flush(fifo_chan_rx_t* rx) {
	xassert(NULL != rx);
	xassert(!rx->buf_out); // flush would be confusing if buf is out.
	
#if defined(FIFO_CHAN_USE_XC) && FIFO_CHAN_USE_XC
	return chan_non_blocking_flush(rx->chan);
#else
	bool retval = false;
	SELECT_RES( CASE_THEN(rx->chan, got_data),
			    DEFAULT_THEN(empty) ) {
		got_data:
			(void)s_chan_in_byte(rx->chan);
			s_chan_out_byte(rx->chan, RX_NOTI_VAL);
			retval = true;
			// safe to skip reset because the above two lines will
			// not change this threads event state.
			SELECT_CONTINUE_NO_RESET;

		empty:
			break;
	}
	return retval;
#endif
}

/// get next buffer from the channel. The buffer is safe to use until fifo_chan_rx_done() is called.
/// As this is a fifo, it will be undefined behaviour if this function is called twice without calling
/// done.
/// returns NULL if the channel was empty.
STATIC_INLINE void* fifo_chan_rx_receive(fifo_chan_rx_t* rx) {
	xassert(NULL != rx);
	xassert(!rx->buf_out);

#if defined(FIFO_CHAN_USE_XC) && FIFO_CHAN_USE_XC
	uint8_t idx;
	if(chan_non_blocking_receive(rx->chan, &idx)) {
		rx->buf_out = true;
		return &((uint8_t*)rx->buffer)[idx * rx->elem_size];
	}
	else {
		return NULL;
	}
#else
	SELECT_RES( CASE_THEN(rx->chan, got_data),
			    DEFAULT_THEN(empty) ) {
		got_data:
			rx->buf_out = true;
			uint8_t idx = s_chan_in_byte(rx->chan);
			return &((uint8_t*)rx->buffer)[idx * rx->elem_size];

		empty:
			return NULL;
	}
#endif
}


