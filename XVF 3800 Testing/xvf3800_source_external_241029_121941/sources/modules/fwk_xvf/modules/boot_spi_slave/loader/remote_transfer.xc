// Copyright 2016-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#include <xs1.h>
#include "stringify.h"
#include "remote_transfer.h"

#define CRC_DISABLE_MAGIC 0x0D15AB1E

unsigned words_transferred = 0;

unsafe static void transfer(chanend c, const struct image *image)
{
  outuint(c, (unsigned)c);

  outuint(c, image->len_words);
  for (int i = 0; i < image->len_words; i++) {
    unsigned w = image->start[i];
    outuint(c, w);
  }

  outuint(c, CRC_DISABLE_MAGIC);
  outct(c, XS1_CT_END);

  words_transferred = image->len_words;
}

void remote_transfer(unsigned remote_chanend_id, const struct image *image)
{
  unsafe chanend c;

  asm("getr %0, " STRINGIFY(XS1_RES_TYPE_CHANEND) : "=r"(c));
  asm("setd res[%0], %1" :: "r"(c), "r"(remote_chanend_id));

  unsafe {
    transfer((chanend)c, image);
  }

  asm("freer res[%0]" :: "r"(c));
}
