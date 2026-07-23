cmake_minimum_required(VERSION 3.20.0)

project(fifo_chan)

if(${CMAKE_SYSTEM_PROCESSOR} STREQUAL XCORE_XS3A)

	add_library(fifo_chan INTERFACE)

	target_include_directories(fifo_chan INTERFACE api)

	file(GLOB FIFO_CHAN_SOURCES "src/*.c" "src/*.xc")
	target_sources(fifo_chan INTERFACE ${FIFO_CHAN_SOURCES})
	target_compile_definitions(fifo_chan INTERFACE FIFO_CHAN_USE_XC=1)
	add_library(fwk_xvf::fifo_chan ALIAS fifo_chan)

	if(BUILD_TESTS)
		add_subdirectory(test)
	endif()
endif()
	
