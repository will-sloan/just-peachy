// Copyright 2024 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#define DEBUG_UNIT DFU_COMMON
#ifndef DEBUG_PRINT_ENABLE_DFU_COMMON
#define DEBUG_PRINT_ENABLE_DFU_COMMON 0
#endif
#include "debug_print.h"

#include <stddef.h>
#include <stdint.h>
#include "quadflashlib.h"

#include "dfu_common.h"
#include "rtos_dfu_image.h"
#include "rtos_qspi_flash.h"
#include "platform/driver_instances.h"

static size_t bytes_avail = 0;
static uint32_t dn_base_addr = 0;
static int erase_counter = 0;
static size_t total_len = 0;

uint32_t dfu_common_write_to_flash(uint8_t alt,
                                   uint16_t block_num,
                                   uint8_t const *data,
                                   uint16_t length)
{
    debug_printf("Received Alt %d Block %d length %d\n", alt, block_num, length);
    rtos_dfu_image_t *dfu_image_ctx = get_dfu_image_ctx();
    rtos_qspi_flash_t *qspi_ctx = get_qspi_flash_ctx();
    uint32_t return_value = 0;

    // rtos_dfu_image_print_debug(dfu_image_ctx);
    unsigned dp_base_ad = rtos_dfu_image_get_data_partition_addr(dfu_image_ctx);
    switch (alt)
    {
    default:
    case 0:
        return_value = 3; // DFU_STATUS_ERR_WRITE
        break;
    case 1:
        if (dn_base_addr == 0)
        {
            total_len = 0;
            dn_base_addr = rtos_dfu_image_get_upgrade_addr(dfu_image_ctx);
            bytes_avail = dp_base_ad - dn_base_addr;
        }
        debug_printf("Using addr 0x%x\nsize %u\n", dn_base_addr, bytes_avail);
        if (length > 0)
        {
            // Reset the erase counter at the first transfer block,
            // this allows a DFU download operation to be repeated without
            // rebooting the device
            if (block_num == 0)
            {
                erase_counter = 0;
            }
            unsigned cur_addr = dn_base_addr + (block_num * length);
            if ((bytes_avail - total_len) >= length)
            {
                size_t sector_sz = rtos_qspi_flash_sector_size_get(qspi_ctx);
                size_t page_sz = rtos_qspi_flash_page_size_get(qspi_ctx);
                int pages_per_sector = sector_sz / page_sz;
                xassert(length == page_sz);

                uint8_t *tmp_buf = rtos_osal_malloc(sizeof(uint8_t) * page_sz);
                rtos_qspi_flash_lock(qspi_ctx);
                {
                    memcpy(tmp_buf, data, length);
                    if (erase_counter == 0)
                    {
                        debug_printf("Erase %d at 0x%x\n", sector_sz, cur_addr);
                        rtos_qspi_flash_erase(
                            qspi_ctx,
                            cur_addr,
                            sector_sz);
                        erase_counter = pages_per_sector;
                    }
                    erase_counter--;
                    debug_printf("Write %d at 0x%x\n", length, cur_addr);
                    rtos_qspi_flash_write(
                        qspi_ctx,
                        (uint8_t *)tmp_buf,
                        cur_addr,
                        length);
                    // Add a delay if we are using the RPC interface,
                    // this happens when we are not running on the flash tile
                    #if !ON_TILE(FLASH_TILE_NO)
                    vTaskDelay(pdMS_TO_TICKS(DOWNLOAD_RPC_INTERFACE_DELAY_MS));
                    #endif
                }
                rtos_qspi_flash_unlock(qspi_ctx);
                rtos_osal_free(tmp_buf);
                total_len += length;
            }
            else
            {
                debug_printf("Insufficient space\n");
                return_value = 8; // DFU_STATUS_ERR_ADDRESS
            }
        }
        break;
    }
    return return_value;
}

uint32_t dfu_common_make_manifest()
{
    debug_printf("Download completed, enter manifestation\n");
    rtos_qspi_flash_t *qspi_flash_ctx = get_qspi_flash_ctx();

    /* Perform a read to ensure all writes have been flushed */
    uint32_t dummy = 0;
    rtos_qspi_flash_read(
        qspi_flash_ctx,
        (uint8_t *)&dummy,
        0,
        sizeof(dummy));

    /* Reset download */
    dn_base_addr = 0;

    // flashing op for manifest is complete without error
    // Application can perform checksum.
    // Should it fail, return appropriate status such as errVERIFY.
    return 0; // DFU_STATUS_OK
}

uint16_t dfu_common_read_from_flash(uint8_t alt,
                                    uint16_t block_num,
                                    uint8_t *data,
                                    uint16_t length)
{
    debug_printf("In dfu_common_read_from_flash\n");
    uint32_t endaddr = 0;
    uint32_t addr = block_num * length;
    uint16_t retval = 0;

    debug_printf("Upload Alt %d Block %d length %d\n", alt, block_num, length);
    rtos_dfu_image_t *dfu_image_ctx = get_dfu_image_ctx();
    rtos_qspi_flash_t *qspi_flash_ctx = get_qspi_flash_ctx();

    switch (alt)
    {
    default:
        break;
    case 0:
        debug_printf("In case 0\n");
        if (rtos_dfu_image_get_factory_size(dfu_image_ctx) > 0)
        {
            debug_printf("Factory size > 0\n");
            addr += rtos_dfu_image_get_factory_addr(dfu_image_ctx);
            endaddr = (rtos_dfu_image_get_factory_addr(dfu_image_ctx) +
                       rtos_dfu_image_get_factory_size(dfu_image_ctx));
        }
        else
        {
            debug_printf("Factory size <= 0\n");
        }
        break;
    case 1:
        debug_printf("In case 1\n");
        if (rtos_dfu_image_get_upgrade_size(dfu_image_ctx) > 0)
        {
            debug_printf("Upgrade size > 0\n");
            addr += rtos_dfu_image_get_upgrade_addr(dfu_image_ctx);
            endaddr = (rtos_dfu_image_get_upgrade_addr(dfu_image_ctx) +
                       rtos_dfu_image_get_upgrade_size(dfu_image_ctx));
        }
        else
        {
            debug_printf("Upgrade size <= 0\n");
        }
        break;
    }

    debug_printf("Addr: %d, endaddr: %d\n", addr, endaddr);

    if (addr < endaddr)
    {
        rtos_qspi_flash_read(qspi_flash_ctx, data, addr, length);
        retval = length;
    }

    debug_printf("retval: %d\n", retval);

    return retval;
}
