// Saved-audio C ABI conformance harness. See README_NATIVE_STREAM_SMOKE_V1.md.
// No devices, network, playback, training or model downloads.
#include <nemo_speech/asr.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr size_t max_bytes = 16 * 1024 * 1024;
constexpr size_t max_frames = 60 * 16000;
constexpr size_t push_frames = 1280;
size_t output_bytes = 0;
void need(bool ok, const std::string& message) {
    if (!ok) throw std::runtime_error(message);
}
void checked(nemo_speech_asr_status status, const char* operation) {
    if (status == NEMO_SPEECH_ASR_OK) return;
    const char* detail = nemo_speech_asr_last_error();
    throw std::runtime_error(std::string(operation) + ": " + (detail ? detail : "no native error"));
}
std::string quoted(const char* value) {
    need(value != nullptr, "Null native string");
    std::ostringstream out; out << '"';
    size_t n = 0;
    for (const unsigned char* p = reinterpret_cast<const unsigned char*>(value); *p; ++p) {
        need(++n <= 1024 * 1024, "Native string exceeds bound");
        if (*p == '"' || *p == '\\') out << '\\' << static_cast<char>(*p);
        else if (*p < 0x20) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << unsigned(*p) << std::dec;
        else out << static_cast<char>(*p);
    }
    out << '"'; return out.str();
}
void emit(const std::string& line) {
    need(line.size() + 1 <= max_bytes - output_bytes, "JSONL output cap reached");
    std::cout << line << '\n' << std::flush;
    need(bool(std::cout), "Output write failed"); output_bytes += line.size() + 1;
}
uint16_t u16(const std::vector<unsigned char>& b, size_t p) {
    need(p + 2 <= b.size(), "Truncated WAV integer");
    return uint16_t(b[p]) | (uint16_t(b[p+1]) << 8);
}
uint32_t u32(const std::vector<unsigned char>& b, size_t p) {
    need(p + 4 <= b.size(), "Truncated WAV integer");
    return uint32_t(b[p]) | (uint32_t(b[p+1]) << 8) | (uint32_t(b[p+2]) << 16) | (uint32_t(b[p+3]) << 24);
}
bool tag(const std::vector<unsigned char>& b, size_t p, const char* expected) {
    return p + 4 <= b.size() && std::memcmp(b.data()+p, expected, 4) == 0;
}
std::vector<float> read_wav(const char* path) {
    static_assert(sizeof(float) == 4 && std::numeric_limits<float>::is_iec559, "IEEE float32 required");
    std::ifstream in(path, std::ios::binary | std::ios::ate); need(bool(in), "WAV open failed");
    const auto size = in.tellg(); need(size >= 12 && size <= std::streamoff(max_bytes), "WAV size outside bound");
    std::vector<unsigned char> bytes(static_cast<size_t>(size)); in.seekg(0);
    in.read(reinterpret_cast<char*>(bytes.data()), size); need(bool(in), "WAV read incomplete");
    need(tag(bytes,0,"RIFF") && tag(bytes,8,"WAVE") && uint64_t(u32(bytes,4))+8 == bytes.size(), "Exact RIFF WAV required");
    size_t data = 0, data_size = 0; bool have_fmt = false, have_data = false;
    uint16_t format = 0, bits = 0, align = 0;
    for (size_t p = 12; p < bytes.size();) {
        need(p + 8 <= bytes.size(), "Truncated WAV chunk");
        const size_t n = u32(bytes,p+4), start = p+8;
        need(n <= bytes.size()-start && (n % 2 == 0 || n < bytes.size()-start), "WAV chunk or padding truncated");
        if (tag(bytes,p,"fmt ")) {
            need(!have_fmt && n >= 16, "Duplicate or short WAV format"); have_fmt = true;
            format = u16(bytes,start); bits = u16(bytes,start+14); align = u16(bytes,start+12);
            need(u16(bytes,start+2) == 1 && u32(bytes,start+4) == 16000, "Mono 16-kHz WAV required");
            need((format == 1 && bits == 16) || (format == 3 && bits == 32), "Only PCM16 or IEEE float32 WAV supported");
            need(align == bits/8 && u32(bytes,start+8) == 16000u*align, "WAV rate/alignment mismatch");
        } else if (tag(bytes,p,"data")) {
            need(!have_data, "Duplicate WAV data"); have_data = true; data = start; data_size = n;
        }
        p = start+n+(n%2);
    }
    need(have_fmt && have_data && data_size % align == 0, "Missing/misaligned WAV data");
    const size_t frames = data_size/align;
    need(frames >= 1281 && frames <= max_frames, "Saved source must contain 1281 to 960000 frames");
    std::vector<float> samples(frames);
    for (size_t i = 0; i < frames; ++i) {
        if (format == 1) {
            const uint16_t raw = u16(bytes,data+i*2);
            const int32_t signed_value = raw < 32768 ? int32_t(raw) : int32_t(raw)-65536;
            samples[i] = float(signed_value)/32768.f;
        } else {
            const uint32_t raw = u32(bytes,data+i*4); std::memcpy(&samples[i],&raw,4);
        }
        need(std::isfinite(samples[i]) && std::abs(samples[i]) <= 1.f, "Non-finite or out-of-range saved sample");
    }
    return samples;
}
using Recognizer = std::unique_ptr<nemo_speech_asr_recognizer, decltype(&nemo_speech_asr_destroy)>;
using Stream = std::unique_ptr<nemo_speech_asr_stream, decltype(&nemo_speech_asr_stream_close)>;
using Result = std::unique_ptr<nemo_speech_asr_result, decltype(&nemo_speech_asr_result_destroy)>;
struct Run { size_t sent = 0, events = 0, finals = 0; std::vector<std::string> final_signatures; };

size_t drain(nemo_speech_asr_stream* stream, const char* name, const char* phase, Run& run) {
    size_t count = 0;
    while (true) {
        nemo_speech_asr_result* raw = nullptr;
        const auto status = nemo_speech_asr_stream_next(stream,&raw);
        Result result(raw,&nemo_speech_asr_result_destroy); checked(status,"next");
        if (!result) return count;
        need(++run.events <= 4000 && ++count <= 4000, "Result drain exceeded bound");
        need(nemo_speech_asr_result_alternative_count(raw) == 1, "Expected one greedy alternative");
        const bool final = nemo_speech_asr_result_is_final(raw);
        const float processed = nemo_speech_asr_result_audio_processed(raw);
        const float confidence = nemo_speech_asr_result_confidence(raw,0);
        need(std::isfinite(processed) && std::isfinite(confidence), "Non-finite native result");
        const size_t words = nemo_speech_asr_result_word_count(raw,0); need(words <= 10000,"Word count exceeded bound");
        std::ostringstream signature;
        signature << "{\"text\":" << quoted(nemo_speech_asr_result_transcript(raw,0)) << ",\"words\":[";
        for (size_t i = 0; i < words; ++i) {
            if (i) signature << ',';
            signature << "{\"text\":" << quoted(nemo_speech_asr_result_word_text(raw,0,i))
                << ",\"start_ms\":" << nemo_speech_asr_result_word_start_time(raw,0,i)
                << ",\"end_ms\":" << nemo_speech_asr_result_word_end_time(raw,0,i) << '}';
            need(signature.tellp() <= std::streamoff(max_bytes), "Native signature exceeds bound");
        }
        signature << "]}";
        std::ostringstream event; event << std::setprecision(9)
            << "{\"kind\":\"event\",\"case\":" << quoted(name) << ",\"phase\":" << quoted(phase)
            << ",\"sent_frames\":" << run.sent << ",\"is_final\":" << (final?"true":"false")
            << ",\"audio_processed_seconds_raw\":" << processed << ",\"confidence_raw\":" << confidence
            << ",\"channel_raw\":" << nemo_speech_asr_result_channel_tag(raw) << ",\"hypothesis\":" << signature.str() << '}';
        emit(event.str());
        if (final) { ++run.finals; run.final_signatures.push_back(signature.str()); }
    }
}

Run run_case(nemo_speech_asr_recognizer* recognizer, const std::vector<float>& samples,
             const char* name, size_t frames, bool force) {
    need(frames <= samples.size(),"Case escaped saved source");
    nemo_speech_asr_recognition_options options{}; options.size = sizeof(options);
    options.language_code = "en-US"; options.interim_results = true; options.enable_word_time_offsets = true;
    options.enable_automatic_punctuation = true; options.verbatim_transcripts = true; options.max_alternatives = 1;
    nemo_speech_asr_stream* raw = nullptr;
    const auto status = nemo_speech_asr_streaming_recognize(recognizer,&options,&raw);
    Stream stream(raw,&nemo_speech_asr_stream_close); checked(status,"streaming_recognize"); need(bool(stream),"Null stream");
    emit(std::string("{\"kind\":\"case_start\",\"case\":")+quoted(name)+",\"frames\":"+std::to_string(frames)+"}");
    Run run; bool forced = false;
    const size_t force_at = std::min(size_t(197440),frames/2);
    while (run.sent < frames) {
        size_t count = std::min(push_frames,frames-run.sent);
        if (force && !forced && run.sent < force_at) count = std::min(count,force_at-run.sent);
        checked(nemo_speech_asr_stream_push_f32(raw,samples.data()+run.sent,count,16000),"push_f32");
        run.sent += count; drain(raw,name,"push",run);
        if (force && !forced && run.sent >= force_at) {
            checked(nemo_speech_asr_stream_force_endpoint(raw),"force_endpoint"); forced = true;
            drain(raw,name,"forced_endpoint",run);
        }
    }
    checked(nemo_speech_asr_stream_finish(raw),"finish"); drain(raw,name,"finish",run);
    need(drain(raw,name,"post_finish_empty_drain",run) == 0,"Results remain after complete finish drain");
    need(run.sent == frames && forced == force,"Sample accounting or forced endpoint differs");
    stream.reset(); // Explicitly close before the next stream on this recognizer.
    emit(std::string("{\"kind\":\"case_closed\",\"case\":")+quoted(name)+",\"sent_frames\":"+std::to_string(run.sent)
        +",\"events\":"+std::to_string(run.events)+",\"finals\":"+std::to_string(run.finals)
        +",\"forced_endpoint\":"+(forced?"true":"false")+",\"stream_closed\":true}");
    return run;
}
} // namespace

int main(int argc, char** argv) {
    try {
        need(argc == 3,"Usage: native_stream_smoke_v1 MODEL.gguf SAVED_MONO_16K.wav");
        const auto samples = read_wav(argv[2]);
        nemo_speech_asr_backend_config backend{}; backend.size = sizeof(backend); backend.gpu = -1;
        nemo_speech_asr_model_config model{}; model.size = sizeof(model); model.path = argv[1];
        nemo_speech_asr_streaming_config streaming{}; streaming.size = sizeof(streaming);
        streaming.chunk_size = .16f; streaming.ctc_left_padding = 1.92f; streaming.ctc_right_padding = 1.92f; streaming.rnnt_right_context = 1;
        nemo_speech_asr_decoder_config decoder{}; decoder.size = sizeof(decoder); decoder.kind = NEMO_SPEECH_ASR_DECODER_GREEDY;
        nemo_speech_asr_endpointing_config endpoint{}; endpoint.size = sizeof(endpoint); endpoint.enable = true; endpoint.vad_based = false; endpoint.stop_history_eou_ms = 800;
        nemo_speech_asr_recognizer_config config{}; config.size = sizeof(config); config.backend = &backend;
        config.model = &model; config.streaming = &streaming; config.decoder = &decoder; config.endpointing = &endpoint;
        emit(std::string("{\"kind\":\"start\",\"schema\":\"n5-native-stream-smoke-v1\",\"native_version\":")
            +quoted(nemo_speech_asr_version())+",\"frames\":"+std::to_string(samples.size())
            +",\"push_frames\":1280,\"sample_rate\":16000,\"gpu\":-1,\"ctc_chunk\":0.16,\"ctc_left\":1.92,\"ctc_right\":1.92,\"rnnt_right\":1,\"stop_ms\":800,\"hashes_verified_by_harness\":false}");
        nemo_speech_asr_recognizer* raw = nullptr; const auto status = nemo_speech_asr_create(&config,&raw);
        Recognizer recognizer(raw,&nemo_speech_asr_destroy); checked(status,"create"); need(bool(recognizer),"Null recognizer");
        run_case(raw,samples,"empty",0,false); run_case(raw,samples,"one_sample",1,false);
        run_case(raw,samples,"short_tail",1281,false);
        const Run first = run_case(raw,samples,"saved_source",samples.size(),false);
        const Run repeat = run_case(raw,samples,"saved_source_repeat",samples.size(),false);
        need(first.finals > 0 && first.final_signatures == repeat.final_signatures,"Final text/word state parity failed");
        run_case(raw,samples,"saved_source_forced",samples.size(),true); recognizer.reset();
        emit("{\"kind\":\"result\",\"status\":\"PASS_NATIVE_STREAM_CONFORMANCE_ONLY\",\"cases\":6,\"resident_state_parity\":true,\"recognizer_closed\":true,\"N4_accepted\":false,\"N5_complete\":false,\"CM5_tested\":false}");
        return 0;
    } catch (const std::exception& error) {
        try { emit(std::string("{\"kind\":\"failure\",\"status\":\"FAILED_PRESERVED\",\"error\":")+quoted(error.what())+"}"); }
        catch (...) { std::cerr << "Failure receipt exceeded output limit or output unavailable\n"; }
        return 1;
    }
}
