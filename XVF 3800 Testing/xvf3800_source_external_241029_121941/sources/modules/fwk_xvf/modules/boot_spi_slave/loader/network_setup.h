// Copyright 2019-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
//
// PLL and interconnect setup for a dual-tile XS2 device
//
// Largely a specialised version of xflash stage 2 loader
//
#ifndef __network_setup_h__
#define __network_setup_h__

#include <stdint.h>

struct network_info {
  struct {
    uint32_t number;
    uint32_t direction;
    uint32_t delay;
  } usb_link;
  uint32_t user_routing[2];
  uint32_t user_id;
  uint32_t usb_id;
  uint32_t pll_ctl;
  uint32_t ref_div;
};

void network_setup(const struct network_info *network_info);

#endif
