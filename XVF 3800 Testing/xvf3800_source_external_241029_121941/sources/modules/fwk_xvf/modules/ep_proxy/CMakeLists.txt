add_library(ep_proxy_local INTERFACE)
target_sources(ep_proxy_local
    INTERFACE
        src/usb_proxy.c
)
target_include_directories(ep_proxy_local
    INTERFACE
        api
        api/local
)
target_link_libraries(ep_proxy_local
    INTERFACE
        rtos::sw_services::device_control
)

## Create an alias
add_library(fwk_xvf::ep_proxy_local ALIAS ep_proxy_local)

add_library(ep_proxy_remote INTERFACE)
target_sources(ep_proxy_remote
    INTERFACE
        src/usb_driver.c
)
target_include_directories(ep_proxy_remote
    INTERFACE
        api
        api/remote
)
target_link_libraries(ep_proxy_remote
    INTERFACE
        rtos::sw_services::device_control_nousbdriver
)

## Create an alias
add_library(fwk_xvf::ep_proxy_remote ALIAS ep_proxy_remote)

## USB design to enable a hybrid approach with the usb_buffer running as a bare metal thread
# Everything from fwk_rtos' usb driver except for rtos_usb.c which needs to be changed to enable hybrid
add_library(ep_hybrid INTERFACE)
target_sources(ep_hybrid
    INTERFACE
        src/usb_driver_hybrid.c
        ../rtos/modules/drivers/usb/src/xud_xfer_data.S
)
target_include_directories(ep_hybrid
    INTERFACE
        ../rtos/modules/drivers/usb/api
        ../rtos/modules/drivers/usb/src
)
target_link_libraries(ep_hybrid
    INTERFACE
        rtos::sw_services::device_control_nousbdriver
)

## Create an alias
add_library(fwk_xvf::ep_hybrid ALIAS ep_hybrid)
