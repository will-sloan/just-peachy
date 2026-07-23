include(dac/dac.cmake)
add_subdirectory(XK-VOICE-SQ66-EVK)
add_subdirectory(xvf3820_proto)
# Add instructions for extra build configs
if(EXISTS  ${CMAKE_CURRENT_LIST_DIR}/extra-configs.cmake)
    include("extra-configs.cmake")
endif()
