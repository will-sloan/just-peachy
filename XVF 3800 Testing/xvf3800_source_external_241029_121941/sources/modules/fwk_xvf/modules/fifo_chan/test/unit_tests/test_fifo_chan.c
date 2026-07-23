// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// @brief tests for fifo_chan/tx and fifo_chan/rx
#include "unity.h"

// UUT
#include "fifo_chan/rx.h"
#include "fifo_chan/tx.h"

#include <stdio.h>
#include <xcore/channel_streaming.h>

// get elements in array
#define ARRAY_COUNT(x) (sizeof x / sizeof *x)

static streaming_channel_t m_chan;

void setUp() { }
void tearDown()
{

    // free m_chan here so it isn't forgotten.
    // this means the end state of all tests
    // is that the m_chan is empty
    if (m_chan.end_a || m_chan.end_b) {
        s_chan_free(m_chan);
        m_chan = (streaming_channel_t) { 0 };
    }
}

/// Verify that when the tx struct is initialised, the address and size of the elements are sent
/// over the channel, and the fill level is 0
void test_tx_init()
{
    fifo_chan_tx_t tx;
    static const int int_buf_size = 3;
    static const int char_buf_size = 4;
    int int_buf[int_buf_size];
    char char_buf[char_buf_size];

    streaming_channel_t channel = s_chan_alloc();

    fifo_chan_tx_init(&tx, channel.end_a, &int_buf, sizeof(*int_buf), int_buf_size);

    TEST_ASSERT_EQUAL((uint32_t)int_buf, s_chan_in_word(channel.end_b));
    TEST_ASSERT_EQUAL(sizeof(*int_buf), s_chan_in_word(channel.end_b));
    TEST_ASSERT_EQUAL(int_buf_size, tx.credits);

    fifo_chan_tx_init(&tx, channel.end_a, &char_buf, sizeof(*char_buf), char_buf_size);

    TEST_ASSERT_EQUAL((uint32_t)char_buf, s_chan_in_word(channel.end_b));
    TEST_ASSERT_EQUAL(sizeof(*char_buf), s_chan_in_word(channel.end_b));

    s_chan_free(channel);
}

/// Verify that the two init functions communicate correctly.
void test_tx_then_rx_init(void)
{

    static const int buf_size = 3;
    int buf[buf_size];

    fifo_chan_rx_t rx;
    fifo_chan_tx_t tx;
    m_chan = s_chan_alloc();

    fifo_chan_tx_init(&tx, m_chan.end_a, buf, sizeof(*buf), buf_size);
    fifo_chan_rx_init(&rx, m_chan.end_b);

    TEST_ASSERT_EQUAL(sizeof(*buf), rx.elem_size);
    TEST_ASSERT_EQUAL(buf, rx.buffer);
}

/// verify that tx will give out all it's buffers if rx doesn't do anything
void test_tx_send(void)
{
    static const int buf_size = 3;
    int buf[buf_size];

    fifo_chan_tx_t tx;
    fifo_chan_rx_t rx;
    m_chan = s_chan_alloc();
    fifo_chan_tx_init(&tx, m_chan.end_a, buf, sizeof(*buf), buf_size);

    // need to init an rx to clear the channel of init data
    fifo_chan_rx_init(&rx, m_chan.end_b);

    for (int i = 0; i < buf_size; ++i) {
        void* p = fifo_chan_tx_next_buf(&tx);
        fifo_chan_tx_send(&tx);
        TEST_ASSERT_NOT_NULL(p);
    }

    // get nothing when called for buf_size +1th time.
    void* p = fifo_chan_tx_next_buf(&tx);
    TEST_ASSERT_NULL(p);

    TEST_ASSERT_EQUAL(0, s_chan_in_byte(m_chan.end_b));
    TEST_ASSERT_EQUAL(1, s_chan_in_byte(m_chan.end_b));
    TEST_ASSERT_EQUAL(2, s_chan_in_byte(m_chan.end_b));
}

/// test that incremental indices are sent to the receiver
void test_tx_to_rx_basic(void)
{

    static const int buf_size = 3;
    int buf[buf_size];

    fifo_chan_tx_t tx;
    fifo_chan_rx_t rx;
    m_chan = s_chan_alloc();
    fifo_chan_tx_init(&tx, m_chan.end_a, buf, sizeof(*buf), buf_size);
    fifo_chan_rx_init(&rx, m_chan.end_b);

    for (int i = 0; i < buf_size; ++i) {
        // send buffer
        int* exp = fifo_chan_tx_next_buf(&tx);
        *exp = i;
        fifo_chan_tx_send(&tx);

        // receive buffer
        int* a = fifo_chan_rx_receive(&rx);

        // buffer contents made it
        TEST_ASSERT_EQUAL(*exp, *a);
        // buffer address is correct.
        TEST_ASSERT_EQUAL(&buf[i], a);

        fifo_chan_rx_done(&rx);
    }

    // read the final read notification
    (void)fifo_chan_tx_next_buf(&tx);
}

/// test the fifo loops correctly and that
/// receiving makes space
void test_fifo_sunny_day(void)
{

    static const int buf_size = 3;
    int buf[buf_size];

    fifo_chan_tx_t tx;
    fifo_chan_rx_t rx;
    m_chan = s_chan_alloc();
    fifo_chan_tx_init(&tx, m_chan.end_a, buf, sizeof(*buf), buf_size);
    fifo_chan_rx_init(&rx, m_chan.end_b);

    // expect it to loop around the three idx in
    // buf
    uint8_t exp_idx[] = { 0, 1, 2,
        0, 1, 2,
        0, 1 };
    for (int i = 0; i < ARRAY_COUNT(exp_idx); ++i) {
        // send buffer
        int* exp = fifo_chan_tx_next_buf(&tx);
        *exp = i;
        fifo_chan_tx_send(&tx);

        // receive buffer
        int* a = fifo_chan_rx_receive(&rx);

        // buffer contents made it
        TEST_ASSERT_EQUAL(*exp, *a);
        // buffer address is correct.
        TEST_ASSERT_EQUAL(&buf[exp_idx[i]], a);

        fifo_chan_rx_done(&rx);
    }
    // read the final read notification
    (void)fifo_chan_tx_next_buf(&tx);
}

/// Test rx returns NULL when there are no received messages
/// and does not block
void test_rx_no_messages(void)
{

    static const int buf_size = 3;
    int buf[buf_size];

    fifo_chan_tx_t tx;
    fifo_chan_rx_t rx;
    m_chan = s_chan_alloc();
    fifo_chan_tx_init(&tx, m_chan.end_a, buf, sizeof(*buf), buf_size);
    fifo_chan_rx_init(&rx, m_chan.end_b);

    // NULL after init
    int* next = fifo_chan_rx_receive(&rx);
    TEST_ASSERT_NULL(next);

    // send arbitrary data
    (void)fifo_chan_tx_next_buf(&tx);
    fifo_chan_tx_send(&tx);

    // now it is not  NULL
    next = fifo_chan_rx_receive(&rx);
    TEST_ASSERT_NOT_NULL(next);
    fifo_chan_rx_done(&rx);

    // no messages again
    next = fifo_chan_rx_receive(&rx);
    TEST_ASSERT_NULL(next);

    // read the final read notification
    (void)fifo_chan_tx_next_buf(&tx);
}


/// Test that rx flush gives all credits back to tx.
/// also test that flush the buffer doesn't induce risk
/// of blocking
/// This is tested by spending all the credits, the flushing
/// then tx/rx a few times, then flush. do this more than once
void test_rx_flush(void) {

    // 3 was used in the other tests, choosing different number
    // here to show 3 isn't the only number
    static const int buf_size = 5;
    int buf[buf_size];

    fifo_chan_tx_t tx;
    fifo_chan_rx_t rx;
    m_chan = s_chan_alloc();
    fifo_chan_tx_init(&tx, m_chan.end_a, buf, sizeof(*buf), buf_size);
    fifo_chan_rx_init(&rx, m_chan.end_b);

    for(int i = 0; i < 10; ++i) {
        // change behaviour each iteration
        if(i % 2) {
            printf("fill -> flush\n");
            // fill tx
            TEST_ASSERT_NOT_NULL(fifo_chan_tx_next_buf(&tx));
            fifo_chan_tx_send(&tx);
            TEST_ASSERT_NOT_NULL(fifo_chan_tx_next_buf(&tx));
            fifo_chan_tx_send(&tx);
            TEST_ASSERT_NOT_NULL(fifo_chan_tx_next_buf(&tx));
            fifo_chan_tx_send(&tx);
            TEST_ASSERT_NOT_NULL(fifo_chan_tx_next_buf(&tx));
            fifo_chan_tx_send(&tx);
            TEST_ASSERT_NOT_NULL(fifo_chan_tx_next_buf(&tx));
            fifo_chan_tx_send(&tx);

            TEST_ASSERT_NULL(fifo_chan_tx_next_buf(&tx));

            // flush
            fifo_chan_rx_flush(&rx);
            TEST_ASSERT_NULL(fifo_chan_rx_receive(&rx));
        }
        else {
            printf("communicate\n");
            // send and receive more than buf_size so idx 
            // should not always go back to 0
            for(int j = 0; j < buf_size+2; ++j) {
                TEST_ASSERT_NOT_NULL(fifo_chan_tx_next_buf(&tx));
                fifo_chan_tx_send(&tx);
                TEST_ASSERT_NOT_NULL(fifo_chan_rx_receive(&rx));
                fifo_chan_rx_done(&rx);
            }
        }
    }
    // drain read notifications
    fifo_chan_tx_flush(&tx);
}

