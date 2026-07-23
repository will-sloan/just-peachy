// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#define DEBUG_UNIT HID_INIT
#ifndef DEBUG_PRINT_ENABLE_HID_INIT
    #define DEBUG_PRINT_ENABLE_HID_INIT 0
#endif
#include "rtos_printf.h"

#include <stdint.h>
#include <stdbool.h>

#include "app_conf.h"
#include "servicer.h"
#include "tusb.h"
#include "usb_hid.h"
#include "usb_descriptors.h"
#include "hid_telephony_device.h"

/**
 * This file contains HID initialisation functions
*/


hid_button_config_t* init_hid_button_config()
{
  hid_button_config_t *hid_button_config = rtos_osal_malloc(TOTAL_HID_BUTTONS * sizeof(hid_button_config_t)); // Allocate the button configuration array
  // Initialise all the button config structures
#if (IO_EXPANDER_ENABLED)
  {
    hid_button_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = BUTTON_HOOKSWITCH_OFFSET, .size = 1, .gpi_source = GPI_SOURCE_EVK, .gpi_pin_index = EVK_BUTTON_INDEX, .button_type = BUTTON_TYPE_OSC, .button_press_precondition = NO_BUTTON_PRESS_PRECONDITION};
    hid_button_config[HOOKSWITCH_BUTTON] = config;
  }
  {
    hid_button_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = BUTTON_MUTE_OFFSET, .size = 1, .gpi_source = GPI_SOURCE_IO_EXP, .gpi_pin_index = IO_EXP_MUTE_BUTTON_INDEX, .button_type = BUTTON_TYPE_OSC, .button_press_precondition=HOOKSWITCH_BUTTON};
    hid_button_config[MUTE_BUTTON] = config;
  }
  {
    hid_button_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = BUTTON_FLASH_OFFSET, .size = 1, .gpi_source = GPI_SOURCE_IO_EXP, .gpi_pin_index = IO_EXP_ACTION_BUTTON_INDEX, .button_type = BUTTON_TYPE_OSC, .button_press_precondition = NO_BUTTON_PRESS_PRECONDITION};
    hid_button_config[FLASH_BUTTON] = config;
  }
  {
    hid_button_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = BUTTON_REDIAL_OFFSET, .size = 1, .gpi_source = BUTTON_GPI_UNMAPPED, .gpi_pin_index = BUTTON_GPI_UNMAPPED, .button_type = BUTTON_TYPE_OSC, .button_press_precondition = NO_BUTTON_PRESS_PRECONDITION};
    hid_button_config[REDIAL_BUTTON] = config;
  }
  {
    hid_button_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = BUTTON_DIALPAD_OFFSET, .size = 4, .gpi_source = BUTTON_GPI_UNMAPPED, .gpi_pin_index = BUTTON_GPI_UNMAPPED, .button_type = BUTTON_TYPE_OSC, .button_press_precondition = NO_BUTTON_PRESS_PRECONDITION};
    hid_button_config[DIALPAD] = config;
  }
  {
    hid_button_config_t config = {.report_id = REPORT_ID_VOLUME_BUTTONS, .offset = BUTTON_VOL_UP_OFFSET, .size = 1, .gpi_source = GPI_SOURCE_IO_EXP, .gpi_pin_index = IO_EXP_VOL_UP_BUTTON_INDEX, .button_type = BUTTON_TYPE_RTC, .button_press_precondition = NO_BUTTON_PRESS_PRECONDITION};
    hid_button_config[VOLUME_UP_BUTTON] = config;
  }
  {
    hid_button_config_t config = {.report_id = REPORT_ID_VOLUME_BUTTONS, .offset = BUTTON_VOL_DOWN_OFFSET, .size = 1, .gpi_source = GPI_SOURCE_IO_EXP, .gpi_pin_index = IO_EXP_VOL_DN_BUTTON_INDEX, .button_type = BUTTON_TYPE_RTC, .button_press_precondition = NO_BUTTON_PRESS_PRECONDITION};
    hid_button_config[VOLUME_DOWN_BUTTON] = config;
  }
  {
    hid_button_config_t config = {.report_id = REPORT_ID_TEAMS_BUTTON, .offset = BUTTON_TEAMS_OFFSET, .size = 1, .gpi_source = BUTTON_GPI_UNMAPPED, .gpi_pin_index = BUTTON_GPI_UNMAPPED, .button_type = BUTTON_TYPE_OSC, .button_press_precondition = NO_BUTTON_PRESS_PRECONDITION};
    hid_button_config[TEAMS_BUTTON] = config;
  }
#else
  {
    hid_button_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = BUTTON_HOOKSWITCH_OFFSET, .size = 1, .gpi_source = BUTTON_GPI_UNMAPPED, .gpi_pin_index = BUTTON_GPI_UNMAPPED, .button_type = BUTTON_TYPE_OSC, .button_press_precondition = NO_BUTTON_PRESS_PRECONDITION};
    hid_button_config[HOOKSWITCH_BUTTON] = config;
  }
  {
    hid_button_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = BUTTON_MUTE_OFFSET, .size = 1, .gpi_source = GPI_SOURCE_EVK, .gpi_pin_index = EVK_BUTTON_INDEX, .button_type = BUTTON_TYPE_OSC, .button_press_precondition=HOOKSWITCH_BUTTON};
    hid_button_config[MUTE_BUTTON] = config;
  }
  {
    hid_button_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = BUTTON_FLASH_OFFSET, .size = 1, .gpi_source = BUTTON_GPI_UNMAPPED, .gpi_pin_index = BUTTON_GPI_UNMAPPED, .button_type = BUTTON_TYPE_OSC, .button_press_precondition = NO_BUTTON_PRESS_PRECONDITION};
    hid_button_config[FLASH_BUTTON] = config;
  }
  {
    hid_button_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = BUTTON_REDIAL_OFFSET, .size = 1, .gpi_source = BUTTON_GPI_UNMAPPED, .gpi_pin_index = BUTTON_GPI_UNMAPPED, .button_type = BUTTON_TYPE_OSC, .button_press_precondition = NO_BUTTON_PRESS_PRECONDITION};
    hid_button_config[REDIAL_BUTTON] = config;
  }
  {
    hid_button_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = BUTTON_DIALPAD_OFFSET, .size = 4, .gpi_source = BUTTON_GPI_UNMAPPED, .gpi_pin_index = BUTTON_GPI_UNMAPPED, .button_type = BUTTON_TYPE_OSC, .button_press_precondition = NO_BUTTON_PRESS_PRECONDITION};
    hid_button_config[DIALPAD] = config;
  }
  {
    hid_button_config_t config = {.report_id = REPORT_ID_VOLUME_BUTTONS, .offset = BUTTON_VOL_UP_OFFSET, .size = 1, .gpi_source = BUTTON_GPI_UNMAPPED, .gpi_pin_index = BUTTON_GPI_UNMAPPED, .button_type = BUTTON_TYPE_RTC, .button_press_precondition = NO_BUTTON_PRESS_PRECONDITION};
    hid_button_config[VOLUME_UP_BUTTON] = config;
  }
  {
    hid_button_config_t config = {.report_id = REPORT_ID_VOLUME_BUTTONS, .offset = BUTTON_VOL_DOWN_OFFSET, .size = 1, .gpi_source = BUTTON_GPI_UNMAPPED, .gpi_pin_index = BUTTON_GPI_UNMAPPED, .button_type = BUTTON_TYPE_RTC, .button_press_precondition = NO_BUTTON_PRESS_PRECONDITION};
    hid_button_config[VOLUME_DOWN_BUTTON] = config;
  }
  {
    hid_button_config_t config = {.report_id = REPORT_ID_TEAMS_BUTTON, .offset = BUTTON_TEAMS_OFFSET, .size = 1, .gpi_source = BUTTON_GPI_UNMAPPED, .gpi_pin_index = BUTTON_GPI_UNMAPPED, .button_type = BUTTON_TYPE_OSC, .button_press_precondition = NO_BUTTON_PRESS_PRECONDITION};
    hid_button_config[TEAMS_BUTTON] = config;
  }
#endif
  return hid_button_config;
}





hid_led_config_t* init_hid_led_config()
{
  hid_led_config_t *hid_led_config = rtos_osal_malloc(TOTAL_HID_LEDS * sizeof(hid_led_config_t)); // Allocate the LED configuration array.

  // Initialise all the LED config structures
  /**
   * Note that it is possible to map multiple LEDS to the same GPO pin. For example, the RING and HOLD LEDs both mapped to the IO_EXP_IS31FL3193_RGB_LED in FAST and SLOW flash mode respectively in the hid_led_config below. However, this can lead to ambiguous reporting
   * of the LED states depending on the order in which LED events are notified in the output reports. For instance, if the RING and OFF-HOOK LEDs were mapped to the same GPO pin, when a call stops ringing and gets picked up, output reports are sent with RING=0 and OFF_HOOK=1.
   * However, these can come as one output report or 2 reports with RING=0 followed by OFF_HOOK=1 or OFF_HOOK=1 followed by RING=0. The report order is entirely host dependant and could potentially change everytime. The GPO setting logic simply looks in an output report and if
   * the LED state changed wrt the previous report, sets the GPO accordingly so we could end up with completely different GPO state depending on the output report order.
   *
   * TLDR; Don't map multiple LEDs on the same GPO. If doing so, map LEDS that don't change states close to each other, for example RING and HOLD, like done in the config below.
   *
   */
#if (IO_EXPANDER_ENABLED)
  {
    hid_led_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = LED_OFFHOOK_OFFSET, .gpo_source = GPO_SOURCE_EVK, .gpo_pin_index = EVK_LED_GREEN, .notify_hid_task = true, .trigger_hid_input_index = HOOKSWITCH_BUTTON, .led_mode=LED_MODE_STEADY};
    hid_led_config[OFFHOOK_LED] = config;
  }
  {
    hid_led_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = LED_MUTE_OFFSET, .gpo_source = GPO_SOURCE_IO_EXP, .gpo_pin_index = IO_EXP_PCAL6416A_LED, .notify_hid_task = false, .trigger_hid_input_index = NO_HID_IN_TRIGGER, .led_mode=LED_MODE_STEADY};
    hid_led_config[MUTE_LED] = config;
  }
  {
    hid_led_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = LED_RING_OFFSET, .gpo_source = GPO_SOURCE_IO_EXP, .gpo_pin_index = IO_EXP_IS31FL3193_RGB_LED, .notify_hid_task = true, .trigger_hid_input_index = NO_HID_IN_TRIGGER, .led_mode=LED_MODE_FAST_FLASH};
    hid_led_config[RING_LED] = config;
  }
  {
    hid_led_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = LED_HOLD_OFFSET, .gpo_source = GPO_SOURCE_IO_EXP, .gpo_pin_index = IO_EXP_IS31FL3193_RGB_LED, .notify_hid_task = false, .trigger_hid_input_index = NO_HID_IN_TRIGGER, .led_mode=LED_MODE_SLOW_FLASH};
    hid_led_config[HOLD_LED] = config;
  }
#else
  {
    hid_led_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = LED_OFFHOOK_OFFSET, .gpo_source = GPO_SOURCE_EVK, .gpo_pin_index = EVK_LED_GREEN, .notify_hid_task = true, .trigger_hid_input_index = HOOKSWITCH_BUTTON, .led_mode=LED_MODE_STEADY};
    hid_led_config[OFFHOOK_LED] = config;
  }
  {
    hid_led_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = LED_MUTE_OFFSET, .gpo_source = GPO_SOURCE_EVK, .gpo_pin_index = EVK_LED_RED, .notify_hid_task = false, .trigger_hid_input_index = NO_HID_IN_TRIGGER, .led_mode=LED_MODE_STEADY};
    hid_led_config[MUTE_LED] = config;
  }
  {
    hid_led_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = LED_RING_OFFSET, .gpo_source = LED_GPO_UNMAPPED, .gpo_pin_index = LED_GPO_UNMAPPED, .notify_hid_task = true, .trigger_hid_input_index = NO_HID_IN_TRIGGER, .led_mode=LED_MODE_FAST_FLASH};
    hid_led_config[RING_LED] = config;
  }
  {
    hid_led_config_t config = {.report_id = REPORT_ID_MISC_BUTTONS, .offset = LED_HOLD_OFFSET, .gpo_source = LED_GPO_UNMAPPED, .gpo_pin_index = LED_GPO_UNMAPPED, .notify_hid_task = false, .trigger_hid_input_index = NO_HID_IN_TRIGGER, .led_mode=LED_MODE_SLOW_FLASH};
    hid_led_config[HOLD_LED] = config;
  }
#endif
  return hid_led_config;
}


hid_report_config_t* init_hid_input_report_config()
{
  // Allocate memory for the Input reports
  hid_misc_buttons_report_t *misc_buttons_report = rtos_osal_malloc(sizeof(hid_misc_buttons_report_t));
  hid_vol_buttons_report_t *vol_buttons_report = rtos_osal_malloc(sizeof(hid_vol_buttons_report_t));
  hid_teams_buttons_report_t *teams_button_report = rtos_osal_malloc(sizeof(hid_teams_buttons_report_t));

  memset(misc_buttons_report, 0, sizeof(hid_misc_buttons_report_t));
  memset(vol_buttons_report, 0, sizeof(hid_vol_buttons_report_t));
  memset(teams_button_report, 0, sizeof(hid_teams_buttons_report_t));

  // Allocate the input report config array
  hid_report_config_t *hid_input_report_config = rtos_osal_malloc(TOTAL_INPUT_REPORTS * sizeof(hid_report_config_t));

  // Initialise the report config structures
  {
    hid_report_config_t config = {.report = (uint8_t*)misc_buttons_report, .report_size = sizeof(hid_misc_buttons_report_t), .report_id = REPORT_ID_MISC_BUTTONS, .last_timestamp = 0};
    hid_input_report_config[INPUT_REPORT_MISC_BUTTONS] = config;
  }

  {
    hid_report_config_t config = {.report = (uint8_t*)vol_buttons_report, .report_size = sizeof(hid_vol_buttons_report_t), .report_id = REPORT_ID_VOLUME_BUTTONS, .last_timestamp = 0};
    hid_input_report_config[INPUT_REPORT_VOLUME_BUTTONS] = config;
  }

  {
    hid_report_config_t config = {.report = (uint8_t*)teams_button_report, .report_size = sizeof(hid_teams_buttons_report_t), .report_id = REPORT_ID_TEAMS_BUTTON, .last_timestamp = 0};
    hid_input_report_config[INPUT_REPORT_TEAMS_BUTTONS] = config;
  }

  return hid_input_report_config;
}


hid_report_config_t* init_hid_output_report_config()
{
  // Allocate memory for the output reports
  hid_misc_leds_report_t *misc_leds_report = rtos_osal_malloc(sizeof(hid_misc_leds_report_t));

  memset(misc_leds_report, 0, sizeof(hid_misc_leds_report_t));

  // Allocate the output report config array
  hid_report_config_t *hid_output_report_config = rtos_osal_malloc(TOTAL_OUTPUT_REPORTS * sizeof(hid_report_config_t));

  // Initialise the report config structures
  {
    hid_report_config_t config = {.report = (uint8_t*)misc_leds_report, .report_size = sizeof(hid_misc_leds_report_t), .report_id = REPORT_ID_MISC_BUTTONS, .last_timestamp = 0};
    hid_output_report_config[OUTPUT_REPORT_LEDS] = config;
  }
  return hid_output_report_config;
}

// Initialise HID tasks arguments
void hid_init(hid_in_servicer_args_t **hid_in_servicer_args, hid_in_task_args_t **hid_task_args)
{
    hid_button_config_t *hid_button_config = init_hid_button_config();  // Initialise all button configs
    hid_led_config_t *hid_led_config = init_hid_led_config();   // Initialise all LED configs
    hid_report_config_t *hid_input_report_config = init_hid_input_report_config();  // Initialise all Input reports
    hid_report_config_t *hid_output_report_config = init_hid_output_report_config();    // Initialise all Output reports

    rtos_osal_queue_t *hid_in_queue = rtos_osal_malloc(sizeof(rtos_osal_queue_t));  // Create button press notification queue
    rtos_osal_queue_create(hid_in_queue, "hid_button_info_queue", 4, sizeof(button_press_info_t));

    rtos_osal_queue_t *output_report_notify_queue = rtos_osal_malloc(sizeof(rtos_osal_queue_t));    // Create output report notification queue
    rtos_osal_queue_create(output_report_notify_queue, "output_report_notify_q", 4, sizeof(output_state_notify_t));

    // Allocate and initialise the hid_in_servicer args structure
    *hid_in_servicer_args = rtos_osal_malloc(sizeof(hid_in_servicer_args_t));
    (*hid_in_servicer_args)->button_press_queue = hid_in_queue;
    (*hid_in_servicer_args)->device_control_ctx = device_control_gpio_ctx;
    (*hid_in_servicer_args)->hid_button_config = hid_button_config;

    // Allocate and initialise the hid_task args structure
    *hid_task_args = rtos_osal_malloc(sizeof(hid_in_task_args_t));
    (*hid_task_args)->button_press_queue = hid_in_queue;
    (*hid_task_args)->output_report_notify_queue = output_report_notify_queue;
    (*hid_task_args)->hid_button_config = hid_button_config;
    (*hid_task_args)->hid_led_config = hid_led_config;
    (*hid_task_args)->hid_input_report_config = hid_input_report_config;

    // Make these available to the tud_hid_set_report_cb() callback function that handles output reports received on EP0.
    // There's no other option but to share these in global memory since this is a TinyUSB callback function with a fixed API
    set_output_report_notify_queue(output_report_notify_queue);
    set_hid_led_config(hid_led_config);
    set_hid_output_report_config(hid_output_report_config);


}
