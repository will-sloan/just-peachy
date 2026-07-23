// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

// This file contains debug macro tricks for to asssist with profiling of audio manager
// during CI runs. These are turned on by ENABLE_AUDIO_TASK_TIMING_DEBUG in the makefile

#ifndef _TIMING_DEBUG_FIFO_
#define _TIMING_DEBUG_FIFO_

// When building the auto timing test
#if ENABLE_TASK_TIMING_DEBUG

#include <stdlib.h>

// Force compiler to not inline helper functions
#define STATIC_INLINE __attribute__((noinline)) static inline 

// Global pointer declare
#define _AUDIO_DEBUG_GLOBAL_DEFS    audio_task_params_t *audio_task_params_dbg_ptr = NULL; \
                                    int cycle_counter = 0;
// Store global pointer to local
#define _AUDIO_DEBUG_INIT_DEFS      audio_task_params_dbg_ptr = &audio_task_params;
#ifndef TIMING_NUM_ITERATIONS
#error Please set TIMING_NUM_ITERATIONS
#endif
#define _AUDIO_DEBUG_LOOP_DEFS      if(++cycle_counter == TIMING_NUM_ITERATIONS) { \
                                        printf("Completed %d iterations..\n", TIMING_NUM_ITERATIONS); \
                                        exit(0); \
                                    }

// When building the application
#else

// Force inlining of helpers
#define STATIC_INLINE __attribute__((always_inline)) static inline 

// No text insertion
#define _AUDIO_DEBUG_GLOBAL_DEFS
#define _AUDIO_DEBUG_INIT_DEFS
#define _AUDIO_DEBUG_LOOP_DEFS

#endif


#endif // _TIMING_DEBUG_
