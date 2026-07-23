## Create custom board targets for application
add_library(fwk_xvf_board_support_xk_voice_sq66_evk INTERFACE)
target_sources(fwk_xvf_board_support_xk_voice_sq66_evk
    INTERFACE
        platform/driver_instances.c
        platform/platform_init.c
        platform/platform_start.c
        platform/app_pll_ctrl.c
)
target_include_directories(fwk_xvf_board_support_xk_voice_sq66_evk
    INTERFACE
        ${CMAKE_CURRENT_LIST_DIR}
)
target_link_libraries(fwk_xvf_board_support_xk_voice_sq66_evk
    INTERFACE
        core::general
        rtos::freertos
        rtos::drivers::general
        rtos::drivers::dfu_image
)
target_compile_options(fwk_xvf_board_support_xk_voice_sq66_evk
    INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/xvf3800_qf60.xn
)
target_link_options(fwk_xvf_board_support_xk_voice_sq66_evk
    INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/xvf3800_qf60.xn
)
target_compile_definitions(fwk_xvf_board_support_xk_voice_sq66_evk
    INTERFACE
        XCOREAI_EXPLORER=1
        PLATFORM_SUPPORTS_TILE_0=1
        PLATFORM_SUPPORTS_TILE_1=1
        PLATFORM_SUPPORTS_TILE_2=0
        PLATFORM_SUPPORTS_TILE_3=0
        PLATFORM_USES_TILE_0=1
        PLATFORM_USES_TILE_1=1
)

## Create an alias
add_library(fwk_xvf::bsp_config::xk_voice_sq66_evk ALIAS fwk_xvf_board_support_xk_voice_sq66_evk)
