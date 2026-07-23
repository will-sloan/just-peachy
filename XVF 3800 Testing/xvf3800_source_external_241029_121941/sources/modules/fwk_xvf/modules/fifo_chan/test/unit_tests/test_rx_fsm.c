// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// Test the rx fsm
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

static const int m_buf_size = 3;
static int m_buf[m_buf_size];

// storage for received vals to compare
static int rx_vals[100];
static int next_rx_vals_idx;

enum {
	E_NEXT_BUF,
	E_SEND,
	E_RECEIVE,
	E_DONE,
	E_MAX_PROFILES
};
static uint32_t profiles[E_MAX_PROFILES];
static const char* profile_names[] = {
	[E_NEXT_BUF] = "next_buf",
	[E_SEND] = "send",
	[E_RECEIVE] = "receive",
	[E_DONE] = "done"
};

#define PROFILE(ID, ...) do {\
		uint32_t start = get_reference_time(); \
		__VA_ARGS__; \
		uint32_t elapsed = get_reference_time() - start; \
		if(elapsed > profiles[ID]) \
			profiles[ID] = elapsed; \
	}while(0)

void setUp() {
	m_chan = s_chan_alloc();

	fifo_chan_tx_init(&m_tx, m_chan.end_a, m_buf, sizeof *m_buf, m_buf_size);
	fifo_chan_rx_fsm_init(&m_rx_fsm, m_chan.end_b, NULL);

	memset(rx_vals, 0, sizeof rx_vals);
	next_rx_vals_idx = 0;
}

void tearDown() {

	fifo_chan_rx_flush(&m_rx_fsm.rx);
	fifo_chan_tx_flush(&m_tx);

	s_chan_free(m_chan);

}

/// basic test showing that the first buffer is always dropped
/// by the receiver.
void test_rx_fsm_basic(void) {
	
	static const int test_data[] = {5, 6, 7, 8, 9, 10, 11, 12, 13};
	int t_idx = 0;
	int r_idx = 1; // first received value is the second value

	// send value
	int* send = fifo_chan_tx_next_buf(&m_tx);
	*send = test_data[t_idx++];
	printf("-> %d\n", *send);
	fifo_chan_tx_send(&m_tx);

	// get NULL
	int* recv = fifo_chan_rx_fsm_receive(&m_rx_fsm);
	TEST_ASSERT_NULL(recv);


	// send value
	send = fifo_chan_tx_next_buf(&m_tx);
	*send = test_data[t_idx++];
	printf("-> %d\n", *send);
	fifo_chan_tx_send(&m_tx);

	// get NULL
	recv = fifo_chan_rx_fsm_receive(&m_rx_fsm);
	TEST_ASSERT_NULL(recv);

	while(t_idx < ARRAY_COUNT(test_data)) {
	
		send = fifo_chan_tx_next_buf(&m_tx);
		*send = test_data[t_idx++];
		printf("-> %d\n", *send);
		fifo_chan_tx_send(&m_tx);

		recv = fifo_chan_rx_fsm_receive(&m_rx_fsm);
		TEST_ASSERT_NOT_NULL(recv);
		TEST_ASSERT_EQUAL(test_data[r_idx++], *recv);
		printf("<- %d\n", *recv);
		fifo_chan_rx_fsm_done(&m_rx_fsm);
	}
}

static void tx(int val) {
	int* send;
	PROFILE( E_NEXT_BUF,
		send = fifo_chan_tx_next_buf(&m_tx) 
	);
	if(NULL != send) {
		*send = val;
		printf("-> %d\n", *send);
		PROFILE(E_SEND, 
			fifo_chan_tx_send(&m_tx)
		);
	}
	else {
		printf("-> x\n");
	}
}

static void rx() {
	int* recv;
	PROFILE(E_RECEIVE,
		recv = fifo_chan_rx_fsm_receive(&m_rx_fsm)
	);
	if(NULL != recv) {
		rx_vals[next_rx_vals_idx++] = *recv;
		printf("<- %d\n", *recv);
		PROFILE(E_DONE,
			fifo_chan_rx_fsm_done(&m_rx_fsm)
		);
	}
	else {
		printf("<- x\n");
	}
}

/// test the scenarios where 2 or 0 tx happend for each rx. No
/// samples should be lost.
void test_rx_fsm_w_jitter(void) {

	int v = 0;

	// some normal interactions
	rx();
	tx(v++);
	rx();
	tx(v++);
	rx();
	tx(v++);

	// tx speeds up and then slows down
	tx(v++); // 2 tx
	rx();
	tx(v++);
	rx();
	rx();    // 2 rx
	tx(v++);
	rx();

	// tx slows down and then speeds up
	rx();    // 2 rx
	tx(v++);
	rx();
	tx(v++);
	tx(v++); // 2 tx
	rx();
	tx(v++);
	rx();

	// we sent incrementing numbers starting at 0
	// therefore the output should be incrementing
	// numbers starting at 1 as the first val is dropped
	for(int i = 0; i < next_rx_vals_idx; ++i) {
		TEST_ASSERT_EQUAL(i+1, rx_vals[i]);
	}
}

/// Tests that the rx_fsm can recover from the transmitter
/// stopping
void test_rx_fsm_tx_stops_and_restarts(void) {
	int i = 0;

	// Gaps in expected caused by rx fsm detecting
	// new data, dropping it, waiting for it to 
	// fill to the desired level
	int test_data[] = {0, 1, 2, 3, 4, 5, 6, 7, 8};
	int expected[] =  {   1, 2, 3,    5, 6, 7, 8};

	// tx
	tx(test_data[i++]);
	rx();
	tx(test_data[i++]);
	rx();
	tx(test_data[i++]);
	rx();
	tx(test_data[i++]);
	rx();

	rx();
	rx();
	rx();
	rx();
	rx();

	// tx restart, added jitter to check it re-levels the channel
	tx(test_data[i++]);
	rx();
	tx(test_data[i++]);
	tx(test_data[i++]);
	rx();
	rx();
	tx(test_data[i++]);
	rx();
	rx();
	tx(test_data[i++]);

	// final rx to drain the channel
	rx();

	TEST_ASSERT_EQUAL(ARRAY_COUNT(expected), next_rx_vals_idx);
	for(int j = 0; j < next_rx_vals_idx; j++) {
		TEST_ASSERT_EQUAL(expected[j], rx_vals[j]);
	}
}

/// Shows that transmitter can recover from receiver stopping,
/// but only if receiver takes action to reset the fsm
void test_rx_fsm_rx_stops_and_restarts(void) {
	int i = 0;

	// see inline comments below to see where tx stops and starts being
	// received
	int test_data[] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12};
	int expected[] =  {   1, 2,                   9, 10, 11, 12};  

	// tx
	tx(test_data[i++]);
	rx();
	tx(test_data[i++]);
	rx();
	tx(test_data[i++]);  // test_data[2]
	rx();
	tx(test_data[i++]);
	rx();

	tx(test_data[i++]);
	tx(test_data[i++]);
	tx(test_data[i++]);
	tx(test_data[i++]);

	// rx must manually reset here, knowing that
	// it has missed a few cycles
	// this test _does_ fail if this is removed
	fifo_chan_rx_fsm_reset(&m_rx_fsm);

	rx();  // reset
	tx(test_data[i++]);  // test_data[8]
	rx(); // init
	rx(); // skip
	tx(test_data[i++]);
	tx(test_data[i++]);
	rx();
	tx(test_data[i++]);
	tx(test_data[i++]);
	rx();
	rx();
	rx();

	for(int j = 0; j < next_rx_vals_idx; j++) {
		TEST_ASSERT_EQUAL(expected[j], rx_vals[j]);
	}
	TEST_ASSERT_EQUAL(ARRAY_COUNT(expected), next_rx_vals_idx);
}

/// hack to make it print the time profiles at the end of the test
void test_print_profiles(void) {
	printf("\nThis single threaded test is running at 600MHz/5 = 120MHz\n");
	printf("Functions timed using the 100MHz reference ticks took the\n");
	printf("following ticks:\n");
	for(int i = 0; i < E_MAX_PROFILES; i++) {
		printf("%15s:\t%lu\n", profile_names[i], profiles[i]);
	}
	printf("\n");
}
