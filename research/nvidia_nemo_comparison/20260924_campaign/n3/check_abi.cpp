// Compile-only cross-check against the pinned NVIDIA public header.
// See README_ABI.md. This never loads a neural model.
#include <cstddef>
#include "nemo_speech/asr.h"
static_assert(sizeof(void*) == 8, "64-bit host required");
static_assert(sizeof(nemo_speech_asr_recognizer_config) == 80, "Config ABI");
static_assert(sizeof(nemo_speech_asr_recognition_options) == 72, "Options ABI");
static_assert(offsetof(nemo_speech_asr_recognition_options, speech_contexts) == 40, "Context alignment");
static_assert(offsetof(nemo_speech_asr_recognition_options, max_speaker_count) == 64, "Tail alignment");
static_assert(sizeof(nemo_speech_asr_endpointing_config) == 16, "Endpoint ABI");
static_assert(sizeof(nemo_speech_asr_streaming_config) == 24, "Streaming ABI");
