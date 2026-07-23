// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.


#ifndef __DATA_PLANE_H
#define __DATA_PLANE_H

#include "i2s_task.h"
#include "audio_task.h"
#include "mic_array_task.h"
#include "shf_wrapper.h"


// These are dummy burn tasks which are used for development only
DECLARE_JOB(reserved_core, (void));


#endif