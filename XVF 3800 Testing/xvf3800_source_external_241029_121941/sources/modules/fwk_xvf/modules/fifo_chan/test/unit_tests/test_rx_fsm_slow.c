// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// test rx fsm in the case where the buffer is in use for the whole time


#include "unity.h"

#include "fifo_chan/rx_fsm.h"

#include <stdio.h>
#include <string.h>
#include <xcore/channel_streaming.h>
#include <xcore/hwtimer.h>

#include "fifo_chan/tx.h"

// get elements in array
#define ARRAY_COUNT(x) (sizeof x / sizeof *x)

static fifo_chan_tx_t m_tx;
static fifo_chan_rx_fsm_t m_rx_fsm;
static streaming_channel_t m_chan;

static const int m_buf_size = 5;
static int m_buf[m_buf_size];

// storage for received vals to compare
static int rx_vals[100];
static int next_rx_vals_idx;

static int* tx_curr;
static int* rx_curr;

int send_val;

void setUp() {
	m_chan = s_chan_alloc();

	fifo_chan_tx_init(&m_tx, m_chan.end_a, m_buf, sizeof *m_buf, m_buf_size);
	fifo_chan_rx_fsm_init(&m_rx_fsm, m_chan.end_b, NULL);

	memset(rx_vals, 0, sizeof rx_vals);
	next_rx_vals_idx = 0;

	tx_curr = NULL;
	rx_curr = NULL;
	send_val = 0;
}

void tearDown() {
	if(tx_curr) 
		fifo_chan_tx_send(&m_tx);
	if(rx_curr)
		fifo_chan_rx_fsm_done(&m_rx_fsm);
	fifo_chan_rx_flush(&m_rx_fsm.rx);
	fifo_chan_tx_flush(&m_tx);

	s_chan_free(m_chan);

}

static void tx() {
	printf("%d ", m_tx.credits);
	if(NULL != tx_curr) {
		*tx_curr = send_val;
		printf("-> %d\n", *tx_curr);
		fifo_chan_tx_send(&m_tx);
	}
	else {
		printf("-> x\n");
	}
	tx_curr = fifo_chan_tx_next_buf(&m_tx);
	printf("%d ", m_tx.credits);
	if(tx_curr) {
		printf("<-\n");
	}
	else {
		printf("x\n");
	}

	send_val++;
}

static void rx() {
	if(NULL != rx_curr) {
		printf("\t<-\n");
		fifo_chan_rx_fsm_done(&m_rx_fsm);
	}
	else {
		printf("\tx\n");
	}
	rx_curr = fifo_chan_rx_fsm_receive(&m_rx_fsm);
	if(rx_curr) {
		printf("\t%d\n", *rx_curr);
		rx_vals[next_rx_vals_idx++] = *rx_curr;
	}
	else {
		printf("\tx\n");
	}
}


// test the case where tx and rx are greedy with their buffers. This means
// They hold on to a credit until the time where they need the next one. This
// is the worst case
void test_rx_fsm_slow(void) {
	int expected[1000] = {0};
	int ex_idx = 0;
	int ex_val = 0;  // first expected val is 1, 0 is dropped
	rx();
	TEST_ASSERT_EQUAL(NULL, rx_curr);

	tx();  // tx next_buf
	ex_val++;   // tx increments val, but has no buffer to send
	rx();
	TEST_ASSERT_EQUAL(NULL, rx_curr);

	tx();  // first send
	ex_val++; // this value is dropped by rx
	rx();
	// flush
	TEST_ASSERT_EQUAL(NULL, rx_curr);

	tx();
	expected[ex_idx++] = ex_val++;
	rx();
	// skip
	TEST_ASSERT_EQUAL(NULL, rx_curr);

	tx();
	expected[ex_idx++] = ex_val++;
	rx();
	// sync
	TEST_ASSERT_NOT_NULL(rx_curr);
	for(int i = 0; i < 7; i++) {
		tx();
		expected[ex_idx++] = ex_val++;
		rx();

		// rx speeds up and slows down
		tx();
		expected[ex_idx++] = ex_val++;
		rx(); // r
		rx(); // r
		tx();
		expected[ex_idx++] = ex_val++;
		rx();
		tx(); // t
		expected[ex_idx++] = ex_val++;
		tx(); // t
		expected[ex_idx++] = ex_val++;
		rx();

		// tx speeds up and slows down
		tx();
		expected[ex_idx++] = ex_val++;
		tx();
		expected[ex_idx++] = ex_val++;
		rx();
		tx();
		expected[ex_idx++] = ex_val++;
		rx();
		rx();

		if(i % 2) {
			// tx stops
			rx();
			rx();
			rx();
			rx();
			rx();
			TEST_ASSERT_NULL(rx_curr);

			tx();      // sends buf it claimed last time
			ex_val++;  // tx results in flush
			rx();      // receive and flush
			tx();      // send -> next_buf
			expected[ex_idx++] = ex_val++;
			rx();
		}
		else {
			// rx stops
			tx();  
			ex_val++; 
			rx();        // this rx here is because the final value on the
						 // fifo when rx stops is actually the previous tx
						 // therefore the previous tx val needs to not be expected
						 // as it will be flushed


			tx();  
			ex_val++; 
			tx(); 
			ex_val++;
			tx();
			ex_val++;
			tx();
			ex_val++;
			tx();
			ex_val++;
			
			fifo_chan_rx_fsm_reset(&m_rx_fsm);
			rx(); // reset state
			tx(); // claims credit
			ex_val++;
			rx(); // init state, chan empty
			tx(); // send -> next_buf
			ex_val++;
			rx(); // still init, chan not empty
			tx();      // send -> next_buf
			expected[ex_idx++] = ex_val++;
			rx(); // skip
		}
	}

	// normal again
	tx();
	expected[ex_idx++] = ex_val++;
	rx();
	tx();
	expected[ex_idx++] = ex_val++;
	rx();

	// final rx to drain
	rx();


	for(int i = 0; i < ex_idx; ++i) {
		TEST_ASSERT_EQUAL(expected[i], rx_vals[i]);
	}
	
}
