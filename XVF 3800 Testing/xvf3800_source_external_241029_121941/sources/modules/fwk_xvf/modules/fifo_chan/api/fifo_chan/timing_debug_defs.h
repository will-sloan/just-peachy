// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

// This file contains debug macro tricks for to asssist with profiling of audio manager
// during CI runs. These are turned on by ENABLE_AUDIO_TASK_TIMING_DEBUG in the makefile

#ifndef _TIMING_DEBUG_XVF3800_
#define _TIMING_DEBUG_XVF3800_

// When building the auto timing test
#if ENABLE_TASK_TIMING_DEBUG
// Force compiler to not inline helper functions
#define STATIC_INLINE __attribute__((noinline)) static inline 

// When building the application
#else
// Force inlining of helpers
#define STATIC_INLINE __attribute__((always_inline)) static inline 
#endif

#endif // _TIMING_DEBUG_