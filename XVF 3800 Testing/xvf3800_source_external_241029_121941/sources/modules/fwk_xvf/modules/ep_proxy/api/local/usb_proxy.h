// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#pragma once

#include <xcore/chanend.h>
#include <xcore/channel.h>
#include <stdint.h>
#include <stdbool.h>
#include "rtos_osal.h"
#include "xud_device.h"
#include "usb_descriptors.h"
#include "rtos_usb.h"

// Macro magic to make declaring proxies and buffers very easy.

// This is defined here for completeness, undef and redef when you declare your ep_proxies
#define EP_PROXY_BUFFER_SIZE 0

#define EP_PROXY_BUFFER_INIT(ep_num, in_use, bufsize) [ep_num] = {ep_num, in_use, (unsigned char[bufsize]){0}}
#define EP_PROXY_BUFFER_NO_INIT(ep_num, in_use) [ep_num] = {ep_num, in_use, NULL}
#define PROXIED(ep_num) EP_PROXY_BUFFER_INIT(ep_num, true, EP_PROXY_BUFFER_SIZE)
#define NOT_PROXIED(ep_num) EP_PROXY_BUFFER_NO_INIT(ep_num, false)

typedef struct
{
  uint8_t ep_num;
  bool in_use;
  unsigned char * buffer;
} ep_proxy_definition_t;

typedef struct
{
  uint8_t rhport;
  uint8_t event_id;

  union
  {
    // XFER_COMPLETE
    struct {
      uint8_t ep_num;
      uint8_t dir;
      XUD_Result_t result;
      uint8_t is_setup;
      uint32_t len;
    }xfer_complete;

    // FUNC_CALL
    struct {
      uint8_t cmd;
      uint8_t proxy_dir;
    }ep_command;
  };
} ep_proxy_event_t;


void ep_proxy_init(
    channel_t chan_ep0_out,
    channel_t chan_ep0_in,
    channel_t chan_ep1_out,
    channel_t chan_ep1_in,
    chanend_t chan_ep0_proxy,
    chanend_t chan_ep_hid_proxy,
    chanend_t c_ep_proxy_xfer_complete);

void ep_proxy_task(void *app_data);

void ep_proxy_start(unsigned priority);

static inline int endpoint_num(uint32_t endpoint_addr)
{
    return endpoint_addr & 0xF;
}

static inline int endpoint_dir(uint32_t endpoint_addr)
{
    return (endpoint_addr >> 7) & 1;
}