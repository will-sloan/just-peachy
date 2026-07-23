#**********************
# Create alternative targets for device_control.
# The default targets supplied by fwk_rtos assume the use of the default USB driver, which we have here modified on tile[1].
# These two targets are copied and modified from rtos/modules/sw_services/usb and rtos/modules/sw_services/device_control.
#**********************

file(GLOB         TUSB_ROOT_SOURCES   ../rtos/modules/sw_services/usb/thirdparty/tinyusb_src/src/*.c)
file(GLOB_RECURSE TUSB_CLASS_SOURCES  ../rtos/modules/sw_services/usb/thirdparty/tinyusb_src/src/class/*/*.c)
file(GLOB_RECURSE TUSB_COMMON_SOURCES ../rtos/modules/sw_services/usb/thirdparty/tinyusb_src/src/common/*.c)
file(GLOB_RECURSE TUSB_DEVICE_SOURCES ../rtos/modules/sw_services/usb/thirdparty/tinyusb_src/src/device/*.c)

## Create library target
add_library(framework_rtos_sw_services_usb_nodriver INTERFACE)
target_sources(framework_rtos_sw_services_usb_nodriver
    INTERFACE
        ../rtos/modules/sw_services/usb/portable/dcd_xcore.c
        ../rtos/modules/sw_services/usb/portable/tusb_nstackwords.S
        ../rtos/modules/sw_services/usb/FreeRTOS/usb_support.c
        ${TUSB_ROOT_SOURCES}
        ${TUSB_CLASS_SOURCES}
        ${TUSB_COMMON_SOURCES}
        ${TUSB_DEVICE_SOURCES}
)
target_include_directories(framework_rtos_sw_services_usb_nodriver
    INTERFACE
        ../rtos/modules/sw_services/usb/api
        ../rtos/modules/sw_services/usb/portable
        ../rtos/modules/sw_services/usb/thirdparty/tinyusb_src/src
)
target_link_libraries(framework_rtos_sw_services_usb_nodriver
    INTERFACE
        lib_xud
        rtos::osal
        rtos::FreeRTOS::FreeRTOS_SMP
)
## These definitions are only needed while we our port is not upstreamed
target_compile_definitions(framework_rtos_sw_services_usb_nodriver
    INTERFACE
        CFG_TUSB_MCU=OPT_MCU_NONE
        CFG_TUSB_OS=OPT_OS_CUSTOM
        BOARD_DEVICE_RHPORT_NUM=0
        CFG_TUD_TASK_QUEUE_SZ=8
        TUP_DCD_ENDPOINT_MAX=12  ## RTOS_USB_ENDPOINT_COUNT_MAX
        TUP_RHPORT_HIGHSPEED=0x00
)

## Create an alias
add_library(rtos::sw_services::usb_nodriver ALIAS framework_rtos_sw_services_usb_nodriver)


## Create library target
add_library(framework_rtos_sw_services_device_control_nousbdriver INTERFACE)
target_sources(framework_rtos_sw_services_device_control_nousbdriver
    INTERFACE
        ../rtos/modules/sw_services/device_control/src/device_control.c
        ../rtos/modules/sw_services/device_control/src/resource_table.c
        ../rtos/modules/sw_services/device_control/transport/i2c/device_control_i2c.c
        ../rtos/modules/sw_services/device_control/transport/usb/device_control_usb.c
        ../rtos/modules/sw_services/device_control/transport/spi/device_control_spi.c
)
target_include_directories(framework_rtos_sw_services_device_control_nousbdriver
    INTERFACE
        ../rtos/modules/sw_services/device_control/api
        ../rtos/modules/sw_services/device_control/transport/i2c
        ../rtos/modules/sw_services/device_control/transport/usb
        ../rtos/modules/sw_services/device_control/transport/spi
)
target_link_libraries(framework_rtos_sw_services_device_control_nousbdriver
    INTERFACE
        rtos::osal
        rtos::drivers::i2c
        rtos::drivers::spi
        rtos::sw_services::usb_nodriver
)

## Create an alias
add_library(rtos::sw_services::device_control_nousbdriver ALIAS framework_rtos_sw_services_device_control_nousbdriver)
