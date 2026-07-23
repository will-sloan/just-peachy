# add test which uses the test vectors
add_unity_xsim_test(test_pan_pot.c DEFAULT_TARGET)
target_link_libraries(test_pan_pot PUBLIC fwk_xvf::pan_pot)
