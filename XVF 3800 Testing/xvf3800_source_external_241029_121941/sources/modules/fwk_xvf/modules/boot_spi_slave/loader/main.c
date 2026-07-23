// Copyright 2019-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#include <xs1.h>
#include <stddef.h>
#include <syscall.h>
#include "relocate.h"
#include "header.h"
#include "block.h"
#include "network_setup.h"
#include "spi_slave.h"
#include "ready_signal.h"
#include "remote_transfer.h"
#include <xcore/hwtimer.h>

#define IMAGE_BLOCK_WORDS (BLOCK_SIZE / 4)
#define LOADER_SIZE_WORDS IMAGE_BLOCK_WORDS

extern void *memcpy(void *dest, const void *src, size_t size);

void receive_blocks_over_spi(unsigned *dest, int block_count)
{
  for (int i = 0; i < block_count; i++) {
    ready_signal_output(1);

    spi_slave_transaction_receive(dest + IMAGE_BLOCK_WORDS * i,
      IMAGE_BLOCK_WORDS);

    ready_signal_output(0);
  }
}

int main(void)
{
  // relocate and jump to new location
  // we are going into stack space so must avoid using it
  // this means compiling with optimisations and not using memcpy
  { unsigned next_pc;

    RELOCATE(XS1_RAM_BASE + XS1_RAM_SIZE - LOADER_SIZE_WORDS * 4,
      XS1_RAM_BASE + HEADER_MAX_BYTES, LOADER_SIZE_WORDS);

    asm("ldap r11, after_relocation\nmov %0, r11" : "=r"(next_pc) :: "r11");
    asm("bau %0" :: "r"(next_pc +
      XS1_RAM_SIZE - LOADER_SIZE_WORDS * 4 - HEADER_MAX_BYTES));

    asm("after_relocation:");
  }

  unsigned *ram_base = (unsigned*)XS1_RAM_BASE;
  const struct header *header = (const struct header*)ram_base;
  const struct network_info *network_info =
    (const struct network_info*)&header->network_info;

  network_setup(network_info);

  spi_slave_initialise();
  ready_signal_initialise();

  // we will be writing to start of RAM
  // save node ID and block counts from header in start of RAM
  unsigned image_block_count[2] = {
    header->image_block_count[0],
    header->image_block_count[1]
  };
  unsigned user_id = network_info->user_id;

  receive_blocks_over_spi(ram_base, image_block_count[1]);

  struct image image = {ram_base, image_block_count[1] * IMAGE_BLOCK_WORDS};
  remote_transfer(DEFAULT_BOOT_CHANNEL_END_ID(user_id | 1), &image);

  receive_blocks_over_spi(ram_base, image_block_count[0]);

  spi_slave_shutdown();
  ready_signal_shutdown();

  // There's a zero length transfer (CS asserted without clock) that follows every block transfer in the spidev spi.xfer() call.
  // The zero length transfer that follows the last block of the spiboot image xfer ends up being seen by the spi_slave 
  // hil thread in the FW while the FW is starting up. Something about a zero length xfer during FW startup causes the
  // spi slave to get messed up such that the first control command over SPI interface doesn't work while subsequent commands work.
  // The delay here is to workaround the above issue. See https://github.com/xmos/sw_xvf3800/issues/29 for more details.
  // From the Saleae capture I observed that the 0 length xfer happens 508us after the block xfer and the CS assert lasts for 6us,
  // so a delay of anything greater than ~515us should be okay. I've tested with as low as 600us delay and it works fine. Keeping the
  // delay as 5ms just to be on the safe side.
  unsigned delay_ms = 5;
  unsigned delay_ticks = (XS1_TIMER_HZ * delay_ms) / 1000;
  hwtimer_t event_delay_tmr = hwtimer_alloc();
  hwtimer_delay(event_delay_tmr, delay_ticks);
  hwtimer_free(event_delay_tmr);

  asm("bau %0" :: "r"(ram_base));

  return 0;
}
