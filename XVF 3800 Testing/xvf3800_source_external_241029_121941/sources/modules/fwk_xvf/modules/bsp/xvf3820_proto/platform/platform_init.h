// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.


#ifndef PLATFORM_INIT_H_
#define PLATFORM_INIT_H_

#include <xcore/chanend.h>

/// @brief initialise the platform, called before starting the OS
void platform_init(chanend_t other_tile_c);

/// @brief Start the platform, called after starting the OS
void platform_start(void);

#endif /* PLATFORM_INIT_H_ */
