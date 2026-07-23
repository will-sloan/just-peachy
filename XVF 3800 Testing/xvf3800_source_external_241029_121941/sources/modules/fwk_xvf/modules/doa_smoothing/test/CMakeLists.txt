
#*********************************
# Find correct Python installation
#*********************************

set(Python3_FIND_FRAMEWORK NEVER)
set(Python3_FIND_VIRTUALENV ONLY)
find_package(Python3 REQUIRED)

# generate test vectors
set(DOA_INPUT in.dat)
set(DOA_OUTPUT out.dat)
add_custom_command(
    OUTPUT ${DOA_INPUT} ${DOA_OUTPUT}
    COMMAND ${Python3_EXECUTABLE} generate_test_vectors.py 
        ${CMAKE_CURRENT_BINARY_DIR}/${DOA_INPUT} 
        ${CMAKE_CURRENT_BINARY_DIR}/${DOA_OUTPUT}
    WORKING_DIRECTORY ${CMAKE_CURRENT_LIST_DIR}/../python
    DEPENDS 
    ${CMAKE_CURRENT_LIST_DIR}/../python/generate_test_vectors.py
    ${CMAKE_CURRENT_LIST_DIR}/../python/doa_smoothing.py
)

add_custom_target(test_doa_smoothing_vectors
    DEPENDS ${DOA_OUTPUT} ${DOA_INPUT}
)

# add test which uses the test vectors
add_unity_xsim_test(test_doa_smoothing.c DEFAULT_TARGET)
target_link_libraries(test_doa_smoothing PUBLIC fwk_xvf::doa_smoothing)
target_compile_definitions(test_doa_smoothing
    PUBLIC
    DOA_SMOOTHING_INPUT_FILE=${DOA_INPUT}
    DOA_SMOOTHING_EXPECTED_OUTPUT_FILE=${DOA_OUTPUT}
)
add_dependencies(test_doa_smoothing test_doa_smoothing_vectors)

