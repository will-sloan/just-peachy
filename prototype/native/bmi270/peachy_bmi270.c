/* Linux I2C shim for the unmodified Bosch BMI270 SensorAPI. See README.md. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <linux/i2c.h>
#include <linux/i2c-dev.h>
#include <stdint.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>
#include "bmi270.h"

static int bus_fd = -1;
static uint16_t address;
static struct bmi2_dev sensor;

static int8_t read_regs(uint8_t reg, uint8_t *data, uint32_t len, void *ctx) {
    (void)ctx;
    if (len > 512) return -1;
    struct i2c_msg msg[2] = {{address, 0, 1, &reg}, {address, I2C_M_RD, (uint16_t)len, data}};
    struct i2c_rdwr_ioctl_data transfer = {msg, 2};
    return ioctl(bus_fd, I2C_RDWR, &transfer) == 2 ? 0 : -1;
}
static int8_t write_regs(uint8_t reg, const uint8_t *data, uint32_t len, void *ctx) {
    (void)ctx;
    uint8_t bytes[513];
    if (len > 512) return -1;
    bytes[0] = reg; memcpy(bytes + 1, data, len);
    struct i2c_msg msg = {address, 0, (uint16_t)(len + 1), bytes};
    struct i2c_rdwr_ioctl_data transfer = {&msg, 1};
    return ioctl(bus_fd, I2C_RDWR, &transfer) == 1 ? 0 : -1;
}
static void delay_us(uint32_t us, void *ctx) {
    (void)ctx;
    struct timespec delay = {us / 1000000, (us % 1000000) * 1000};
    while (nanosleep(&delay, &delay) && errno == EINTR) {}
}
void peachy_bmi_close(void) {
    if (bus_fd >= 0) { close(bus_fd); bus_fd = -1; }
}
int peachy_bmi_open(const char *path, int addr) {
    if (bus_fd >= 0 || (addr != 0x68 && addr != 0x69)) return -100;
    bus_fd = open(path, O_RDWR | O_CLOEXEC);
    if (bus_fd < 0) return -101;
    address = (uint16_t)addr;
    uint8_t id = 0;
    if (read_regs(0, &id, 1, 0) || id != 0x24) { peachy_bmi_close(); return -102; }
    memset(&sensor, 0, sizeof(sensor));
    sensor.intf = BMI2_I2C_INTF;
    sensor.read = read_regs; sensor.write = write_regs; sensor.delay_us = delay_us;
    sensor.read_write_len = 32;
    int8_t result = bmi270_init(&sensor);
    if (result) { peachy_bmi_close(); return result; }
    struct bmi2_sens_config cfg[2] = {{0}};
    cfg[0].type = BMI2_ACCEL; cfg[1].type = BMI2_GYRO;
    result = bmi2_get_sensor_config(cfg, 2, &sensor);
    if (!result) {
        cfg[0].cfg.acc.odr = BMI2_ACC_ODR_50HZ;
        cfg[0].cfg.acc.range = BMI2_ACC_RANGE_4G;
        cfg[0].cfg.acc.bwp = BMI2_ACC_NORMAL_AVG4;
        cfg[0].cfg.acc.filter_perf = BMI2_PERF_OPT_MODE;
        cfg[1].cfg.gyr.odr = BMI2_GYR_ODR_50HZ;
        cfg[1].cfg.gyr.range = BMI2_GYR_RANGE_500;
        cfg[1].cfg.gyr.bwp = BMI2_GYR_NORMAL_MODE;
        cfg[1].cfg.gyr.noise_perf = BMI2_PERF_OPT_MODE;
        cfg[1].cfg.gyr.filter_perf = BMI2_PERF_OPT_MODE;
        result = bmi2_set_sensor_config(cfg, 2, &sensor);
    }
    if (!result) {
        uint8_t sensors[] = {BMI2_ACCEL, BMI2_GYRO};
        result = bmi2_sensor_enable(sensors, 2, &sensor);
    }
    if (result) peachy_bmi_close();
    return result;
}
int peachy_bmi_read(double *values) {
    if (bus_fd < 0) return -103;
    struct bmi2_sens_data data = {0};
    int8_t result = bmi2_get_sensor_data(&data, &sensor);
    if (result) return result;
    if (!(data.status & BMI2_DRDY_ACC) || !(data.status & BMI2_DRDY_GYR)) return 1;
    values[0] = data.acc.x * (4. / 32768.);
    values[1] = data.acc.y * (4. / 32768.);
    values[2] = data.acc.z * (4. / 32768.);
    values[3] = data.gyr.x * (500. / 32768.);
    values[4] = data.gyr.y * (500. / 32768.);
    values[5] = data.gyr.z * (500. / 32768.);
    return 0;
}
