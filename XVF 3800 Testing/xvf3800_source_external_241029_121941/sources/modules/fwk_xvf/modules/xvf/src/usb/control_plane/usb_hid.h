// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#ifndef _USB_HID_H
#define _USB_HID_H

#include <stdint.h>
#include "device_control.h"
#include "tusb.h"


#define SET_BITS(report, h, l) ((report) | (TU_GENMASK(h, l)))      /// Set bits[l : h+1] within a byte
#define CLEAR_BITS(report, h, l) ((report) & ~(TU_GENMASK(h, l)))   /// Clear bits[l : h+1] in a byte
#define IS_SET(report, h, l) ((report) & (TU_GENMASK(h, l)))        /// 1 if bits[l : h+1] within the byte are set

#define BUTTON_GPI_UNMAPPED (0xff)              /// No GPI pin mapped to the button
#define NO_BUTTON_PRESS_PRECONDITION (0xff)     /// No having another button pressed as a pre-condition for sending button press report for this button.
#define NO_HID_IN_TRIGGER   (0xff)              /// No HID IN report indicating a specific button needs to be sent when receiving an output report with a specific LED set to 1
#define LED_GPO_UNMAPPED  (0xff)                /// No GPO (port,pin) mapped for this LED
#define IDLE_TIME_NOT_SET (-1)                  /// Host has never set the Idle duration using the SetIdle command on EP0
#define IDLE_TIME_INDEFINITE_DURATION (0)         /// Idle time indicating HID IN endpoint to send report only when something changes

/// BUTTONS
/// @brief Indexes for referring to all the supported Buttons in all the HID input reports.
///        Used for indexing into the hid_button_config_t array
typedef enum
{
  HOOKSWITCH_BUTTON = 0,
  MUTE_BUTTON,
  FLASH_BUTTON,
  REDIAL_BUTTON,
  DIALPAD,
  VOLUME_UP_BUTTON,
  VOLUME_DOWN_BUTTON,
  TEAMS_BUTTON,
  TOTAL_HID_BUTTONS /// number of buttons supported over all reports
}e_all_buttons;

/// @brief Buttons sources. The EVK and the IO expander board
typedef enum
{
  GPI_SOURCE_EVK = 0,
  GPI_SOURCE_IO_EXP
}all_gpi_sources_t;

/// @brief Button indexes for the buttons on the EVK.
typedef enum
{
    EVK_BUTTON_INDEX = 0,
    TOTAL_EVK_BUTTONS
}all_evk_buttons_t;

/// @brief Button indexes for the buttons on the IO expander
typedef enum
{
    IO_EXP_MUTE_BUTTON_INDEX = 0,
    IO_EXP_VOL_UP_BUTTON_INDEX,
    IO_EXP_VOL_DN_BUTTON_INDEX,
    IO_EXP_ACTION_BUTTON_INDEX,
    TOTAL_IO_EXP_BUTTONS
}all_io_exp_buttons_t;

/// @brief Supported button usage types
typedef enum
{
  BUTTON_TYPE_OSC,  /// One shot control. Once the button is pressed and released, send input report with button set to 1, followed by input report with button set to 0
  BUTTON_TYPE_RTC,  /// Re-trigger control. When the button is pressed, send input report with button set to 1. When button is released, send input report with button set to 0
}button_usage_types_t;

/// @brief  Button states
typedef enum
{
  BUTTON_STATE_RELEASED,
  BUTTON_STATE_PRESSED
}button_state_t;

/// LEDS
/// @brief Indexes for referring to all the supported LEDs in all the HID output reports.
///        Used for indexing into the hid_led_config_t array
typedef enum
{
  OFFHOOK_LED = 0,
  MUTE_LED,
  RING_LED,
  HOLD_LED,
  TOTAL_HID_LEDS /// number of LEDs supported over all reports
}e_all_leds_t;

/// @brief LED modes for setting the EVK and IO Expander LEDS to, in response to the HID output reports
typedef enum
{
  LED_MODE_STEADY,
  LED_MODE_FAST_FLASH,
  LED_MODE_SLOW_FLASH,
  LED_MODE_OFF,
}e_led_mode_t;

/// @brief LED sources. The EVK and the IO expander board
typedef enum
{
  GPO_SOURCE_EVK = 0,
  GPO_SOURCE_IO_EXP
}all_gpo_sources_t;

/// @brief LEDs on the EVK board
typedef enum
{
  EVK_LED_GREEN,
  EVK_LED_RED,
  TOTAL_EVK_LEDS
}all_evk_leds_t;

/// @brief LEDs on the IO Expander board
typedef enum
{
    IO_EXP_PCAL6416A_LED, // Red LED on the IO expander
    IO_EXP_IS31FL3193_RGB_LED,  // IS31FL3193 RGB LED on the IO expander
    TOTAL_IO_EXP_LEDS
}all_io_exp_leds_t;


/// @brief Indexes for referring to all the supported HID Input reports. Used for indexing into the hid_report_config_t array
typedef enum
{
  INPUT_REPORT_MISC_BUTTONS = 0,
  INPUT_REPORT_VOLUME_BUTTONS,
  INPUT_REPORT_TEAMS_BUTTONS,
  TOTAL_INPUT_REPORTS   /// Total number of HID input reports supported by the device
}e_all_input_reports;



/// @brief Indexes for referring to all the supported HID Output reports. Used for indexing into the hid_report_config_t array
typedef enum
{
  OUTPUT_REPORT_LEDS = 0,
  TOTAL_OUTPUT_REPORTS  /// Total number of HID output reports supported by the device
}e_all_output_reports;

// All feature reports. TODO Pending.
typedef enum
{
  FEATURE_REPORT_ASP = 0,
  TOTAL_FEATURE_REPORTS /// Total number of HID feature reports supported by the device
}e_all_feature_reports;

/// @brief Data structure used when notifying the hid_task() of a LED state change as seen in an output report by the TUSB tud_hid_set_report_cb() callback function.
typedef struct
{
  uint8_t led_index;    /// Index of the LED for which the output report indicated a state change
  bool state;        /// Latest state of the LED (0 or 1)
}output_state_notify_t;

/// @brief  Data structure used when notifying a button press event. This is used for notification from io_config_servicer() -> hid_in_servicer()
///         and from hid_in_servicer -> hid_task()
typedef struct
{
    uint8_t gpi_source;         /// Source of the GPI pin (e_all_gpi_sources). Only relevant for the button press notification to hid_in_servicer
    uint8_t index;              /// GPI pin index (io_config_servicer() -> hid_in_servicer()) or button index (hid_in_servicer -> hid_task())
    uint8_t state;              /// Button state (button_state_t)
    uint32_t press_duration;    /// Button press duration.
}button_press_info_t;


/// @brief Button configuration structure. This contains everything the hid_task() needs to know about a button
///        when handling a button pressed notification from the hid_in_servicer()
typedef struct
{
  uint8_t               report_id;      /// ReportID to which the button belongs
  uint8_t               offset;         /// bit-offset within the report
  uint8_t               size;           /// number of bits within the report allocated for the button
  all_gpi_sources_t     gpi_source;     /// Source of the GPI Pin. GPI_SOURCE_EVK or GPI_SOURCE_IO_EXP
  uint8_t               gpi_pin_index;  /// GPI pin index that the button maps to (all_evk_buttons_t or all_io_exp_buttons_t). BUTTON_GPI_UNMAPPED if unmapped.
  button_usage_types_t  button_type;    /// Usage type. One shot control or re-trigger control
  uint8_t button_press_precondition;    /// Button that needs to be indicated as pressed in the input report
                                        /// as a pre condition for indicating this button as pressed in the input report.
                                        /// For example, the hook-switch button needs to be set in the input report as a pre-condition for indicating the mute button as pressed in the report.
}hid_button_config_t;

/// @brief LED configuration structure. This contains everything the tud_hid_set_report_cb() needs to know about an LED
///          when its state change is reported in an output report.
typedef struct
{
  uint8_t               report_id;      /// ReportID to which the LED belongs.
  uint8_t               offset;         /// bit-offset within the report. Note, LEDs are assumed to be always 1 bit in size
  all_gpo_sources_t     gpo_source;     /// Source of the GPO Pin. GPO_SOURCE_EVK or GPO_SOURCE_IO_EXP
  uint8_t               gpo_pin_index;  /// pin index of the GPO port (all_evk_leds_t or all_io_exp_leds_t) that the LED maps to. LED_GPO_UNMAPPED if unmapped
  bool                  notify_hid_task;   /// Flag indicating whether the hid_task() needs to be notified in the event of an output report indicating
                                            /// state change for this LED
  uint8_t               trigger_hid_input_index;  /// Index of the HID button for which a button state change is triggered by this LED state change.
                                    /// For example, the off-hook LED state change triggers an input report with the hook-switch button reflecting the current off-hook LED state.
  e_led_mode_t          led_mode;   /// Mode to configure the LED in
}hid_led_config_t;


/// @brief Report configuration structure. This contains all the information about a report
typedef struct
{
    uint8_t *report;            /// Pointer to the report buffer
    uint8_t report_size;        /// Report size in bytes
    uint8_t report_id;          /// ReportID
    uint32_t last_timestamp;    /// Reference timer timestamp when the report was last sent or received
}hid_report_config_t;


/// @brief Arguments sent while creating the hid_in_servicer() task
typedef struct
{
    device_control_t              *device_control_ctx;    /// device_control ctx handle on which to register as a servicer
    rtos_osal_queue_t             *button_press_queue;    /// RTOS Queue handle on which to notify button presses to the hid_task()
    const hid_button_config_t     *hid_button_config;     /// Array of button config structures
}hid_in_servicer_args_t;

/// @brief Arguments sent while creating the hid_task() task
typedef struct
{
    rtos_osal_queue_t             *button_press_queue;            /// RTOS Queue handle on which to receive button press notifications from the hid_task()
    rtos_osal_queue_t             *output_report_notify_queue;    /// RTOS Queue handle on which tud_hid_set_report_cb() notifies LED state change to hid_task()
    const hid_button_config_t     *hid_button_config;             /// Array of button config structures
    const hid_led_config_t        *hid_led_config;                /// Array of LED config structures
    hid_report_config_t           *hid_input_report_config;       /// Array of input report configuration structures
}hid_in_task_args_t;


/// HID initialisation functions

/// @brief  Initialise the HID buttons
/// @return Initialised HID button config array
hid_button_config_t* init_hid_button_config();

/// @brief  Initialise the HID LEDs
/// @return Initialised HID LED config array
hid_led_config_t* init_hid_led_config();

/// @brief  Initialise HID input reports
/// @return Initialised HID input report config array
hid_report_config_t* init_hid_input_report_config();

/// @brief  Initialise HID output reports
/// @return Initialsed HID output report config array
hid_report_config_t* init_hid_output_report_config();

/// @brief Initialise the HID input, output reports, buttons and LED config structures. Allocate RTOS message queues used for communicating
///         between HID tasks. Set up the hid_task and the hid_in_servicer args structures that are passed in as args when these tasks
///         are created
/// @param hid_in_servicer_args     Pointer to the hid_in_servicer_args_t handle that is allocated and intialised in this function
/// @param hid_task_args            Pointer to the hid_in_task_args_t handle that is allocated and initialised in this function
void hid_init(hid_in_servicer_args_t **hid_in_servicer_args, hid_in_task_args_t **hid_task_args);

/// Getters and setters

/// @brief Get the idle duration set by the SetIdle command in tud_hid_set_report_cb()
/// @return idle duration
int32_t get_idle_duration();

/// @brief Set the output report notification queue handle such that it's visible to tud_hid_set_report_cb()
/// @param output_report_notify_queue Handle to the output report notification queue
void set_output_report_notify_queue(rtos_osal_queue_t *output_report_notify_queue);

/// @brief  Set the LED config structure handle such that it's visible to tud_hid_set_report_cb()
/// @param hid_led_config Array of LED config structures for all the LEDs
void set_hid_led_config(const hid_led_config_t *hid_led_config);

/// @brief  Set the Output report config structure handle such that it's visible to tud_hid_set_report_cb()
/// @param  hid_output_report_config Array of report config structures for all output reports
void set_hid_output_report_config(hid_report_config_t *hid_output_report_config);


/// HID Tasks

/// @brief  HID Input Endpoint task.
/// This task is responsible for sending reports over the HID IN endpoint. The reports are updated based on the
/// button press notifications that it receives from the hid_in_servicer() and in response to output report notifications
/// that it receives from the tud_hid_set_report_cb() function.
/// @param  Pointer to the task arguments structure hid_in_task_args_t
void hid_task(void *arg);

/// @brief HID IN servicer task.
/// This is the servicer that handles button press notification commands from the
/// io_config_servicer. It registers on the device_control_gpio_ctx to receive commands from io_config_servicer,
/// parses the command and forwards the button press event notification to the hid_task on the button_press_queue
/// message queue.
/// @param args Pointer to the task argument structure button_press_queue
void hid_in_servicer(void *args);

#endif // _USB_HID_H
