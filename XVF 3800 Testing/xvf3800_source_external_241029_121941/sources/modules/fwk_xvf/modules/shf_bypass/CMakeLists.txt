cmake_minimum_required(VERSION 3.20.0)

project(shf_bypass)

if(${CMAKE_SYSTEM_PROCESSOR} STREQUAL XCORE_XS3A)

	add_library(shf_bypass INTERFACE)

	target_include_directories(shf_bypass INTERFACE api)
    file(GLOB SHF_BYPASS_SOURCES "src/*.c" "src/*.xc")
	target_sources(shf_bypass INTERFACE ${SHF_BYPASS_SOURCES})
	add_library(fwk_xvf::shf_bypass ALIAS shf_bypass)
endif()
