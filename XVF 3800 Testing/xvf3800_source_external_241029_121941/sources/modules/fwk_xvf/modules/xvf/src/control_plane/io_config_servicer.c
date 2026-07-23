// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#define DEBUG_UNIT IO_CONFIG_SERVICER_TASK
#ifndef DEBUG_PRINT_ENABLE_IO_CONFIG_SERVICER_TASK
    #define DEBUG_PRINT_ENABLE_IO_CONFIG_SERVICER_TASK 0
#endif
#include "debug_print.h"

#include <stdio.h>
#include <stdbool.h>
#include <platform.h>
#include <assert.h>
#include "platform/platform_conf.h"
#include "platform/driver_instances.h"
#include "device_control_i2c.h"
#include "device_control_spi.h"
#include "servicer.h"
#include "control_init.h"
#include "io_config_cmds.h"
#include "user_config.h"
#include "io_config_servicer_defaults.h"
#include "device_enums.h"
#include "internal_commands.h"
#if (appconfUSB_CTRL_ENABLED && HID_CONTROL)
    #include "hid_task_cmds.h"
    #include "usb_hid.h"    // For button_press_info_t
#endif
#if (IO_EXPANDER_ENABLED)
#include "io_expander.h"
#endif

// Sets nth bit of A to x
#define SET_BIT(A, x, n) (A = (A & ~(0x1 << n)) | (x << n))

typedef struct
{
    uint32_t port;
    uint8_t pin;
    uint32_t _previous_event_time;
} gpi_pin_id_t;

typedef struct
{
    uint32_t port;
    rtos_gpio_port_id_t _rtos_port_id;
    uint32_t _previous_value;
} gpi_port_id_t;

// Declares the pins used for GPI.
// Up to 32 GPI pins may be declared.
// Indices are assigned 0 -> 31 in order of declaration.
// Ensure that the number of pins declared here is equal to GPIO_NUM_INPUT_PINS.
// Field _previous_event_time is set internally and should not be set here.
static gpi_pin_id_t gpi_pins[GPIO_NUM_INPUT_PINS] = {
    {.port = PORT_GPI_0, .pin = 3}, // Mute button. Only bit 3 is pinned out on the pkg
    {.port = PORT_GPI_1, .pin = 0}  // Teams button
};

// Because of the way RTOS GPIO events are handled (per port), we also need a set of structures holding one (and only one) reference to each of the ports in use.
// Fields _rtos_port_id and _previous_value are set internally and should not be set here.
static gpi_port_id_t gpi_ports[GPIO_NUM_INPUT_PORTS] = {
    {.port = PORT_GPI_0},
    {.port = PORT_GPI_1}
};

static gpi_config_t gpi_cfg;
static rtos_osal_mutex_t gpi_mutex; // Guards gpi_cfg, which is accessed by two different tasks

static rtos_osal_mutex_t device_control_mutex; // Guards accessing device_control_gpio_ctx while sending commands from IO config servicer to GPO or the HID task

// Defines shared memory between the button ISR and the deferred callback routine
static uint32_t previous_values;
static uint32_t current_values;


/**
 * @brief Send a command to the GPO task to write to a GPO pin
 *
 * This function sends a command to write to a GPO pin over the device_control_gpio_ctx.
 *
 * @param device_control_ctx    Pointer to the device_control context that the command will be sent over.
 * @param pin_index             GPO pin index to write to
 * @param state             state that the GPO pin needs to be configured to. 1 ON, 0 OFF.
 */
control_ret_t write_gpo_pin(device_control_t *device_control_ctx, uint32_t pin_index, uint32_t state /*1 ON, 0 OFF*/)
{
    // Try sending a command to the GPO task now!
    #define XFER_RX_SIZE (12) // Maximum we need right now is 8+3 bytes for the GPO_SERVICER_RESID_GPO_PORT_PIN_INDEX command
    uint8_t rx_buf[XFER_RX_SIZE];
    control_ret_t ret;
    size_t payload_len = 3*sizeof(uint8_t);

    uint8_t port_pin_state[3] = {0, pin_index, state};
    memcpy(rx_buf, port_pin_state, payload_len); // Payload
    ret = send_write_cmd_to_servicer(device_control_ctx, GPO_SERVICER_RESID, GPO_SERVICER_RESID_GPO_PIN_VAL, rx_buf, payload_len, &device_control_mutex);
    if(ret != CONTROL_SUCCESS)
    {
        debug_printf("GPO_SERVICER_RESID_GPO_PIN_VAL command when sent from GPI servicer returns error %d\n", ret);
    }
    return ret;
}

uint32_t flag_signal_start_control = 0;
control_ret_t signal_io_start(device_control_t *device_control_ctx)
{
    uint8_t rx_buf[sizeof(int32_t)];
    control_ret_t ret;
    size_t payload_len = 1*sizeof(uint32_t); // Payload length
    uint32_t start = 1;
    memcpy(rx_buf, &start, payload_len); // Payload
    ret = send_write_cmd_to_servicer(device_control_ctx, GPO_SERVICER_RESID, GPO_SERVICER_RESID_INTERNAL_GPO_START_CONTROL_TASK, rx_buf, payload_len, &device_control_mutex);
    if(ret != CONTROL_SUCCESS)
    {
        debug_printf("GPO_SERVICER_RESID_GPO_PIN_VAL command when sent from GPI servicer returns error %d\n", ret);
    }
    flag_signal_start_control = 1; // Its safe to sa
    return ret;
}

RTOS_GPIO_ISR_CALLBACK_ATTR
static void button_callback(rtos_gpio_t *ctx, void *app_data, rtos_gpio_port_id_t port_id, uint32_t value)
{
    TaskHandle_t gpiTask = app_data;
    BaseType_t xYieldRequired = pdFALSE;

    uint32_t xcore_port_id = 0;
    uint32_t previous_value = 0;

    bool error = true;
    for (int i = 0; i < GPIO_NUM_INPUT_PORTS; i++)
    {
        if (port_id == gpi_ports[i]._rtos_port_id)
        {
            previous_value = gpi_ports[i]._previous_value;
            xcore_port_id = gpi_ports[i].port;
            gpi_ports[i]._previous_value = value;

            error = false;
            break;
        }
    }
    xassert_not(error); // If this asserts, button_callback recieved a port_id that isn't listed in gpi_ports.

    // We know that one (and only one) pin has changed since the last time we saw this port on an interrupt (unless two events have occured within (10ns+interrupt time) of eachother). Identify which one.
    uint32_t changed_idx = previous_value ^ value;
    uint8_t xcore_pin_number = 32 - clz(changed_idx) - 1;
    uint32_t mask = 1 << xcore_pin_number;

    uint8_t pin_index;
    uint32_t pin_previous = (previous_value & mask) ? 1 : 0;
    uint32_t pin_current = (value & mask) ? 1 : 0;

    error = true;

    // gpi_pins also accessed by deferred callback, but only the ._previous_event_time member, so no mutex needed.

    for (pin_index = 0; pin_index < GPIO_NUM_INPUT_PINS; pin_index++)
    {
        if (xcore_port_id == gpi_pins[pin_index].port &&
            xcore_pin_number == gpi_pins[pin_index].pin)
        {
            error = false;
            break;
        }
    }
    xassert_not(error); // If this asserts, the pin that we recieved an event on isn't listed in gpi_pins.

    // We know the pin index, the current value, and the previous value.
    debug_printf("Interrupt %d: was %d, now %d\n", pin_index, pin_previous, pin_current);

    /*
     * Once pin and changed value has been identified, we post to mailbox 0 that the event has occured, which triggers the deferred callback
     * 0 also currently records which pin the event occured on, although that information is not currently used by the deferred callback.
     */

    SET_BIT(previous_values, pin_previous, pin_index);
    SET_BIT(current_values, pin_current, pin_index);

    xTaskNotifyFromISR(gpiTask, 1 << pin_index, eSetBits, &xYieldRequired);

    portYIELD_FROM_ISR(xYieldRequired);
}

static void process_gpi_event(void * args)
{
    xassert(args != NULL);
    device_control_t *device_control_ctx = NULL;    // device_control ctx on which to inform hid_task about button presses
    device_control_ctx = args;

    for(;;)
    {
        uint32_t local_previous_values;
        uint32_t local_current_values;

        xTaskNotifyWait(0, ~0, NULL, portMAX_DELAY);
        taskENTER_CRITICAL();
        // Atomically read the previous_ and current_values set by the ISR.
        // Past this point, even if this task is interrupted, the values it will use on return from interrupt will be the values read here.
        local_previous_values = previous_values;
        local_current_values = current_values;
        debug_printf("%d\n%d\n", local_previous_values, local_current_values);
        taskEXIT_CRITICAL();

        for (uint8_t pin_index = 0; pin_index < GPIO_NUM_INPUT_PINS; pin_index++)
        {
            const uint32_t mask = 1 << pin_index;
            const uint8_t current_value = (mask & local_current_values) ? 1 : 0;
            const uint8_t previous_value = (mask & local_previous_values) ? 1 : 0;
            if (current_value == previous_value)
            {
                // No change on this port since the last time we looked.
                // Do nothing.
                continue;
            }
            else
            {
                io_config_servicer_resid_gpi_active_level_t active_level;
                io_config_servicer_resid_gpi_event_config_t edge_direction;
                bool event_triggered = true;

                // Whether or not we have an event set up to notify the user, we should always update the current value.
                // Pack all the gpi_cfg accesses into one place here so we can cleanly mutex, but also return as soon as possible if no further action needed.

                rtos_osal_mutex_get(&gpi_mutex, RTOS_OSAL_WAIT_FOREVER);
                active_level = gpi_cfg.active_level[pin_index];
                edge_direction = gpi_cfg.event_config[pin_index];

                gpi_cfg.value[pin_index] = current_value;
                rtos_osal_mutex_put(&gpi_mutex);

                const uint8_t previous_state = ~(previous_value ^ active_level) & 0x1;
                const uint8_t current_state = ~(current_value ^ active_level) & 0x1;


                // Debounce at this point - if there's too recently been an event on this pin, ignore this one completely
                uint32_t time_now = get_reference_time();
                if (time_now - gpi_pins[pin_index]._previous_event_time < (GPI_DEBOUNCE_MS*XS1_TIMER_KHZ))
                {
                    debug_printf("Debounce %d\n", pin_index);
                    event_triggered = false;
                }
                else
                {
#if (appconfUSB_CTRL_ENABLED && HID_CONTROL)
                    button_press_info_t button_info;
                    button_info.gpi_source = GPI_SOURCE_EVK;
                    button_info.index = pin_index;
                    button_info.press_duration = 0;

                    if(current_value < previous_value)
                    {
                        button_info.state = BUTTON_STATE_PRESSED;
                    }
                    else
                    {
                        button_info.press_duration = time_now - gpi_pins[pin_index]._previous_event_time;
                        button_info.state = BUTTON_STATE_RELEASED;
                    }
                    if(device_control_ctx != NULL) // Notify the HID task
                    {
                        control_ret_t ret = send_write_cmd_to_servicer(device_control_ctx, HID_TASK_RESID, HID_TASK_RESID_INTERNAL_BUTTON_PRESS, (const uint8_t*)&button_info, sizeof(button_press_info_t), &device_control_mutex);
                        xassert (ret == CONTROL_SUCCESS);
                    }
#endif
                    // gpi_pins also accessed by interrupt, but only the .port and .pin members, so no mutex required
                    gpi_pins[pin_index]._previous_event_time = time_now;
                }

                if (!event_triggered)
                {
                    continue;
                }

                switch (edge_direction)
                {
                    case EdgeNone:
                        // If EdgeNone is set then we don't care about events on this pin.
                        debug_printf("GPI event, but EdgeNone behaviour set, prev: %d, new: %d\n", current_state, previous_state);
                        event_triggered = false;
                        break;
                    case EdgeFalling:
                        if (current_state > previous_state)
                        {
                            // If current_state > previous_state then we saw a rising edge, not a falling edge.
                            debug_printf("GPI event, but EdgeFalling behaviour set, prev: %d, new: %d\n", current_state, previous_state);
                            event_triggered = false;
                        }
                        break;
                    case EdgeRising:
                        if (current_state < previous_state)
                        {
                            // If current_state < previous_state then we saw a falling edge, not a rising edge.
                            debug_printf("GPI event, but EdgeRising behaviour set, prev: %d, new: %d\n", current_state, previous_state);
                            event_triggered = false;
                        }
                        break;
                    case EdgeBoth:
                    default:
                        // If we get here, then we know that an edge happened.
                        break;
                }

                if (event_triggered)
                {
                    rtos_osal_mutex_get(&gpi_mutex, RTOS_OSAL_WAIT_FOREVER);
                    gpi_cfg.event_pending[pin_index] = 1;
                    rtos_osal_mutex_put(&gpi_mutex);

                    write_gpo_pin(device_control_ctx, GPO_INT_N_PIN, 0); // This will be set when the user checks the event pending flag
                    debug_printf("int_n pin set\n");
                }
            }
        }
    }
}

//-----------------Servicer read write callback functions for the IO config servicer -----------------------//
/**
 * @brief IO config servicer read request handler function
 *
 * We don't use the generic servicer read request handler function for IO config servicer since a command for its underlying resource (GPO servicer)
 * needs to be forwarded over the internal device context and not the shared memory message queue which is used in the generic case.
 *
 * @param resid         Resource ID of the command
 * @param cmd           Command ID of the command
 * @param payload       pointer to the payload array that needs to be updated with the read response.
 * @param payload_len   Payload length in bytes.
 * @param app_data      App specific data
 * @return CONTROL_SUCCESS if command processed successfully. control_ret_t error status otherwise
 */
DEVICE_CONTROL_CALLBACK_ATTR
static control_ret_t read_cmd_io_config(control_resid_t resid, control_cmd_t cmd, uint8_t *payload, size_t payload_len, void *app_data)
{
    control_ret_t ret = CONTROL_SUCCESS;
    servicer_t *servicer = (servicer_t*)app_data;

    // For read commands, payload[0] is reserved from status. So payload_len is one more than the payload_len stored in the resource command map
    payload_len -= 1;
    uint8_t *payload_ptr = &payload[1]; //Excluding the status byte, which is updated later.

    debug_printf("Servicer ID %d on tile %d received READ command %02x for resid %02x\n\t",servicer->id, THIS_XCORE_TILE, cmd, resid);
    debug_printf("The command is requesting %d bytes\n\t", payload_len);


    control_resource_info_t *current_res_info = get_res_info(resid, servicer);
    xassert(current_res_info != NULL); // This should never happen
    control_cmd_info_t *current_cmd_info;
    ret = validate_cmd(&current_cmd_info, current_res_info, cmd, payload_ptr, payload_len);
    if(ret != CONTROL_SUCCESS)
    {
        payload[0] = ret; // Update status in byte 0
        return ret;
    }

    // Check if command is for the servicer itself
    if(current_res_info->resource == servicer->res_info[0].resource)
    {
        ret = gpi_servicer_read_cmd(current_res_info, cmd, payload_ptr, payload_len); // Note: Only payload[1] onwards is updated by the resource. Error checking happens only at this level
    }
    else
    {
        // Forward command to the GPO resource. This is done differently from a generic servicer
        // since the underlying resource is communicated to on the device_control_gpio_ctx and not a shared memory message queue.
        ret = send_read_cmd_to_servicer(device_control_gpio_ctx, current_res_info->resource, cmd, payload_ptr, payload_len, &device_control_mutex);
    }

    payload[0] = ret; // Status is returned in the first byte
    return ret;
}

/**
 * @brief IO config servicer write request handler function
 *
 * We don't use the generic servicer write request handler function for IO config servicer since a command for its underlying resource (GPO servicer)
 * needs to be forwarded over the internal device context and not the shared memory message queue which is used in the generic case.
 *
 * @param resid         Resource ID of the command
 * @param cmd           Command ID of the command
 * @param payload       pointer to the payload array that contains the write command payload.
 * @param payload_len   Payload length in bytes.
 * @param app_data      App specific data
 * @return CONTROL_SUCCESS if command processed successfully. control_ret_t error status otherwise
 */
DEVICE_CONTROL_CALLBACK_ATTR
static control_ret_t write_cmd_io_config(control_resid_t resid, control_cmd_t cmd, const uint8_t *payload, size_t payload_len, void *app_data)
{
    control_ret_t ret = CONTROL_SUCCESS;
    servicer_t *servicer = (servicer_t*)app_data;
    //debug_printf("Device control WRITE. Servicer ID %d\n\t", servicer->id);

    debug_printf("Servicer ID %d on tile %d received WRITE command %02x for resid %02x\n\t", servicer->id, THIS_XCORE_TILE, cmd, resid);
    debug_printf("The command has %d bytes\n\t", payload_len);

    control_resource_info_t *current_res_info = get_res_info(resid, servicer);
    xassert(current_res_info != NULL);
    control_cmd_info_t *current_cmd_info;
    ret = validate_cmd(&current_cmd_info, current_res_info, cmd, payload, payload_len);
    if(ret != CONTROL_SUCCESS)
    {
        return ret;
    }
    // Check if command is for the servicer itself
    if(current_res_info->resource == servicer->res_info[0].resource)
    {
        ret = gpi_servicer_write_cmd(current_res_info, cmd, payload, payload_len);
    }
    else
    {
        // Forward command to the GPO resource. This is done differently from a generic servicer
        // since the underlying resource is communicated to on the device_control_gpio_ctx and not a shared memory message queue.
        ret = send_write_cmd_to_servicer(device_control_gpio_ctx, current_res_info->resource, cmd, payload, payload_len, &device_control_mutex);
    }
    return ret;
}

extern TaskHandle_t io_config_servicer_parent_task; // For notifying the IO config servicer's parent task when it's safe to create the other servicers
void io_config_servicer(void *args) {
    /**
     * IO Config servicer task
     * - Start DAC
     * - Acts like the transport end of the device_control_gpio_ctx which it uses to send commands to the GPO task.
     * - Handle GPIO commands. GPI commands are processed in this task while GPO commands are forwarded to the GPO task over internal device_control_gpio_ctx
     */

    device_control_servicer_t servicer_ctx;

    servicer_t *servicer = (servicer_t*)args;
    xassert(servicer != NULL);
    
    control_resid_t *resources = (control_resid_t*)pvPortMalloc(servicer->num_resources * sizeof(control_resid_t));
    for(int i=0; i<servicer->num_resources; i++)
    {
        resources[i] = servicer->res_info[i].resource;
    }

    rtos_osal_mutex_create(&gpi_mutex, "gpi_cfg guard mutex", RTOS_OSAL_NOT_RECURSIVE);

    rtos_osal_mutex_create(&device_control_mutex, "device_control_gpio_ctx guard mutex", RTOS_OSAL_NOT_RECURSIVE); // Mutex used to guard the use of device_control_gpio_ctx, over which the IO config servicer
                                                                                                                   // communicates with both the GPO and the HID Servicers.

    control_ret_t dc_ret;
    // This task will act like the transport end to the device_control_gpio_ctx and sends GPO commands to the GPO servicer
    // Register resources on the device_control_gpio_ctx
    dc_ret = device_control_resources_register(device_control_gpio_ctx,
                                               pdMS_TO_TICKS(5000));
    rtos_gpio_t * gpio_ctx_t1 = get_gpio_ctx(1);

    if (dc_ret != CONTROL_SUCCESS) {
        debug_printf("Device control resources failed to register for device_control_gpio_ctx on tile %d\n", THIS_XCORE_TILE);
    } else {
        debug_printf("Device control resources registered for device_control_gpio_ctx on tile %d\n", THIS_XCORE_TILE);
    }
    xassert(dc_ret == CONTROL_SUCCESS);

    // It's safe to initialise the DAC now since device_control_gpio_ctx has been set up and this task can send commands to the GPO task.
    // This is one-off call to initialise user hardware in user_config.c
    int init_error = user_init_hardware(device_control_gpio_ctx);
    (void) init_error; // Disable compiler warning for now until we want to do something with init_errors

    // Signal to the GPO task that it's safe to start i2c_slave now
    signal_io_start(device_control_gpio_ctx);
#if !appconfUSB_ENABLED
    xTaskNotify(io_config_servicer_parent_task, 1, eSetValueWithOverwrite); // Notify the main task that it's safe to create the remaining Servicers
#endif

    // Now that DAC is initialised, create the IO expander task. Any use of rtos_i2c_master_ctx from this point on will be by the io_expander_task
#if (IO_EXPANDER_ENABLED)
    io_expander_task_args_t io_exp_args;
    io_exp_args.mutex = &device_control_mutex;
    io_exp_args.device_control_ctx = device_control_gpio_ctx;
    xTaskCreate((TaskFunction_t) io_expander_task, // Task for handling GPIO to I2C
                        "io_expander_task",
                        portTASK_STACK_DEPTH(io_expander_task),
                        &io_exp_args,
                        appconfTEST_TASK_PRIORITY,
                        NULL);
#endif

    debug_printf("Calling device_control_servicer_register(), servicer ID %d, on tile %d, core %d.\n", servicer->id, THIS_XCORE_TILE, rtos_core_id_get());

    if(APP_CONTROL_TRANSPORT_COUNT > 0)
    {
        // Register as a servicer on the I2C or SPI slave control device_control contexts
        dc_ret = device_control_servicer_register(&servicer_ctx,
                                            device_control_ctxs,
                                            APP_CONTROL_TRANSPORT_COUNT,
                                            resources, servicer->num_resources);
    }
    debug_printf("Out of device_control_servicer_register(), servicer ID %d, on tile %d. servicer_ctx address = 0x%x\n", servicer->id, THIS_XCORE_TILE, &servicer_ctx);

    // Set up and enable GPI interrupts and configuration state

    TaskHandle_t gpiTaskHandle = NULL;
    xTaskCreate(process_gpi_event,
                "GPI event processor",
                RTOS_THREAD_STACK_SIZE(process_gpi_event),
                device_control_gpio_ctx,
                appconfTEST_TASK_PRIORITY,
                &gpiTaskHandle);

    // Don't need to mutex these gpi_cfg accesses as the other task can't run yet as the ISR isn't active
    gpi_cfg = *gpi_config_get();

    for (int i = 0; i < GPIO_NUM_INPUT_PINS; i++)
    {
        gpi_pins[i]._previous_event_time = 0;
    }

    for (int i = 0; i < GPIO_NUM_INPUT_PORTS; i++)
    {
        rtos_gpio_port_id_t p = rtos_gpio_port(gpi_ports[i].port);
        gpi_ports[i]._rtos_port_id = p;

        rtos_gpio_port_enable(gpio_ctx_t1, p);
        gpi_ports[i]._previous_value = rtos_gpio_port_in(gpio_ctx_t1, p);

        rtos_gpio_isr_callback_set(gpio_ctx_t1, p, button_callback, gpiTaskHandle);
        rtos_gpio_interrupt_enable(gpio_ctx_t1, p);
    }


    // Set INT_N pin to 1 by default
    write_gpo_pin(device_control_gpio_ctx, GPO_INT_N_PIN, 1);

    vPortFree(resources);

    if(APP_CONTROL_TRANSPORT_COUNT > 0)
    {
        for(;;){
            device_control_servicer_cmd_recv(&servicer_ctx, read_cmd_io_config, write_cmd_io_config, servicer, RTOS_OSAL_WAIT_FOREVER);
        }
    }
    else
    {
        for(;;){
            vTaskDelay(pdMS_TO_TICKS(100));
        }
    }
}

void set_int_n_if_appropriate()
{
    bool events_pending = false;
    for (int i = 0; i < GPIO_NUM_INPUT_PINS; i++)
    {
        events_pending |= gpi_cfg.event_pending[i];
    }

    if (!events_pending)
    {
        write_gpo_pin(device_control_gpio_ctx, GPO_INT_N_PIN, 1);
        debug_printf("int_n pin set\n");
    }
}


control_ret_t gpi_servicer_read_cmd(control_resource_info_t *res_info, control_cmd_t cmd, uint8_t *payload, size_t payload_len)
{
    control_ret_t ret = CONTROL_SUCCESS;
    uint8_t cmd_id = CONTROL_CMD_CLEAR_READ(cmd);

    rtos_osal_mutex_get(&gpi_mutex, RTOS_OSAL_WAIT_FOREVER);

    switch (cmd_id)
    {
    case IO_CONFIG_SERVICER_RESID_GPI_INDEX:
    {
        memcpy(payload, &gpi_cfg.pindex, sizeof(io_config_servicer_resid_gpi_index_t));

        break;
    }
    case IO_CONFIG_SERVICER_RESID_GPI_EVENT_CONFIG:
    {
        io_config_servicer_resid_gpi_event_config_t result = gpi_cfg.event_config[gpi_cfg.pindex];

        memcpy(payload, &result, sizeof(io_config_servicer_resid_gpi_event_config_t));

        break;
    }
    case IO_CONFIG_SERVICER_RESID_GPI_ACTIVE_LEVEL:
    {
        io_config_servicer_resid_gpi_active_level_t result = gpi_cfg.active_level[gpi_cfg.pindex];

        memcpy(payload, &result, sizeof(io_config_servicer_resid_gpi_event_config_t));

        break;
    }
    case IO_CONFIG_SERVICER_RESID_GPI_VALUE:
    {
        /*
        * Active level:
        * value = V, active level = A, output = O
        *
        *  V A | O
        * ---------
        *  0 0 | 1  <-- value is 0, active level 0, so output high
        *  0 1 | 0
        *  1 0 | 0
        *  1 1 | 1
        *                                                      |-----| - to set output to 0 or 1
        * O = not (V xor A) => result = ~(value ^ active_level) & 0x1
        *
        */
        io_config_servicer_resid_gpi_value_t result = ~(gpi_cfg.value[gpi_cfg.pindex] ^ gpi_cfg.active_level[gpi_cfg.pindex]) & 0x1;

        memcpy(payload, &result, sizeof(io_config_servicer_resid_gpi_value_t));

        break;
    }
    case IO_CONFIG_SERVICER_RESID_GPI_EVENT_PENDING:
    {
        io_config_servicer_resid_gpi_event_pending_t result = gpi_cfg.event_pending[gpi_cfg.pindex];
        memcpy(payload, &result, sizeof(io_config_servicer_resid_gpi_event_pending_t));

        gpi_cfg.event_pending[gpi_cfg.pindex] = 0;

        set_int_n_if_appropriate();

        break;
    }
    case IO_CONFIG_SERVICER_RESID_GPI_VALUE_ALL:
    {
        io_config_servicer_resid_gpi_value_all_t result = 0;
        for (int idx = 0; idx < GPIO_NUM_INPUT_PINS; idx++)
        {
            // Construct bitmap; {0, 1, 0, 0} => 0b0100, with reference to active levels.
            result |= ((~(gpi_cfg.value[idx] ^ gpi_cfg.active_level[idx]) & 0x1) << idx);
        };

        memcpy(payload, &result, sizeof(io_config_servicer_resid_gpi_value_all_t));

        break;
    }
    case IO_CONFIG_SERVICER_RESID_GPI_EVENT_PENDING_ALL:
    {
        io_config_servicer_resid_gpi_event_pending_all_t result = 0;
        for (int idx = 0; idx < GPIO_NUM_INPUT_PINS; idx++)
        {
            // Construct bitmap; {0, 1, 0, 0} => 0b0100
            result &= (gpi_cfg.event_pending[idx] << idx);
            gpi_cfg.event_pending[idx] = 0;
        };

        memcpy(payload, &result, sizeof(io_config_servicer_resid_gpi_event_pending_all_t));

        set_int_n_if_appropriate();
        break;
    }
    default:
        break;

    }
    rtos_osal_mutex_put(&gpi_mutex);
    return ret;
}

control_ret_t gpi_servicer_write_cmd(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t payload_len)
{
    control_ret_t ret = CONTROL_SUCCESS;
    uint8_t cmd_id = CONTROL_CMD_CLEAR_READ(cmd);

    rtos_osal_mutex_get(&gpi_mutex, RTOS_OSAL_WAIT_FOREVER);
    switch (cmd_id)
    {
    case IO_CONFIG_SERVICER_RESID_GPI_INDEX:
    {
        memcpy(&gpi_cfg.pindex, payload, sizeof(io_config_servicer_resid_gpi_index_t));
        gpi_cfg.pindex = (gpi_cfg.pindex > GPIO_NUM_INPUT_PINS-1) ? 0 : gpi_cfg.pindex; // Silently set pin index to 0 if an invalid number is given

        break;
    }
    case IO_CONFIG_SERVICER_RESID_GPI_EVENT_CONFIG:
    {
        memcpy(&gpi_cfg.event_config[gpi_cfg.pindex], payload, sizeof(io_config_servicer_resid_gpi_event_config_t));

        break;
    }
    case IO_CONFIG_SERVICER_RESID_GPI_ACTIVE_LEVEL:
    {
        uint32_t active_level;
        memcpy(&active_level, payload, payload_len);

        gpi_cfg.active_level[gpi_cfg.pindex] = active_level ? 1 : 0; // active_level is a boolean
        break;
    }
    default:
        break;
    }
    rtos_osal_mutex_put(&gpi_mutex);
    return ret;
}
