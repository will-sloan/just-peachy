// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#define DEBUG_UNIT GPO_SERVICER
#ifndef DEBUG_PRINT_ENABLE_GPO_SERVICER
    #define DEBUG_PRINT_ENABLE_GPO_SERVICER 0
#endif
#include "debug_print.h"

#include <stdio.h>
#include <platform.h>
#include "platform/platform_conf.h"
#include "platform/driver_instances.h"
#include <xcore/hwtimer.h>
#include <xcore/triggerable.h>
#include "device_control_i2c.h"
#include "device_control_spi.h"
#include "servicer.h"
#include "control_init.h"
#include "io_config_cmds.h"
#include "gpo_servicer_defaults.h"
#include "usb_hid.h"

#define GPIO_PWM_BITS                       6
#define GPIO_PWM_RESOLUTION                 (1 << GPIO_PWM_BITS)
#define GPIO_PWM_FRAME_FREQUENCY            250
#define GPIO_PWM_BIT_FREQUENCY              (GPIO_PWM_FRAME_FREQUENCY * GPIO_PWM_RESOLUTION)

#define GPIO_FLASH_BIT_PERIOD_MS            100   // How long each bit of the serial mask is ANDed with GPO output

static hwtimer_t xKernelTimer;
static TimerHandle_t blinky_timer_ctx = NULL;
static unsigned pwm_counter = 0;
unsigned flashing_counter = 0;

static gpo_config_t gpo_cfg;
static uint32_t start_io = 0;
static gpo_led_mapping_t gpo_led_mapping[TOTAL_EVK_LEDS] = {{0}};

static inline uint32_t get_duty_cycles_from_percentage(uint32_t duty_percent)
{
    return (GPIO_PWM_RESOLUTION * duty_percent) / 100;
}

/**
 * @brief Initialise the GPO task
 *
 * This function enables the GPO port and sets the initial state of all pins on the port.
 * All pins are set to active low by default with a duty percentage of 0 so disabled by default
 */
static inline void init_gpo(void)
{
    rtos_gpio_t * gpio_ctx_t0 = get_gpio_ctx(0);
    gpo_cfg = *gpo_config_get();
    gpo_cfg.led_ports[0] = rtos_gpio_port(GPO_TILE_0_PORT_8C); // on tile 0. Red LED -> bit6, Green LED -> bit7
    rtos_gpio_port_enable(gpio_ctx_t0, gpo_cfg.led_ports[0]);

    for (int i = 0; i < GPIO_NUM_OUTPUT_PORTS; i++)
    {
        for (int j = 0; j < GPO_PORT_BITS; j++)
        {
            gpo_cfg.output_port_duty[i][j] = get_duty_cycles_from_percentage(gpo_cfg.output_duty_percent[i][j]); // Set output port initial values set above

        }
    }

    gpo_led_mapping[EVK_LED_GREEN].port_index = 0;
    gpo_led_mapping[EVK_LED_GREEN].pin_index = GPO_LED_GREEN_PIN;

    gpo_led_mapping[EVK_LED_RED].port_index = 0;
    gpo_led_mapping[EVK_LED_RED].pin_index = GPO_LED_RED_PIN;
}

/**
 * @brief Flash serial mask shift interrut callback function
 *
 * The flash serial mask contains the pin state for a 100 ms interval, so the 32bit mask holds the GPO pin state for 3.2 seconds.
 * This function increments and wraps around the flash counter which governs the bit in the flash serial mask that is looked at in the PWM
 * interrupt function to govern the pin state.
 * @param xTimer
 */
static void led_blinky_cb(TimerHandle_t xTimer)
{
    flashing_counter += 1;

    if(flashing_counter >= sizeof(gpo_cfg.flash_serial_mask[0][0])*8) // LED state in 32*8 100ms periods configurable through the flash_serial_mask
    {
        flashing_counter = 0;
    }
    return;
}

/**
 * @brief PWM timer interrupt callback function.
 *
 * This function is called every 1/(GPIO_PWM_FRAME_FREQUENCY*GPIO_PWM_RESOLUTION) = 0.03125 ms and sets the value of all pins
 * on the GPO port. It looks at the pwm duty cycle and the flash serial mask bit for a pin to decide its state.
 * A read or write on the GPO port cannot happen in any other place in the control plane other than in this function.
 * To change a pin state the host or other tasks in the control plane can issue GPO commands to the GPO servicer task which will then
 * handle the pin state change by changing the pin duty cycle that gets reflected when the port in configured in the PWMTimerISR.
 */
DEFINE_RTOS_INTERRUPT_CALLBACK( PWMTimerISR, pvData )
{
    uint32_t ulLastTrigger;
    uint32_t ulNow;
    //int xCoreID;
    //xCoreID = 0;
    //configASSERT( xCoreID == rtos_core_id_get() );
    /* Need the next interrupt to be scheduled relative to
     * the current trigger time, rather than the current
     * time. */
    ulLastTrigger = hwtimer_get_trigger_time( xKernelTimer );
    rtos_gpio_t * gpio_ctx_t0 = get_gpio_ctx(0);


    //printintln(ulLastTrigger);
    /* Check to see if the ISR is late. If it is, we don't
     * want to schedule the next interrupt to be in the past. */
    for (int i = 0; i < GPIO_NUM_OUTPUT_PORTS; i++)
    {
        //uint32_t start_time = get_reference_time();
        uint32_t port_val = rtos_gpio_port_in(gpio_ctx_t0, gpo_cfg.led_ports[i]);
        //uint32_t end_time = get_reference_time();
        //uint32_t diff = end_time - start_time;
        //printintln(diff);
        for (int bit = 0; bit < GPO_PORT_BITS; bit++)
        {
            uint32_t mask = ~((unsigned)1 << bit);
            port_val &= mask; // Zero out the relevant bit

            mask = (unsigned)1 << bit;
            //get on and off state for 'bit' position
            uint32_t state_off = (~gpo_cfg.active_level_bitmap[i]) & mask;
            uint32_t state_on = gpo_cfg.active_level_bitmap[i] & mask;

            if ((gpo_cfg.output_port_duty[i][bit] > pwm_counter) &&
                (gpo_cfg.flash_serial_mask[i][bit] & (1 << flashing_counter)))
            {
                //Turn the bit on
                port_val |= state_on;
            }
            else
            {
                //set the bit to off
                port_val |= state_off;
            }
        }
        rtos_gpio_port_out(gpio_ctx_t0, gpo_cfg.led_ports[i], port_val); // ON
    }

    pwm_counter += 1;
    if (pwm_counter == GPIO_PWM_RESOLUTION)
    {
        pwm_counter = 0;
    }

    ulNow = hwtimer_get_time( xKernelTimer );
    if( ulNow - ulLastTrigger >= configCPU_CLOCK_HZ / GPIO_PWM_BIT_FREQUENCY )
    {
        ulLastTrigger = ulNow;
    }
    ulLastTrigger += configCPU_CLOCK_HZ / GPIO_PWM_BIT_FREQUENCY;
    hwtimer_change_trigger_time( xKernelTimer, ulLastTrigger );
}

//----------------- GPO Servicer read write command callback functions-----------------------//
/**
 * @brief GPO servicer control read request handler function.
 *
 * Since GPO servicer is a special case and only responds to commands on the internal device control context,
 * this handler function is a simplified version of the generic read request handler function. It doesn't do
 * any error checking since all currently supported error checking
 * takes place in the IO config servicer where the command is first received from the host.
 *
 * @param resid         Resource ID of the command
 * @param cmd           Command ID of the command
 * @param payload       pointer to the payload array that needs to be updated with the read response. This does NOT contain the extra byte for error status. (Can consider changing in future)
 * @param payload_len   Payload length in bytes.
 * @param app_data      App specific data
 * @return CONTROL_SUCCESS always since error checking is done at the IO config servicer level.
 */
DEVICE_CONTROL_CALLBACK_ATTR
static control_ret_t gpo_read_cmd(control_resid_t resid, control_cmd_t cmd, uint8_t *payload, size_t payload_len, void *app_data)
{
    debug_printf("GPO Servicer on tile %d received READ command %02x for resid %02x\n\t", THIS_XCORE_TILE, cmd, resid);
    debug_printf("The command is requesting %d bytes\n\t", payload_len);

    gpo_servicer_read_cmd(cmd, payload, payload_len);
    return CONTROL_SUCCESS;

}

/**
 * @brief GPO servicer control read request handler function.
 *
 * Since GPO servicer is a special case and only responds to commands on the internal device control context,
 * this handler function is a simplified version of the generic write request handler function. It doesn't do
 * any error checking since all currently supported error checking
 * takes place in the IO config servicer where the command is first received from the host.
 *
 * @param resid         Resource ID of the command
 * @param cmd           Command ID of the command
 * @param payload       pointer to the payload array that contains the write command paylad.
 * @param payload_len   Payload length in bytes.
 * @param app_data      App specific data
 * @return CONTROL_SUCCESS always since error checking is done at the IO config servicer level.
 */
DEVICE_CONTROL_CALLBACK_ATTR
static control_ret_t gpo_write_cmd(control_resid_t resid, control_cmd_t cmd, const uint8_t *payload, size_t payload_len, void *app_data)
{
    debug_printf("GPO Servicer on tile %d received WRITE command %02x for resid %02x\n\t", THIS_XCORE_TILE, cmd, resid);
    debug_printf("The command has %d bytes\n\t", payload_len);

    gpo_servicer_write_cmd(cmd, payload, payload_len);
    return CONTROL_SUCCESS;
}

void gpo_servicer(void *args)
{
    /**
     * GPO Servicer task
     * - This task is a servicer on tile 0 and also an underlying resource of the IO config task on tile 1.
     * - It registers only over the internal device_control_gpio_ctx to receive commands from the IO config servicer.
     * - It handles all GPO commands.
     * - It starts the control IO task (SPI slave or I2C Slave) when signalled by the IO config servicer through the GPO_SERVICER_RESID_INTERNAL_GPO_START_CONTROL_TASK command.
     */
    device_control_servicer_t servicer_ctx;

    servicer_t *servicer = (servicer_t*)args;
    xassert(servicer != NULL);

    control_resid_t *resources = (control_resid_t*)pvPortMalloc(servicer->num_resources * sizeof(control_resid_t));
    for(int i=0; i<servicer->num_resources; i++)
    {
        resources[i] = servicer->res_info[i].resource;
    }

    // Initialise GPO with desired PWM, active levels and output
    init_gpo();

    // Set up the blinky interrupt
    blinky_timer_ctx = xTimerCreate("blinky",
                                    pdMS_TO_TICKS(GPIO_FLASH_BIT_PERIOD_MS),
                                    pdTRUE,
                                    NULL,
                                    led_blinky_cb);

    xTimerStart(blinky_timer_ctx, 0);

    // Setup the PWM interrupt
#if (appconfNUM_FREE_RTOS_CORES > 1)
    uint32_t core_exclude_map = 0;
    rtos_osal_thread_core_exclusion_get(NULL, &core_exclude_map);
#endif
    xKernelTimer = hwtimer_alloc();
    uint32_t ulNow;
    ulNow = hwtimer_get_time( xKernelTimer );
    debug_printf( "The time is now (%u)\n", ulNow );
    ulNow += configCPU_CLOCK_HZ / GPIO_PWM_BIT_FREQUENCY;
    triggerable_setup_interrupt_callback( xKernelTimer, NULL, RTOS_INTERRUPT_CALLBACK( PWMTimerISR ) );
    hwtimer_set_trigger_time( xKernelTimer, ulNow );
    /* Ensure that the PWM timer interrupt is enabled on the requested core */
#if (appconfNUM_FREE_RTOS_CORES > 1)
    rtos_osal_thread_core_exclusion_set(NULL, ~(1 << GPO_PWM_ISR_CORE));
#endif
    triggerable_enable_trigger( xKernelTimer );
    /* Restore the core exclusion map for the calling thread */
#if (appconfNUM_FREE_RTOS_CORES > 1)
    rtos_osal_thread_core_exclusion_set(NULL, core_exclude_map);
#endif

    control_ret_t dc_ret;
    debug_printf("Calling device_control_servicer_register(), servicer ID %d, on tile %d, core %d.\n", servicer->id, THIS_XCORE_TILE, rtos_core_id_get());
    // Register on the internal device_control_gpio_ctx over which GPO servicer is connected to the IO config servicer.
    // GPO servicer only receives commands from the IO config servicer and not from the external host.
    dc_ret = device_control_servicer_register(&servicer_ctx,
                                        &device_control_gpio_ctx,
                                        1,
                                        resources, servicer->num_resources);
    debug_printf("Out of device_control_servicer_register(), servicer ID %d, on tile %d. servicer_ctx address = 0x%x\n", servicer->id, THIS_XCORE_TILE, &servicer_ctx);

    vPortFree(resources);

    // Wait for control commands
    for(;;){
        device_control_servicer_cmd_recv(&servicer_ctx, gpo_read_cmd, gpo_write_cmd, servicer, RTOS_OSAL_WAIT_FOREVER);
    }
}

control_ret_t gpo_servicer_read_cmd(control_cmd_t cmd, uint8_t *payload, size_t payload_len)
{
    /**
     *  GPO read command handler
     */

    control_ret_t ret = CONTROL_SUCCESS;
    uint8_t cmd_id = CONTROL_CMD_CLEAR_READ(cmd);

    if(cmd_id == GPO_SERVICER_RESID_GPO_PORT_PIN_INDEX)
    {
        memcpy(payload, &gpo_cfg.port_index, sizeof(gpo_servicer_resid_gpo_port_pin_index_t));
        memcpy(payload + sizeof(gpo_servicer_resid_gpo_port_pin_index_t), &gpo_cfg.pin_index, sizeof(gpo_servicer_resid_gpo_port_pin_index_t));
    }
    else if (cmd_id == GPO_SERVICER_RESID_GPO_PIN_ACTIVE_LEVEL)
    {
        uint32_t port_idx = gpo_cfg.port_index;
        uint32_t pin_idx = gpo_cfg.pin_index;

        gpo_servicer_resid_gpo_pin_active_level_t active_level = (gpo_cfg.active_level_bitmap[port_idx] >> pin_idx) & 0x1;
        memcpy(payload, &active_level, sizeof(gpo_servicer_resid_gpo_pin_active_level_t));
    }
    else if (cmd_id == GPO_SERVICER_RESID_GPO_PIN_PWM_DUTY)
    {
        uint32_t port_idx = gpo_cfg.port_index;
        uint32_t pin_idx = gpo_cfg.pin_index;
        memcpy(payload, &gpo_cfg.output_duty_percent[port_idx][pin_idx], payload_len);
    }
    else if (cmd_id == GPO_SERVICER_RESID_GPO_PIN_FLASH_MASK )
    {
        uint32_t port_idx = gpo_cfg.port_index;
        uint32_t pin_idx = gpo_cfg.pin_index;
        memcpy(payload, &gpo_cfg.flash_serial_mask[port_idx][pin_idx], payload_len);
    }
    return ret;
}

control_ret_t gpo_servicer_write_cmd(control_cmd_t cmd, const uint8_t *payload, size_t payload_len)
{
    /**
     *  GPO write command handler
     */
    control_ret_t ret = CONTROL_SUCCESS;
    uint8_t cmd_id = CONTROL_CMD_CLEAR_READ(cmd);

    if(cmd_id == GPO_SERVICER_RESID_GPO_PORT_PIN_INDEX)
    {
        memcpy(&gpo_cfg.port_index, payload, sizeof(gpo_servicer_resid_gpo_port_pin_index_t));
        memcpy(&gpo_cfg.pin_index, payload + sizeof(gpo_servicer_resid_gpo_port_pin_index_t), sizeof(gpo_servicer_resid_gpo_port_pin_index_t));
        gpo_cfg.pin_index = (gpo_cfg.pin_index > GPO_PORT_BITS) ? 0 : gpo_cfg.pin_index; // Set to 0 if invalid value provided. Not returning any error for this
        gpo_cfg.pin_index = gpo_cfg.pin_index;
    }
    else if (cmd_id == GPO_SERVICER_RESID_GPO_PIN_ACTIVE_LEVEL)
    {
        uint32_t port_idx = gpo_cfg.port_index;
        uint32_t pin_idx = gpo_cfg.pin_index;

        uint32_t active_level;
        memcpy(&active_level, payload, payload_len);
        active_level = active_level >= 1 ? 1 : 0; // active_level is a boolean

        uint32_t mask = ~((unsigned)1 << pin_idx);
        gpo_cfg.active_level_bitmap[port_idx] &= mask; // Zero out the relevant bit
        gpo_cfg.active_level_bitmap[port_idx] |= (active_level << pin_idx);
    }
    else if(cmd_id == GPO_SERVICER_RESID_GPO_PIN_PWM_DUTY)
    {
        uint32_t port_idx = gpo_cfg.port_index;
        uint32_t pin_idx = gpo_cfg.pin_index;
        uint8_t duty_percent;
        memcpy(&duty_percent, payload, payload_len);
        duty_percent = (duty_percent > 100) ? 100 : duty_percent;

        gpo_cfg.output_duty_percent[port_idx][pin_idx] = duty_percent;
        gpo_cfg.output_port_duty[port_idx][pin_idx] = get_duty_cycles_from_percentage((uint32_t)gpo_cfg.output_duty_percent[port_idx][pin_idx]);
    }
    else if(cmd_id == GPO_SERVICER_RESID_GPO_PIN_FLASH_MASK)
    {
        uint32_t port_idx = gpo_cfg.port_index;
        uint32_t pin_idx = gpo_cfg.pin_index;
        memcpy(&gpo_cfg.flash_serial_mask[port_idx][pin_idx], payload, sizeof(gpo_servicer_resid_gpo_pin_flash_mask_t));
    }
    else if(cmd_id == GPO_SERVICER_RESID_GPO_PIN_VAL)
    {
        gpo_servicer_resid_gpo_pin_val_t port_pin_val[GPO_SERVICER_RESID_GPO_PIN_VAL_NUM_VALUES];

        memcpy(port_pin_val, payload, GPO_SERVICER_RESID_GPO_PIN_VAL_NUM_VALUES*sizeof(gpo_servicer_resid_gpo_pin_val_t));

        gpo_cfg.flash_serial_mask[port_pin_val[0]][port_pin_val[1]] = ~0; // Set flash mask to always ON

        if(port_pin_val[2])
        {
            // Set duty to 100%
            gpo_cfg.output_duty_percent[port_pin_val[0]][port_pin_val[1]] = 100;
        }
        else
        {
            // Set duty to 0
            gpo_cfg.output_duty_percent[port_pin_val[0]][port_pin_val[1]] = 0;
        }
        gpo_cfg.output_port_duty[port_pin_val[0]][port_pin_val[1]] = get_duty_cycles_from_percentage((uint32_t)gpo_cfg.output_duty_percent[port_pin_val[0]][port_pin_val[1]]);
    }
    else if(cmd_id == GPO_SERVICER_RESID_INTERNAL_GPO_START_CONTROL_TASK)
    {
        if(start_io == 0)
        {
            debug_printf("Start SPI Slave or I2C Slave IO task\n");
            // IO config servicer is signalling to start the control IO tasks
            control_start_io_tasks();
            start_io = 1;
        }
    }
    else if(cmd_id == GPO_SERVICER_RESID_INTERNAL_GPO_LED_STATE)
    {
        gpo_servicer_resid_internal_gpo_led_state_t led_index_mode[GPO_SERVICER_RESID_INTERNAL_GPO_LED_STATE_NUM_VALUES];

        memcpy(led_index_mode, payload, GPO_SERVICER_RESID_GPO_PIN_VAL_NUM_VALUES*sizeof(gpo_servicer_resid_gpo_pin_val_t));
        uint8_t led_index = led_index_mode[0];
        uint8_t led_mode = led_index_mode[1];
        xassert(led_index < TOTAL_EVK_LEDS);
        uint8_t port = gpo_led_mapping[led_index].port_index;
        uint8_t pin = gpo_led_mapping[led_index].pin_index;

        gpo_cfg.output_duty_percent[port][pin] = 100;
        if(led_mode == LED_MODE_FAST_FLASH)
        {
            gpo_cfg.flash_serial_mask[port][pin] = 0xaaaaaaaa;
        }
        else if(led_mode == LED_MODE_SLOW_FLASH)
        {
            gpo_cfg.flash_serial_mask[port][pin] = 0xff00ff00;
        }
        else if(led_mode == LED_MODE_STEADY)
        {
            gpo_cfg.flash_serial_mask[port][pin] = 0xffffffff;
        }
        else if(led_mode == LED_MODE_OFF)
        {
            gpo_cfg.flash_serial_mask[port][pin] = 0;
        }
        gpo_cfg.output_port_duty[port][pin] = get_duty_cycles_from_percentage((uint32_t)gpo_cfg.output_duty_percent[port][pin]);
    }
    return ret;
}

