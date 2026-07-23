cmake_minimum_required(VERSION 3.21.0)

project(fwk_xvf LANGUAGES CXX C ASM)

if(PROJECT_IS_TOP_LEVEL)
    include(${CMAKE_INSTALL_PREFIX}/xshf.cmake)
    if(BUILD_TESTS)
        enable_testing()
        add_custom_target(all_tests)
        include(modules/unity.cmake)
        add_subdirectory(test/unit_test/)
    endif()
else()
    # don't let BUILD_TESTS propogate into
    # subdirectories of this project if this 
    # is not the top level project
    set(BUILD_TESTS OFF)
endif()


add_subdirectory(modules)
