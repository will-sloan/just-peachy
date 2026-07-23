// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#define DEBUG_UNIT SHF_BYPASS
#ifndef DEBUG_PRINT_ENABLE_SHF_BYPASS
    #define DEBUG_PRINT_ENABLE_SHF_BYPASS 0
#endif
#include "debug_print.h"

#include "shf_bypass/shf_bypass.h"

#include <stdint.h>
#include <string.h>
#include <xcore/assert.h>
#include <xcore/parallel.h>
#include <xcore/channel.h>
#include <xcore/hwtimer.h>

/* ****************
 * Macros
 * ****************/
// set to 1 to set the 7 worker threads to print a regular output
#ifndef DEBUG_PRINT_WORKER_BURN_THREADS
#define DEBUG_PRINT_WORKER_BURN_THREADS     0   //Print progress of the SHF worker threads or not
#endif

#define DUMMY_WAIT_PERCENTAGE       92.5f   // The amount of time the busy wait test task keeps running as a proportiuon of frame frequency
#define AEC_DUMMY_WAIT_TICKS        ((uint32_t)((XS1_TIMER_HZ * (float)BECLEAR_SAMPLES_PER_FRAME / BECLEAR_SAMPLE_FREQUENCY) * DUMMY_WAIT_PERCENTAGE / 100.0))
#define PP_DUMMY_WAIT_TICKS         ((uint32_t)((XS1_TIMER_HZ * (float)BECLEAR_SAMPLES_PER_FRAME / BECLEAR_SAMPLE_FREQUENCY) * DUMMY_WAIT_PERCENTAGE / 100.0))

#define SETSR(c)                asm volatile("setsr %0" : : "n"(c));
#define CLRSR(c)                asm volatile("clrsr %0" : : "n"(c));
#define SET_HIGH_PRIORITY()     SETSR(XS1_SR_QUEUE_MASK)    // Force the xcore to schedule once every 5 processor clocks
#define SET_FAST_MODE()         SETSR(XS1_SR_FAST_MASK)     // Force the xcore to schedule even if blocked on event

#define TIME_AFTER(A, B) ((int)((B) - (A)) < 0)

// nbeams + fast moving + autoselect
//#define BECLEAR_NUMBER_OF_OUTPUTS (BECLEAR_MAX_NUMBER_OF_BEAMS + 2)

/* ****************
 * Function declarations
 * ****************/
DECLARE_JOB(aec_worker_task, (unsigned, unsigned, unsigned));

DECLARE_JOB(pp_worker_task, (unsigned, unsigned, unsigned));


/* ****************
 * Data definitions
 * ****************/

/// chanend attached to AEC for xfer data to and from PP
static chanend_t m_aec_chanend;

/// PP end of the AEC <-> PP channel
static chanend_t m_pp_chanend;

/* ********************
 * Function definitions
 * ********************/

uint32_t shf_bypass_wait(uint32_t delay_ticks){
    uint32_t loops = 0;
    uint32_t time_delay = get_reference_time() + delay_ticks;
    while(TIME_AFTER(time_delay, get_reference_time())){
        loops += 1;
    }
    return loops;
}

void shf_bypass_event_wait(uint32_t delay_ticks){
    hwtimer_t event_delay_tmr = hwtimer_alloc();
    hwtimer_delay(event_delay_tmr, delay_ticks);
    hwtimer_free(event_delay_tmr);
}

void aec_worker_task(unsigned task_num, unsigned burn, unsigned priority){
    if(priority){
        SET_HIGH_PRIORITY();
    }
    if(burn){
        shf_bypass_wait(AEC_DUMMY_WAIT_TICKS);
    }else{
        shf_bypass_event_wait(AEC_DUMMY_WAIT_TICKS);
    }
    if(DEBUG_PRINT_WORKER_BURN_THREADS){
        debug_printf("aec_%u_task Tile[%d] logical core ID[%u]\n", task_num, THIS_XCORE_TILE, get_logical_core_id());
    }
}

void shf_bypass_init_aec(chanend_t c) {
    m_aec_chanend = c;
}

void shf_bypass_main_aec(
    float* const* const mics,
    float* const* const spks,
    float* const* const qcom,
    float* const* const aecmics,
    unsigned burn
) {
    xassert(0 != m_aec_chanend);
    xassert(NULL != mics);
    xassert(NULL != spks);
    xassert(NULL != qcom);
    xassert(NULL != aecmics);
    xassert(NULL != *mics);
    xassert(NULL != *spks);
    xassert(NULL != *qcom);
    xassert(NULL != *aecmics);

    // Exchange buffers with PP thread.
    for(int i = 0; i < BECLEAR_NUMBER_OF_OUTPUTS; ++i)
    {
        chan_in_buf_word(m_aec_chanend, (uint32_t*)qcom[i], BECLEAR_SAMPLES_PER_FRAME);
    }
    for(int i = 0; i < BECLEAR_MAX_NUMBER_OF_MICS; ++i)
    {
        chan_out_buf_word(m_aec_chanend, (uint32_t*)mics[i], BECLEAR_SAMPLES_PER_FRAME);
    }
    // aecmics = qcom = mics from last frame
    for(int i = 0; i < BECLEAR_MAX_NUMBER_OF_MICS; ++i)
    {
        memcpy(aecmics[i], qcom[i], BECLEAR_SAMPLES_PER_FRAME * sizeof(float));
    }
    (void)spks; // nothing to do

    PAR_JOBS(
        PJOB(aec_worker_task, (0, burn, 1)),          // All tasks are high priority
        PJOB(aec_worker_task, (1, burn, 1)),
        PJOB(aec_worker_task, (2, burn, 1)),
        PJOB(aec_worker_task, (3, burn, 1))
    );
}

void pp_worker_task(unsigned task_num, unsigned burn, unsigned priority){
    if(priority){
        SET_HIGH_PRIORITY();
    }
    if(burn){
        shf_bypass_wait(PP_DUMMY_WAIT_TICKS);
    }else{
        shf_bypass_event_wait(PP_DUMMY_WAIT_TICKS);
    }

    if(DEBUG_PRINT_WORKER_BURN_THREADS){
        debug_printf("pp_%d_task Tile[%d] logical core ID[%u]\n", task_num, THIS_XCORE_TILE, get_logical_core_id());
    }
}


void shf_bypass_init_pp(chanend_t c) {
    m_pp_chanend = c;
}

void shf_bypass_main_pp(unsigned burn, float buf[BECLEAR_MAX_NUMBER_OF_MICS][BECLEAR_SAMPLES_PER_FRAME]) {
    xassert(0 != m_pp_chanend);

    // Exchange buffers with AEC
    for(int i = 0; i < BECLEAR_MAX_NUMBER_OF_MICS; ++i)
    {
        chan_out_buf_word(m_pp_chanend, (uint32_t*)&buf[i][0], BECLEAR_SAMPLES_PER_FRAME);
    }
    for(int i = 0; i < BECLEAR_MAX_NUMBER_OF_MICS; ++i)
    {
        chan_in_buf_word(m_pp_chanend, (uint32_t*)&buf[i][0], BECLEAR_SAMPLES_PER_FRAME);
    }

    PAR_JOBS(
        PJOB(pp_worker_task, (0, burn, 1)),          // Only two of the three tasks are high priority
        PJOB(pp_worker_task, (1, burn, 1)),
        PJOB(pp_worker_task, (2, burn, 0))
    );

}
