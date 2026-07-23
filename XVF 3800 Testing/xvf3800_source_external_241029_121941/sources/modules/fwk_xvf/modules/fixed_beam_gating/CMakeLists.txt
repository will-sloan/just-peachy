cmake_minimum_required(VERSION 3.21.0)
project(fixed_beam_gating LANGUAGES C)

set(LIB_NAME fwk_xvf_fixed_beam_gating)
add_library(${LIB_NAME} STATIC src/fixed_beam_gating.c)
target_include_directories(${LIB_NAME} PUBLIC api)
target_compile_options(${LIB_NAME} PRIVATE -g -O3 -mno-dual-issue -Wall -Werror)

add_library(fwk_xvf::fixed_beam_gating ALIAS fwk_xvf_fixed_beam_gating)
