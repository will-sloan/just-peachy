// Copyright 2019-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
// Copy of minimal SPI slave implementation from ROM
#ifndef __spi_slave_h__
#define __spi_slave_h__

void spi_slave_initialise(void);

// returns number of words received
// will retry if chip select goes away too early or CRC fails
unsigned spi_slave_transaction_receive(unsigned *received_data,
                                       unsigned num_words);

void spi_slave_shutdown(void);

#endif

