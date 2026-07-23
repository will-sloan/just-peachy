// Copyright 2019-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#include <xs1.h>
#include <xclib.h>
#include <xs3a_registers.h>
#include "is_simulation.h"
#include "galaxian.h"
#include "network_setup.h"

#define PLL_LOCK_DELAY_MS 50
#define DEFAULT_NODE_ID 0

void network_setup(const struct network_info *ni)
{
  const unsigned usb_delays =
    ((ni->usb_link.delay - 1) << XS1_XLINK_INTER_TOKEN_DELAY_SHIFT) |
    ((ni->usb_link.delay - 1) << XS1_XLINK_INTRA_TOKEN_DELAY_SHIFT);

  // configure master's PLL, reference divider and SSwitch divider
  // with reboot to allow for a large change such as 500 to 600 MHz
  { unsigned pll_ctl;
    read_sswitch_reg(DEFAULT_NODE_ID, XS1_SSWITCH_PLL_CTL_NUM, &pll_ctl);
    if (pll_ctl != ni->pll_ctl && !is_simulation_badfood_in_ram()) {
      write_sswitch_reg(DEFAULT_NODE_ID, XS1_SSWITCH_PLL_CTL_NUM, ni->pll_ctl);
      __builtin_unreachable();
    }
    write_sswitch_reg(DEFAULT_NODE_ID, XS1_SSWITCH_REF_CLK_DIVIDER_NUM, ni->ref_div);
    write_sswitch_reg(DEFAULT_NODE_ID, XS1_SSWITCH_CLK_DIVIDER_NUM, 0);
  }

  // set master user node ID
  write_sswitch_reg_no_ack(DEFAULT_NODE_ID, XS1_SSWITCH_NODE_ID_NUM, ni->user_id);

  // now set master user routing so we can reach the slave again
  { write_sswitch_reg(ni->user_id, XS1_SSWITCH_DIMENSION_DIRECTION0_NUM,
      ni->user_routing[0]);

    write_sswitch_reg(ni->user_id, XS1_SSWITCH_DIMENSION_DIRECTION1_NUM,
      ni->user_routing[1]);
  }

  // open USB link, set its direction and send hello
  // lookup table already has an entry alongside other user routing entries
  { write_sswitch_reg(ni->user_id, XS1_SSWITCH_XLINK_0_NUM + ni->usb_link.number,
      usb_delays | XS1_XLINK_ENABLE_MASK | XS1_XLINK_WIDE_MASK);

    write_sswitch_reg(ni->user_id, XS1_SSWITCH_SLINK_0_NUM + ni->usb_link.number,
      ni->usb_link.direction << XS1_LINK_DIRECTION_SHIFT);

    write_sswitch_reg(ni->user_id, XS1_SSWITCH_XLINK_0_NUM + ni->usb_link.number,
      usb_delays | XS1_XLINK_ENABLE_MASK|XS1_XLINK_WIDE_MASK|XS1_XLINK_HELLO_MASK);
  }

  // This has been commented out as setting up the PLL caused the bootloader to hang on AI

  // configure USB PLL
  // write_sswitch_reg(ni->usb_id, XS1_GLX_CFG_LINK_CTRL_ADRS, GLX_XCORE_HELLO);
  // write_sswitch_reg(ni->usb_id, XS1_GLX_CFG_SYS_CLK_FREQ_ADRS, 24);
}
