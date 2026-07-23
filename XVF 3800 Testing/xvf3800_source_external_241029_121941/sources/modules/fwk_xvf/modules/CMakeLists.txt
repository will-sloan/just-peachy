
function(add_subdir_short_path dir)
    # To make paths shorter on windows. This
    # function sets the binary directory for the subdirectory being added
    # to be in ${CMAKE_BINARY_DIR}/xvfm rather than the default
    # which would be relative to ${CMAKE_CURRENT_BINARY_DIR} which is a
    # much more nested directory
    add_subdirectory(${dir} ${CMAKE_BINARY_DIR}/xvfm/${dir})
endfunction()

## Add frameworks
if(${CMAKE_SYSTEM_NAME} STREQUAL XCORE_XS3A)
    ## Need to guard so host targets will not be built
    add_subdir_short_path(core)
endif()

add_subdir_short_path(io)
add_subdir_short_path(rtos)

## Add additional modules
add_subdir_short_path(fifo_chan)
add_subdir_short_path(qspi_fast_read)
add_subdir_short_path(lib_src)
add_subdir_short_path(shf_bypass)
add_subdir_short_path(sw_pll)
add_subdir_short_path(bsp)
add_subdir_short_path(xvf)
add_subdir_short_path(device_control_nousbdriver)
add_subdir_short_path(ep_proxy)
add_subdir_short_path(yaml_autogen)
add_subdir_short_path(doa_smoothing)
add_subdir_short_path(pan_pot)
add_subdir_short_path(fixed_beam_gating)
