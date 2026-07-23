// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

/*
This utility is a fast, lightweight program to boot the XVF38X0 in the quickest
possible time from a Raspberry Pi host. It uses I2C to set the boot_sel mode
pin to boot the XVF38X0 from SPI slave, asserts reset and then sends the
bit-reversed binary in 4 kB blocks over SPI inserting pauses at two critical points
to allow the XVF38X0 boot process to complete internal tasks.

See the composer process (see generate_image.py) output which provides the <transfer_block_num>
argument which needs to be passed in the command line.

This utility has been tested to 50 MHz SPI clock speed and achieves boot times in the order 
of 160 ms on the XMOS hardware. Note that, depending on SI of the hardware used, a
higher or lower maximum rate may be achievable in your system.
*/

#include <stdio.h>
#include <stdint.h>
#include <unistd.h>
#include <string.h>
#include <unistd.h>
#include <stdlib.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/time.h>
#include <linux/types.h>
#include <linux/spi/spidev.h>
#include <linux/i2c-dev.h>
#include <linux/i2c.h>

#define SPI_BLOCK_SIZE      4096    // Fixed - do not modify
#define PLL_DELAY_MS        1       // Time to wait for PLL to settle
#define PLL_DELAY_BLOCK     1       // After which block to apply PLL wait. This is always 1
#define TRANSFER_DELAY_MS   5       // Time to wait for transfer from Tile[0] to Tile[1]

#define SPI_CHANNEL         0       // The SPI channel (CS number) used on RPI
#define I2C_BUS             1       // Which I2C peripheral to use on RPI
#define I2C_ADDRESS         0x20    // The slave address of the I2C IO expander on the XMOS board

double time_time(void)
{
   struct timeval tv;
   double t;
   gettimeofday(&tv, 0);
   t = (double)tv.tv_sec + ((double)tv.tv_usec / 1E6);
   return t;
}

int i2cOpen(int bus, int SlaveAddress)
{
    if(bus < 0 || bus > 1) return -1;

    char i2c_dev[32];
    sprintf(i2c_dev,"/dev/i2c-%d", bus);

    int i2c_fd = open(i2c_dev, O_RDWR);
    if(i2c_fd < 0)
    {
        printf("Failed to open the i2c bus \n");
        return -10;
    }

    // Ensure address is within valid range
    if(SlaveAddress < 1 || SlaveAddress > 0x7f) return -1;
    if (ioctl(i2c_fd, I2C_SLAVE, SlaveAddress) < 0)
    {
        printf("Failed to acquire bus access and/or talk to slave.\n");
        close(i2c_fd);
        return -11;
    }
    return i2c_fd;
}

int i2cClose(int i2c_fd)
{
   return close(i2c_fd);
}

int i2cWriteReg(int i2c_fd, uint8_t slave_addr, uint8_t reg, uint8_t data)
{
    int retval;
    uint8_t outbuf[2];

    struct i2c_msg msgs[1];
    struct i2c_rdwr_ioctl_data msgset[1];

    outbuf[0] = reg;
    outbuf[1] = data;

    msgs[0].addr = slave_addr;
    msgs[0].flags = 0;
    msgs[0].len = 2;
    msgs[0].buf = outbuf;

    msgset[0].msgs = msgs;
    msgset[0].nmsgs = 1;

    if (ioctl(i2c_fd, I2C_RDWR, &msgset) < 0) 
    {
        printf("ERROR: ioctl(I2C_RDWR) in i2c_write\n");
        return -1;
    }

    return 0;
}

int i2cReadReg(int i2c_fd, uint8_t slave_addr, uint8_t reg, uint8_t *result) 
{
    int retval;
    uint8_t outbuf[1], inbuf[1];
    struct i2c_msg msgs[2];
    struct i2c_rdwr_ioctl_data msgset[1];

    msgs[0].addr = slave_addr;
    msgs[0].flags = 0;
    msgs[0].len = 1;
    msgs[0].buf = outbuf;

    msgs[1].addr = slave_addr;
    msgs[1].flags = I2C_M_RD | I2C_M_NOSTART;
    msgs[1].len = 1;
    msgs[1].buf = inbuf;

    msgset[0].msgs = msgs;
    msgset[0].nmsgs = 2;

    outbuf[0] = reg;

    inbuf[0] = 0;

    *result = 0;
    if (ioctl(i2c_fd, I2C_RDWR, &msgset) < 0) {
        printf("ERROR: ioctl(I2C_RDWR) in i2c_read\n");
        return -1;
    }

    *result = inbuf[0];
    return 0;
}

int spiOpen(unsigned spiChan, unsigned spiBaud, unsigned spiFlags)
{
   int spi_fd;
   char spiMode;
   char spiBits  = 8;
   char dev[32];
   spiMode  = spiFlags & 3;
   spiBits  = 8;
   sprintf(dev, "/dev/spidev0.%d", spiChan);

   if ((spi_fd = open(dev, O_RDWR)) < 0)
   {
      return -1;
   }
   if (ioctl(spi_fd, SPI_IOC_WR_MODE, &spiMode) < 0)
   {
      close(spi_fd);
      return -2;
   }
   if (ioctl(spi_fd, SPI_IOC_WR_BITS_PER_WORD, &spiBits) < 0)
   {
      close(spi_fd);
      return -3;
   }
   if (ioctl(spi_fd, SPI_IOC_WR_MAX_SPEED_HZ, &spiBaud) < 0)
   {
      close(spi_fd);
      return -4;
   }
   return spi_fd;
}

int spiClose(int spi_fd)
{
   return close(spi_fd);
}

int spiWrite(int spi_fd, unsigned spi_clk_hz, uint8_t *buf, unsigned count)
{
   int err;
   struct spi_ioc_transfer spi;
   memset(&spi, 0, sizeof(spi));
   spi.tx_buf        = (unsigned) buf;
   spi.rx_buf        = (unsigned) NULL;
   spi.len           = count;
   spi.speed_hz      = spi_clk_hz;
   spi.delay_usecs   = 0;
   spi.bits_per_word = 8;
   spi.cs_change     = 0;
   err = ioctl(spi_fd, SPI_IOC_MESSAGE(1), &spi);
   return err;
}

void prepare_for_boot(void)
{
    #define IOEXP_OP_REG    0x01
    #define IOEXP_DIR_REG   0x03

    int i2c_fd = i2cOpen(I2C_BUS, I2C_ADDRESS);
    
    uint8_t dir_reg = 0;
    i2cReadReg(i2c_fd, I2C_ADDRESS, IOEXP_DIR_REG, &dir_reg);
    printf("read IOEXP_DIR_REG: 0x%x\n", dir_reg);
    dir_reg &= ~0x09; // enable reset and boot_sel drive. Low = output
    printf("writing IOEXP_DIR_REG: 0x%x\n", dir_reg);
    i2cWriteReg(i2c_fd, I2C_ADDRESS, IOEXP_DIR_REG, dir_reg);

    uint8_t output_reg = 0;
    i2cReadReg(i2c_fd, I2C_ADDRESS, IOEXP_OP_REG, &output_reg);
    printf("read IOEXP_OP_REG: 0x%x\n", output_reg);
    output_reg &= ~0x01; // asssert reset low
    output_reg |= 0x08;//  and boot_sel high
    printf("writing IOEXP_OP_REG: 0x%x\n", output_reg);
    i2cWriteReg(i2c_fd, I2C_ADDRESS, IOEXP_OP_REG, output_reg);

    usleep(5); // wait for reset to be latched (min width 5 us for reset in XMOS datasheet)

    dir_reg |= 0x01; // deassert reset
    printf("writing IOEXP_DIR_REG: 0x%x\n", dir_reg);
    i2cWriteReg(i2c_fd, I2C_ADDRESS, IOEXP_DIR_REG, dir_reg);

    usleep(PLL_DELAY_MS * 1000); // wait 1 ms (PLL settle after boot)
    
    i2cClose(i2c_fd);
}

void complete_boot(void)
{
    int i2c_fd = i2cOpen(I2C_BUS, I2C_ADDRESS);

    uint8_t dir_reg = 0;
    i2cReadReg(i2c_fd, I2C_ADDRESS, IOEXP_DIR_REG, &dir_reg);
    printf("read IOEXP_DIR_REG: 0x%x\n", dir_reg);

    dir_reg |= 0x08; // deassert boot_sel
    printf("writing IOEXP_DIR_REG: 0x%x\n", dir_reg);
    i2cWriteReg(i2c_fd, I2C_ADDRESS, IOEXP_DIR_REG, dir_reg);

    i2cClose(i2c_fd);
}

void bitrev(uint8_t * array, size_t sz)
{
    const uint8_t bitrev_lookup[] = 
    { 
        0x00, 0x80, 0x40, 0xc0, 0x20, 0xa0, 0x60, 0xe0, 
        0x10, 0x90, 0x50, 0xd0, 0x30, 0xb0, 0x70, 0xf0, 
        0x08, 0x88, 0x48, 0xc8, 0x28, 0xa8, 0x68, 0xe8, 
        0x18, 0x98, 0x58, 0xd8, 0x38, 0xb8, 0x78, 0xf8, 
        0x04, 0x84, 0x44, 0xc4, 0x24, 0xa4, 0x64, 0xe4, 
        0x14, 0x94, 0x54, 0xd4, 0x34, 0xb4, 0x74, 0xf4, 
        0x0c, 0x8c, 0x4c, 0xcc, 0x2c, 0xac, 0x6c, 0xec, 
        0x1c, 0x9c, 0x5c, 0xdc, 0x3c, 0xbc, 0x7c, 0xfc, 
        0x02, 0x82, 0x42, 0xc2, 0x22, 0xa2, 0x62, 0xe2, 
        0x12, 0x92, 0x52, 0xd2, 0x32, 0xb2, 0x72, 0xf2, 
        0x0a, 0x8a, 0x4a, 0xca, 0x2a, 0xaa, 0x6a, 0xea, 
        0x1a, 0x9a, 0x5a, 0xda, 0x3a, 0xba, 0x7a, 0xfa, 
        0x06, 0x86, 0x46, 0xc6, 0x26, 0xa6, 0x66, 0xe6, 
        0x16, 0x96, 0x56, 0xd6, 0x36, 0xb6, 0x76, 0xf6, 
        0x0e, 0x8e, 0x4e, 0xce, 0x2e, 0xae, 0x6e, 0xee, 
        0x1e, 0x9e, 0x5e, 0xde, 0x3e, 0xbe, 0x7e, 0xfe, 
        0x01, 0x81, 0x41, 0xc1, 0x21, 0xa1, 0x61, 0xe1, 
        0x11, 0x91, 0x51, 0xd1, 0x31, 0xb1, 0x71, 0xf1, 
        0x09, 0x89, 0x49, 0xc9, 0x29, 0xa9, 0x69, 0xe9, 
        0x19, 0x99, 0x59, 0xd9, 0x39, 0xb9, 0x79, 0xf9, 
        0x05, 0x85, 0x45, 0xc5, 0x25, 0xa5, 0x65, 0xe5, 
        0x15, 0x95, 0x55, 0xd5, 0x35, 0xb5, 0x75, 0xf5, 
        0x0d, 0x8d, 0x4d, 0xcd, 0x2d, 0xad, 0x6d, 0xed, 
        0x1d, 0x9d, 0x5d, 0xdd, 0x3d, 0xbd, 0x7d, 0xfd, 
        0x03, 0x83, 0x43, 0xc3, 0x23, 0xa3, 0x63, 0xe3, 
        0x13, 0x93, 0x53, 0xd3, 0x33, 0xb3, 0x73, 0xf3, 
        0x0b, 0x8b, 0x4b, 0xcb, 0x2b, 0xab, 0x6b, 0xeb, 
        0x1b, 0x9b, 0x5b, 0xdb, 0x3b, 0xbb, 0x7b, 0xfb, 
        0x07, 0x87, 0x47, 0xc7, 0x27, 0xa7, 0x67, 0xe7, 
        0x17, 0x97, 0x57, 0xd7, 0x37, 0xb7, 0x77, 0xf7, 
        0x0f, 0x8f, 0x4f, 0xcf, 0x2f, 0xaf, 0x6f, 0xef, 
        0x1f, 0x9f, 0x5f, 0xdf, 0x3f, 0xbf, 0x7f, 0xff
    };

    for(int i = 0; i < sz; i++){
        array[i] = bitrev_lookup[array[i]];
    }
}

void parse_args(int argc, char * argv[], char *fname, int *spi_clk_hz, int *transfer_block_num)
{
    if (argc != 4){
        printf("Usage: %s <filename> <spi_speed_hz> <transfer_block_num>\n", argv[0]);
        printf("The composer process (see generate_image.py) provides the <transfer_block_num> argument.\n\n");
        exit(1);
    }
    strcpy(fname, argv[1]);
    *spi_clk_hz = atoi(argv[2]);
    *transfer_block_num = atoi(argv[3]);
}

int load_bin(char *fname, uint8_t **bin_ptr)
{
    FILE *fp = fopen(fname, "rb");
    fseek(fp, 0L, SEEK_END);
    size_t sz = ftell(fp);
    fseek(fp, 0L, SEEK_SET);
    uint8_t *bin = malloc(sz);
    fread(bin, sz, 1, fp);
    fclose(fp);
    *bin_ptr = bin;
    bitrev(bin, sz);

    int num_blocks = sz / SPI_BLOCK_SIZE;
    int remainder = sz % SPI_BLOCK_SIZE;
    printf("Loaded bit-reversed binary with %d blocks of %d kB. %d Bytes leftover.\n", num_blocks, SPI_BLOCK_SIZE, remainder);

    if(remainder != 0)
    {
        printf("Error: binary size should be a multiple of %d Bytes\n", SPI_BLOCK_SIZE);
        exit(2);
    }

    return num_blocks;
}

void transmit_binary(int num_blocks, int transfer_block_num, int spi_clk_hz, uint8_t *bin )
{
    int spi_fd = spiOpen(SPI_CHANNEL, spi_clk_hz, 0);
    if (spi_fd < 0){
        printf("Error opening SPI device: %d\n", spi_fd);
        exit(3);
    }

    for (int i = 0; i < num_blocks; i++)
    {
        if(i == PLL_DELAY_BLOCK) {
            printf("PLL delay: %d ms after block %d.\n", PLL_DELAY_MS, i);    
            usleep(PLL_DELAY_MS * 1000); // PLL delay after reboot
        }
        if(i == transfer_block_num){
            printf("Transfer delay: %d ms after block %d.\n", TRANSFER_DELAY_MS, i);
            usleep(TRANSFER_DELAY_MS * 1000);
        }

        // Work out which block we need to point to
        uint8_t *bin_ptr = bin + SPI_BLOCK_SIZE * i;
        spiWrite(spi_fd, spi_clk_hz, bin_ptr, SPI_BLOCK_SIZE);

        // This was found to be needed on RPi4
        usleep(5);
    }
    spiClose(spi_fd);
}

int main(int argc, char * argv[])
{
    char fname[512]; //Allow long paths for CI etc.
    int spi_clk_hz;
    int transfer_block_num = 0;
    parse_args(argc, argv, fname, &spi_clk_hz, &transfer_block_num);

    printf("Transmitting file %s at %d bps.\n", fname, spi_clk_hz);

    uint8_t *bin = NULL;
    int num_blocks = load_bin(fname, &bin);

    prepare_for_boot();

    // tmp debug
    usleep(500 * 1000);
    
    double start, diff, sps;
    start = time_time();

    transmit_binary(num_blocks, transfer_block_num, spi_clk_hz, bin);

    diff = time_time() - start;
    printf("Sent %d bytes @ %d bps (requested) time=%.3f s\n", SPI_BLOCK_SIZE * num_blocks, spi_clk_hz, diff);

    complete_boot();
    free(bin);

    return 0;
}
