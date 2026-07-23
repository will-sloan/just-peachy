
add_unity_xsim_test(test_fifo_chan.c DEFAULT_TARGET)
target_link_libraries(test_fifo_chan PUBLIC fwk_xvf::fifo_chan)


add_unity_xsim_test(test_rx_fsm.c DEFAULT_TARGET)
target_link_libraries(test_rx_fsm PUBLIC fwk_xvf::fifo_chan)

add_unity_xsim_test(test_rx_fsm_slow.c DEFAULT_TARGET)
target_link_libraries(test_rx_fsm_slow PUBLIC fwk_xvf::fifo_chan)

add_unity_xsim_test(test_rx_fsm_sync_data.c DEFAULT_TARGET)
target_link_libraries(test_rx_fsm_sync_data PUBLIC fwk_xvf::fifo_chan)
