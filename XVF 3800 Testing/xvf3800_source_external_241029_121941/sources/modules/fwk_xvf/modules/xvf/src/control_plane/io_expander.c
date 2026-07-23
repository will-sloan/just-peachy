// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#define DEBUG_UNIT IO_EXPANDER
#ifndef DEBUG_PRINT_ENABLE_IO_EXPANDER
    #define DEBUG_PRINT_ENABLE_IO_EXPANDER 0
#endif
#include "rtos_printf.h"
#include <stdint.h>
#include <string.h>

#include "FreeRTOS.h"

// bsp
#include "platform/driver_instances.h"

#if IO_EXPANDER_ENABLED

#include "servicer.h" // For device_control_gpio_ctx
#include "hid_task_cmds.h"
#include "usb_hid.h"    // For button_press_info_t
#include "io_expander.h"
#include "internal_commands.h"
#include "io_expander_cmds.h"
#include "io_expander_cmds_map.h"

/// @brief Various LED sources on the IO Expander board
typedef enum
{
    IO_EXP_GPO_PORT_PCAL6416A,  // RED LED
    IO_EXP_GPO_PORT_IS31FL3193  // RGB LED
}io_exp_gpo_port_t;

/// @brief IO expander button info for the button listed in all_io_exp_buttons_t
typedef struct
{
    uint8_t pin;    // GPI pin index for the button
    uint32_t _previous_event_time;  // Timestamp of the last button event
} io_exp_gpi_info_t;

/// @brief IO Expander LED info for the LEDs in all_io_exp_leds_t.
typedef struct {
    io_exp_gpo_port_t port; // LED type, red or RGB. The LED programming is completely different between the 2 and is handled as 2 separate cases in the io_exp_drive_leds() function
}io_exp_gpo_config_t;

/// @brief  LED state for the LEDs in all_io_exp_leds_t
typedef struct
{
    e_led_mode_t led_mode;  // current state of the LED
    uint32_t counter;   // current counter value, that tracks flashing etc.
}io_exp_gpo_led_state_t;

/// @brief IO Expander GPO state
typedef struct
{
    io_exp_gpo_led_state_t led_state[TOTAL_IO_EXP_LEDS];    /// LED state
    rtos_osal_mutex_t gpo_state_mutex;  /// Mutex that guards the led_state access by io_expander_gpo_servicer()->io_exp_write_cmd() and io_expander_task()->io_exp_drive_leds()
    uint8_t mute_led_val;   /// Current value written to the mute LED
    uint8_t rgb_led_shutdown_val;   /// Current value written to the IS31FL3193 Shutdown Register that controls the value driven on the RGB LED
}io_exp_gpo_state_t;

static const uint8_t addr_ioexp = 0x21;         /// I2C address of the IO Expander, PCAL6416A
static const uint8_t addr_IS31FL3193 = 0x68;    /// I2C address of the IS31FL3193 RGB LED driver on the IO Expander

/// GPI pin index for the various buttons on the IO Expander
#define IO_EXP_MUTE_BUTTON_PIN      0   // pin 0
#define IO_EXP_VOL_DN_BUTTON_PIN    1   // pin 1
#define IO_EXP_ACTION_BUTTON_PIN    2   // pin 2
#define IO_EXP_VOL_UP_BUTTON_PIN    3   // pin 3

#define BUTTON_MASK_MUTE        (1 << (IO_EXP_MUTE_BUTTON_PIN))
#define BUTTON_MASK_VOL_DN      (1 << (IO_EXP_VOL_DN_BUTTON_PIN))
#define BUTTON_MASK_ACTION      (1 << (IO_EXP_ACTION_BUTTON_PIN))
#define BUTTON_MASK_VOL_UP      (1 << (IO_EXP_VOL_UP_BUTTON_PIN))
#define BUTTON_MASK_ALL         (BUTTON_MASK_MUTE | BUTTON_MASK_VOL_DN | BUTTON_MASK_ACTION | BUTTON_MASK_VOL_UP)

#define IO_EXP_POLL_TIME_MS     (50)  // Wakeup interval for the IO Expander task

#define COUNTER_THRESHOLD_SLOW_FLASH (10)   /// Counter threshold controlling the slow flash speed. Toggle between ON OFF every COUNTER_THRESHOLD_SLOW_FLASH wakeups of the IO Expander task
#define COUNTER_THRESHOLD_FAST_FLASH (1)    /// Counter threshold controlling the fast flash speed. Toggle between ON OFF every COUNTER_THRESHOLD_FAST_FLASH wakeups of the IO Expander task

#define MUTE_LED_ON_MASK           (0x10)     /// Mute LED ON mask
#define RGB_LED_SHUTDOWN_MASK       (1)       /// RGB LED shutdown mask


/// @brief Handler for write commands sent to the IO_EXPANDER_SERVICER_RESID resource
/// Empty since there are no read commands supported by the IO_EXPANDER_SERVICER_RESID resource
DEVICE_CONTROL_CALLBACK_ATTR
static control_ret_t io_exp_read_cmd(control_resid_t resid, control_cmd_t cmd, uint8_t *payload, size_t payload_len, void *app_data)
{
    return CONTROL_SUCCESS;
}

/// @brief Handler for write commands sent to the IO_EXPANDER_SERVICER_RESID resource
/// @param resid Resource ID
/// @param cmd Command ID
/// @param payload      pointer to the payload buffer
/// @param payload_len  payload length in bytes
/// @param app_data     pointer to application specific data
/// @return
DEVICE_CONTROL_CALLBACK_ATTR
static control_ret_t io_exp_write_cmd(control_resid_t resid, control_cmd_t cmd, const uint8_t *payload, size_t payload_len, void *app_data)
{
    io_exp_gpo_state_t *gpo_state = app_data;
    if(cmd == IO_EXPANDER_SERVICER_RESID_INTERNAL_GPO_LED_STATE)
    {
        uint8_t led_index = payload[0];
        e_led_mode_t mode = payload[1];

        // Protect with mutex since accessed from io_expander_task
        rtos_osal_mutex_get(&gpo_state->gpo_state_mutex, RTOS_OSAL_WAIT_FOREVER);
        gpo_state->led_state[led_index].led_mode = mode;
        gpo_state->led_state[led_index].counter = 0;
        rtos_osal_mutex_put(&gpo_state->gpo_state_mutex);
    }
    return CONTROL_SUCCESS;
}

/// @brief IO Expander GPO Servicer task. Receives GPO commands from tud_hid_set_report_cb() -> handle_hid_output_report_bit_change() -> send_led_command()
///        over the device_control_usb_ctx
/// @param args
static void io_expander_gpo_servicer(void *args)
{
    xassert(args != NULL);
    io_exp_gpo_state_t *gpo_state = args;

    control_ret_t dc_ret;
    device_control_servicer_t servicer_ctx;
    // Register to receive commands on the device_control_usb_ctx
    control_resid_t resources[1] = {IO_EXPANDER_SERVICER_RESID};
    dc_ret = device_control_servicer_register(&servicer_ctx,
                                        device_control_ctxs,
                                        APP_CONTROL_TRANSPORT_COUNT,
                                        resources, 1);

    for(;;)
    {
        device_control_servicer_cmd_recv(&servicer_ctx, io_exp_read_cmd, io_exp_write_cmd, gpo_state, RTOS_OSAL_WAIT_FOREVER);
    }

}

/// @brief Initialise GPO on the IO Expander
/// @param state Pointer to the GPO state structure
/// @param config  Pointer to the GPO config structure
/// @param i2c_master_ctx RTOS I2C master handle
static void init_io_exp_gpo(io_exp_gpo_state_t *state, io_exp_gpo_config_t *config, rtos_i2c_master_t * i2c_master_ctx)
{
    // Initialise GPO config
    config[IO_EXP_PCAL6416A_LED].port = IO_EXP_GPO_PORT_PCAL6416A;
    config[IO_EXP_IS31FL3193_RGB_LED].port = IO_EXP_GPO_PORT_IS31FL3193;

    // Initialise GPO state
    state->mute_led_val = MUTE_LED_ON_MASK;
    state->rgb_led_shutdown_val = RGB_LED_SHUTDOWN_MASK;
    for(int i=0; i<TOTAL_IO_EXP_LEDS; i++)
    {
        state->led_state[i].led_mode = LED_MODE_OFF;
        state->led_state[i].counter = 0;
    }
    i2c_regop_res_t res = I2C_REGOP_SUCCESS;

    res |= rtos_i2c_master_reg_write(i2c_master_ctx, addr_ioexp, 0x2, 0); // Turn off mute LED

    // Initialise RGB LED and turn it off by default
    res |= rtos_i2c_master_reg_write(i2c_master_ctx, addr_IS31FL3193, 0x03, 0x10); // Current setting to 5mA
    res |= rtos_i2c_master_reg_write(i2c_master_ctx, addr_IS31FL3193, 0x00, (0x2|state->rgb_led_shutdown_val));  // Start in a shutdown state
    // Set colour to something I like at a bearable brightness level. Note that setting the LED colour as part of the INTERNAL_GPO_LED_STATE command is not supported
    // since the rest of the LEDs don't support setting this.
    res |= rtos_i2c_master_reg_write(i2c_master_ctx, addr_IS31FL3193, 0x4, 00);
    res |= rtos_i2c_master_reg_write(i2c_master_ctx, addr_IS31FL3193, 0x5, 10);
    res |= rtos_i2c_master_reg_write(i2c_master_ctx, addr_IS31FL3193, 0x6, 10);
    res |= rtos_i2c_master_reg_write(i2c_master_ctx, addr_IS31FL3193, 0x7, 0x0);

    if (res != I2C_REGOP_SUCCESS) {
        rtos_printf("Err writing to I2C...\n");
        xassert(0);
    }

    rtos_osal_mutex_create(&state->gpo_state_mutex, "gpo state guard mutex", RTOS_OSAL_NOT_RECURSIVE);
}

/// @brief This function drives the LEDs on the IO expander board, based on the LED state in gpo_state->led_state.
///        The gpo_state->led_state is updated in io_exp_write_cmd() based on GPO commands received from tud_hid_set_report_cb() -> handle_hid_output_report_bit_change() -> send_led_command()
/// @param gpo_state Pointer to the GPO state structure
/// @param gpo_config  Pointer to the GPO config structure
/// @param i2c_master_ctx RTOS I2C master handle
static void io_exp_drive_leds(io_exp_gpo_state_t *gpo_state, io_exp_gpo_config_t *gpo_config, rtos_i2c_master_t * i2c_master_ctx)
{
    i2c_regop_res_t res = I2C_REGOP_SUCCESS;
    // Update gpo_state under the mutex
    rtos_osal_mutex_get(&gpo_state->gpo_state_mutex, RTOS_OSAL_WAIT_FOREVER);
    for(int i=0; i<TOTAL_IO_EXP_LEDS; i++)
    {
        io_exp_gpo_port_t led_port = gpo_config[i].port;
        if(led_port == IO_EXP_GPO_PORT_PCAL6416A)   // Red LED on the IO Exp
        {
            if(gpo_state->led_state[i].led_mode == LED_MODE_OFF)
            {
                gpo_state->mute_led_val = 0;
            }
            else if(gpo_state->led_state[i].led_mode == LED_MODE_STEADY)
            {
                gpo_state->mute_led_val = MUTE_LED_ON_MASK;
            }
            else if((gpo_state->led_state[i].led_mode == LED_MODE_FAST_FLASH) || (gpo_state->led_state[i].led_mode == LED_MODE_SLOW_FLASH))
            {
                uint32_t counter_threshold = (gpo_state->led_state[i].led_mode == LED_MODE_FAST_FLASH) ? COUNTER_THRESHOLD_FAST_FLASH : COUNTER_THRESHOLD_SLOW_FLASH;
                gpo_state->led_state[i].counter += 1;
                if(gpo_state->led_state[i].counter > counter_threshold) // Toggle LED state every counter_threshold calls to this function
                {
                    gpo_state->mute_led_val ^= MUTE_LED_ON_MASK;
                    gpo_state->led_state[i].counter = 0;
                }
            }
            res |= rtos_i2c_master_reg_write(i2c_master_ctx, addr_ioexp, 0x2, gpo_state->mute_led_val); // Write to Mute LED register
        }
        else if(led_port == IO_EXP_GPO_PORT_IS31FL3193) // RGB LED
        {
            // Setting colour for the RGB LED is not supported.
            if(gpo_state->led_state[i].led_mode == LED_MODE_OFF)
            {
                gpo_state->rgb_led_shutdown_val = RGB_LED_SHUTDOWN_MASK; // Always shutdown
            }
            else if(gpo_state->led_state[i].led_mode == LED_MODE_STEADY)
            {
                gpo_state->rgb_led_shutdown_val = 0;    // Never shutdown
            }
            else if((gpo_state->led_state[i].led_mode == LED_MODE_FAST_FLASH) || (gpo_state->led_state[i].led_mode == LED_MODE_SLOW_FLASH))
            {
                uint32_t counter_threshold = (gpo_state->led_state[i].led_mode == LED_MODE_FAST_FLASH) ? COUNTER_THRESHOLD_FAST_FLASH : COUNTER_THRESHOLD_SLOW_FLASH;

                gpo_state->led_state[i].counter += 1;
                if(gpo_state->led_state[i].counter > counter_threshold)
                {
                    gpo_state->rgb_led_shutdown_val ^= RGB_LED_SHUTDOWN_MASK;   // Toggle shutdown every counter_threshold calls of this function
                    gpo_state->led_state[i].counter = 0;
                }
            }
            res |= rtos_i2c_master_reg_write(i2c_master_ctx, addr_IS31FL3193, 0x00, (0x20|gpo_state->rgb_led_shutdown_val));    // Write to the shutdown register
        }
        if (res != I2C_REGOP_SUCCESS) {
            rtos_printf("Err writing to I2C...\n");
            xassert(0);
        }
    }
    rtos_osal_mutex_put(&gpo_state->gpo_state_mutex);
}

void io_expander_task(void *args) {
    rtos_printf("io_expander_task..\n");

    xassert(args != NULL);
    device_control_t *device_control_ctx = ((io_expander_task_args_t*)args)->device_control_ctx; // Device control context on which to notify HID Servicer of button presses
    rtos_osal_mutex_t *mutex = ((io_expander_task_args_t*)args)->mutex; // Mutex guarding the device control context access

    io_exp_gpo_config_t io_exp_gpo_config[TOTAL_IO_EXP_LEDS];
    io_exp_gpo_state_t io_exp_gpo_state;

    rtos_i2c_master_t * i2c_master_ctx = get_i2c_master_ctx();

    i2c_regop_res_t res = I2C_REGOP_SUCCESS;
    res = rtos_i2c_master_reg_write(i2c_master_ctx, addr_ioexp, 0x2, 0x00); // drive mute led and dac_rst low
    res |= rtos_i2c_master_reg_write(i2c_master_ctx, addr_ioexp, 0x6, ~(int8_t)0b10010000); // all input except mic_off and dac_rst
    res |= rtos_i2c_master_reg_write(i2c_master_ctx, addr_ioexp, 0x7, ~0x00); // all input
    res |= rtos_i2c_master_reg_write(i2c_master_ctx, addr_ioexp, 0x44, 0x0f); // Latching on bits 0..3
    res |= rtos_i2c_master_reg_write(i2c_master_ctx, addr_ioexp, 0x45, 0x00); // No latching

    if (res != I2C_REGOP_SUCCESS) {
        rtos_printf("Err writing to I2C...\n");
        xassert(0);
    }

    init_io_exp_gpo(&io_exp_gpo_state, io_exp_gpo_config, i2c_master_ctx);

    io_exp_gpi_info_t io_exp_gpi_info[TOTAL_IO_EXP_BUTTONS] = {
        {.pin =  IO_EXP_MUTE_BUTTON_PIN, ._previous_event_time = 0},    // IO_EXP_MUTE_BUTTON_INDEX
        {.pin =  IO_EXP_VOL_UP_BUTTON_PIN, ._previous_event_time = 0},  // IO_EXP_VOL_UP_BUTTON_INDEX
        {.pin =  IO_EXP_VOL_DN_BUTTON_PIN, ._previous_event_time = 0},  // IO_EXP_VOL_DN_BUTTON_INDEX
        {.pin =  IO_EXP_ACTION_BUTTON_PIN, ._previous_event_time = 0},  // IO_EXP_ACTION_BUTTON_INDEX
    };


    // Create task for receiving internal GPO commands from tud_hid_set_report_cb()
    xTaskCreate((TaskFunction_t) io_expander_gpo_servicer,
                        "io_expander_gpo_task",
                        portTASK_STACK_DEPTH(io_expander_gpo_servicer),
                        &io_exp_gpo_state,
                        appconfTEST_TASK_PRIORITY,
                        NULL);

    uint8_t prev_button_status = BUTTON_MASK_ALL;


    for(;;){
        // Do button things
        uint8_t button_status = 0;
        res |= rtos_i2c_master_reg_read(i2c_master_ctx, addr_ioexp, 0, &button_status) & BUTTON_MASK_ALL; // read i/p port
        if (res != I2C_REGOP_SUCCESS) {
            rtos_printf("Err writing to I2C...\n");
            xassert(0);
        }

        uint8_t changed_bits = (button_status ^ prev_button_status);    // Find buttons with changed state

        if(changed_bits)
        {
            uint32_t now = get_reference_time();

            for(int i=0; i<TOTAL_IO_EXP_BUTTONS; i++)
            {
                uint8_t mask = 1 << io_exp_gpi_info[i].pin;

                if(changed_bits & mask)
                {
                    uint8_t current_value = button_status & mask;
                    uint8_t prev_value = prev_button_status & mask;

                    button_press_info_t button_info;
                    button_info.gpi_source = GPI_SOURCE_IO_EXP;
                    button_info.index = i;
                    button_info.press_duration = 0;
                    if(current_value < prev_value) // Buttons on the IO expander are active low
                    {
                        button_info.state = BUTTON_STATE_PRESSED;
                    }
                    else
                    {
                        button_info.state = BUTTON_STATE_RELEASED;
                        button_info.press_duration = now - io_exp_gpi_info[i]._previous_event_time;
                    }
                    // Notify the HID servicer of the button event
                    control_ret_t ret = send_write_cmd_to_servicer(device_control_ctx, HID_TASK_RESID, HID_TASK_RESID_INTERNAL_BUTTON_PRESS, (const uint8_t*)&button_info, sizeof(button_press_info_t), mutex);
                    xassert (ret == CONTROL_SUCCESS);

                    if(current_value > prev_value)
                    {
                        rtos_printf("Button index 0x%x pressed. press_duration = %u\n", i, button_info.press_duration);
                    }

                    io_exp_gpi_info[i]._previous_event_time = now;
                }
            }
        }
        prev_button_status = button_status;

        // Do LED things
        io_exp_drive_leds(&io_exp_gpo_state, io_exp_gpo_config, i2c_master_ctx);

        vTaskDelay(pdMS_TO_TICKS(IO_EXP_POLL_TIME_MS));
    }
}
#endif
