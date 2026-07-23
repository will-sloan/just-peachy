// Copyright 2019-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#ifndef __header_h__
#define __header_h__

#ifndef __ASSEMBLER__

#include <stdint.h>
#include "network_setup.h"

struct header {
  uint32_t trampoline;
  struct network_info network_info;
  uint32_t image_block_count[2];
};

#endif

#define HEADER_MAX_BYTES 128

#endif
