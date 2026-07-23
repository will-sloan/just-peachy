#!/usr/bin/env python3
# Copyright 2019-2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.
# requires dtparam=spi=on in /boot/config.txt

"""
This script configures the XVF38xx board in boot from SPI slave and load a binary file.
It requires a bin file as input parameter
"""

import sys
import os
import time
import argparse
import spidev
import RPi.GPIO as GPIO
import smbus
from pathlib import Path
import subprocess

i2c_bus = smbus.SMBus(1)


if sys.version[0] != '3':
    print("Run this script with Python 3")
    sys.exit(1)

#Class to access the i2c io expanders
class io_expander_gpio:
    def __init__(self):
        self.xvf_rst_n =    (0,0)
        self.int_n =        (0,1)
        self.dac_rst_n =    (0,2)
        self.boot_sel =     (0,3)
        self.mclk_oe =      (0,4)
        self.spi_oe =       (0,5)
        self.i2s_oe =       (0,6)
        self.mute =         (0,7)
        self.port_out_regs = [1]
        self.port_dir_regs = [3]
        self.io_exp_addr = 0x20
        self.num_regs = 4

    def get_oe_level(self):
        oe_level = 1
        return oe_level

    def set_pin(self, port_pin, level, enabled=True):
        """
        Enables an output and sets to a level on
        I2C expander. Leaves other signals alone

        Args:
        port_pin tuple of port idx followed by pin idx
        pin - 0..7
        level - 0 or 1
        enabled = sets direction register to 0 of true (enables op) otherwise 1=Hi Z
        """

        port_num = port_pin[0] #logical port number
        pin = port_pin[1]
        port_reg_out = self.port_out_regs[port_num] #i2c addr of reg
        port_reg_dir = self.port_dir_regs[port_num]

        #Current state of regs so we read-modify-write
        state = {}
        for i in range(self.num_regs):
            state[i] = i2c_bus.read_byte_data(self.io_exp_addr, i)
            # print(f"pre state {i}: 0x{state[i]:02x}")
        mask = 1 << pin

        #write enable bit
        if enabled:
            data_to_write = ~mask & state[port_reg_dir]
            i2c_bus.write_byte_data(self.io_exp_addr, port_reg_dir, data_to_write)
        else:
            data_to_write = mask | state[port_reg_dir]
            i2c_bus.write_byte_data(self.io_exp_addr, port_reg_dir, data_to_write)

        #write value
        if level != 0:
            data_to_write = state[port_reg_out] | mask
            i2c_bus.write_byte_data(self.io_exp_addr, port_reg_out, data_to_write)
        else:
            data_to_write = ~mask & state[port_reg_out]
            i2c_bus.write_byte_data(self.io_exp_addr, port_reg_out, data_to_write)

def prepare_for_boot(i2c_gpio):
    """
    Function to set XVF38xx board in SPI slave boot mode

    Args:
        io_expander_gpio object

    Returns:
        None
    """

    #Note these are quite slow so reset is asserted for a good millisecond
    i2c_gpio.set_pin(i2c_gpio.xvf_rst_n, 0) # assert reset
    i2c_gpio.set_pin(i2c_gpio.boot_sel, 1) # set BOOT_SEL high to select boot from SPI master
    i2c_gpio.set_pin(i2c_gpio.xvf_rst_n, 1, enabled=False) # deassert reset

def complete_boot(i2c_gpio):
    """
    Function to set XVF38xx board into normal run mode

    Args:
        io_expander_gpio object

    Returns:
        None

    """
    i2c_gpio.set_pin(i2c_gpio.boot_sel, 0) # disable BOOT_SEL

def send_image(bin_filename, verbose=False, max_spi_speed_mhz = 5, block_transfer_pause_ms = 1):
    """
    Function to send the given image to the device via SPI slave

    Args:
        bin_filename:   binary file containing the image to boot
        verbose:        flag to print debug printouts

    Returns:
        None
    """

    # Unload and reload the SPI drivers in case SPI control hasn't left the pins in the correct state
    # Alternatively, we could modify the bcm2835_spi_end() function that is called in the host app to leave the
    # pins in a state such that SpiDev works. This alternate fix is logged in https://github.com/xmos/sw_xvf3800/issues/29
    # and would involve changing the fwk_rtos/blob/develop/modules/sw_services/device_control/host/device_access_spi_rpi.c file.
    # I don't want to move to a new version of xcore_sdk as part of this PR so going with the driver unload/reload workaround for now.
    cmd = "sudo rmmod spidev"
    subprocess.run(cmd.split())
    cmd = "sudo rmmod spi_bcm2835"
    subprocess.run(cmd.split())
    cmd = "sudo modprobe spidev"
    subprocess.run(cmd.split())
    cmd = "sudo modprobe spi_bcm2835"
    subprocess.run(cmd.split())

    #setup SPI
    spi = spidev.SpiDev()
    bus_spi = 0
    device = 0
    spi.open(bus_spi, device)

    #SPI Settings
    spi.max_speed_hz = int(max_spi_speed_mhz * 1000000)
    spi.mode = 0b00 #XMOS supports 00 or 11

    spi_block_size = 4096 #Limitation in spidev and xfer2 doesn't work!

    i2c_gpio = io_expander_gpio()

    prepare_for_boot(i2c_gpio)

    def bit_reversed_byte(byte_to_reverse):
        """
        Function to reverse the bit-order of a byte

        Args:
            byte_to_reverse: byte to process

        Retruns:
            byte in reversed order
        """
        return int('{:08b}'.format(byte_to_reverse)[::-1], 2)


    # Create a table to map byte values to their bit-reversed values
    reverse_table  = [bit_reversed_byte(byte) for byte in range(256)]

    data = []
    with open(bin_filename, "rb") as f:
        bytes_read = f.read()
        data = list(bytes_read)
        binary_size = len(data)
        block_count = 0
        print('Read file "{0}" size: {1} Bytes'.format(args.bin_filename, binary_size))
        if binary_size % spi_block_size != 0:
            print("Warning - binary file not a multiple of {} - {} remainder".format( \
                  spi_block_size, binary_size % spi_block_size))
        while binary_size > 0:
            block = [reverse_table[byte] for byte in data[:spi_block_size]]
            del data[:spi_block_size]
            binary_size = len(data)
            if verbose:
                print("Sending {} Bytes in block {} checksum 0x{:X}".format( \
                      len(block), block_count, sum(block)))
            spi.xfer(block)

            if block_count == 0:
                # Long delay for PLL reboot
                time.sleep(0.1)
            elif binary_size > 0:
                time.sleep(block_transfer_pause_ms / 1000)
            block_count += 1
    spi.close()
    print("Sending complete")

    # Pause to allow for the device to boot up
    time.sleep(0.1)
    complete_boot(i2c_gpio)


if __name__ == "__main__":
    start_time = time.time()
    parser = argparse.ArgumentParser(description='Load an image via SPI slave from an RPi')
    parser.add_argument('bin_filename', help='binary file name')
    parser.add_argument('--max-spi-speed-mhz', type=float, default=5, \
                        help='Max SPI speed in MHz')
    parser.add_argument('--block-transfer-pause-ms', type=float, default=2, \
                        help='pause between SPI transfers in milliseconds, default 2ms') # block-transfer-pause-ms needs to be big enough to allow
                        # the transfer of FW image from one tile to the other. This happens in the loader code after receiving the last block of
                        # tile1 image and before receiving the first block of tile0 image. See https://github.com/xmos/sw_xvf3800/issues/896 for details.
    parser.add_argument('--verbose', action='store_true', \
                        help='print debug information')
    args = parser.parse_args()

    if not Path(args.bin_filename).is_file():
        print("Error: input file {} not found".format(args.bin_filename))
        exit(1)

    send_image(args.bin_filename, args.verbose, args.max_spi_speed_mhz, args.block_transfer_pause_ms)

    end_time = time.time()
    if args.verbose:
        print("Sending image took {:.3} seconds".format(end_time - start_time))
