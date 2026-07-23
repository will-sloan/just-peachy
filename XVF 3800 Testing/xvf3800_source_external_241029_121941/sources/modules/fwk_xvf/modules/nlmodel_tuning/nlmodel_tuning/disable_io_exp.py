# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.


import smbus
import time

def clear_io_expander():
    """
    Function to clear the I2C IO expander (Hi Z) XVF boards

    Args:
        bus - I2C access object

    Returns:
        None
    """
    bus = smbus.SMBus(1)
    # I2C expander bus address for XVF36XX and XVF3800 with PCAL6408A expander device
    I2C_EXPANDER_ADDRESS = 0x20

    # I2C expander register addresses 
    I2C_EXPANDER_CONFIGURATION_REG = 0x03
    I2C_EXPANDER_INTERRUPT_MASK_REG = 0x45

    # All GPIO Hi-Z
    bus.write_byte_data(I2C_EXPANDER_ADDRESS, I2C_EXPANDER_CONFIGURATION_REG, 0xff)
    time.sleep(0.1)

    # Disable all interrupts
    bus.write_byte_data(I2C_EXPANDER_ADDRESS, I2C_EXPANDER_INTERRUPT_MASK_REG, 0xff)


if __name__ == "__main__":
    clear_io_expander()
