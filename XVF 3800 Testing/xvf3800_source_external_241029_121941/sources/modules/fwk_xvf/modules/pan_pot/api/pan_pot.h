// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

/// API definition of pan_pot, designed for panning a mono input sample 
/// onto stereo output channels based on a direction of arrival. 
///
/// This module implements 4.5dB and linear algorithms. There is a link in 
/// the readme for this module with details on the algorithms, but the following
/// is a brief summary.
///
/// Linear - Computes a multiplier for each channel which is linear across the 
///          range of angles. This means that the amplitude in each channel in 
///          the center position is 0.5. Assuming the two channels power is additive,
///          which can be the case when the audio is playing into a room then this 
///          leads to a power of -3dB in the center and 0dB at the edges. However 
///          if the signals amplitude is additive then it will be correct.
///
/// Constant Power - (Not provided) This algorithm uses sine and cosine to produce
///          a signal which has constant power at every position, assuming the 
///          signals power is additive.
///
/// -4.5dB - Depending on the signal, the position of the speakers, and the position
///          of the user, it is possible for power to be additive or amplitude to be
///          additive. In which case this compromise algorithm should sound best in
///          most cases.
///
/// Choosing: Use `pan_pot_fast`. If that is too slow, use `pan_pot_linear`. If pan_pot_fast
/// is too inaccurate then use `pan_pot`. 
///


#pragma once
#include <stdint.h>

/// left and right channels, result of a pan pot
typedef struct {
    float l;  /// left channel
    float r;  /// right channel
} pan_pot_ratio_t;


/// Calculate the panning multipliers for left and right channel using the -4.5dB
/// algorithm. Use pan_pot_apply to apply these ratios to a sample.
///
/// The left output will be 0 for angles π radians away from left, and 
/// 1 when the angle is the same as left. Right output will be vice versa.
///
/// @param angle Direction of arrival of the sample. Expects value in range 0 to 2π
/// @param left_angle The angle that will be considered as "left". Expects value in
/// range 0 to 2π
pan_pot_ratio_t pan_pot(float angle, float left_angle);

/// Same as `pan_pot` except it uses look up table instead of sqrt and cos.
/// it's about 1.5x faster at the cost of some accuracy.
pan_pot_ratio_t pan_pot_fast(float angle, float left_angle);

/// Same as `pan_pot` except uses the linear algorithm which is the 
/// fastest and lightest algorithm.
pan_pot_ratio_t pan_pot_linear(float angle, float left_angle);

/// Apply the pan pot to a sample.
///
/// @param out output buffer is an array of 2. Left will be written to out[0] and
/// right will be written to out[1].
/// @param pot A precomputed pan pot using one of the above functions.
/// @param sample The sample to pan.
void pan_pot_apply(int32_t* out, const pan_pot_ratio_t* pot, int32_t sample);

