// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// XC has much faster implementation of non-blocking select that lib_xcore
/// here are some helper functions that greatly speed up this fifo

/// Given a channel c, if the channel is empty, return false. Else
/// for each byte on the channel, read it and put a read notification
/// back on the channel, then return true
int chan_non_blocking_flush(streaming chanend c) {
	int retval = 0;
	int done = 0;
	unsigned char rx;
	const unsigned char notification = 0;
	while(!done) {
		select {
			case c :> rx:
				retval = 1;
				c <: notification;
				break;

			default:
				done = 1;
				break;
		}
	}
	return retval;
}

	
/// read a byte from a channel, it it had a byte copy it to data,
/// and return 1, else return 0
int chan_non_blocking_receive(streaming chanend c, unsigned char &data) {
	select {
		case c :> data:
			return 1;

		default:
			return 0;
	}
}

/// try and read a byte from a channel, return true if something was there
/// else false
/// @warning: discards the data it finds on the channel.
int chan_non_blocking_check_notification(streaming chanend c) {
	unsigned char rx;
	select {
		case c :> rx:
			return 1;
		default:
			return 0;
	}
}
