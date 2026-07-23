
## Create custom board targets for dacs
add_library(fwk_xvf_board_support_xk_voice_sq66_evk_dac_dac3101 INTERFACE)
target_sources(fwk_xvf_board_support_xk_voice_sq66_evk_dac_dac3101
    INTERFACE
        ${CMAKE_CURRENT_LIST_DIR}/dac3101/dac3101.c
)
target_include_directories(fwk_xvf_board_support_xk_voice_sq66_evk_dac_dac3101
    INTERFACE
        ${CMAKE_CURRENT_LIST_DIR}/dac3101
)
target_compile_definitions(fwk_xvf_board_support_xk_voice_sq66_evk_dac_dac3101
    INTERFACE
        DAC3101=1
)

## Create an alias
add_library(fwk_xvf::bsp_config::dac::dac3101 ALIAS fwk_xvf_board_support_xk_voice_sq66_evk_dac_dac3101)
