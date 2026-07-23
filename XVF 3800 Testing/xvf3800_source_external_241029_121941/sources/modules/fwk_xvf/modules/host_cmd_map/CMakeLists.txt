## Rasbian version that we currently use 3.13  is the latest possible version of cmake
## This cmake file will not be integrated with the top-level cmake structure till this is resolved
cmake_minimum_required(VERSION 3.13)
# Force release mode so that it won't use debug dlls
set(CMAKE_BUILD_TYPE "Release" CACHE STRING "Only Release mode is allowed" FORCE)

# Update the variable below to use the desired usb_param_values.yaml file
# This variable will update the release path too
set(PRODUCT_DEFAULT_SPECIFIER "product" CACHE STRING "Specifier of the default values to use")
message(STATUS "Using PRODUCT_DEFAULT_SPECIFIER: ${PRODUCT_DEFAULT_SPECIFIER}")

project(xvf3800_host_app)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED On)
set(CMAKE_CXX_EXTENSIONS Off)

set(RELEASE_DIR ${CMAKE_CURRENT_LIST_DIR}/../../../../build/release)

# Use different release paths for different specifiers of default values
set(CMAKE_INSTALL_PREFIX ${RELEASE_DIR}/host/${PRODUCT_DEFAULT_SPECIFIER})

if((UNIX AND NOT APPLE) AND (${CMAKE_SYSTEM_PROCESSOR} STREQUAL "armv7l"))
    set(CMAKE_INSTALL_PREFIX ${CMAKE_INSTALL_PREFIX}/rpi)
elseif((UNIX AND NOT APPLE) AND (${CMAKE_SYSTEM_PROCESSOR} STREQUAL "x86_64"))
    set(CMAKE_INSTALL_PREFIX ${CMAKE_INSTALL_PREFIX}/linux_x86_64)
elseif(APPLE AND (${CMAKE_SYSTEM_PROCESSOR} STREQUAL "x86_64"))
    set(CMAKE_INSTALL_PREFIX ${CMAKE_INSTALL_PREFIX}/mac_x86_64)
elseif(APPLE AND (${CMAKE_SYSTEM_PROCESSOR} STREQUAL "arm64"))
    set(CMAKE_INSTALL_PREFIX ${CMAKE_INSTALL_PREFIX}/mac_arm64)
elseif(WIN32)
    set(CMAKE_INSTALL_PREFIX ${CMAKE_INSTALL_PREFIX}/win32)
    set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS TRUE)
    include(GenerateExportHeader)
else()
    message(FATAL_ERROR "The platform you are using is not supported")
endif()
## Include the device control API. This is part of the framework RTOS.
if(EXISTS ${CMAKE_CURRENT_LIST_DIR}/../rtos/modules/sw_services/device_control)
    set(DEVICE_CONTROL_PATH ${CMAKE_CURRENT_LIST_DIR}/../rtos/modules/sw_services/device_control)
else()
    message(FATAL_ERROR "Device control API cannot be found. Have you downloaded fwk_rtos?")
endif()
enable_language(CXX C)

#*********************************
# Find correct Python installation
#*********************************

set(Python3_FIND_FRAMEWORK NEVER)
set(Python3_FIND_VIRTUALENV ONLY)
find_package(Python3 REQUIRED)

## Define YAML autogen macro
#*********************************************************
# Autogenerate files from the cmds .yaml file
#*********************************************************
add_subdirectory(../yaml_autogen CMakeYAMLCruft)
macro(AUTOGEN PROJECT_ROOT AUTOGEN_DIR_INTERNAL)

    set( YAML_DIR ${PROJECT_ROOT}/yaml_files)

    # Four output folders - device, host, common, and the documentation directory.
    set( AUTOGEN_COMMON ${AUTOGEN_DIR_INTERNAL}/common )
    set( AUTOGEN_HOST ${AUTOGEN_DIR_INTERNAL}/host )

    # Set up keywords to make writing the Python incantations clearer
    set( YAML_COMMANDS_DIR ${YAML_DIR}/control_commands )
    set( YAML_SETTINGS_DIR ${YAML_DIR}/settings_and_defaults )
    get_filename_component(YAML_COMMANDS_DIR ${YAML_COMMANDS_DIR} ABSOLUTE)
    get_filename_component(YAML_SETTINGS_DIR ${YAML_SETTINGS_DIR} ABSOLUTE)

    set( YAML_TEMPLATES_CMD ${YAML_AUTOGEN_TEMPLATES_LOCATION}/command_map)
    set( YAML_TEMPLATES_DOC ${YAML_AUTOGEN_TEMPLATES_LOCATION}/documentation)
    set( YAML_TEMPLATES_DEFAULTS ${YAML_AUTOGEN_TEMPLATES_LOCATION}/defaults)
    set( YAML_TEMPLATES_ENUM ${YAML_AUTOGEN_TEMPLATES_LOCATION}/enums)

    set( YAML_PROC_GENERIC   yaml_autogen.outputs.generic_process )
    set( YAML_PROC_DEFAULTS  yaml_autogen.outputs.default_values )
    set( YAML_PROC_DOCS      yaml_autogen.outputs.documentation )
    set( YAML_PROC_ENUM      yaml_autogen.outputs.enum_consumers )
    set( YAML_PROC_MULTI     yaml_autogen.outputs.multiple_command_input )

    unset(YAML_GENERATED_FILES)

    # For each of the control commands YAMLs, generate a corresponding:
    # x.h in common
    # In all of these, blob together shf_aec & aec, shf_pp & pp
    file( GLOB YAML_CONTROL_COMMANDS ${YAML_COMMANDS_DIR}/*.yaml )

    # Remove shf_ files we know will be there, we'll put them back in later.
    # This is a slightly hacky bodge since we know they'll all be in the same directory.
    set ( YAML_CONTROL_COMMANDS_NO_SHF ${YAML_CONTROL_COMMANDS})
    list( FILTER YAML_CONTROL_COMMANDS_NO_SHF EXCLUDE REGEX shf_aec_cmds\.yaml)
    list( FILTER YAML_CONTROL_COMMANDS_NO_SHF EXCLUDE REGEX shf_pp_cmds\.yaml)


    foreach(CMD_YAML_PATH ${YAML_CONTROL_COMMANDS_NO_SHF})
        get_filename_component(CMD_YAML ${CMD_YAML_PATH} NAME_WE)

        set(CMD_OUT ${AUTOGEN_COMMON}/${CMD_YAML}.h)

        # Deal with blobbing the SHF commands in
        string(FIND ${CMD_YAML} "aec_cmds" IS_AEC)
        string(FIND ${CMD_YAML} "pp_cmds" IS_PP)
        if(NOT IS_AEC EQUAL -1)
            string(REPLACE "aec_cmds.yaml" "shf_aec_cmds.yaml" SHF_AEC ${CMD_YAML_PATH})
            list(APPEND CMD_YAML_PATH ${SHF_AEC})
        endif()
        if(NOT IS_PP EQUAL -1)
            string(REPLACE "pp_cmds.yaml" "shf_pp_cmds.yaml" SHF_PP ${CMD_YAML_PATH})
            list(APPEND CMD_YAML_PATH ${SHF_PP})
        endif()

        add_custom_command(
            OUTPUT ${CMD_OUT}
            COMMAND ${Python3_EXECUTABLE} -m ${YAML_PROC_MULTI} -i ${CMD_YAML_PATH} -t ${YAML_TEMPLATES_CMD}/cmd_map.h.jinja -o ${CMD_OUT}
            COMMENT "Generating ${CMD_YAML}.h"
            VERBATIM
        )

        list(APPEND YAML_GENERATED_FILES ${CMD_OUT})
    endforeach()

    # Generate the other 1-to-1 files:
    # usb_param_values.h in common,
    # res_id_defines.h in common,
    # device_enums.h in common,


    set(USB_PARAM_OUT ${AUTOGEN_COMMON}/usb_param_values.h)
    set(RES_IDX_OUT ${AUTOGEN_COMMON}/res_id_defines.h)
    set(RES_IDX_OVERRIDE_OUT ${AUTOGEN_COMMON}/res_id_defines_override.h)
    set(DEVICE_ENUM_OUT ${AUTOGEN_COMMON}/device_enums.h)

    add_custom_command(
        OUTPUT ${USB_PARAM_OUT}
        COMMAND ${Python3_EXECUTABLE} -m ${YAML_PROC_GENERIC} -i ${YAML_SETTINGS_DIR}/${PRODUCT_DEFAULT_SPECIFIER}/usb_param_values.yaml -t ${YAML_TEMPLATES_DEFAULTS}/usb_params.h.jinja -o ${USB_PARAM_OUT} -y usb
        COMMENT "Generating usb_param_values.h"
        VERBATIM
    )
    add_custom_command(
        OUTPUT ${RES_IDX_OUT}
        COMMAND ${Python3_EXECUTABLE} -m ${YAML_PROC_GENERIC} -i ${YAML_SETTINGS_DIR}/resource_indices.yaml -t ${YAML_TEMPLATES_CMD}/res_id_defines.h.jinja -o ${RES_IDX_OUT} -y indices
        COMMENT "Generating res_id_defines.h"
        VERBATIM
    )
    add_custom_command(
        OUTPUT ${RES_IDX_OVERRIDE_OUT}
        COMMAND ${Python3_EXECUTABLE} -m ${YAML_PROC_GENERIC} -i ${YAML_COMMANDS_DIR}/dfu_cmds.yaml -t ${YAML_TEMPLATES_CMD}/res_id_defines_override.h.jinja -o ${RES_IDX_OVERRIDE_OUT} -y indices_override
        COMMENT "Generating res_id_defines_override.h from dfu_cmds.yaml"
        DEPENDS ${YAML_COMMANDS_DIR}/dfu_cmds.yaml ${YAML_TEMPLATES_CMD}/res_id_defines_override.h.jinja
        VERBATIM
    )
    add_custom_command(
        OUTPUT ${DEVICE_ENUM_OUT}
        COMMAND ${Python3_EXECUTABLE} -m ${YAML_PROC_GENERIC} -i ${YAML_SETTINGS_DIR}/device_enums.yaml -t ${YAML_TEMPLATES_ENUM}/device_enums.h.jinja -o ${DEVICE_ENUM_OUT} -y enums
        COMMENT "Generating device_enums.h"
        VERBATIM
    )
    list(APPEND YAML_GENERATED_FILES ${USB_PARAM_OUT} ${RES_IDX_OUT} ${DEVICE_ENUM_OUT} ${RES_IDX_OVERRIDE_OUT})

    # Generate the host files:
    # host_cmd_map.h
    # range_check.h
    # range_map.h
    # print_enum_functions.h - enum consumer
    # super_print_arg.h - enum consumer
    # enum_str_map.h

    set(HOST_CMD_OUT ${AUTOGEN_HOST}/host_cmd_map.h)
    set(RANGE_CHECK_OUT ${AUTOGEN_HOST}/range_check.h)
    set(RANGE_MAP_OUT ${AUTOGEN_HOST}/range_map.h)
    set(PRINT_ENUM_FUNC_OUT ${AUTOGEN_HOST}/print_enum_functions.h)
    set(SUPER_PRINT_ARG_OUT ${AUTOGEN_HOST}/super_print_arg.h)
    set(ENUM_STR_MAP_OUT ${AUTOGEN_HOST}/enum_str_map.h)
    set(TRANSPORT_CFG_OUT ${AUTOGEN_COMMON}/transport_config.h)

    add_custom_command(
        OUTPUT ${HOST_CMD_OUT}
        COMMAND ${Python3_EXECUTABLE} -m ${YAML_PROC_MULTI} -i ${YAML_CONTROL_COMMANDS} -t ${YAML_TEMPLATES_CMD}/host_cmd_map_impl.h.jinja -o ${HOST_CMD_OUT} --remove-internal
        COMMENT "Generating host_cmd_map.h"
        VERBATIM
    )
    add_custom_command(
        OUTPUT ${RANGE_CHECK_OUT}
        COMMAND ${Python3_EXECUTABLE} -m ${YAML_PROC_MULTI} -i ${YAML_CONTROL_COMMANDS} -t ${YAML_TEMPLATES_CMD}/host_range_check_impl.h.jinja -o ${RANGE_CHECK_OUT} --remove-internal
        COMMENT "Generating range_check.h"
        VERBATIM
    )
    add_custom_command(
        OUTPUT ${RANGE_MAP_OUT}
        COMMAND ${Python3_EXECUTABLE} -m ${YAML_PROC_MULTI} -i ${YAML_CONTROL_COMMANDS} -t ${YAML_TEMPLATES_CMD}/host_range_map_impl.h.jinja -o ${RANGE_MAP_OUT} --remove-internal
        COMMENT "Generating range_map.h"
        VERBATIM
    )
    add_custom_command(
        OUTPUT ${PRINT_ENUM_FUNC_OUT}
        COMMAND ${Python3_EXECUTABLE} -m ${YAML_PROC_ENUM} -i ${YAML_CONTROL_COMMANDS} -t ${YAML_TEMPLATES_ENUM}/print_enum_functions.h.jinja -o ${PRINT_ENUM_FUNC_OUT} --remove-internal -e ${YAML_SETTINGS_DIR}/device_enums.yaml
        COMMENT "Generating print_enum_functions.h"
        VERBATIM
    )
    add_custom_command(
        OUTPUT ${SUPER_PRINT_ARG_OUT}
        COMMAND ${Python3_EXECUTABLE} -m ${YAML_PROC_ENUM} -i ${YAML_CONTROL_COMMANDS} -t ${YAML_TEMPLATES_ENUM}/super_print_arg.h.jinja -o ${SUPER_PRINT_ARG_OUT} --remove-internal -e ${YAML_SETTINGS_DIR}/device_enums.yaml
        COMMENT "Generating super_print_arg.h"
        VERBATIM
    )
    add_custom_command(
        OUTPUT ${ENUM_STR_MAP_OUT}
        COMMAND ${Python3_EXECUTABLE} -m ${YAML_PROC_GENERIC} -i ${YAML_SETTINGS_DIR}/device_enums.yaml -t ${YAML_TEMPLATES_ENUM}/enum_str_map.h.jinja -o ${ENUM_STR_MAP_OUT} -y enums
        COMMENT "Generating enum_str_map.h"
        VERBATIM
    )
    add_custom_command(
        OUTPUT ${TRANSPORT_CFG_OUT}
        COMMAND ${Python3_EXECUTABLE} -m ${YAML_PROC_GENERIC} -i ${YAML_SETTINGS_DIR}/transport_config.yaml -t ${YAML_TEMPLATES_DEFAULTS}/transport_config.h.jinja -o ${TRANSPORT_CFG_OUT} -y transport
        COMMENT "Generating transport_config.h"
        DEPENDS ${YAML_SETTINGS_DIR}/transport_config.yaml ${YAML_TEMPLATES_DEFAULTS}/transport_config.h.jinja
        VERBATIM
    )

    list(APPEND YAML_GENERATED_FILES ${HOST_CMD_OUT} ${RANGE_CHECK_OUT} ${RANGE_MAP_OUT} ${PRINT_ENUM_FUNC_OUT} ${SUPER_PRINT_ARG_OUT} ${ENUM_STR_MAP_OUT} ${TRANSPORT_CFG_OUT})

    add_custom_target(yaml_generation
        DEPENDS ${YAML_GENERATED_FILES})

endmacro()

#*********************************************************
# Autogenerate the cmd_map files from the cmds .yaml file
#*********************************************************
set(XVF_PROJECT_ROOT ${CMAKE_CURRENT_LIST_DIR}/../../../..)

file( GLOB YAML_ROOT_DIR ${XVF_PROJECT_ROOT}/app_xvf38*0/autogeneration)
message("Command map files found at ${YAML_ROOT_DIR}")

set( AUTOGEN_DIR ${CMAKE_CURRENT_BINARY_DIR}/src.autogen )

AUTOGEN(${YAML_ROOT_DIR} ${AUTOGEN_DIR})

#*************************************
# Add the command map shared library
#*************************************
add_library(command_map SHARED ${CMAKE_CURRENT_LIST_DIR}/command_map.cpp)
add_dependencies(command_map yaml_generation)
target_link_options(command_map PRIVATE -fPIC)
target_include_directories(command_map PUBLIC ${DEVICE_CONTROL_PATH}/api)
target_include_directories(command_map PUBLIC ${AUTOGEN_DIR}/common ${AUTOGEN_DIR}/host)
target_sources(command_map PRIVATE ${CMAKE_CURRENT_LIST_DIR}/command_map.cpp)
target_compile_definitions(command_map
    PRIVATE
    _USE_MATH_DEFINES=1
)

if(WIN32)
    generate_export_header(command_map)
endif()

add_custom_command(TARGET command_map
    POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy $<TARGET_FILE:command_map> ${CMAKE_INSTALL_PREFIX}/$<TARGET_FILE_NAME:command_map>
)
message(STATUS "Command map will be saved in ${CMAKE_INSTALL_PREFIX}")
message(STATUS "Building with ${CMAKE_C_COMPILER_ID}")
