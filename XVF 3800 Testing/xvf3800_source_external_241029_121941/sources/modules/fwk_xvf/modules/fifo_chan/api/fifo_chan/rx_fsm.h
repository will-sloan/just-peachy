// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// An implementation of a state machine that uses the rx fifo to
/// force a certain fill level in the channel. This makes the assumption
/// that the average period that tx and rx will send and consume messages
/// will be the same over time. This implemenation hard codes the fill
/// level to at least 1.
#ifndef FIFO_CHAN_RX_FSM_H
#define FIFO_CHAN_RX_FSM_H

#include <xcore/assert.h>

#include "fifo_chan/rx.h"

#ifndef FIFO_CHAN_RX_FSM_SKIP_ITERATIONS
#define FIFO_CHAN_RX_FSM_SKIP_ITERATIONS 1
#endif

typedef enum {
	RX_FSM_STATE_INIT,
	RX_FSM_STATE_SKIP,
	RX_FSM_STATE_SYNC,
	RX_FSM_STATE_RESET,
} fifo_chan_rx_states_t;


typedef struct {
	/// rx instance used for comms
	fifo_chan_rx_t rx;

	/// current state
	fifo_chan_rx_states_t state;
	fifo_chan_rx_states_t next_state;

	/// used in the SKIP state to determine when it has skipped enough
	uint8_t skip_counter;

	/// Pointer to some data returned when in the SKIP state, and 
	/// post INIT, when the first data has been detected.
	void* sync_data;
} fifo_chan_rx_fsm_t;

/// set default state and initialise the contained fifo_chan_rx_t
/// @param rx_fsm rx instance
/// @param chan chaned used by this instance for communicating
/// @param sync_data pointer that will be returned by the fsm during sync. This can be used
///                  to make rx_fsm appear as a normal rx. This must point to static data.
STATIC_INLINE void fifo_chan_rx_fsm_init(fifo_chan_rx_fsm_t* rx_fsm, chanend_t chan, void* sync_data) {
	xassert(NULL != rx_fsm);
	fifo_chan_rx_init(&rx_fsm->rx, chan);
	rx_fsm->state = RX_FSM_STATE_INIT;
	rx_fsm->next_state = RX_FSM_STATE_INIT;
	rx_fsm->sync_data = sync_data;
}

/// Reset the fsm, call when you know there has been a pause in receiving and
/// the channel might be over full
STATIC_INLINE void fifo_chan_rx_fsm_reset(fifo_chan_rx_fsm_t* rx_fsm) {
	xassert(NULL != rx_fsm);

	rx_fsm->next_state = RX_FSM_STATE_RESET;
}

/// Receive next buf if the fill level is known to be good. otherwise NULL
STATIC_INLINE void* fifo_chan_rx_fsm_receive(fifo_chan_rx_fsm_t* rx_fsm) {
	xassert(NULL != rx_fsm);
	
	rx_fsm->state = rx_fsm->next_state;

	void* retval = NULL;
	switch(rx_fsm->state) {
		case RX_FSM_STATE_INIT:
			if(fifo_chan_rx_flush(&rx_fsm->rx)) {
				rx_fsm->next_state = RX_FSM_STATE_SKIP;
				rx_fsm->skip_counter = FIFO_CHAN_RX_FSM_SKIP_ITERATIONS;
				retval = rx_fsm->sync_data;
			}
			break;
	
		case RX_FSM_STATE_SKIP:
			rx_fsm->skip_counter -= 1;
			retval = rx_fsm->sync_data;
			if(0 == rx_fsm->skip_counter) {
				rx_fsm->next_state = RX_FSM_STATE_SYNC;
			}
			break;

		case RX_FSM_STATE_SYNC:
			retval = fifo_chan_rx_receive(&rx_fsm->rx);
			if(NULL == retval) {
				rx_fsm->next_state = RX_FSM_STATE_INIT;
			}
			break;

		case RX_FSM_STATE_RESET:
			fifo_chan_rx_flush(&rx_fsm->rx);
			rx_fsm->next_state = RX_FSM_STATE_INIT;
			break;
	}
	return retval;
}

/// notify tx that rx is finished with the most recent buffer. don't call
/// if receive returned NULL
STATIC_INLINE void fifo_chan_rx_fsm_done(fifo_chan_rx_fsm_t* rx_fsm) {
	if(RX_FSM_STATE_SYNC == rx_fsm->state) {
		fifo_chan_rx_done(&rx_fsm->rx);
	}
}

#endif
