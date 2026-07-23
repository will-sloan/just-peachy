// Copyright 2019-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#ifndef __remote_transfer_h__
#define __remote_transfer_h__

#define DEFAULT_BOOT_CHANNEL_END_ID(node_id) \
  (XS1_RES_TYPE_CHANEND << XS1_RES_ID_TYPE_SHIFT) | \
  (0 << XS1_CHAN_ID_CHANNUM_SHIFT) | \
  ((node_id) << XS1_CHAN_ID_PROCESSOR_SHIFT)

struct image {
#ifdef __XC__
  const unsigned * unsafe start;
#else
  const unsigned * start;
#endif
  int len_words;
};

void remote_transfer(unsigned remote_chanend_id, const struct image *image);

#endif
