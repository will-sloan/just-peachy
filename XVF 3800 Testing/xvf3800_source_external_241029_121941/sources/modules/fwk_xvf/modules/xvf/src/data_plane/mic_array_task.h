// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.


#ifndef _MIC_ARRAY_TASK_H_
#define _MIC_ARRAY_TASK_H_

#include <xcore/parallel.h>
#include <xcore/chanend.h>

/// @brief the i2s task spins up mic array
/// @param c_mic_to_audio the channel connecting to audio from mic_array
void mic_array_task(chanend_t c_mic_to_audio);
DECLARE_JOB(mic_array_task, (chanend_t));

#ifdef __cplusplus
extern "C" {
#endif
void ma_init();
void ma_task(chanend_t c_mic_to_audio);
#ifdef __cplusplus
}
#endif
#endif
