// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#ifndef _TUSB_HID_TELEPHONY_DEVICE_H_
#define _TUSB_HID_TELEPHONY_DEVICE_H_

#include "hid.h"

#ifdef __cplusplus
 extern "C" {
#endif

#define HID_IN_EP_bInterval               (7)   // poll hid in ep every 2**(7-1) * 125us = 8ms
#define HID_IN_EP_POLLING_INTERVAL        (((uint32_t)1 << (HID_IN_EP_bInterval-1)) / 8)
#define HID_IN_TASK_SCHEDULING_INTERVAL   (HID_IN_EP_POLLING_INTERVAL)  // same as polling interval to begin with

/// HID Usage Table - Table 11.1: LED Page
enum {
  HID_USAGE_LED_MUTE                                        = 0x09,
  HID_USAGE_LED_OFF_HOOK                                    = 0x17,
  HID_USAGE_LED_RING                                        = 0x18,
  HID_USAGE_LED_HOLD                                        = 0x20,
};

/// HID Usage Table - Table 12.1: Button Page
enum {
  HID_USAGE_BUTTON_7                                        = 0x07,
};

/// HID Usage Table - Table 14.1: Telephony Device Page
 enum {
  HID_USAGE_TELEPHONY_PHONE                                 = 0x01,
  HID_USAGE_TELEPHONY_HEADSET                               = 0x05,
  HID_USAGE_TELEPHONY_KEYPAD                                = 0x06,
  HID_USAGE_TELEPHONY_HOOKSWITCH                            = 0x20,
  HID_USAGE_TELEPHONY_FLASH                                 = 0x21,
  HID_USAGE_TELEPHONY_REDIAL                                = 0x24,
  HID_USAGE_TELEPHONY_PHONE_MUTE                            = 0x2f,
 };

/**
 * Input reports
 * ----------------------------Report ID 1. MISC_BUTTONS----Byte 0---------------------------
 * |      padding b4-b7     |  b3 redial |   b2 flash |   b1 phone mute  | b0 hookswitch    |
 * ------------------------------------------------------------------------------------------
 * ----------------------------Report ID 1. MISC_BUTTONS----Byte 1---------------------------
 * |      padding b4-b7     |           b0 - 3 dialpad button index                         |
 * ------------------------------------------------------------------------------------------
 *
 * ----------------------------Report ID 2. VOL_BUTTONS----Byte 0----------------------------
 * |      padding b2 - b7   |       b1 Vol decrement        |       b0 Vol increment        |
 * ------------------------------------------------------------------------------------------
 *
 * ----------------------------Report ID 0x9B. TEAMS_BUTTON----Byte 0------------------------
 * |      padding b2 - b7   |                     b0 Teams button                           |
 * ------------------------------------------------------------------------------------------
 *
 *  Output report
 * ----------------------------Report ID 1. LEDS ----Byte 0-----------------------------------
 * |      padding b4-b7     |  b3 hold LED |   b2 ring LED |   b1 mute LED | b0 offhook LED  |
 * -------------------------------------------------------------------------------------------
 *
 */
// Teams buttons report descriptor template
#define TUD_HID_REPORT_DESC_MISC_BUTTONS(...) \
  HID_USAGE_PAGE ( HID_USAGE_PAGE_TELEPHONY                  ) ,\
  HID_USAGE      ( HID_USAGE_TELEPHONY_PHONE                 ) ,\
  HID_COLLECTION ( HID_COLLECTION_APPLICATION                ) ,\
    /* Report ID if any */\
    __VA_ARGS__ \
    HID_USAGE       ( HID_USAGE_TELEPHONY_HOOKSWITCH         ) ,\
    HID_LOGICAL_MIN ( 0                                      ) ,\
    HID_LOGICAL_MAX ( 1                                      ) ,\
    HID_REPORT_COUNT( 1                                      ) ,\
    HID_REPORT_SIZE ( 1                                      ) ,\
    HID_INPUT       ( HID_DATA | HID_VARIABLE | HID_ABSOLUTE ) ,\
    HID_USAGE       ( HID_USAGE_TELEPHONY_PHONE_MUTE         ) ,\
    HID_INPUT       ( HID_DATA | HID_VARIABLE | HID_ABSOLUTE ) ,\
    HID_USAGE       ( HID_USAGE_TELEPHONY_FLASH              ) ,\
    HID_INPUT       ( HID_DATA | HID_VARIABLE | HID_ABSOLUTE ) ,\
    HID_USAGE       ( HID_USAGE_TELEPHONY_REDIAL             ) ,\
    HID_INPUT       ( HID_DATA | HID_VARIABLE | HID_ABSOLUTE ) ,\
    HID_USAGE_PAGE  ( HID_USAGE_PAGE_BUTTON                  ) ,\
    /* This button has been chosen to support the HOLD procedure in Teams */ \
    HID_USAGE       ( HID_USAGE_BUTTON_7                     ) ,\
    HID_INPUT       ( HID_DATA | HID_VARIABLE | HID_ABSOLUTE ) ,\
    /* 3 bit padding */ \
    HID_REPORT_COUNT( 1                                      ) ,\
    HID_REPORT_SIZE ( 3                                      ) ,\
    HID_INPUT       ( HID_CONSTANT                           ) ,\
    HID_USAGE_PAGE  ( HID_USAGE_PAGE_TELEPHONY               ) ,\
    HID_USAGE       ( HID_USAGE_TELEPHONY_KEYPAD             ) ,\
    HID_LOGICAL_MIN ( 1                                      ) ,\
    HID_LOGICAL_MAX ( 12                                     ) ,\
    HID_REPORT_COUNT( 1                                      ) ,\
    HID_REPORT_SIZE ( 4                                      ) ,\
    HID_USAGE_MIN   ( 0xB0                                   ) ,\
    HID_USAGE_MAX   ( 0xBB                                   ) ,\
    HID_INPUT       ( HID_DATA | HID_ARRAY | HID_ABSOLUTE    ) ,\
    HID_LOGICAL_MIN ( 0                                      ) ,\
    HID_LOGICAL_MAX ( 1                                      ) ,\
    /* 4 bit padding */ \
    HID_REPORT_COUNT( 1                                      ) ,\
    HID_REPORT_SIZE ( 4                                      ) ,\
    HID_INPUT       ( HID_CONSTANT                           ) ,\
    HID_USAGE_PAGE  ( HID_USAGE_PAGE_LED                     ) ,\
    HID_USAGE       ( HID_USAGE_LED_OFF_HOOK                 ) ,\
    HID_LOGICAL_MIN ( 0                                      ) ,\
    HID_LOGICAL_MAX ( 1                                      ) ,\
    HID_REPORT_COUNT( 1                                      ) ,\
    HID_REPORT_SIZE ( 1                                      ) ,\
    HID_OUTPUT      ( HID_DATA | HID_VARIABLE | HID_ABSOLUTE ) ,\
    HID_USAGE       ( HID_USAGE_LED_MUTE                     ) ,\
    HID_OUTPUT      ( HID_DATA | HID_VARIABLE | HID_ABSOLUTE ) ,\
    HID_USAGE       ( HID_USAGE_LED_RING                     ) ,\
    HID_OUTPUT      ( HID_DATA | HID_VARIABLE | HID_ABSOLUTE ) ,\
    HID_USAGE       ( HID_USAGE_LED_HOLD                     ) ,\
    HID_OUTPUT      ( HID_DATA | HID_VARIABLE | HID_ABSOLUTE ) ,\
    /* 4 bit padding */ \
    HID_REPORT_COUNT( 1                                      ) ,\
    HID_REPORT_SIZE ( 4                                      ) ,\
    HID_OUTPUT      ( HID_CONSTANT                           ) ,\
  HID_COLLECTION_END  \

#define TUD_HID_REPORT_DESC_VOLUME_BUTTONS(...) \
  HID_USAGE_PAGE ( HID_USAGE_PAGE_CONSUMER                   ), \
  HID_USAGE      ( HID_USAGE_CONSUMER_CONTROL                ) ,\
  HID_COLLECTION ( HID_COLLECTION_APPLICATION                ) ,\
    /* Report ID if any */                                      \
    __VA_ARGS__                                                 \
    HID_LOGICAL_MIN ( 0                                      ) ,\
    HID_LOGICAL_MAX ( 1                                      ) ,\
    HID_REPORT_COUNT( 1                                      ) ,\
    HID_REPORT_SIZE ( 1                                      ) ,\
    HID_USAGE       ( HID_USAGE_CONSUMER_VOLUME_INCREMENT   )  ,\
    HID_INPUT       ( HID_DATA | HID_VARIABLE | HID_ABSOLUTE ) ,\
    HID_USAGE       ( HID_USAGE_CONSUMER_VOLUME_DECREMENT    ) ,\
    HID_INPUT       ( HID_DATA | HID_VARIABLE | HID_ABSOLUTE ) ,\
    /* 6 bit padding */                                         \
    HID_REPORT_COUNT( 1                                      ) ,\
    HID_REPORT_SIZE ( 6                                      ) ,\
    HID_INPUT       ( HID_CONSTANT                           ) ,\
  HID_COLLECTION_END  \

#define TUD_HID_REPORT_DESC_TEAMS_BUTTON(...) \
  HID_USAGE_PAGE_N ( 0xFF99, 2                               ) ,\
  HID_USAGE      ( 0x01                                      ) ,\
  HID_COLLECTION ( HID_COLLECTION_APPLICATION                ) ,\
    /* Report ID if any */                                      \
    __VA_ARGS__                                                 \
    HID_LOGICAL_MIN ( 0                                      ) ,\
    HID_LOGICAL_MAX ( 1                                      ) ,\
    HID_REPORT_COUNT( 1                                      ) ,\
    HID_REPORT_SIZE ( 1                                      ) ,\
    HID_USAGE       ( 0x04                                   ) ,\
    HID_INPUT       ( HID_DATA | HID_VARIABLE | HID_RELATIVE ) ,\
    /* 7 bit padding */                                         \
    HID_REPORT_COUNT( 1                                      ) ,\
    HID_REPORT_SIZE ( 7                                      ) ,\
    HID_INPUT       ( HID_CONSTANT                           ) ,\
  HID_COLLECTION_END                                            \


#define TUD_HID_REPORT_DESC_TEAMS_ASP(...) \
  HID_USAGE_PAGE_N ( 0xFF99, 2                              ) ,\
  HID_USAGE        ( 0x03                                   ) ,\
  HID_COLLECTION   ( HID_COLLECTION_APPLICATION             ) ,\
    /* Report ID if any */                                     \
    __VA_ARGS__                                                \
    HID_LOGICAL_MIN   ( 0                                   ) ,\
    HID_LOGICAL_MAX_N ( 255, 2                              ) ,\
    HID_USAGE_MIN     ( 0x00                                ) ,\
    HID_USAGE_MAX     ( 0xff                                ) ,\
    HID_REPORT_COUNT_N( 63, 2                               ) ,\
    HID_REPORT_SIZE   ( 8                                   ) ,\
    HID_FEATURE       ( HID_DATA | HID_VARIABLE | HID_ABSOLUTE ) ,\
  HID_COLLECTION_END  \



/// Input reports
/// misc button report.
typedef struct TU_ATTR_PACKED
{
  uint8_t misc_buttons; /**< hookswitch, mute, flash, redial buttons */
  uint8_t dialpad_button_idx; /**< index of keypad button pressed. 0 = nothing pressed */
} hid_misc_buttons_report_t;

/// Vol button report
typedef struct TU_ATTR_PACKED
{
  uint8_t vol_buttons; /**< Volume increment and volume decrement buttons */
} hid_vol_buttons_report_t;

/// Teams button report
typedef struct TU_ATTR_PACKED
{
  uint8_t teams_button;
} hid_teams_buttons_report_t;

/// Misc button bit offsets within the hid_misc_buttons_report_t report
#define BUTTON_HOOKSWITCH_OFFSET  (0)
#define BUTTON_MUTE_OFFSET        (1)
#define BUTTON_FLASH_OFFSET       (2)
#define BUTTON_REDIAL_OFFSET      (3)
#define BUTTON_BUTTON7_OFFSET     (4) // Microsoft Teams Devices General Specification. 'Button Page (0x09) Usages Supported by Microsoft Teams'
#define BUTTON_DIALPAD_OFFSET     (8)

/// Volume button bit offsets within the hid_vol_buttons_report_t report
#define BUTTON_VOL_UP_OFFSET (0)
#define BUTTON_VOL_DOWN_OFFSET (1)

/// Teams Button bit offset within the hid_teams_buttons_report_t report
#define BUTTON_TEAMS_OFFSET (0)


/// Output reports
typedef struct TU_ATTR_PACKED
{
  uint8_t state; /**< offhook, mute, ring, hold buttons */
} hid_misc_leds_report_t;

/// LED offsets within the hid_misc_leds_report_t report
#define LED_OFFHOOK_OFFSET (0)
#define LED_MUTE_OFFSET (1)
#define LED_RING_OFFSET (2)
#define LED_HOLD_OFFSET (3)


#ifdef __cplusplus
 }
#endif

#endif
