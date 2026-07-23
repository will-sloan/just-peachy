cmake_minimum_required(VERSION 3.21.0)
project(doa_smoothing LANGUAGES C)

set(LIB_NAME fwk_xvf_doa_smoothing)
add_library(${LIB_NAME} STATIC src/doa_smoothing.c)
target_include_directories(${LIB_NAME} PUBLIC api)
target_compile_options(${LIB_NAME} PRIVATE -g -O3 -mno-dual-issue -Wall -Werror)

add_library(fwk_xvf::doa_smoothing ALIAS fwk_xvf_doa_smoothing)

if(BUILD_TESTS)
    add_subdirectory(test)
endif()

