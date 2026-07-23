# Creates an interface for the common sources in XVF38x0 products.
# As this is an interface library, configuration can be applied by
# adding compile definitions to the app which links against it

file(GLOB XVF_SOURCES_COMMON        src/control_plane/*.c
                                    src/control_driver/*.c
                                    src/tile_common/*.c
                                    src/usb/control_plane/*.c
                                    src/usb/config/*.c)

# We will give different compiler switches for this timing critical code
file(GLOB XVF_SOURCES_DATA_PLANE    src/data_plane/*.c
                                    src/usb/data_plane/*.c
                                    src/data_plane/*.cpp)

foreach(FILE_NAME ${APP_SOURCES_COMMON})
    get_filename_component(extension ${FILE_NAME} EXT)
    if(${extension} MATCHES ".cpp")
        set_source_files_properties(${FILE_NAME} PROPERTIES COMPILE_OPTIONS "-std=c++14")
    endif()
endforeach()

add_library(fwk_xvf_xvf INTERFACE)
target_sources(fwk_xvf_xvf INTERFACE ${XVF_SOURCES_COMMON} ${XVF_SOURCES_DATA_PLANE} ${XVF_SOURCES_DATA_PLANE_SHF})
target_compile_definitions(
    fwk_xvf_xvf
    INTERFACE
    XUD_CORE_CLOCK=800
    XUD_SERIES_SUPPORT=4
    BLD_REPO_HASH=${ACTUAL_APPLICATION_GIT_HASH}
    BLD_MODIFIED=${BLD_MODIFIED}
    BLD_HOST=${BLD_HOST}
    HIL_IO_SPI_SLAVE_FAST_MODE=0
)

target_include_directories(
    fwk_xvf_xvf
    INTERFACE
    src/data_plane
    src/data_plane/audio_task
    src/control_plane
    src/control_driver
    src/tile_common
    src/usb/data_plane
    src/usb/control_plane
    src/usb/config
    src/user_interfaces/
)

target_link_libraries(
    fwk_xvf_xvf
    INTERFACE
    lib_i2s
    lib_i2c
    lib_mic_array
    lib_sw_pll
    lib_xud
    lib_src
    fwk_xvf::fifo_chan
    fwk_xvf::shf_bypass
    fwk_xvf::fixed_beam_gating
)

target_link_options(
    fwk_xvf_xvf
    INTERFACE
    -Wl,--defsymbol,tud_audio_rx_done_pre_read_cb=0
    -Wl,--defsymbol,tud_audio_rx_done_post_read_cb=0
    -Wl,--defsymbol,tud_audio_tx_done_pre_load_cb=0
    -Wl,--defsymbol,tud_audio_tx_done_post_load_cb=0
    -Wl,--defsymbol,tud_hid_report_complete_cb=0
    -Wl,--defsymbol,tud_hid_report_fail_cb=0
    -Wl,--defsymbol,tud_hid_set_idle_cb=0
    -Wl,--defsymbol,tud_hid_set_protocol_cb=0
    -Wl,--defsymbol,tud_xcore_data_cb=0
    -Wl,--defsymbol,tud_xcore_sof_cb=0
)

add_library(fwk_xvf::xvf ALIAS fwk_xvf_xvf)

# Confusing limitation of `set_source_files_properties` is that it only
# applies to sources that are used in targets in the current directory.
# INTERFACE libraries don't count. The next 20 lines find all the targets
# that have been defined so far and applies the dataplane compile options
# to the data plane files for the directories that those targets were defined in.
function(get_all_targets var)
    set(targets)
    get_all_targets_recursive(targets ${CMAKE_SOURCE_DIR})
    set(${var} ${targets} PARENT_SCOPE)
endfunction()

# recurses through all directories added with `add_subdirectory`
# and finds any targets that have been defined there.
macro(get_all_targets_recursive targets dir)
    get_property(subdirectories DIRECTORY ${dir} PROPERTY SUBDIRECTORIES)
    foreach(subdir ${subdirectories})
        get_all_targets_recursive(${targets} ${subdir})
    endforeach()

    get_property(current_targets DIRECTORY ${dir} PROPERTY BUILDSYSTEM_TARGETS)
    list(APPEND ${targets} ${current_targets})
endmacro()

get_all_targets(all_targets)

# source file properties are added after the flags of any target that these files are included
# in. So it does not matter if these sources are added to a target which specifies a different
# optimisation level.
set_source_files_properties(SOURCE ${XVF_SOURCES_DATA_PLANE} TARGET_DIRECTORY ${all_targets} PROPERTIES COMPILE_FLAGS "-O3 -mno-dual-issue")
set_source_files_properties(SOURCE ${XVF_SOURCES_DATA_PLANE_SHF} TARGET_DIRECTORY ${all_targets} PROPERTIES COMPILE_FLAGS "-O3 -mno-dual-issue")
