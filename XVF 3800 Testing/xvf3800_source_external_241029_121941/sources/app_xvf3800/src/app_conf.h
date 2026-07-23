// Copyright 2022-2024 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

// Also please see the .xn file in bsp_config for port mapping

#ifndef APP_CONF_H_
#define APP_CONF_H_

/* Application tile specifiers */
#include "platform.h"
#include "BeClearCommon.h"

/* App data plane configuration */
// CMake-configured
#if !(INT_DEVICE || INT_HOST || UA) || ((INT_DEVICE + INT_HOST + UA) > 1)
#error Must define either INT_DEVICE or INT_HOST or UA
#endif // CONFIG CHECK

#ifndef appconfLRCLK_NOMINAL_HZ
#define appconfLRCLK_NOMINAL_HZ                 16000
#endif  //appconfLRCLK_NOMINAL_HZ

#ifndef appconfUSB_IN_OUT_NOMINAL_HZ
#define appconfUSB_IN_OUT_NOMINAL_HZ            16000
#endif  //appconfUSB_OUT_NOMINAL_HZ

#ifndef appconfUSB_IN_NOMINAL_HZ
#define appconfUSB_IN_NOMINAL_HZ                appconfUSB_IN_OUT_NOMINAL_HZ
#endif  //appconfUSB_IN_NOMINAL_HZ

#ifndef appconfUSB_OUT_NOMINAL_HZ
#define appconfUSB_OUT_NOMINAL_HZ               appconfUSB_IN_OUT_NOMINAL_HZ
#endif  //appconfUSB_OUT_NOMINAL_HZ

#ifndef appconfEXTERNAL_MCLK
#define appconfEXTERNAL_MCLK                    0 // On intdev builds only, we can accept an external MCLK if needed (no sw_pll clock recovery)
#endif  //appconfEXTERNAL_MCLK

#ifndef appconfUSB_CHANNELS_IN
#define appconfUSB_CHANNELS_IN                  2 // TODO make 1 and ensure all buffer handling works
#endif  //appconfUSB_CHANNELS_IN

#ifndef appconfUSB_CHANNELS_OUT
#define appconfUSB_CHANNELS_OUT                 2
#endif  //appconfUSB_CHANNELS_OUT

#ifndef appconfSPATIAL
// set to 1 to pan the auto select beam onto left and right
// channels using DoA in the post_shf_dsp function. Note that
// this also requires linking against fwk_xvf::pan_pot, see
// example spatial build configs for more info.
#define appconfSPATIAL 0
#endif

#if defined(MIC_ARRAY_TYPE_SQR) && MIC_ARRAY_TYPE_SQR
#define MIC_ARRAY_TYPE BECLEAR_CIRCULAR_ARRAY
#elif defined(MIC_ARRAY_TYPE_LIN) && MIC_ARRAY_TYPE_LIN
#define MIC_ARRAY_TYPE BECLEAR_LINEAR_ARRAY
#else
#error "Incorrectly set mic array type"
#endif

#if INT_DEVICE
#define appconfI2S_ROLE_MASTER                  0
#define appconfFIXED_MCLK_APP_PLL               0
#if appconfEXTERNAL_MCLK
    #define appconfRECOVER_MCLK_I2S_APP_PLL     0
#else
    #define appconfRECOVER_MCLK_I2S_APP_PLL     1
#endif
#define appconfUSB_ENABLED                      0
#define HID_CONTROL                             0
#define MIC_ARRAY_CONFIG_MCLK_FREQ              12288000
#define appconfNUM_I2S_PINS_IN                  1
#define appconfPROCESSED_MIC_OUT_PORT           PORT_I2S_DATA1
#define appconfFAR_END_IN_PORT                  PORT_I2S_DATA0
#define DFU_CONTROL                             1


#elif INT_HOST
#define appconfI2S_ROLE_MASTER                  1
#define appconfFIXED_MCLK_APP_PLL               1
#define appconfRECOVER_MCLK_I2S_APP_PLL         0
#define appconfUSB_ENABLED                      0
#define HID_CONTROL                             0
#define MIC_ARRAY_CONFIG_MCLK_FREQ              24576000
#define appconfNUM_I2S_PINS_IN                  1
#define appconfPROCESSED_MIC_OUT_PORT           PORT_I2S_DATA0
#define appconfFAR_END_IN_PORT                  PORT_I2S_DATA1

#else // UA
#define appconfI2S_ROLE_MASTER                  1
#define appconfFIXED_MCLK_APP_PLL               0
#define appconfRECOVER_MCLK_I2S_APP_PLL         0 // The clock is recovered instead in usb_buffer
#define appconfUSB_ENABLED                      1
#define MIC_ARRAY_CONFIG_MCLK_FREQ              12288000
#define appconfNUM_I2S_PINS_IN                  1
#define appconfPROCESSED_MIC_OUT_PORT           PORT_I2S_DATA0 //TODO this is actually far end out
#define appconfFAR_END_IN_PORT                  PORT_I2S_DATA1
#define DFU_CONTROL                             1
#define HID_CONTROL                             1
#endif // End INT_DEVICE/INT_HOST/UA

#ifndef IO_EXPANDER_ENABLED
#define IO_EXPANDER_ENABLED (0)
#endif

#if !HID_CONTROL
#define IO_EXPANDER_ENABLED (0) // If HID is not enabled, disable IO Expander as well
#endif

#define appconfFAR_END_OUT_PORT                 PORT_I2S_DATA2 // Optional output pin when far-end DSP enabled on INT configs

#define appconfINT_PACKED_BIT_DEPTH             32 // INTegrated, not INTeger - as opposed to UA

#define appconfBCLK_NOMINAL_HZ                  (appconfLRCLK_NOMINAL_HZ * 64)
#define appconfMCLK_NOMINAL_HZ                  MIC_ARRAY_CONFIG_MCLK_FREQ
#ifndef appconfNUM_I2S_PINS_OUT                     // This handles the case for the extra I2S output pin
    #define appconfNUM_I2S_PINS_OUT             1
#endif

#define MIC_ARRAY_CONFIG_USE_DC_ELIMINATION     1
#define MIC_ARRAY_CONFIG_SAMPLES_PER_FRAME      1

#define MIC_ARRAY_CONFIG_PDM_FREQ               3072000
#define MIC_ARRAY_CONFIG_MIC_IN_COUNT           8   // We use an 8b port
#define MIC_ARRAY_CONFIG_MIC_COUNT              4   // Of which we care about 4b
#define MIC_ARRAY_CONFIG_USE_DDR                0

#define appconfSHF_NOMINAL_HZ                   16000

// If unset, burn command will not actually enable burn
#define appconfBURN_MODE_SUPPORTED              1

/* App control plane configuration */
#define appconfI2C_MASTER_RATE_KHZ              100
#ifndef appconfSPI_CTRL_ENABLED
    #define appconfSPI_CTRL_ENABLED 0 //spi control is disabled by default
#endif
#ifndef appconfI2C_CTRL_ENABLED
    #define appconfI2C_CTRL_ENABLED 0 //i2c control is disabled by default
#endif

#ifndef appconfUSB_CTRL_ENABLED
    #define appconfUSB_CTRL_ENABLED 0
#endif

#define APP_CONTROL_TRANSPORT_COUNT ((appconfSPI_CTRL_ENABLED) + (appconfI2C_CTRL_ENABLED) + (appconfUSB_CTRL_ENABLED))

#define GPI_DEBOUNCE_MS                         25

/* Intertile port settings under RTOS */
#define appconfRPC_DATA_PORT                    10

/* FreeRTOS Task Priorities */
#define appconfSTARTUP_TASK_PRIORITY            (configMAX_PRIORITIES - 2)
#define appconfTEST_TASK_PRIORITY               (configMAX_PRIORITIES - 1)
#define appconfRPC_TASK_PRIORITY                (configMAX_PRIORITIES - 2)

#define appconfDEVICE_CONTROL_I2C_PORT          1
#define appconfDEVICE_CONTROL_USB_PORT          2
#define appconfDEVICE_CONTROL_SPI_PORT          3
#define appconfDEVICE_CONTROL_GPIO_PORT         4
#define appconfUSB_MANAGER_SYNC_PORT            5
#define appconfUSB_COMMUNICATE_PLL_STATUS_PORT  6

/* Task Priorities */
#define appconfDEVICE_CONTROL_I2C_CLIENT_PRIORITY   (configMAX_PRIORITIES-1)
#define appconfDEVICE_CONTROL_SPI_CLIENT_PRIORITY   (configMAX_PRIORITIES-1)
#define appconfDEVICE_CONTROL_GPIO_CLIENT_PRIORITY   (configMAX_PRIORITIES-1)
#define appconfDEVICE_CONTROL_USB_CLIENT_PRIORITY   (configMAX_PRIORITIES-1)

/* XCORE resources */

/* Ports */
#define MIC_ARRAY_CONFIG_PORT_MCLK              PORT_PDM_MCLK
#define MIC_ARRAY_CONFIG_PORT_PDM_CLK           PORT_PDM_CLK
#define MIC_ARRAY_CONFIG_PORT_PDM_DATA          PORT_PDM_DATA
/* See also modules/fwk_xvf/modules/bsp/XK-VOICE-SQ66-EVK/xvf3800_qf60.xn for port map */

/* Port bit assignments for multi-bit ports */
/* GPO Tile[0] Port 8C pinout  Bits 0..2 inclusive are not pinned out */
#define GPO_DAC_RST_N_PIN                       3
#define GPO_SQ_nLIN_PIN                         4
#define GPO_INT_N_PIN                           5
#define GPO_LED_RED_PIN                         6
#define GPO_LED_GREEN_PIN                       7

/* Clock blocks */
/* tile 0 */
#define MIC_ARRAY_CONFIG_CLOCK_BLOCK_A          XS1_CLKBLK_1 // Only one block used for SDR mics
#define SPI_SLAVE_CLKBLK                        XS1_CLKBLK_2
#define FLASH_CLKBLK                            XS1_CLKBLK_3
#define RESERVED_FOR_XUD_A                      XS1_CLKBLK_4 // Defined within lib_xud
#define RESERVED_FOR_XUD_B                      XS1_CLKBLK_5 // Defined within lib_xud

/* tile 1 */
#define MCLK_CLKBLK                             XS1_CLKBLK_1 // Used for sw_pll
#define UNUSED_CLKBLK_CC                        XS1_CLKBLK_2
#define I2S_CLKBLK                              XS1_CLKBLK_3
#define UNUSED_CLKBLK_EE                        XS1_CLKBLK_4
#define UNUSED_CLKBLK_FF                        XS1_CLKBLK_5

/* Software PLL settings for mclk recovery configurations */
/* see fractions.h and register_setup.h for other pll settings */
#define PLL_RATIO                   (MIC_ARRAY_CONFIG_MCLK_FREQ / appconfLRCLK_NOMINAL_HZ)
#define PLL_CONTROL_LOOP_COUNT_UA   80   // How many SoF periods per control loop iteration. Aim for ~100Hz
#define PLL_CONTROL_LOOP_COUNT_INT  512  // How many refclk ticks (LRCLK) per control loop iteration. Aim for ~100Hz
#define PLL_PPM_RANGE               1000 // Max allowable diff in clk count. For the PID constants we
                                         // have chosen, this number should be larger than the number
                                         // of elements in the look up table as the clk count diff is
                                         // added to the LUT index with a multiplier of 1. Only used for INT mclkless


// Max sample delay on reference signal
#define appconfMAX_SYS_DELAY                    256
// Max delay on the microphones, note that there are 4 mics so this has
// potentially significant memory impact.
#define appconfMAX_MIC_DELAY                    64

/* Logical cores */
#if ON_TILE(0)
/*  Bare metal task summary
    3 HP for PP
    1 NP for mic_array
    2 NP for USB XUD and buffer (UA only)

    FreeRTOS logical cores
    4 NP for INT (one or two of which will be a slave control peripheral)
    1 NP for UA
*/
#if (appconfUSB_ENABLED == 0)
#define appconfNUM_FREE_RTOS_CORES              4
#else
#define appconfNUM_FREE_RTOS_CORES              2
#endif
#define appconfTOTAL_HEAP_SIZE                  (23 * 1024)

#elif ON_TILE(1)
/*  Bare metal task summary
    4 HP for AEC
    1 NP for i2s/audio
    1 NP for customer DSP
    1 spare

    FreeRTOS logical cores
    1 NP
*/
#define appconfNUM_FREE_RTOS_CORES              1
#if IO_EXPANDER_ENABLED
    #define appconfTOTAL_HEAP_SIZE                  (24 * 1024)
#else
    #define appconfTOTAL_HEAP_SIZE                  (22 * 1024)
#endif
#ifndef RESERVE_USER_MEMORY
#error
#endif

#if RESERVE_USER_MEMORY
#define USER_MEMORY_RESERVED_BYTES              (17 * 1024) // Placeholder for user DSP and control code. See https://github.com/xmos/sw_xvf3800/issues/74
#else
#define USER_MEMORY_RESERVED_BYTES              1  // used as array size so must be non-zero
#endif

#else
#error Not configured for more than 2 tiles
#endif

// Check the rate matches with BeClear at compile time
// This macro looks odd but it is the only way to check a float value at compile time. Credit: Daniel and the Linux kernel
#define STATIC_INT_FLOAT_EQUALITY_CHECK(I, V)    typedef char assert_var[2*!!(I == V)-1];
STATIC_INT_FLOAT_EQUALITY_CHECK(appconfSHF_NOMINAL_HZ, BECLEAR_SAMPLE_FREQUENCY)

#ifndef appconfUSB_AUDIO_SAMPLE_RATE
#define appconfUSB_AUDIO_SAMPLE_RATE appconfUSB_IN_OUT_NOMINAL_HZ
#define appconfAUDIO_PIPELINE_FRAME_ADVANCE     256
#endif


#include "aec_cmds.h"
#define SHF_AEC_FAR_EXTGAIN_CMD BECLEAR_SUPERHANDSFREE_AEC_FAR_EXTGAIN // This command is internally programmed in tud_audio_set_req_entity_cb() when the external gain is applied by the host on the ref signal.
// The command ID define is different between the WB and SWB Beclear versions, so we declare a define that is accessed by tud_audio_set_req_entity_cb() in fwk_xvf to get the
// correct command ID define depending whether we're running the WB or SWB application.

#endif /* APP_CONF_H_ */
