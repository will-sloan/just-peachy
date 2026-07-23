// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// Tests that assert the rx fsm returns `sync data` at the correct times
///
///

#include "unity.h"

#include "fifo_chan/tx.h"
#include "fifo_chan/rx_fsm.h"
#include "xcore/channel_streaming.h"
#include <stdint.h>


void setUp() {}
void tearDown() {}

/// Test that when sync data is provided, it is correctly returned
/// when syncing and NULL is returned when out of sync. This iterates
/// a couple of times to validate the state machine
void test_rx_fsm_sync_data(void) {
	#define TEST_BUF_SIZE 3
	int tx_buf[TEST_BUF_SIZE];
	int sync_data = 123;
	streaming_channel_t chan = s_chan_alloc();

	fifo_chan_tx_t tx;
	fifo_chan_rx_fsm_t rx;

	fifo_chan_tx_init(&tx, chan.end_a, tx_buf, sizeof *tx_buf, TEST_BUF_SIZE);
	fifo_chan_rx_fsm_init(&rx, chan.end_b, &sync_data);

	TEST_ASSERT_EQUAL(&sync_data, rx.sync_data);

	for(int i = 0; i < 5; ++i) {
		// tx has sent nothing, get NULL
		TEST_ASSERT_EQUAL(NULL, fifo_chan_rx_fsm_receive(&rx));

		int* t = fifo_chan_tx_next_buf(&tx);
		*t = 0;
		fifo_chan_tx_send(&tx);


		// tx sent something, get sync data
		int* r = fifo_chan_rx_fsm_receive(&rx);
		TEST_ASSERT_EQUAL(&sync_data, r);
		// mark as done even though this isn't a proper buffer
		// buf receiver doesn't have to know.
		fifo_chan_rx_fsm_done(&rx);

		t = fifo_chan_tx_next_buf(&tx);
		*t = 1;
		fifo_chan_tx_send(&tx);


		// tx sent something, get sync data
		r = fifo_chan_rx_fsm_receive(&rx);
		TEST_ASSERT_EQUAL(&sync_data, r);
		fifo_chan_rx_fsm_done(&rx);
		
		uint_fast8_t before_credits = tx.credits;
		
		t = fifo_chan_tx_next_buf(&tx);
		*t = 2;
		fifo_chan_tx_send(&tx);

		// should be synced now, get second received data.
		r = fifo_chan_rx_fsm_receive(&rx);
		TEST_ASSERT_EQUAL(1, *r);
		fifo_chan_rx_fsm_done(&rx);

		// do lots of send and receiver
		before_credits = tx.credits;
		
		t = fifo_chan_tx_next_buf(&tx);
		*t = 3;
		fifo_chan_tx_send(&tx);

		// rx returned a credit and tx claimed one
		TEST_ASSERT_EQUAL(before_credits, tx.credits); 


		fifo_chan_rx_fsm_receive(&rx);
		fifo_chan_rx_fsm_done(&rx);
		fifo_chan_rx_fsm_receive(&rx);
		fifo_chan_rx_fsm_done(&rx);
		fifo_chan_rx_fsm_receive(&rx);
	}
}


