// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#define DEBUG_UNIT HID_TASK
#ifndef DEBUG_PRINT_ENABLE_HID_TASK
    #define DEBUG_PRINT_ENABLE_HID_TASK 0
#endif
#include "rtos_printf.h"

#include <stdint.h>

#include "tusb.h"
#include "FreeRTOS.h"
#include "usb_hid.h"

#include "task.h"
#include "usb_descriptors.h"
#include "hid_telephony_device.h"
#include <xcore/hwtimer.h>


#define NUM_TICKS_PER_MS    (XS1_TIMER_KHZ)

// This file contains the functions for implementing the HID Input endpoint functionality

// Get input report for this report_id
static inline hid_report_config_t* get_input_report(hid_report_config_t *input_reports, uint8_t report_id)
{
  for(uint32_t i=0; i<TOTAL_INPUT_REPORTS; i++)
  {
    if(input_reports[i].report_id == report_id)
    {
      return &input_reports[i];
    }
  }
  return NULL;
}

// Set bit in a report
static inline void set_report_bits(uint8_t *report, const hid_button_config_t *config)
{
  uint8_t byte_index = config->offset / 8;
  uint8_t offset = config->offset % 8;
  report[byte_index] = SET_BITS((report[byte_index]), (offset + config->size - 1), offset);
}

// Clear bits in a report
static inline void clear_report_bits(uint8_t *report, const hid_button_config_t *config)
{
  uint8_t byte_index = config->offset / 8;
  uint8_t offset = config->offset % 8;
  report[byte_index] = CLEAR_BITS((report[byte_index]), (offset + config->size - 1), offset);
}

static bool send_hid_report(hid_report_config_t *report, bool change_pending)
{
  uint8_t report_id = report->report_id;
  void *report_ptr = report->report;
  size_t report_size = report->report_size;
  uint32_t last_sent_report_ts = report->last_timestamp;
  int32_t idle_duration = get_idle_duration();

  if ( !tud_hid_ready() )
  {
    return false;
  }
  if(report_ptr != NULL)
  {
    if(idle_duration == IDLE_TIME_NOT_SET) // host hasn't issued set_idle. Always send report
    {
      return tud_hid_n_report(0, report_id, report_ptr, report_size);
    }
    else if(idle_duration == IDLE_TIME_INDEFINITE_DURATION) // idle duration set to indefinite. Only send when change pending
    {
      if(change_pending)
      {
        return tud_hid_n_report(0, report_id, report_ptr, report_size);
      }
    }
    else // Idle duration valid and non-zero. Send only if change pending or required time has elapsed
    {
      if(change_pending)
      {
        return tud_hid_n_report(0, report_id, report_ptr, report_size);
      }
      else
      {
        // if idle_duration time has passed since the last report, send one now
        uint32_t time_diff = get_reference_time() - last_sent_report_ts;
        if(time_diff >= (idle_duration * NUM_TICKS_PER_MS))
        {
          return tud_hid_n_report(0, report_id, report_ptr, report_size);
        }
      }
    }
  }
  return false;
}

static hid_report_config_t* send_hid_report_wrapper(hid_report_config_t *report, bool change_pending)
{
  bool sent = send_hid_report(report, change_pending);
  if(sent == true)
  {
    report->last_timestamp = get_reference_time();
  }
  // If send fails, mark this report for retry if it has a pending change, otherwise we skip to the next report in the cycle
  if((sent == false) && (change_pending == true))
  {
    return report;
  }
  return NULL;
}


void hid_task(void *args)
{
  // State variables
  bool osc_seq_in_progress = false; // Flag indicating if an OSC button report sequence is in progress
  hid_button_config_t config_in_progress = {0}; // OSC button config for which the report sequence is in progress

  hid_report_config_t *pending_report = NULL; // Pointer to a report that could not be sent in a previous call to send_hid_report()
  uint8_t cycle_report_index = 0;   // Report index when cycling through reports when there's no pending change
  bool state_ringing = false; // State of the ring LED

  xassert(args != NULL);
  hid_in_task_args_t *hid_task_args = args;

  uint32_t current_time = get_reference_time();
  for(int i=0; i<TOTAL_INPUT_REPORTS; i++)
  {
    hid_task_args->hid_input_report_config[i].last_timestamp = current_time;
  }

  output_state_notify_t output_notify = {0};
  while(1)
  {
    // Poll periodically
    vTaskDelay(pdMS_TO_TICKS(HID_IN_TASK_SCHEDULING_INTERVAL));

    // Step 1: Check if there's a pending report that couldn't be sent last time
    if(pending_report != NULL)
    {
      pending_report = send_hid_report_wrapper(pending_report, true);
      continue;
    }

    // Step 2: Check if there's a button sequence in progress
    if(osc_seq_in_progress)
    {
      const hid_button_config_t *config = &config_in_progress;

      hid_report_config_t *report_config = get_input_report(hid_task_args->hid_input_report_config, config->report_id);
      xassert(report_config != NULL);

      clear_report_bits(report_config->report, config); // Complete the sequence by clearing the button bit in the input report
      osc_seq_in_progress = false;

      pending_report = send_hid_report_wrapper(report_config, true);
      continue;
    }

    // Step 3: Check if there are any notifications from output reports
    rtos_osal_status_t ret = rtos_osal_queue_receive(hid_task_args->output_report_notify_queue, &output_notify, RTOS_OSAL_NO_WAIT);

    if(ret == RTOS_OSAL_SUCCESS)
    {
      if(output_notify.led_index == RING_LED)
      {
        // Update the ring state so we can decide if hookswitch button press translates to a Button7 button or Hookswitch button report
        state_ringing = output_notify.state;
      }

      // Check if we need to set something in an input report
      if(hid_task_args->hid_led_config[output_notify.led_index].trigger_hid_input_index != NO_HID_IN_TRIGGER)
      {
        uint8_t trigger_input_index = hid_task_args->hid_led_config[output_notify.led_index].trigger_hid_input_index;
        const hid_button_config_t *config = &hid_task_args->hid_button_config[trigger_input_index];

        hid_report_config_t *report_config = get_input_report(hid_task_args->hid_input_report_config, config->report_id);
        xassert(report_config != NULL);

        if(output_notify.state == 1) // Set
        {
          set_report_bits(report_config->report, config);
        }
        else // Clear
        {
          clear_report_bits(report_config->report, config);
        }
        pending_report = send_hid_report_wrapper(report_config, true);
        continue;
      }
    }

    // Step 4: Finally, check for button press notifications
    if(hid_task_args->button_press_queue != NULL)
    {
      button_press_info_t button_event;
      rtos_osal_status_t ret = rtos_osal_queue_receive(hid_task_args->button_press_queue, &button_event, RTOS_OSAL_NO_WAIT);

      if(ret == RTOS_OSAL_SUCCESS)
      {
        const hid_button_config_t *config = &hid_task_args->hid_button_config[button_event.index];

        hid_report_config_t *report_config = get_input_report(hid_task_args->hid_input_report_config, config->report_id);

        xassert(report_config != NULL);

        bool go_ahead = true;
        if(config->button_press_precondition != NO_BUTTON_PRESS_PRECONDITION) // Is there a pre-condition for this button showing as pressed in the input report?
        // example, hook-switch needs to be pressed before notifying mute button press
        {
          // Check if the precondition button is pressed
          const hid_button_config_t *pre_config = &hid_task_args->hid_button_config[config->button_press_precondition];

          hid_report_config_t *pre_report_config = get_input_report(hid_task_args->hid_input_report_config, pre_config->report_id);
          xassert(pre_report_config != NULL);

          uint8_t byte_index = pre_config->offset / 8;
          uint8_t offset = pre_config->offset % 8;
          if(!IS_SET((pre_report_config->report[byte_index]), (offset + pre_config->size - 1), offset))
          {
            go_ahead = false; // If the pre condition button is not set, ignore this button press
          }
        }

        if(go_ahead == true)
        {
          if(config->button_type == BUTTON_TYPE_OSC)
          {
            if(button_event.state == BUTTON_STATE_RELEASED) // For OSC button, send report only when button is pressed and released
            {
              memcpy(&config_in_progress, config, sizeof(hid_button_config_t));
              // If the hookswitch button is pressed, depending on whether a call is incoming or not (RING==1), either send a report with hookswitch set to 1 or send a report with button7 set to 1.
              // This is too custom to be handled generically through the hid_report_config_t structure.
              if(config->offset == BUTTON_HOOKSWITCH_OFFSET)  // Hookswitch pressed, but check the ringing state
              {
                if(state_ringing == true) // If ringing, override instead with Button7 press
                {
                  config_in_progress.offset = BUTTON_BUTTON7_OFFSET;
                }
              }
              set_report_bits(report_config->report, &config_in_progress);  // Set button bit to 1 in the report
              osc_seq_in_progress = true;
              pending_report = send_hid_report_wrapper(report_config, true);  // Send the first report of the OSC sequence
            }
          }
          else if(config->button_type == BUTTON_TYPE_RTC) // For re-trigger control, notify for both press and release
          {
            if(button_event.state == BUTTON_STATE_PRESSED)
            {
              set_report_bits(report_config->report, config);
            }
            else if (button_event.state == BUTTON_STATE_RELEASED)
            {
              clear_report_bits(report_config->report, config);
            }
            pending_report = send_hid_report_wrapper(report_config, true);
          }
        }
        continue;
      }
    }

    // If we've reached here and pending_report is also NULL, means we haven't sent any reports.
    // Cycle through the existing reports in case set_idle is not set to indefinite delay and we need to send non change pending reports.
    if(pending_report == NULL)
    {
      pending_report = send_hid_report_wrapper(&hid_task_args->hid_input_report_config[cycle_report_index], false);
      cycle_report_index += 1;
      if(cycle_report_index == TOTAL_INPUT_REPORTS)
      {
        cycle_report_index = 0;
      }

    }
  }
}
