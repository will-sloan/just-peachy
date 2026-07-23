// Copyright 2021-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#ifndef DAC3101_H_
#define DAC3101_H_

#include <stdint.h>

// TLV320DAC3101 Device I2C Address
#define DAC3101_I2C_DEVICE_ADDR 0x18

// TLV320DAC3101 Register Addresses
// Page 0
#define DAC3101_PAGE_CTRL     0x00 // Register 0 - Page Control
#define DAC3101_SW_RST        0x01 // Register 1 - Software Reset
#define DAC3101_CLK_GEN_MUX   0x04 // Register 4 - Clock-Gen Muxing
#define DAC3101_PLL_P_R       0x05 // Register 5 - PLL P and R Values
#define DAC3101_PLL_J         0x06 // Register 6 - PLL J Value
#define DAC3101_PLL_D_MSB     0x07 // Register 7 - PLL D Value (MSB)
#define DAC3101_PLL_D_LSB     0x08 // Register 8 - PLL D Value (LSB)
#define DAC3101_NDAC_VAL      0x0B // Register 11 - NDAC Divider Value
#define DAC3101_MDAC_VAL      0x0C // Register 12 - MDAC Divider Value
#define DAC3101_DOSR_VAL_MSB  0x0D // Register 13 - DOSR Divider Value (MS Byte)
#define DAC3101_DOSR_VAL_LSB  0x0E // Register 14 - DOSR Divider Value (LS Byte)
#define DAC3101_CLKOUT_MUX    0x19 // Register 25 - CLKOUT MUX
#define DAC3101_CLKOUT_M_VAL  0x1A // Register 26 - CLKOUT M_VAL
#define DAC3101_CODEC_IF      0x1B // Register 27 - CODEC Interface Control
#define DAC3101_B_DIV_VAL     0x1E // Register 30 - BCLK Divider
#define DAC3101_DAC_PROC_BLK  0x3C // Register 60 - DAC Processing Block selection
#define DAC3101_DAC_DAT_PATH  0x3F // Register 63 - DAC Data Path Setup
#define DAC3101_DAC_VOL       0x40 // Register 64 - DAC Vol Control
#define DAC3101_DACL_VOL_D    0x41 // Register 65 - DAC Left Digital Vol Control
#define DAC3101_DACR_VOL_D    0x42 // Register 66 - DAC Right Digital Vol Control
#define DAC3101_GPIO1_IO      0x33 // Register 51 - GPIO1 In/Out Pin Control
// Page 1
#define DAC3101_HP_DRVR       0x1F // Register 31 - Headphone Drivers
#define DAC3101_SPK_AMP       0x20 // Register 32 - Class-D Speaker Amp
#define DAC3101_HP_DEPOP      0x21 // Register 33 - Headphone Driver De-pop
#define DAC3101_DAC_OP_MIX    0x23 // Register 35 - DAC_L and DAC_R Output Mixer Routing
#define DAC3101_HPL_VOL_A     0x24 // Register 36 - Analog Volume to HPL
#define DAC3101_HPR_VOL_A     0x25 // Register 37 - Analog Volume to HPR
#define DAC3101_SPKL_VOL_A    0x26 // Register 38 - Analog Volume to Left Speaker
#define DAC3101_SPKR_VOL_A    0x27 // Register 39 - Analog Volume to Right Speaker
#define DAC3101_HPL_DRVR      0x28 // Register 40 - Headphone Left Driver
#define DAC3101_HPR_DRVR      0x29 // Register 41 - Headphone Right Driver
#define DAC3101_SPKL_DRVR     0x2A // Register 42 - Left Class-D Speaker Driver
#define DAC3101_SPKR_DRVR     0x2B // Register 43 - Right Class-D Speaker Driver
// Page 8
#define DAC3101_L_BQD_A_N0_HI 0x02 // Register 02 - Left Biquad A Coeff. N0 High Bits
#define DAC3101_L_BQD_A_N0_LO 0x03 // Register 03 - Left Biquad A Coeff. N0 Low Bits
#define DAC3101_L_BQD_A_N1_HI 0x04 // Register 04 - Left Biquad A Coeff. N1 High Bits
#define DAC3101_L_BQD_A_N1_LO 0x05 // Register 05 - Left Biquad A Coeff. N1 Low Bits
#define DAC3101_L_BQD_A_N2_HI 0x06 // Register 06 - Left Biquad A Coeff. N2 High Bits
#define DAC3101_L_BQD_A_N2_LO 0x07 // Register 07 - Left Biquad A Coeff. N2 Low Bits
#define DAC3101_L_BQD_A_D1_HI 0x08 // Register 08 - Left Biquad A Coeff. D1 High Bits
#define DAC3101_L_BQD_A_D1_LO 0x09 // Register 09 - Left Biquad A Coeff. D1 Low Bits
#define DAC3101_L_BQD_A_D2_HI 0x0A // Register 10 - Left Biquad A Coeff. D2 High Bits
#define DAC3101_L_BQD_A_D2_LO 0x0B // Register 11 - Left Biquad A Coeff. D2 Low Bits
#define DAC3101_R_BQD_A_N0_HI 0x42 // Register 66 - Right Biquad A Coeff. N0 High Bits
#define DAC3101_R_BQD_A_N0_LO 0x43 // Register 67 - Right Biquad A Coeff. N0 Low Bits
#define DAC3101_R_BQD_A_N1_HI 0x44 // Register 68 - Right Biquad A Coeff. N1 High Bits
#define DAC3101_R_BQD_A_N1_LO 0x45 // Register 69 - Right Biquad A Coeff. N1 Low Bits
#define DAC3101_R_BQD_A_N2_HI 0x46 // Register 70 - Right Biquad A Coeff. N2 High Bits
#define DAC3101_R_BQD_A_N2_LO 0x47 // Register 71 - Right Biquad A Coeff. N2 Low Bits
#define DAC3101_R_BQD_A_D1_HI 0x48 // Register 72 - Right Biquad A Coeff. D1 High Bits
#define DAC3101_R_BQD_A_D1_LO 0x49 // Register 73 - Right Biquad A Coeff. D1 Low Bits
#define DAC3101_R_BQD_A_D2_HI 0x4A // Register 74 - Right Biquad A Coeff. D2 High Bits
#define DAC3101_R_BQD_A_D2_LO 0x4B // Register 75 - Right Biquad A Coeff. D2 Low Bits

#define DAC3101_L_BQD_B_N0_HI 0x0C // Register 12 - Left Biquad B Coeff. N0 High Bits
#define DAC3101_L_BQD_B_N0_LO 0x0D // Register 13 - Left Biquad B Coeff. N0 Low Bits
#define DAC3101_L_BQD_B_N1_HI 0x0E // Register 14 - Left Biquad B Coeff. N1 High Bits
#define DAC3101_L_BQD_B_N1_LO 0x0F // Register 15 - Left Biquad B Coeff. N1 Low Bits
#define DAC3101_L_BQD_B_N2_HI 0x10 // Register 16 - Left Biquad B Coeff. N2 High Bits
#define DAC3101_L_BQD_B_N2_LO 0x11 // Register 17 - Left Biquad B Coeff. N2 Low Bits
#define DAC3101_L_BQD_B_D1_HI 0x12 // Register 18 - Left Biquad B Coeff. D1 High Bits
#define DAC3101_L_BQD_B_D1_LO 0x13 // Register 19 - Left Biquad B Coeff. D1 Low Bits
#define DAC3101_L_BQD_B_D2_HI 0x14 // Register 20 - Left Biquad B Coeff. D2 High Bits
#define DAC3101_L_BQD_B_D2_LO 0x15 // Register 21 - Left Biquad B Coeff. D2 Low Bits
#define DAC3101_R_BQD_B_N0_HI 0x4C // Register 76 - Right Biquad B Coeff. N0 High Bits
#define DAC3101_R_BQD_B_N0_LO 0x4D // Register 77 - Right Biquad B Coeff. N0 Low Bits
#define DAC3101_R_BQD_B_N1_HI 0x4E // Register 78 - Right Biquad B Coeff. N1 High Bits
#define DAC3101_R_BQD_B_N1_LO 0x4F // Register 79 - Right Biquad B Coeff. N1 Low Bits
#define DAC3101_R_BQD_B_N2_HI 0x50 // Register 80 - Right Biquad B Coeff. N2 High Bits
#define DAC3101_R_BQD_B_N2_LO 0x51 // Register 81 - Right Biquad B Coeff. N2 Low Bits
#define DAC3101_R_BQD_B_D1_HI 0x52 // Register 82 - Right Biquad B Coeff. D1 High Bits
#define DAC3101_R_BQD_B_D1_LO 0x53 // Register 83 - Right Biquad B Coeff. D1 Low Bits
#define DAC3101_R_BQD_B_D2_HI 0x54 // Register 84 - Right Biquad B Coeff. D2 High Bits
#define DAC3101_R_BQD_B_D2_LO 0x55 // Register 85 - Right Biquad B Coeff. D2 Low Bits

#define DAC3101_L_BQD_C_N0_HI 0x16 // Register 22 - Left Biquad C Coeff. N0 High Bits
#define DAC3101_L_BQD_C_N0_LO 0x17 // Register 23 - Left Biquad C Coeff. N0 Low Bits
#define DAC3101_L_BQD_C_N1_HI 0x18 // Register 24 - Left Biquad C Coeff. N1 High Bits
#define DAC3101_L_BQD_C_N1_LO 0x19 // Register 25 - Left Biquad C Coeff. N1 Low Bits
#define DAC3101_L_BQD_C_N2_HI 0x1A // Register 26 - Left Biquad C Coeff. N2 High Bits
#define DAC3101_L_BQD_C_N2_LO 0x1B // Register 27 - Left Biquad C Coeff. N2 Low Bits
#define DAC3101_L_BQD_C_D1_HI 0x1C // Register 28 - Left Biquad C Coeff. D1 High Bits
#define DAC3101_L_BQD_C_D1_LO 0x1D // Register 29 - Left Biquad C Coeff. D1 Low Bits
#define DAC3101_L_BQD_C_D2_HI 0x1E // Register 30 - Left Biquad C Coeff. D2 High Bits
#define DAC3101_L_BQD_C_D2_LO 0x1F // Register 31 - Left Biquad C Coeff. D2 Low Bits
#define DAC3101_R_BQD_C_N0_HI 0x56 // Register 86 - Right Biquad C Coeff. N0 High Bits
#define DAC3101_R_BQD_C_N0_LO 0x57 // Register 87 - Right Biquad C Coeff. N0 Low Bits
#define DAC3101_R_BQD_C_N1_HI 0x58 // Register 88 - Right Biquad C Coeff. N1 High Bits
#define DAC3101_R_BQD_C_N1_LO 0x59 // Register 89 - Right Biquad C Coeff. N1 Low Bits
#define DAC3101_R_BQD_C_N2_HI 0x5A // Register 90 - Right Biquad C Coeff. N2 High Bits
#define DAC3101_R_BQD_C_N2_LO 0x5B // Register 91 - Right Biquad C Coeff. N2 Low Bits
#define DAC3101_R_BQD_C_D1_HI 0x5C // Register 92 - Right Biquad C Coeff. D1 High Bits
#define DAC3101_R_BQD_C_D1_LO 0x5D // Register 93 - Right Biquad C Coeff. D1 Low Bits
#define DAC3101_R_BQD_C_D2_HI 0x5E // Register 94 - Right Biquad C Coeff. D2 High Bits
#define DAC3101_R_BQD_C_D2_LO 0x5F // Register 95 - Right Biquad C Coeff. D2 Low Bits

/**
 * Initialize the DAC
 *
 * \param sample_rate  Sample rate in hz
 *
 * \returns   0 on success
 *            -1 otherwise
 */
int dac3101_init(uint32_t sample_rate);

/**
 * User defined function to perform the reg write
 *
 * \returns   0 on success
 *            -1 otherwise
 */
int dac3101_reg_write(uint8_t reg, uint8_t val);

/**
 * User defined function to perform the reset the device
 */
void dac3101_codec_reset(void* args);

/**
 * User defined function to perform a wait
 *
 * When called, this function must not return until
 * at least wait_ms milliseconds has passed
 */
void dac3101_wait(uint32_t wait_ms);

#endif /* DAC3101_H_ */
