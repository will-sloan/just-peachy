// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#define DEBUG_UNIT USB_HID
#ifndef DEBUG_PRINT_ENABLE_USB_HID
    #define DEBUG_PRINT_ENABLE_USB_HID 0
#endif
#include "rtos_printf.h"

#include <stdint.h>
#include <xcore/hwtimer.h>

#include "tusb.h"
#include "usb_hid.h"
#include "FreeRTOS.h"
#include "task.h"
#include "usb_descriptors.h"
#include "hid_telephony_device.h"
#include "servicer.h" // For button_press_info_t
#include "io_config_cmds.h"
#include "io_expander_cmds.h"
#include "io_expander_cmds_map.h"
#include "device_control_usb.h" // For device_control_usb_get_ctrl_ctx_cb()

// This file contains the callback functions for handling HID requests on EP0

// Variables available globally in this file.
static const hid_led_config_t *g_hid_led_config = NULL;
static hid_report_config_t *g_hid_output_report_config = NULL;
static rtos_osal_queue_t *g_output_report_notify_queue = NULL;
static int32_t g_set_idle_duration = IDLE_TIME_INDEFINITE_DURATION;

int32_t get_idle_duration()
{
  return g_set_idle_duration;
}

void set_output_report_notify_queue(rtos_osal_queue_t *output_report_notify_queue)
{
  g_output_report_notify_queue = output_report_notify_queue;
}

void set_hid_led_config(const hid_led_config_t *hid_led_config)
{
  g_hid_led_config = hid_led_config;
}

void set_hid_output_report_config(hid_report_config_t *hid_output_report_config)
{
  g_hid_output_report_config = hid_output_report_config;
}

static void set_idle_duration(int32_t idle_duration)
{
  g_set_idle_duration = idle_duration;
}

static control_ret_t send_internal_write_cmd(device_control_t *device_control_ctx, control_resid_t resid, control_cmd_t cmd, const uint8_t *payload, size_t payload_len)
{
    uint8_t tx_buf[1]; // For status
    size_t tx_len;
    device_control_request(device_control_ctx,
                                resid,
                                cmd,
                                payload_len);

    // Device control does not expect a constant payload, so cast it away.
    device_control_payload_transfer_bidir(device_control_ctx, (uint8_t *)payload, payload_len, tx_buf, &tx_len);
    return tx_buf[0]; // Status is returned in tx_buf[0];
}


static inline hid_report_config_t* get_output_report(hid_report_config_t *output_reports, uint8_t report_id)
{
  for(uint32_t i=0; i<TOTAL_OUTPUT_REPORTS; i++)
  {
    if(output_reports[i].report_id == report_id)
    {
      return &output_reports[i];
    }
  }
  return NULL;
}

static inline void send_led_command(uint8_t led_index, bool current_state) // Send LED command to the relevant servicer (GPO or IO Expander)
{
  if(g_hid_led_config[led_index].gpo_source == GPO_SOURCE_EVK)
  {
    if(g_hid_led_config[led_index].gpo_pin_index != LED_GPO_UNMAPPED) // If there's a GPO LED mapped to this LED
    {
      gpo_servicer_resid_internal_gpo_led_state_t payload[GPO_SERVICER_RESID_INTERNAL_GPO_LED_STATE_NUM_VALUES];
      payload[0] = g_hid_led_config[led_index].gpo_pin_index;
      payload[1] = (current_state == 1) ? g_hid_led_config[led_index].led_mode : LED_MODE_OFF;  // LED Flash mode
      send_internal_write_cmd(device_control_usb_get_ctrl_ctx_cb(), GPO_SERVICER_RESID, GPO_SERVICER_RESID_INTERNAL_GPO_LED_STATE, payload, GPO_SERVICER_RESID_INTERNAL_GPO_LED_STATE_NUM_VALUES); // Notify GPO servicer
    }
  }
  else if(g_hid_led_config[led_index].gpo_source == GPO_SOURCE_IO_EXP)
  {
    if(g_hid_led_config[led_index].gpo_pin_index != LED_GPO_UNMAPPED) // If there's a GPO LED mapped to this LED
    {
      io_expander_servicer_resid_internal_gpo_led_state_t payload[IO_EXPANDER_SERVICER_RESID_INTERNAL_GPO_LED_STATE_NUM_VALUES];
      payload[0] = g_hid_led_config[led_index].gpo_pin_index;
      payload[1] = (current_state == 1) ? g_hid_led_config[led_index].led_mode : LED_MODE_OFF;  // LED flash mode
      send_internal_write_cmd(device_control_usb_get_ctrl_ctx_cb(), IO_EXPANDER_SERVICER_RESID, IO_EXPANDER_SERVICER_RESID_INTERNAL_GPO_LED_STATE, payload, IO_EXPANDER_SERVICER_RESID_INTERNAL_GPO_LED_STATE_NUM_VALUES); // Notify IO Expander
    }
  }
}

static void handle_hid_output_report_bit_change(uint8_t report_id, uint8_t offset, bool current_state)
{
  if(g_hid_led_config == NULL)
  {
    return;
  }

  // Find from offset to e_all_leds LED index
  uint8_t led_index = TOTAL_HID_LEDS;
  for(uint8_t i=0; i<TOTAL_HID_LEDS; i++)
  {
    if((g_hid_led_config[i].report_id == report_id) && (g_hid_led_config[i].offset == offset))
    {
      led_index = i;
      break;
    }
  }
  xassert(led_index < TOTAL_HID_LEDS);

  // Send LED command to the relevant servicer (GPO or IO Expander)
  send_led_command(led_index, current_state);

  // Notify the HID task if needed
  if((g_hid_led_config[led_index].notify_hid_task == true) && (g_output_report_notify_queue != NULL))
  {
    output_state_notify_t output_notify = {led_index, current_state};
    rtos_osal_status_t ret = rtos_osal_queue_send(g_output_report_notify_queue, &output_notify, RTOS_OSAL_NO_WAIT);
    if(ret != RTOS_OSAL_SUCCESS)
    {
      rtos_printf("output_report_notify_queue FULL! Dropping the output report notification\n");
    }
  }
}

// TinyUSB callbacks - weakly declared in TUSB source

uint16_t tud_hid_get_report_cb(uint8_t itf, uint8_t report_id, hid_report_type_t report_type, uint8_t* buffer, uint16_t reqlen)
{
    // TODO not Implemented
    (void) itf;
    (void) report_id;
    (void) report_type;
    (void) buffer;
    (void) reqlen;

    // Feature report indicating Teams button short press event. Uncomment if testing Teams button press. Will be implemented properly when implementing feature reports
    /*memset(buffer, 0, reqlen);
    if(report_type == HID_REPORT_TYPE_FEATURE)
    {
      buffer[0] = 0x41;
      buffer[2] = 1;
      buffer[5] = 1;
      buffer[6] = 1;
    }*/

    return reqlen;
}

// Invoked when received SET_REPORT control request or
// received data on OUT endpoint ( Report ID = 0, Type = 0 )
void tud_hid_set_report_cb(uint8_t instance, uint8_t report_id, hid_report_type_t report_type, uint8_t const* buffer, uint16_t bufsize)
{
  (void) instance;

  if((report_type == HID_REPORT_TYPE_OUTPUT) && (g_hid_output_report_config != NULL))
  {
    hid_report_config_t *report_config = get_output_report(g_hid_output_report_config, report_id); // Get a copy of the previous output report with this reportID
    xassert(report_config != NULL);
    xassert(report_config->report_size == bufsize);

    for(uint32_t byte=0; byte<bufsize; byte++)
    {
      uint8_t changed_bits = (buffer[byte]) ^ (report_config->report[byte]); // Get the changed bits in this report when compared with the previous report
      for(uint8_t i=0; i<8; i++)  // Handle changed bits in the O/P report. Note that we assume that each LED is a single bit in the output report
      {
        if(IS_SET(changed_bits, i, i))
        {
          bool current_state = IS_SET((buffer[byte]), i, i);
          handle_hid_output_report_bit_change(report_id, (byte*8 + i), current_state);
        }
      }
    }
    // Update previous hid output report
    memcpy(report_config->report, buffer, bufsize);
  }
}


bool tud_hid_set_idle_cb(uint8_t instance, uint8_t idle_rate)
{
  // note: reportID wise idle rate setting is not supported in TinyUSB since this function only gets sent
  // the idle_rate (tu_u16_high(request->wValue)) and not the reportID.
  if(!idle_rate)
  {
    set_idle_duration(IDLE_TIME_INDEFINITE_DURATION); // Indefinite
  }
  else
  {

    set_idle_duration(tu_max32((idle_rate * 4), HID_IN_EP_POLLING_INTERVAL)); // cannot go below HID_IN_EP_POLLING_INTERVAL
  }
  return true;
}
