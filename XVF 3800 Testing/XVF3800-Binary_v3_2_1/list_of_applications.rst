

*******************************
APPENDIX – List of applications
*******************************

The application file names are described here.

More information about the applications below can be found in the User Guide.

All paths are relative to the /binaries/ directory in the release package.

UA device applications
----------------------

====================================================================================   ======================================================================================
Build with USB audio at 16 kHz
====================================================================================   ======================================================================================
/usb/16kHz/application_xvf3800_ua-io16-lin.xe                                          linear microphone array, control over USB
/usb/16kHz/application_xvf3800_ua-io16-sqr.xe                                          square/rectangular microphone array, control over USB
====================================================================================   ======================================================================================

====================================================================================   ======================================================================================
Build with USB audio at 48 kHz
====================================================================================   ======================================================================================
/usb/48kHz/application_xvf3800_ua-io48-lin.xe                                          linear microphone array, control over USB
/usb/48kHz/application_xvf3800_ua-io48-sqr.xe                                          square/rectangular microphone array, control over USB
/additional/application_xvf3800_ua-io48-lin-io-exp.xe                                  linear microphone array, control over USB, and I2C-to-IO expander to control buttons and LEDs
/additional/application_xvf3800_ua-io48-lin-spatial.xe                                 linear microphone array, control over USB, and mapping of focused beams to stereo output
====================================================================================   ======================================================================================

INT device applications
-----------------------

====================================================================================   ======================================================================================
Build with I2S audio at 16 kHz
====================================================================================   ======================================================================================
/i2s/16kHz/i2c/application_xvf3800_intdev-lr16-lin-i2c.xe                              linear microphone array, control over I2C slave
/i2s/16kHz/i2c/application_xvf3800_intdev-lr16-sqr-i2c.xe                              square/rectangular microphone array, control over I2C slave
/i2s/16kHz/spi/application_xvf3800_intdev-lr16-lin-spi.xe                              linear microphone array, control over SPI slave
/i2s/16kHz/spi/application_xvf3800_intdev-lr16-sqr-spi.xe                              square/rectangular microphone array, control over SPI slave
/additional/external_master_clock/application_xvf3800_intdev-lr16-lin-i2c-extmclk.xe   linear microphone array, control over I2C slave, and external Master clock
/additional/external_master_clock/application_xvf3800_intdev-lr16-sqr-i2c-extmclk.xe   square/rectangular microphone array, control over I2C slave, and external Master clock
/additional/external_master_clock/application_xvf3800_intdev-lr16-lin-spi-extmclk.xe   linear microphone array, control over SPI slave, and external Master clock
/additional/external_master_clock/application_xvf3800_intdev-lr16-sqr-spi-extmclk.xe   square/rectangular microphone array, control over SPI slave, and external Master clock
====================================================================================   ======================================================================================

====================================================================================   ======================================================================================
Build with I2S audio at 48 kHz
====================================================================================   ======================================================================================
/additional/application_xvf3800_intdev-lr48-lin-i2c-spatial.xe                         linear microphone array, control over I2C slave, and mapping of focused beams to stereo output
/i2s/48kHz/i2c/application_xvf3800_intdev-lr48-lin-i2c.xe                              linear microphone array, control over I2C slave
/i2s/48kHz/i2c/application_xvf3800_intdev-lr48-sqr-i2c.xe                              square/rectangular microphone array, control over I2C slave
/i2s/48kHz/spi/application_xvf3800_intdev-lr48-lin-spi.xe                              linear microphone array, control over SPI slave
/i2s/48kHz/spi/application_xvf3800_intdev-lr48-sqr-spi.xe                              square/rectangular microphone array, control over SPI slave
/additional/external_master_clock/application_xvf3800_intdev-lr48-lin-i2c-extmclk.xe   linear microphone array, control over I2C slave, and external Master CLK
/additional/external_master_clock/application_xvf3800_intdev-lr48-sqr-i2c-extmclk.xe   square/rectangular microphone array, control over I2C slave, and external Master CLK
/additional/external_master_clock/application_xvf3800_intdev-lr48-lin-spi-extmclk.xe   linear microphone array, control over SPI slave, and external Master CLK
/additional/external_master_clock/application_xvf3800_intdev-lr48-sqr-spi-extmclk.xe   square/rectangular microphone array, control over SPI slave, and external Master CLK
====================================================================================   ======================================================================================

