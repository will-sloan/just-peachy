// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// A somewhat reusable implementation of an audio mux. Goals:
/// * Inputs to the mux will be arbitrary sized contiguous buffers
/// * Outputs of the mux will be individual elements from specified
///   index from any of the Inputs
/// * minimal runtime overhead
/// * Ability to add and remove inputs without changing indexes (for
///   backwards compatibility). 
/// * int32_t
///
///

#ifndef MUX_H
#define MUX_H 

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include "timing_debug_defs.h"

/// A mux will be an array of mux_source_t, each initialised with MUX_SOURCE_INIT
/// The buffer can also be NULL or some memory initialised elsewhere if needed
typedef struct {
	int32_t* buf;
	uint32_t n_elems;
} mux_source_t;

/// Initialiser for a mux_source_t using compound literal to create
/// block scoped buffer
#define MUX_SOURCE_INIT(size) { (int32_t[(size)]){0}, (size) }

/// count elems in an array
#define MUX_N_SOURCES(mux) (sizeof(mux)/sizeof(*mux))

/// Type to hold all information needed to index into the mux. Packed to give certainty
/// that there is no padding and it can be treated as an array when needed.
typedef struct __attribute__((packed)) {
	/// idx of buf
	uint8_t buf;

	/// idx of elem in buf
	uint8_t idx;
} mux_index_t;

/// fill buffer with values from mux. No checking is applied to this so we assume a sensible input
/// @param[in] mux array of mux_source_t containing data
/// @param[out] outbuf buffer of length n_out to be filled with specified data
/// @param[in] index array of indexes of length n_out to select inputs
/// @param n_out number of elements in index and out_buf
STATIC_INLINE void mux(const mux_source_t* mux, int32_t* out_buf, const mux_index_t* index, const size_t n_out) {
	for(int i = 0; i < n_out; ++i) 
	{
		out_buf[i] = mux[index[i].buf].buf[index[i].idx];
	}
}

#endif // MUX_H 
