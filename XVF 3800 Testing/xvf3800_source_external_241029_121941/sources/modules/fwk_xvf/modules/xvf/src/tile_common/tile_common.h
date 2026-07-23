// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.


#ifndef TILE_COMMON_H
#define TILE_COMMON_H

#include "FreeRTOS.h"
#include "xcore/channel.h"
#include <stdint.h>

#include <xcore/parallel.h>

#define SETSR(c)                asm volatile("setsr %0" : : "n"(c));   
#define CLRSR(c)                asm volatile("clrsr %0" : : "n"(c));
#define SET_HIGH_PRIORITY()     SETSR(XS1_SR_QUEUE_MASK)    // Force the xcore to schedule once every 5 processor clocks
#define SET_FAST_MODE()         SETSR(XS1_SR_FAST_MASK)     // Force the xcore to schedule even if blocked on event
#define CLEAR_KEDI()            CLRSR(XS1_SR_KEDI_MASK)

#define timeafter(A, B)         ((int)((B) - (A)) < 0)      // Macro for safely calculating of time event has passed


typedef struct {
	uint8_t tile;
	uint8_t id;
} tile_common_task_info_t;


/// @brief obedient task which will suffer the whims of the OS
/// @param args expects a tile_common_task_info_t
void tile_common_rtos_burn_thread(void* args);

/// @brief start the scheduler and run task_function in the OS
DECLARE_JOB(tile_common_start_rtos_app, (chanend_t, TaskFunction_t, UBaseType_t, void*))
void tile_common_start_rtos_app(chanend_t c, TaskFunction_t task_function, UBaseType_t task_stack, void* servicer_args);
void report_chanends(unsigned id);
void report_locks(unsigned id);

/// @brief Querey whether or not to use core burn 
/// @returns 1 if burn should be used, 0 if not
uint8_t get_core_burn_status(void);

/// @brief Querey whether or not we have booted from SPI slave
/// @returns 1 if SPI slave boot, 0 if not (Flash or JTAG)
uint8_t is_spi_slave_boot();

/// @brief Sets the core burn status magic flag and resets causing a reboot. Only callable from Tile[1] where the magic flag is held
/// @param 1 if burn should be used, 0 if not
void set_core_burn_status_and_reboot(uint8_t burn_status);

/// @brief reboot the package that called this function after delay ms 
/// @param delay a count in ms that will wait until the reboot happens
void reboot_xvf3800(unsigned delay);

#if ON_TILE(0)
/// @brief Sets the core burn status flag
/// @param 1 if burn should be used, 0 if not
void set_core_burn_status(uint8_t burn_status);

#else // ON_TILE(1)


/// @brief Sets the SPI slave status on tile[1]
/// @returns 1 if SPI slave boot, 0 if not (Flash or JTAG)
void set_spi_slave_boot_status(uint8_t);

#endif // ON_TILE(1)


/// @brief Sets the UA bit depth. Will ignore the command if not a valid bit depth
/// @param bit_depth_in 16, 24 or 32 
/// @param bit_depth_out 16, 24 or 32 
void set_usb_bit_depth(uint8_t bit_depth_in, uint8_t bit_depth_out);


/// @brief Querey the bit depth for a particular direction
/// @param bit_depth_in address to be written
/// @param bit_depth_out address to be written 
void get_usb_bit_depth(uint8_t *bit_depth_in, uint8_t *bit_depth_out);


#endif // TILE_COMMON_H
