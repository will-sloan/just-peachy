// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#include <xcore/chanend.h>
#include <xcore/channel.h>
#include <xcore/chanend.h>
#include <xcore/hwtimer.h>
#include <xcore/interrupt_wrappers.h>
#include <xcore/interrupt.h>
#include <xcore/triggerable.h>
#include <xcore/lock.h>
#include <xcore/hwtimer.h>
#include <xcore/select.h>
#include <xcore/parallel.h>
#include <xcore/assert.h>

#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define DEBUG_UNIT USB_BUFFER
#ifndef DEBUG_PRINT_ENABLE_USB_BUFFER
    #define DEBUG_PRINT_ENABLE_USB_BUFFER 0
#endif
#include "debug_print.h"

/* App headers */
#include "xud_device.h"
#include "usb_buffer.h"
#include "fifo_impl.h"
#include "fifo_check.h"
#include "sample_packing.h"
#include "sw_pll.h"
#include "tile_common.h"
#include "tusb_config.h"
#include "dbcalc.h"
#include "usb_audio_volume.h"
#include "audio_rates.h"

/* Config headers for sw_pll */
#include "fractions_1000ppm.h"
#include "register_setup_1000ppm.h"

/* Includes for usb_buffer control command handling */
#include "usb_buffer_cmds.h"
#include "tusb_config.h"
#include "usb_descriptors.h" // For ITF_NUM_AUDIO_STREAMING_SPK and ITF_NUM_AUDIO_STREAMING_MIC defines

#include "pll_servicer.h" // For get_usb_buffer_pll_lock_status declaration

// Buffer state used for reporting on the control interface
enum {
    BUFFER_WAIT_FOR_STABLE, // State waiting for stable after a stream start event
    BUFFER_STABLE_SINCE_STREAM_START,          // State streaming and stable
    BUFFER_UNSTABLE_SINCE_STREAM_START,        // State streaming and unstable (sticky)
};

// Shared variables between the USB Buffer servicer and resource
static bool mute_d2h[CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_TX + 1] = {0};                         // +1 for master channel 0
static bool mute_h2d[CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_RX + 1] = {0};                         // +1 for master channel 0
static int16_t volume_d2h[CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_TX + 1] = {0};                    // +1 for master channel 0. These are dB val in 8.8
static int16_t volume_h2d[CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_RX + 1] = {0};                    // +1 for master channel 0
static uint32_t vol_mul_d2h[CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_TX] = {0};                      // No +1 because master channel is included already. These are the volume scaling vals
static uint32_t vol_mul_h2d[CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_RX] = {0};                      // No +1 because master channel is included already
static uint8_t h2d_itf_alt_setting = 0;
static uint8_t d2h_itf_alt_setting = 0;
static sw_pll_lock_status_t lock_status = SW_PLL_LOCKED; // Needs to be communicated to the the other tile to the servicer handling AUDIO_MGR_RESID_PLL_LOCK_STATUS command

// Variable tracking if the D2H buffer is ever unstable while streaming. Retains the buffer_stable state between streaming events and gets reset when a new streaming start event occurs.
static int8_t d2h_buffer_stable_since_stream_start = BUFFER_WAIT_FOR_STABLE;
// Variable tracking if the H2D buffer is ever unstable while streaming. Retains the buffer_stable state between streaming events and gets reset when a new streaming start event occurs.
static int8_t h2d_buffer_stable_since_stream_start = BUFFER_WAIT_FOR_STABLE;

int8_t get_usb_buffer_pll_lock_status()
{
    return lock_status;
}

static void update_vol_mul(const unsigned chan, const unsigned num_audio_chan, const int16_t volumes[], const bool mutes[], uint32_t vol_muls[])
{
    // Add dB values to master (which means cascade multipliers using log rules)
    if(chan > 0)
    {
        // Update individuals
        int32_t db_val_frac = volumes[chan];     // Sign extend to 32b
        db_val_frac += volumes[0];               // cacade master gain
        uint32_t vol_mul = db_to_mult(db_val_frac, USB_AUDIO_VOLUME_FRAC_BITS, USB_AUDIO_VOL_MUL_FRAC_BITS);
        if(mutes[chan] || mutes[0]) // mute if individual or master
        {
            vol_muls[chan - 1] = 0;
        }
        else
        {
            vol_muls[chan - 1] = vol_mul;
        }
    }
    else
    {
        // Update both with new master settings
        for(int i = 0; i < num_audio_chan; i++)
        {
            int32_t db_val_frac = volumes[0];    // Sign extend master to 32b
            db_val_frac += volumes[i + 1];       // cacade idividual gains
            uint32_t vol_mul = db_to_mult(db_val_frac, USB_AUDIO_VOLUME_FRAC_BITS, USB_AUDIO_VOL_MUL_FRAC_BITS);
            bool mute = mutes[i + 1] || mutes[0];  // mute if individual or master
            vol_muls[i] = mute ? 0 : vol_mul;
        }
    }
}

// Initialise volume multipliers
void init_vol_muls(void)
{
    for(int chan=0; chan<CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_TX + 1; chan++)
    {
        update_vol_mul(chan, appconfUSB_CHANNELS_IN, volume_d2h, mute_d2h, vol_mul_d2h);
    }
    for(int chan=0; chan<CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_RX + 1; chan++)
    {
        update_vol_mul(chan, appconfUSB_CHANNELS_OUT, volume_h2d, mute_h2d, vol_mul_h2d);
    }
}


// Mute and Vol control command handlers
control_ret_t usb_buffer_servicer_write_cmd(control_cmd_t cmd, const uint8_t * payload, size_t payload_len)
{
    switch(cmd)
    {
        case USB_BUFFER_SERVICER_RESID_INTERNAL_MIC_MUTE:
            mute_d2h[payload[0]] = payload[1];  // 0 master, 1 left, 2 right

            update_vol_mul(payload[0], appconfUSB_CHANNELS_IN, volume_d2h, mute_d2h, vol_mul_d2h);

            return CONTROL_SUCCESS;
        case USB_BUFFER_SERVICER_RESID_INTERNAL_SPK_MUTE:
            mute_h2d[payload[0]] = payload[1];  // 0 master, 1 left, 2 right

            update_vol_mul(payload[0], appconfUSB_CHANNELS_OUT, volume_h2d, mute_h2d, vol_mul_h2d);

            return CONTROL_SUCCESS;
        case USB_BUFFER_SERVICER_RESID_INTERNAL_MIC_VOL:
        {
            usb_buffer_servicer_resid_internal_mic_vol_t vals[USB_BUFFER_SERVICER_RESID_INTERNAL_MIC_VOL_NUM_VALUES];
            memcpy(vals, payload, payload_len);
            unsigned chan = vals[0];    // 0 master, 1 left, 2 right
            volume_d2h[chan] = vals[1];

            update_vol_mul(chan, appconfUSB_CHANNELS_IN, volume_d2h, mute_d2h, vol_mul_d2h);

            return CONTROL_SUCCESS;
        }
        case USB_BUFFER_SERVICER_RESID_INTERNAL_SPK_VOL:
        {
            usb_buffer_servicer_resid_internal_spk_vol_t vals[USB_BUFFER_SERVICER_RESID_INTERNAL_SPK_VOL_NUM_VALUES];
            memcpy(vals, payload, payload_len);
            unsigned chan = vals[0];    // 0 master, 1 left, 2 right
            volume_h2d[chan] = vals[1];

            update_vol_mul(chan, appconfUSB_CHANNELS_OUT, volume_h2d, mute_h2d, vol_mul_h2d);

            return CONTROL_SUCCESS;
        }
        case USB_BUFFER_SERVICER_RESID_INTERNAL_ALT_INTERFACE:
        {
            if(payload[0] == ITF_NUM_AUDIO_STREAMING_SPK)
            {
               h2d_itf_alt_setting = payload[1];
            }
            else if(payload[0] == ITF_NUM_AUDIO_STREAMING_MIC)
            {
                d2h_itf_alt_setting = payload[1];
            }
            return CONTROL_SUCCESS;
        }
    }
    return CONTROL_SUCCESS;
}

control_ret_t usb_buffer_servicer_read_cmd(control_cmd_t cmd, uint8_t *payload, size_t payload_len)
{
    uint8_t cmd_id = CONTROL_CMD_CLEAR_READ(cmd);
    control_ret_t ret = CONTROL_SUCCESS;
    switch(cmd_id)
    {
        case USB_BUFFER_SERVICER_RESID_USB_D2H_BUFFER_STABLE:
        {
            usb_buffer_servicer_resid_usb_d2h_buffer_stable_t val = (d2h_buffer_stable_since_stream_start == BUFFER_STABLE_SINCE_STREAM_START) ? 1 : 0;
            memcpy(payload, &val, sizeof(usb_buffer_servicer_resid_usb_d2h_buffer_stable_t));
            break;
        }
        case USB_BUFFER_SERVICER_RESID_USB_H2D_BUFFER_STABLE:
        {
            usb_buffer_servicer_resid_usb_h2d_buffer_stable_t val = (h2d_buffer_stable_since_stream_start == BUFFER_STABLE_SINCE_STREAM_START) ? 1 : 0;
            memcpy(payload, &val, sizeof(usb_buffer_servicer_resid_usb_h2d_buffer_stable_t));
            break;
        }
    }
    return ret;
}


// I2S sends a data token which is enough to pre-trigger the select in usb_buffer. This means that
// some of the select latency is hidden and usb_buffer is ready to service exchange_samples_with_usb immediately
// It keeps the switch path open until exchange_samples_with_usb has completed
static inline void start_exchange_samples_with_i2s(chanend_t chan_usb_to_i2s){
    chanend_in_byte(chan_usb_to_i2s);
}

static inline void exchange_samples_with_i2s( chanend_t chan_usb_to_i2s,
                                                int32_t samples_host_to_device[SAMPLE_COLLECTION_SIZE][appconfUSB_CHANNELS_OUT],
                                                int32_t samples_device_to_host[SAMPLE_COLLECTION_SIZE][appconfUSB_CHANNELS_IN])
{

    // Host to device
    for(int ch = 0; ch < appconfUSB_CHANNELS_IN; ch++){
        for(int smp = 0; smp < get_usb_to_i2s_packet_size(); smp++){
            int32_t sample = samples_host_to_device[smp][ch];
            chanend_out_word(chan_usb_to_i2s, sample);
        }
    }

    // Device to host
    for(int ch = 0; ch < appconfUSB_CHANNELS_OUT; ch++){
        for(int smp = 0; smp < get_i2s_to_usb_packet_size(); smp++){
            int32_t sample = chanend_in_word(chan_usb_to_i2s);
            samples_device_to_host[smp][ch] = sample;
        }
    }

    // This is the same as CT_END (which clears the channel) except that the token is consumed by the destination chanend.
    // So Audio is free to continue without waiting.
    chanend_out_control_token(chan_usb_to_i2s, XS1_CT_PAUSE);
}


// Audio buffer controls
#define DIV_ROUND_UP(n, d) (n / d + 1)  //Always rounds up to the next integer. Needed for 48001Hz case etc.
#define BIGGEST(a, b) (a > b ? a : b)

//Defines for endpoint buffer sizes. Samples is total number of samples across all channels
#define MAX_OUT_SAMPLES_PER_SOF_PERIOD    (DIV_ROUND_UP(appconfUSB_OUT_NOMINAL_HZ * SOF_COUNT_PER_TRANSFER, SOF_FREQ_HZ) * appconfUSB_CHANNELS_OUT)
#define NOM_OUT_SAMPLES_PER_SOF_PERIOD    ((appconfUSB_OUT_NOMINAL_HZ * SOF_COUNT_PER_TRANSFER / SOF_FREQ_HZ) * appconfUSB_CHANNELS_OUT)
#define MAX_IN_SAMPLES_PER_SOF_PERIOD     (DIV_ROUND_UP(appconfUSB_IN_NOMINAL_HZ * SOF_COUNT_PER_TRANSFER, SOF_FREQ_HZ) * appconfUSB_CHANNELS_IN)
#define NOM_IN_SAMPLES_PER_SOF_PERIOD     ((appconfUSB_IN_NOMINAL_HZ * SOF_COUNT_PER_TRANSFER / SOF_FREQ_HZ) * appconfUSB_CHANNELS_IN)

// In case we need to fall back to FS when default is HS
#define MAX_OUT_SAMPLES_PER_SOF_PERIOD_FS    (DIV_ROUND_UP(appconfUSB_OUT_NOMINAL_HZ, SOF_FREQ_HZ_FS) * appconfUSB_CHANNELS_OUT)
#define NOM_OUT_SAMPLES_PER_SOF_PERIOD_FS    ((appconfUSB_OUT_NOMINAL_HZ / SOF_FREQ_HZ_FS) * appconfUSB_CHANNELS_OUT)
#define MAX_IN_SAMPLES_PER_SOF_PERIOD_FS     (DIV_ROUND_UP(appconfUSB_IN_NOMINAL_HZ, SOF_FREQ_HZ_FS) * appconfUSB_CHANNELS_IN)
#define NOM_IN_SAMPLES_PER_SOF_PERIOD_FS     ((appconfUSB_IN_NOMINAL_HZ / SOF_FREQ_HZ_FS) * appconfUSB_CHANNELS_IN)

#define MAX_OUTPUT_SLOT_SIZE              4
#define MAX_INPUT_SLOT_SIZE               4

#define OUT_AUDIO_BUFFER_SIZE_BYTES_DEFAULT       (MAX_OUT_SAMPLES_PER_SOF_PERIOD * MAX_OUTPUT_SLOT_SIZE)
#define IN_AUDIO_BUFFER_SIZE_BYTES_DEFAULT        (MAX_IN_SAMPLES_PER_SOF_PERIOD * MAX_INPUT_SLOT_SIZE)

// In case we need to fall back to FS when default is HS
#define OUT_AUDIO_BUFFER_SIZE_BYTES_FS    (MAX_OUT_SAMPLES_PER_SOF_PERIOD_FS * MAX_OUTPUT_SLOT_SIZE)
#define IN_AUDIO_BUFFER_SIZE_BYTES_FS     (MAX_IN_SAMPLES_PER_SOF_PERIOD_FS * MAX_INPUT_SLOT_SIZE)

// Buffers are statically allocated, so make sure that the biggest size buffer is allocated
#define OUT_AUDIO_BUFFER_SIZE_BYTES_MAX        BIGGEST(OUT_AUDIO_BUFFER_SIZE_BYTES_DEFAULT, OUT_AUDIO_BUFFER_SIZE_BYTES_FS)
#define IN_AUDIO_BUFFER_SIZE_BYTES_MAX         BIGGEST(IN_AUDIO_BUFFER_SIZE_BYTES_DEFAULT, IN_AUDIO_BUFFER_SIZE_BYTES_FS)

#define FIFO_SIZE_SCALE                     4
#define TARGET_OUT_FIFO_LENGTH_DEFAULT            (FIFO_SIZE_SCALE * MAX_OUT_SAMPLES_PER_SOF_PERIOD)
#define TARGET_IN_FIFO_LENGTH_DEFAULT             (FIFO_SIZE_SCALE * MAX_IN_SAMPLES_PER_SOF_PERIOD)

// In case we need to fall back to FS when default is HS
#define TARGET_OUT_FIFO_LENGTH_FS            (FIFO_SIZE_SCALE * MAX_OUT_SAMPLES_PER_SOF_PERIOD_FS)
#define TARGET_IN_FIFO_LENGTH_FS             (FIFO_SIZE_SCALE * MAX_IN_SAMPLES_PER_SOF_PERIOD_FS)

#define MIN_OUT_FIFO_LENGTH               (FIFO_SIZE_SCALE * 16)
#define MIN_IN_FIFO_LENGTH                (FIFO_SIZE_SCALE * 16)

#define OUT_FIFO_LENGTH_DEFAULT           BIGGEST(TARGET_OUT_FIFO_LENGTH_DEFAULT, MIN_OUT_FIFO_LENGTH)
#define IN_FIFO_LENGTH_DEFAULT            BIGGEST(TARGET_IN_FIFO_LENGTH_DEFAULT, MIN_IN_FIFO_LENGTH)

// In case we need to fall back to FS when default is HS
#define OUT_FIFO_LENGTH_FS                BIGGEST(TARGET_OUT_FIFO_LENGTH_FS, MIN_OUT_FIFO_LENGTH)
#define IN_FIFO_LENGTH_FS                 BIGGEST(TARGET_IN_FIFO_LENGTH_FS, MIN_IN_FIFO_LENGTH)

// Buffers are statically allocated, so make sure that the biggest size buffer is allocated
#define OUT_FIFO_LENGTH_MAX               BIGGEST(OUT_FIFO_LENGTH_FS, OUT_FIFO_LENGTH_DEFAULT) // Max of default and FullSpeed
#define IN_FIFO_LENGTH_MAX                BIGGEST(IN_FIFO_LENGTH_FS, IN_FIFO_LENGTH_DEFAULT) // Max of default and FullSpeed

// PI controller consts
static sw_pll_15q16_t kp_init = SW_PLL_15Q16(SW_PLL_NUM_LUT_ENTRIES(frac_values_90) / (TARGET_OUT_FIFO_LENGTH_DEFAULT / appconfUSB_CHANNELS_OUT));
#define ADAPTIVE_INITIAL_KI                 0.1     // For fast convergence at startup, sacrificing PLL jitter
#define ADAPTIVE_INITIAL_KII                0       // The II integrator factor is not used
#define ADAPTIVE_STABLE_KP                  0.3     // For slow convergence after FIFO stability detected, for low PLL jitter
#define ADAPTIVE_STABLE_KI                  0.005   // For slow convergence after FIFO stability detected, for low PLL jitter
#define ADAPTIVE_STABILITY_THRESH_S         5       // How many seconds at FIFO level close to 0 to be considered stable
#define ADAPTIVE_STABILITY_EMA_ALPHA        0.002   // Calculated to give a 3dB point of around 0.03Hz (~30s)
#define ADAPTIVE_STABILITY_EMA_Q_BITS       9       // Must be able to take max FIFO size (<512)
#define ADAPTIVE_STABILITY_EMA_SHIFT        (32 - ADAPTIVE_STABILITY_EMA_Q_BITS - 1) // -1 because we have a sign bit
#define ADAPTIVE_STABILITY_STABLE_THRESHOLD 0.1     // Filtered FIFO depth that we can say is stable

// Exponential Moving Average filter
// See test_adaptive_lock.py for model/design
typedef int32_t ema_fixed_point_t;
#if (1 << ADAPTIVE_STABILITY_EMA_Q_BITS) < BIGGEST(OUT_FIFO_LENGTH, IN_FIFO_LENGTH)
#error EMA filter fixed point type does not contain sufficient headroom for FIFO size
#endif
static const int64_t ema_alpha = (ADAPTIVE_STABILITY_EMA_ALPHA * (1 << ADAPTIVE_STABILITY_EMA_SHIFT)); // Pre-calculate EMA coeffs
static const int64_t ema_one_minus_alpha = ((1 << ADAPTIVE_STABILITY_EMA_SHIFT) - ema_alpha);

// Do the EMA filter
static inline ema_fixed_point_t do_ema(const ema_fixed_point_t state, const ema_fixed_point_t data){
    int64_t tmp = ema_alpha * (int64_t)data;
    tmp += ema_one_minus_alpha * (int64_t)state;
    return tmp >> ADAPTIVE_STABILITY_EMA_SHIFT;
}

// FIFO level stability detector. Designed to detect when the FIFO level is stable.
// Uses an EMA filter and time threshold to determine that things have converged close to zero.
// This indicates that the integral term has wound up sufficiently and we can drop Kp
// to allow reduced PLL output jitter
typedef struct stability_detector_t{
    bool stable;
    uint32_t fifo_level_stable_count;
    uint32_t stability_count_threshold;
    ema_fixed_point_t fifo_level_stable_threshold;
    ema_fixed_point_t filtered_fifo_level;
} stability_detector_t;


static inline bool stability_detector(stability_detector_t *stability_detector_state, int32_t fifo_level)
{
    stability_detector_state->filtered_fifo_level = do_ema(stability_detector_state->filtered_fifo_level, fifo_level << ADAPTIVE_STABILITY_EMA_SHIFT);

    // Only sends stable once
    if ((stability_detector_state->stable == false) && (abs(stability_detector_state->filtered_fifo_level) <= abs(stability_detector_state->fifo_level_stable_threshold)))
    {
        stability_detector_state->fifo_level_stable_count += 1;
        // debug_printf("%d %d\n", stability_detector_state->fifo_level_stable_count, stability_detector_state->stability_count_threshold);

        if(stability_detector_state->fifo_level_stable_count == stability_detector_state->stability_count_threshold)
        {
            stability_detector_state->stable = true;
            debug_printf("**STABLE**\n");
            return true;
        }
    }
    else
    {
        stability_detector_state->fifo_level_stable_count = 0;
    }

    return false;
}

// Helper to do a partial init of the PI controller at runtime
static inline void sw_pll_reset_constants(sw_pll_state_t *sw_pll, sw_pll_15q16_t Kp, sw_pll_15q16_t Ki, sw_pll_15q16_t Kii)
{
    sw_pll->pi_state.Kp = Kp;
    sw_pll->pi_state.Ki = Ki;
    sw_pll->pi_state.Kii = Kii;

    sw_pll->pi_state.error_accum = 0;
    if(Ki){
        sw_pll->pi_state.i_windup_limit = ((SW_PLL_NUM_LUT_ENTRIES(frac_values_90) << SW_PLL_NUM_FRAC_BITS) / Ki); // Set to twice the max total error input to LUT
    }else{
        sw_pll->pi_state.i_windup_limit = 0;
    }
}


// Helper to scale the Ki (and Kp) at run time. The key thing is that, when Ki is scaled
// that the windup limit is also scaled up accordingly to prevent clipping of the accumulated error term.
// The accumulated error, used by the Ki term, is also scales so the state is retained proportionally.
// This is quite a specific use case for sw_pll kept locally here that makes the assumption that Ki_old / Ki_new is large
// enough such that trunctating to an integer scaling factor is a good approximation. A factor of over 10 is fine.
static inline void sw_pll_scale_constants(sw_pll_state_t *sw_pll, sw_pll_15q16_t Kp, sw_pll_15q16_t Ki)
{
    sw_pll->pi_state.Kp = Kp;
    sw_pll_15q16_t multiplier = sw_pll->pi_state.Ki / Ki; // This assumes new Ki is smaller, which will alway be true in our control scheme
    debug_printf("Ki old: %d, Ki new: %d, mul: %d, error_accum_old: %d, windup_old: %d\n", sw_pll->Ki, Ki, multiplier, sw_pll->error_accum, sw_pll->i_windup_limit);
    sw_pll->pi_state.Ki = Ki;
    sw_pll->pi_state.error_accum *= multiplier;
    sw_pll->pi_state.i_windup_limit *= multiplier;
    debug_printf("sw_pll->error_accum new: %d, windup_new: %d\n", sw_pll->error_accum, sw_pll->i_windup_limit);
}

// Setup adaptive pll
static void init_adaptive_pll(sw_pll_state_t *sw_pll)
{

    debug_printf("Kp %d\n", kp_init >> 16);
    debug_printf("nom: %d, lut size %d,  FIFO_LEN %d\n", NOM_OUT_SAMPLES_PER_SOF_PERIOD, SW_PLL_NUM_LUT_ENTRIES(frac_values_90), OUT_FIFO_LENGTH_DEFAULT);

    sw_pll_lut_init(sw_pll,
                kp_init,
                SW_PLL_15Q16(ADAPTIVE_INITIAL_KI),
                SW_PLL_15Q16(ADAPTIVE_INITIAL_KII),
                0,  // This is done outside of the do_control_from_error API in sw_pll
                PLL_RATIO,
                0,  // Not used for low-level API of sw_pll
                frac_values_90,
                SW_PLL_NUM_LUT_ENTRIES(frac_values_90),
                APP_PLL_CTL_REG,
                APP_PLL_DIV_REG,
                SW_PLL_NUM_LUT_ENTRIES(frac_values_90) / 2,
                PLL_PPM_RANGE);

    debug_printf("Using SW PLL to track Adaptive USB input.\n");
}

// Convert and also check valid. If invlaid, it will return default to 16b / 2
static unsigned bitdepth_to_subslot(unsigned bitdepth)
{
    if(bitdepth % 8 != 0 || bitdepth < 16 || bitdepth > 32)
    {
        return 2;
    } else {
        return bitdepth / 8;
    }
}

static bool device_reset_event = false; // Set from usb_proxy in case of a device reset event received from XUD. Cleared from usb_buffer after handling the device reset event
static XUD_BusSpeed_t device_speed_after_reset;
/// @brief Called from usb_proxy to inform the usb_buffer of a device reset event
/// @param xud_speed Bus speed at which the host expects the device to operate
void set_device_reset_event(XUD_BusSpeed_t xud_speed)
{
    device_reset_event = true;
    device_speed_after_reset = xud_speed;
}

/// Variables/buffers that need to be modified from handle_device_reset_event() when falling back to FS mode
static XUD_ep ep_audio_in;
static uint8_t buffer_audio_ep_in[IN_AUDIO_BUFFER_SIZE_BYTES_MAX];
static mem_fifo_t host_to_device_fifo;
static mem_fifo_t device_to_host_fifo;
static sw_pll_state_t sw_pll = {0};
static stability_detector_t stability_detector_state;
static unsigned g_nom_in_samples_per_period = NOM_IN_SAMPLES_PER_SOF_PERIOD;
static unsigned g_nom_out_samples_per_period = NOM_OUT_SAMPLES_PER_SOF_PERIOD;
static unsigned num_samples_to_send_to_host = NOM_IN_SAMPLES_PER_SOF_PERIOD / appconfUSB_CHANNELS_IN;


/// @brief  Initialise the H2D FIFO with the default size
/// @param fifo_storage pointer to the FIFO memory
/// @param fifo_size FIFO length in samples
static void init_default_host_to_device_fifo(int8_t *fifo_storage, unsigned fifo_size)
{
    host_to_device_fifo.size = fifo_size; // FIFO size in samples. Initialise to default so change only in case of a fallback to FS
    host_to_device_fifo.data_base_ptr = fifo_storage;
    host_to_device_fifo.write_idx = 0;
    host_to_device_fifo.read_idx = 0;
}

/// @brief  Initialise the D2H FIFO with the default size
/// @param fifo_storage pointer to the FIFO memory
/// @param fifo_size FIFO length in samples
static void init_default_device_to_host_fifo(int8_t *fifo_storage, unsigned fifo_size)
{
    device_to_host_fifo.size = fifo_size; // FIFO size in samples. Initialise to default so change only in case of a fallback to FS
    device_to_host_fifo.data_base_ptr = fifo_storage;
    device_to_host_fifo.write_idx = 0;
    device_to_host_fifo.read_idx = 0;
}

/// @brief Initialise the stability detector state for the default (HS) operating mode
static void init_default_stability_detector_state()
{
    stability_detector_state.stable = false;
    stability_detector_state.fifo_level_stable_count = 0;
    stability_detector_state.stability_count_threshold = ADAPTIVE_STABILITY_THRESH_S * (SOF_FREQ_HZ / PLL_CONTROL_LOOP_COUNT_UA);
    stability_detector_state.fifo_level_stable_threshold = ADAPTIVE_STABILITY_STABLE_THRESHOLD * (1 << ADAPTIVE_STABILITY_EMA_SHIFT);
    stability_detector_state.filtered_fifo_level = 0;
}

/// @brief Handle a device reset event. This function currently handles only resetting to Full speed mode of operation
static inline void handle_device_reset_event()
{
    if(device_speed_after_reset == XUD_SPEED_FS) // At the moment, we only handle a fallback from HS (which is the default) to FS.
    {
        g_nom_in_samples_per_period = NOM_IN_SAMPLES_PER_SOF_PERIOD_FS;
        g_nom_out_samples_per_period = NOM_OUT_SAMPLES_PER_SOF_PERIOD_FS;
        num_samples_to_send_to_host = g_nom_in_samples_per_period / appconfUSB_CHANNELS_IN;

        uint8_t bit_depth_in = 0;
        uint8_t bit_depth_out = 0;
        get_usb_bit_depth(&bit_depth_in, &bit_depth_out);
        const unsigned in_subslot_size = bitdepth_to_subslot(bit_depth_in);
        XUD_SetReady_InPtr(ep_audio_in, (unsigned)buffer_audio_ep_in, g_nom_in_samples_per_period * in_subslot_size); // Set XUD Ready with the new IN size

        // Reset D2H FIFO
        device_to_host_fifo.size = IN_FIFO_LENGTH_FS;
        device_to_host_fifo.write_idx = 0;
        device_to_host_fifo.read_idx = 0;

        // Reset H2D FIFO
        host_to_device_fifo.size = OUT_FIFO_LENGTH_FS;
        host_to_device_fifo.write_idx = 0;
        host_to_device_fifo.read_idx = 0;

        // Reinitialise kp and reset the sw_pll
        kp_init = SW_PLL_15Q16(SW_PLL_NUM_LUT_ENTRIES(frac_values_90) / (TARGET_OUT_FIFO_LENGTH_DEFAULT / appconfUSB_CHANNELS_OUT));
        sw_pll_reset_constants(&sw_pll, kp_init, SW_PLL_15Q16(ADAPTIVE_INITIAL_KI), SW_PLL_15Q16(ADAPTIVE_INITIAL_KII));

        // Reset stability detector state
        stability_detector_state.stable = false;
        stability_detector_state.fifo_level_stable_count = 0;
        stability_detector_state.stability_count_threshold = ADAPTIVE_STABILITY_THRESH_S * (SOF_FREQ_HZ_FS / (PLL_CONTROL_LOOP_COUNT_UA/SOF_FREQ_RATIO)); // PLL_CONTROL_LOOP_COUNT_UA is defined for HS
        stability_detector_state.fifo_level_stable_threshold = ADAPTIVE_STABILITY_STABLE_THRESHOLD * (1 << ADAPTIVE_STABILITY_EMA_SHIFT);
        stability_detector_state.filtered_fifo_level = 0;
    }
}

void usb_buffer(usb_buffer_args_t *args)
/* USB buffer task */
{
     if(get_core_burn_status() != 0){
        SET_FAST_MODE();
    }

    chanend_t chan_ep_audio_out = args->chan_ep_audio_out;
    chanend_t chan_ep_audio_in = args->chan_ep_audio_in;
    chanend_t chan_usb_to_i2s = args->chan_usb_to_i2s;
    chanend_t chan_sof = args->chan_sof;

    // USB Audio vars
    uint8_t buffer_audio_ep_out[OUT_AUDIO_BUFFER_SIZE_BYTES_MAX];

    unsigned num_samples_received_from_host = 0;

    uint8_t d2h_itf_alt_setting_old = d2h_itf_alt_setting; // Used for detecting a change in d2h_itf_alt_setting status
    uint8_t h2d_itf_alt_setting_old = h2d_itf_alt_setting; // Used for detecting a change in h2d_itf_alt_setting status

    uint8_t bit_depth_in = 0;
    uint8_t bit_depth_out = 0;
    get_usb_bit_depth(&bit_depth_in, &bit_depth_out);
    const unsigned in_subslot_size = bitdepth_to_subslot(bit_depth_in);
    const unsigned out_subslot_size = bitdepth_to_subslot(bit_depth_out);

    // FIFOs from EP buffers to audio
    // These are the storage arrays for the FIFO
    int8_t host_to_device_fifo_storage[MAX_OUTPUT_SLOT_SIZE * OUT_FIFO_LENGTH_MAX] = {0}; //OUT_FIFO_LENGTH is in samples. Allocate memory enough to store highest bit-res(32 bit) samples
    int8_t device_to_host_fifo_storage[MAX_INPUT_SLOT_SIZE * IN_FIFO_LENGTH_MAX] = {0};  //IN_FIFO_LENGTH is in samples. Allocate memory enough to store highest bit-res(32 bit) samples

    // Initialise H2D and D2H FIFOs
    init_default_host_to_device_fifo(host_to_device_fifo_storage, OUT_FIFO_LENGTH_DEFAULT);
    init_default_device_to_host_fifo(device_to_host_fifo_storage, IN_FIFO_LENGTH_DEFAULT);

    audio_fifo_state_t h2d_fifo_state = AUDIO_FIFO_EMPTY;
    audio_fifo_state_t d2h_fifo_state = AUDIO_FIFO_EMPTY;

    int host_to_device_fill_level = 0;
    int device_to_host_fill_level = 0;


    // Audio samples for exchanging with audio manager
    int32_t samples_device_to_host[SAMPLE_COLLECTION_SIZE][appconfUSB_CHANNELS_IN] = {{0}};
    int32_t samples_host_to_device[SAMPLE_COLLECTION_SIZE][appconfUSB_CHANNELS_OUT] = {{0}};


    // Control loop vars
    init_adaptive_pll(&sw_pll);
    unsigned sw_pll_control_counter = 0;

    // Init stability_detector_state.
    init_default_stability_detector_state();

    // Audio endpoints
    XUD_ep ep_audio_out = XUD_InitEp(chan_ep_audio_out);
    ep_audio_in = XUD_InitEp(chan_ep_audio_in);

    XUD_SetReady_OutPtr(ep_audio_out, (unsigned)buffer_audio_ep_out);
    XUD_SetReady_InPtr(ep_audio_in, (unsigned)buffer_audio_ep_in, g_nom_in_samples_per_period * in_subslot_size);


    // This holds off exchange with audio until we are ready here
    chan_out_word(chan_usb_to_i2s, 0);

    // Main event loop
    SELECT_RES(
        CASE_THEN(chan_ep_audio_out, event_usb_audio_out),
        CASE_THEN(chan_ep_audio_in, event_usb_audio_in),
        CASE_THEN(chan_usb_to_i2s, event_audio_exchange),
        CASE_THEN(chan_sof, event_sof)
    )
    {
        // Note we only sample the FIFO depth after USB transfers to reduce the jitter of the fill level down to the audio exchange size
        // This avoids a large jitter term of the USB buffer size in the fill level. This allows for smoother control error input.

        // Host to device
        event_usb_audio_out:
        {
            unsigned num_bytes_received_from_host = 0;
            XUD_GetBuffer(ep_audio_out, buffer_audio_ep_out, &num_bytes_received_from_host);

            unsigned total_num_samples_received_from_host = num_bytes_received_from_host / out_subslot_size;
            num_samples_received_from_host = total_num_samples_received_from_host / appconfUSB_CHANNELS_OUT;

            fifo_ret_t ret = FIFO_SUCCESS;

            if (h2d_fifo_state <= AUDIO_FIFO_STABLE){
                ret = fifo_block_push_fast(&host_to_device_fifo, buffer_audio_ep_out, total_num_samples_received_from_host, out_subslot_size);

                // Get fill level at this point so we don't get loads of jitter from USB dumping in large packets
                host_to_device_fill_level = fifo_get_fill_relative_half(&host_to_device_fifo) / appconfUSB_CHANNELS_OUT;

                check_fifo_state_after_push(&h2d_fifo_state, ret, host_to_device_fill_level, -(g_nom_out_samples_per_period / appconfUSB_CHANNELS_OUT / 2), "h2d");
            }
            else
            {
                host_to_device_fill_level = fifo_get_fill_relative_half(&host_to_device_fifo) / appconfUSB_CHANNELS_OUT;
            }

            // Check for the stable -> unstable transition only while streaming since we want to retain the last buffer_stable value between streaming events.
            // This cannot be done in the c_sof event within a if(h2d_itf_alt_setting == 1) check since in the event of a streaming stop,
            // the h2d buffer gets empty even before a d2h_itf_alt_setting = 0 is received.
            if((h2d_buffer_stable_since_stream_start == BUFFER_STABLE_SINCE_STREAM_START) &&
                (h2d_fifo_state != AUDIO_FIFO_STABLE))
            {
                h2d_buffer_stable_since_stream_start = BUFFER_UNSTABLE_SINCE_STREAM_START; // Set to unstable in a sticky way
            }

            // Adaptive USB - we match output rate with input rate
            num_samples_to_send_to_host = num_samples_received_from_host;

            // Mark EP as ready for next frame from host
            XUD_SetReady_OutPtr(ep_audio_out, (unsigned)buffer_audio_ep_out);
        }
        SELECT_CONTINUE_NO_RESET;

        // Device to host
        event_usb_audio_in:
        {
            unsigned total_num_samples_to_send_to_host = num_samples_to_send_to_host * appconfUSB_CHANNELS_IN;
            unsigned num_bytes_to_send_to_host = total_num_samples_to_send_to_host * in_subslot_size;

            if(d2h_fifo_state >= AUDIO_FIFO_STABLE){
                fifo_ret_t ret = fifo_block_pop_fast(&device_to_host_fifo, buffer_audio_ep_in, total_num_samples_to_send_to_host, in_subslot_size);
                device_to_host_fill_level = fifo_get_fill_relative_half(&device_to_host_fifo) / appconfUSB_CHANNELS_IN;

                if(check_fifo_state_after_pop(&d2h_fifo_state, ret, device_to_host_fill_level, get_i2s_to_usb_packet_size() >> 1, "d2h"))
                {
                    // Do nothing - samples are in buffer_audio_ep_in ready to go
                }
                else // check_fifo_state_after_pop says samples invalid, zero samples
                {
                    memset(buffer_audio_ep_in, 0, num_bytes_to_send_to_host);
                }
            }
            else
            {
                // Send zeros until full enough to be considered stable
                memset(buffer_audio_ep_in, 0, num_bytes_to_send_to_host);
                device_to_host_fill_level = fifo_get_fill_relative_half(&device_to_host_fifo) / appconfUSB_CHANNELS_IN;
            }

            // Check for the stable -> unstable transition only while streaming since we want to retain the last buffer_stable value between streaming events.
            // This cannot be done in the c_sof event within a if(d2h_itf_alt_setting == 1) check since in the event of a streaming stop,
            // the d2h buffer gets full even before a d2h_itf_alt_setting = 0 is received.
            if((d2h_buffer_stable_since_stream_start == BUFFER_STABLE_SINCE_STREAM_START) &&
                    (d2h_fifo_state != AUDIO_FIFO_STABLE)) // While streaming, a previously stable buffer seen as unstable for the first time
            {
                d2h_buffer_stable_since_stream_start = BUFFER_UNSTABLE_SINCE_STREAM_START; // Set to unstable in a sticky way
            }

            XUD_SetBuffer(ep_audio_in, buffer_audio_ep_in, num_bytes_to_send_to_host);

            XUD_SetReady_InPtr(ep_audio_in, (unsigned) buffer_audio_ep_in, num_bytes_to_send_to_host);
        }
        SELECT_CONTINUE_NO_RESET;

        event_audio_exchange:
        {
            // Do exchange first so we block i2s for the least possible time
            start_exchange_samples_with_i2s(chan_usb_to_i2s);
            exchange_samples_with_i2s(chan_usb_to_i2s, samples_host_to_device, samples_device_to_host);

            // Process samples from device to host
            uint8_t samples_in_packed[MAX_INPUT_SLOT_SIZE * appconfUSB_CHANNELS_IN * get_i2s_to_usb_packet_size()];
            pack_samples_to_buff(&samples_device_to_host[0][0],
                                get_i2s_to_usb_packet_size() * appconfUSB_CHANNELS_IN,
                                in_subslot_size,
                                &samples_in_packed[0],
                                vol_mul_d2h);

            if(device_reset_event == true)
            {
                handle_device_reset_event();
                device_reset_event = false;
            }

            fifo_ret_t ret = FIFO_SUCCESS;

            if(d2h_fifo_state <= AUDIO_FIFO_STABLE)
            {
                ret = fifo_block_push_fast(&device_to_host_fifo, &samples_in_packed[0], get_i2s_to_usb_packet_size() * appconfUSB_CHANNELS_IN, in_subslot_size);

                check_fifo_state_after_push(&d2h_fifo_state, ret, device_to_host_fill_level, -(get_i2s_to_usb_packet_size() >> 1), "d2h");
            }

            // Process samples from host to device
            uint8_t samples_out_packed[MAX_OUTPUT_SLOT_SIZE * appconfUSB_CHANNELS_OUT * get_usb_to_i2s_packet_size()];

            if (h2d_fifo_state >= AUDIO_FIFO_STABLE) // Only pop if is stable, emptying towards stable or full
            {
                ret = fifo_block_pop_fast(&host_to_device_fifo, &samples_out_packed[0], get_usb_to_i2s_packet_size() * appconfUSB_CHANNELS_OUT, out_subslot_size);

                if(check_fifo_state_after_pop(&h2d_fifo_state, ret, host_to_device_fill_level, (g_nom_out_samples_per_period / appconfUSB_CHANNELS_OUT / 2), "h2d"))
                {
                    unpack_buff_to_samples(&samples_out_packed[0],
                                            get_usb_to_i2s_packet_size() * appconfUSB_CHANNELS_OUT,
                                            out_subslot_size,
                                            &samples_host_to_device[0][0],
                                            vol_mul_h2d);
                }
                else // pop failed, zero samples
                {
                    memset(&samples_host_to_device[0][0], 0, sizeof(samples_host_to_device));
                }
            }
            else
            {
                // Send zeros until the FIFO is full enough
                memset(&samples_host_to_device[0][0], 0, sizeof(samples_host_to_device));
            }

            // Alive tick
            static unsigned count = 0;
            count++;
            if(count > SOF_FREQ_HZ)
            {
                debug_printf("%d %d, %d %d, %d %d\n",
                                h2d_fifo_state,
                                host_to_device_fill_level,
                                d2h_fifo_state,
                                device_to_host_fill_level,
                                stability_detector_state.filtered_fifo_level >> (ADAPTIVE_STABILITY_EMA_SHIFT-10), // 1024x filtered value
                                (int32_t)(ADAPTIVE_STABILITY_STABLE_THRESHOLD * (1 << 10)) // 1024x filtered value
                                );
                count = 0;
            }
        }
        SELECT_CONTINUE_NO_RESET;

        event_sof:
        {
            chanend_in_word(chan_sof);
            lock_status = SW_PLL_LOCKED;
            // Do adaptive rate control. Use the output rate to lock to if streaming out, otherwise use fixed rate and lock local PLL to that. Keeps h2d half full
            if(h2d_itf_alt_setting != 0 && h2d_fifo_state == AUDIO_FIFO_STABLE)
            {
                sw_pll_control_counter++;
                if(sw_pll_control_counter == PLL_CONTROL_LOOP_COUNT_UA){
                    sw_pll_control_counter = 0;
                    lock_status = sw_pll_lut_do_control_from_error(&sw_pll, -host_to_device_fill_level);

                    if (stability_detector(&stability_detector_state, -host_to_device_fill_level))
                    {
                        sw_pll_scale_constants(&sw_pll,SW_PLL_15Q16(ADAPTIVE_STABLE_KP), SW_PLL_15Q16(ADAPTIVE_STABLE_KI));
                    }
                }
            }
            else if(d2h_itf_alt_setting != 0 && d2h_fifo_state == AUDIO_FIFO_STABLE)// We must only be streaming in. Use fixed packet size (nominal) and adapt rate to keep d2h FIFO half full
            {
                sw_pll_control_counter++;
                if(sw_pll_control_counter == PLL_CONTROL_LOOP_COUNT_UA){
                    sw_pll_control_counter = 0;
                    lock_status = sw_pll_lut_do_control_from_error(&sw_pll, device_to_host_fill_level);

                    if (stability_detector(&stability_detector_state, device_to_host_fill_level))
                    {
                        sw_pll_scale_constants(&sw_pll, SW_PLL_15Q16(ADAPTIVE_STABLE_KP), SW_PLL_15Q16(ADAPTIVE_STABLE_KI));
                    }
                }
                num_samples_to_send_to_host = g_nom_in_samples_per_period / appconfUSB_CHANNELS_IN; // The order in USB is IN, OUT, SoF so if no streaming out, set nominal
            }
            else
            {
                // Do nothing - hold current clock rate as is probably correct for when we next start streaming
            }

            // Detect change in d2h_itf_alt_setting
            bool d2h_stopped_event = false;
            bool h2d_stopped_event = false;

            if(d2h_itf_alt_setting != d2h_itf_alt_setting_old)
            {
                d2h_itf_alt_setting_old = d2h_itf_alt_setting;
                if(d2h_itf_alt_setting != 0) // Input stream is starting
                {
                    memset(device_to_host_fifo_storage, 0, sizeof(device_to_host_fifo_storage)); // Ensure full d2h FIFO is cleared as will be old mic data
                    d2h_buffer_stable_since_stream_start = BUFFER_WAIT_FOR_STABLE; // Stream starting. Reset to start looking for the next stable
                }
                else
                {
                    // Clear current input endpoint buffer for next stream start
                    d2h_stopped_event = true;
                    memset(buffer_audio_ep_in, 0, sizeof(buffer_audio_ep_in));
                }
            }
            // Detect change in d2h_itf_alt_setting
            if(h2d_itf_alt_setting != h2d_itf_alt_setting_old)
            {
                h2d_itf_alt_setting_old = h2d_itf_alt_setting;
                if(h2d_itf_alt_setting_old == 0)
                {
                    h2d_stopped_event = true;
                }
                else
                {
                    h2d_buffer_stable_since_stream_start = BUFFER_WAIT_FOR_STABLE; // Stream starting. Reset to start looking for the next stable
                }
            }
            // Look from the start -> stable transition
            if((h2d_fifo_state == AUDIO_FIFO_STABLE) &&
               (h2d_buffer_stable_since_stream_start == BUFFER_WAIT_FOR_STABLE)) // After stream start, h2d stable for the first time
            {
                h2d_buffer_stable_since_stream_start = BUFFER_STABLE_SINCE_STREAM_START; // Set to 1 when buffer seen stable for the first time after a stream start event
            }
            // Look for the start -> stable transition
            if((d2h_fifo_state == AUDIO_FIFO_STABLE) &&
               (d2h_buffer_stable_since_stream_start == BUFFER_WAIT_FOR_STABLE)) // After stream start, h2d stable for the first time
            {
                d2h_buffer_stable_since_stream_start = BUFFER_STABLE_SINCE_STREAM_START; // Set to 1 when buffer seen stable for the first time after a stream start event
            }

            // See if both streams have stopped, if so reset the PI controler and stability detector
            if((h2d_stopped_event && d2h_itf_alt_setting == 0) || (d2h_stopped_event && h2d_itf_alt_setting == 0))
            {
                debug_printf("ALL STOP!!\n");
                sw_pll_reset_pi_state(&sw_pll);
                stability_detector_state.stable = false;
                stability_detector_state.fifo_level_stable_count = 0;
                stability_detector_state.filtered_fifo_level = 0;
                sw_pll_control_counter = 0;
            }
        }
        SELECT_CONTINUE_NO_RESET;

    }
}
