// Copyright 2019-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#include <stdio.h>
#include <stdint.h>
#include <stddef.h>
#include "network_setup.h"
#include "header.h"

int main(void)
{
  printf("%zd trampoline\n",           offsetof(struct header, trampoline));
  printf("%zd network_info\n",         offsetof(struct header, network_info));
  printf("%zd image_block_count\n",    offsetof(struct header, image_block_count));

  printf("%zd usb_link\n",             offsetof(struct network_info, usb_link));
  printf("%zd user_routing\n",         offsetof(struct network_info, user_routing));
  printf("%zd user_id\n",              offsetof(struct network_info, user_id));
  printf("%zd usb_id\n",               offsetof(struct network_info, usb_id));
  printf("%zd pll_ctl\n",              offsetof(struct network_info, pll_ctl));
  printf("%zd ref_div\n",              offsetof(struct network_info, ref_div));

  return 0;
}
