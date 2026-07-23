
set(XVF3820_LIB sw_xvf3820_board_support_xvf3820_proto)


## Create custom board targets for application
add_library(${XVF3820_LIB} INTERFACE)
target_sources(${XVF3820_LIB}
    INTERFACE
        platform/driver_instances.c
        platform/platform_init.c
        platform/platform_start.c
        platform/app_pll_ctrl.c
)
target_include_directories(${XVF3820_LIB}
    INTERFACE
        ${CMAKE_CURRENT_LIST_DIR}
)
target_link_libraries(${XVF3820_LIB}
    INTERFACE
        core::general
        rtos::freertos
        rtos::drivers::general
        rtos::drivers::dfu_image
)
target_compile_definitions(${XVF3820_LIB}
    INTERFACE
        XCOREAI_EXPLORER=1
        PLATFORM_SUPPORTS_TILE_0=1
        PLATFORM_SUPPORTS_TILE_1=1
        PLATFORM_SUPPORTS_TILE_2=1
        PLATFORM_SUPPORTS_TILE_3=1
        PLATFORM_USES_TILE_0=1
        PLATFORM_USES_TILE_1=1
        PLATFORM_USES_TILE_2=1
        PLATFORM_USES_TILE_3=1
)


target_compile_options(${XVF3820_LIB}
    INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/xvf3820.xn
)
target_link_options(${XVF3820_LIB}
    INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/xvf3820.xn
)

## Create an alias
add_library(fwk_xvf::bsp_config::xvf3820_proto ALIAS ${XVF3820_LIB})
