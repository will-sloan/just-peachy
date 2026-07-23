cmake_minimum_required(VERSION 3.21.0)
project(pan_pot LANGUAGES C)

#*********************************
# Find correct Python installation
#*********************************

set(Python3_FIND_FRAMEWORK NEVER)
set(Python3_FIND_VIRTUALENV ONLY)
find_package(Python3 REQUIRED)

# Generate pan_pot_lut.c using the python script
set(PAN_POT_LUT_FILE ${CMAKE_CURRENT_BINARY_DIR}/pan_pot_lut.c)
# cache variable can be easily overidden
set(PAN_POT_LUT_SIZE 10 CACHE STRING "Number of entries in pan pot look up table")
add_custom_command(
    OUTPUT ${PAN_POT_LUT_FILE}
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/python/pan_pot.py ${PAN_POT_LUT_SIZE} ${PAN_POT_LUT_FILE}
)


set(LIB_NAME fwk_xvf_pan_pot)
add_library(${LIB_NAME} STATIC src/pan_pot.c ${PAN_POT_LUT_FILE})
target_include_directories(
    ${LIB_NAME} 
    PUBLIC api
    PRIVATE src
)
# -Ofast enables even more optimisations than -O3, specifically the fast math ones.
target_compile_options(${LIB_NAME} PRIVATE -g -Ofast -mno-dual-issue -Wall -Werror)
target_link_libraries(${LIB_NAME} PRIVATE lib_xcore_math)

add_library(fwk_xvf::pan_pot ALIAS fwk_xvf_pan_pot)

if(BUILD_TESTS)
    add_subdirectory(test)
endif()

