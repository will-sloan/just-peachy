
cmake_minimum_required(VERSION 3.21)

if (WIN32)
    # XCC fails with long paths on windows so
    # instruct cmake to squish the paths
    set(CMAKE_OBJECT_PATH_MAX 200)
endif ()

execute_process(COMMAND git -C ${CMAKE_CURRENT_LIST_DIR} rev-parse ERROR_QUIET OUTPUT_QUIET RESULT_VARIABLE GIT_ERROR_CODE)
set(NO_GIT OFF)
if(NOT GIT_ERROR_CODE EQUAL "0")
    set(NO_GIT ON)
    message("Skipping git version checks (not in a git repo)")
endif()

## Disable in-source build.
if("${CMAKE_SOURCE_DIR}" STREQUAL "${CMAKE_BINARY_DIR}")
    message(FATAL_ERROR "In-source build is not allowed! Please specify a build folder.\n\tex:cmake -B build")
endif()

## Project declaration
project(sw_xvf3800)

## Enable languages for project
enable_language(CXX C ASM)

# all targets which will be built by CI must be marked as a dependency of this target.
add_custom_target(all_ci)
add_custom_target(all_tests)

# See if build has been modified or whether it is outside of git.
# Also pickup build host env variable if set
function(get_bld_info)
    if (NOT ${NO_GIT})
        if (WIN32)
            execute_process(COMMAND cmd /C "git status --porcelain" OUTPUT_VARIABLE VALUE OUTPUT_STRIP_TRAILING_WHITESPACE)
        else ()
            execute_process(COMMAND bash -c "git status --porcelain" OUTPUT_VARIABLE VALUE OUTPUT_STRIP_TRAILING_WHITESPACE)
        endif ()
    endif ()
    if ((${NO_GIT}) OR (${VALUE} MATCHES "not a git repository"))
        set(BLD_MODIFIED "NO_GIT" PARENT_SCOPE)
    elseif (${VALUE} MATCHES " M ")
        set(BLD_MODIFIED "TRUE" PARENT_SCOPE)
    else ()
        set(BLD_MODIFIED "FALSE" PARENT_SCOPE)
    endif ()

    if ("$ENV{XVF3800_BLD_HOST}" STREQUAL "")
        set(BLD_HOST "NA" PARENT_SCOPE) # Not set
    else ()
        set(BLD_HOST $ENV{XVF3800_BLD_HOST} PARENT_SCOPE)
    endif()
endfunction()


# Extract the version number from settings.yml which will be built into source
function(get_version)
    # Read the YAML file.
    file(READ ${CMAKE_CURRENT_LIST_DIR}/settings.yml MY_YAML_STRING)
    string(REGEX MATCH "version: ([0-9]+).([0-9]+).([0-9]+)" DEFAULT_VERSION_MAJOR ${MY_YAML_STRING})
    message(STATUS "${DEFAULT_VERSION_MAJOR}")
    set(DEFAULT_VERSION_MAJOR "${CMAKE_MATCH_1}" PARENT_SCOPE)
    set(DEFAULT_VERSION_MINOR "${CMAKE_MATCH_2}" PARENT_SCOPE)
    set(DEFAULT_VERSION_PATCH "${CMAKE_MATCH_3}" PARENT_SCOPE)
endfunction()

# validate sdk and application git hashes
function(get_actual_git_hashes)
    foreach(PATH_HASH_TO_FIND ${CMAKE_CURRENT_LIST_DIR})
        if (NOT ${NO_GIT})
            if (WIN32)
                execute_process(COMMAND cmd /C "git -C ${PATH_HASH_TO_FIND} rev-parse HEAD" OUTPUT_VARIABLE VALUE OUTPUT_STRIP_TRAILING_WHITESPACE)
            else ()
                execute_process(COMMAND bash -c "git -C ${PATH_HASH_TO_FIND} rev-parse HEAD" OUTPUT_VARIABLE VALUE OUTPUT_STRIP_TRAILING_WHITESPACE)
            endif ()
        endif ()

        if (${VALUE} MATCHES "not a git repository")
            set(ACTUAL_APPLICATION_GIT_HASH "NO_GIT" PARENT_SCOPE)
        else ()
            set(ACTUAL_APPLICATION_GIT_HASH "${VALUE}" PARENT_SCOPE)
        endif ()
    endforeach()
endfunction()

get_actual_git_hashes()
get_version()
get_bld_info()

include(modules/fwk_xvf/modules/rtos/tools/cmake_utils/xmos_macros.cmake)

if(CMAKE_SYSTEM_PROCESSOR STREQUAL XCORE_XS3A)
    include(${CMAKE_INSTALL_PREFIX}/precompiled/xshf/xshf.cmake)
endif()

## Add top level project targets
if(PROJECT_IS_TOP_LEVEL)
    if(BUILD_TESTS)
        include(CTest)
        include(modules/fwk_xvf/modules/unity.cmake)
        add_subdirectory(modules/fwk_xvf/test/sim_test)
    endif()
    add_subdirectory(app_xvf3800)
endif()

add_subdirectory(modules)

# put current compilation database in repo root to make
# life good in some editors
if(CMAKE_EXPORT_COMPILE_COMMANDS)
    add_custom_target(compile_commands ALL
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
        ${CMAKE_BINARY_DIR}/compile_commands.json
        ${CMAKE_SOURCE_DIR}
        COMMENT "Copy compilation database"
        VERBATIM
    )
endif()
