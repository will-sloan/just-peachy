// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// Defines structures and functions required by a module sending
/// data over a fifo chan
#ifndef FIFO_CHAN_TX_H
#define FIFO_CHAN_TX_H

#include <stdint.h>
#include <xcore/select.h>
#include <xcore/channel_streaming.h>
#include <xcore/chanend.h>
#include <xcore/assert.h>
#include <stddef.h>
#include <stdbool.h>
#include "timing_debug_defs.h"

/// circular buffer, initialise with FIFO_CHAN_TX_INITIALISER
typedef struct {

	/// @brief size of the elements in the array, rounded up to word boundary.
	///        client should keep track of actual size if they need it. 
	size_t elem_size;

	/// @brief channel used to send to receiver
	chanend_t chan;

	/// @brief index of next idx to send.
	/// @note this and the below use fast types as profiling shows it makes
	/// a positvie difference. (profile test showed 5 tick speed up in the
	/// next_buf case)
	uint_fast8_t next;

	/// @brief Number of unused buffers
	uint_fast8_t credits;

	/// @brief depth of the fifo
	uint_fast8_t depth;

	/// @brief for asserting correct behaviour only, true between next_buf and send
	bool buf_out;
	
	/// @brief data;
	void* buf;

} fifo_chan_tx_t;

/// XC implementation of the nofitication check
int chan_non_blocking_check_notification(chanend_t c);
		
/// Sends buffer pointer and element size to rx
void fifo_chan_tx_init(fifo_chan_tx_t* tx, chanend_t chan, void* buf, size_t elem_size, uint8_t n_elems);

/// Get pointer to next buffer so it can be written prior to sending, inline as this trivial function
/// will be used in busy places
STATIC_INLINE void* fifo_chan_tx_next_buf(fifo_chan_tx_t* tx) {
	xassert(NULL != tx);
	xassert(!tx->buf_out);

	// check for rx notifications, As we will only claim 1 credits
	// in this function it is only necessary to check for 1 read 
	// notification.

#if defined(FIFO_CHAN_USE_XC) && FIFO_CHAN_USE_XC
	if(chan_non_blocking_check_notification(tx->chan)) {
		tx->credits++;
	}
#else
	SELECT_RES( CASE_THEN(tx->chan, rx_notified),
			    DEFAULT_THEN(empty) ) {
		rx_notified:
			s_chan_in_byte(tx->chan);
			tx->credits++;
			break;

		empty:
			break;
	}
#endif

	// claim a buffer if the credits are available
	if(!tx->credits) {
		return NULL;
	}
	else {
		tx->buf_out = true;
		--tx->credits;
		return &((uint8_t*)tx->buf)[tx->elem_size * tx->next];
	}
}

/// Send the next buffer idx to receiver
STATIC_INLINE void fifo_chan_tx_send(fifo_chan_tx_t* tx) {
	xassert(NULL != tx);
	xassert(tx->buf_out);

	tx->buf_out = false;
	s_chan_out_byte(tx->chan, tx->next);
	tx->next = (tx->next + 1) % tx->depth;
}

/// Flush the receive notifications and top up credits accordingly.
STATIC_INLINE void fifo_chan_tx_flush(fifo_chan_tx_t* tx) {
	xassert(NULL != tx);
	xassert(!tx->buf_out);

#if defined(FIFO_CHAN_USE_XC) && FIFO_CHAN_USE_XC
	while(chan_non_blocking_check_notification(tx->chan)) {
		tx->credits++;
	}
#else
	SELECT_RES( CASE_THEN(tx->chan, rx_notified),
			    DEFAULT_THEN(empty) ) {
		rx_notified:
			s_chan_in_byte(tx->chan);
			tx->credits++;

			// continue without reseting the events, safe
			// because nothing in this case modifies the
			// thread event state
			SELECT_CONTINUE_NO_RESET;

		empty:
			break;
	}
#endif // USE_XC
}

#endif // FIFO_CHAN_TX_H
