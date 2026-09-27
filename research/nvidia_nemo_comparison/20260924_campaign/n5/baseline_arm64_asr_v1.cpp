// Baseline Sherpa ARM64 C ABI smoke. See README_BASELINE_ARM64_ASR_V1.md.
#include <sherpa-onnx/c-api/c-api.h>
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
constexpr size_t max_bytes=16*1024*1024, max_frames=60*16000, push_frames=1600;
size_t output_bytes=0;
void need(bool ok,const std::string& message){if(!ok)throw std::runtime_error(message);}
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
using Recognizer=std::unique_ptr<const SherpaOnnxOnlineRecognizer,decltype(&SherpaOnnxDestroyOnlineRecognizer)>;
using Stream=std::unique_ptr<const SherpaOnnxOnlineStream,decltype(&SherpaOnnxDestroyOnlineStream)>;
using Result=std::unique_ptr<const SherpaOnnxOnlineRecognizerResult,decltype(&SherpaOnnxDestroyOnlineRecognizerResult)>;
void drain(const SherpaOnnxOnlineRecognizer* r,const SherpaOnnxOnlineStream* s){
    size_t guard=0;
    while(SherpaOnnxIsOnlineStreamReady(r,s)){
        need(++guard<=100000,"Stream drain exceeded bound"); SherpaOnnxDecodeOnlineStream(r,s);
    }
}
std::string text(const SherpaOnnxOnlineRecognizer* r,const SherpaOnnxOnlineStream* s){
    Result result(SherpaOnnxGetOnlineStreamResult(r,s),&SherpaOnnxDestroyOnlineRecognizerResult);
    need(bool(result) && result->text,"Missing native result");
    std::string value=result->text; need(value.size()<1024*1024,"Native text exceeded bound");
    const auto first=value.find_first_not_of(" \t\r\n"),last=value.find_last_not_of(" \t\r\n");
    return first==std::string::npos ? "" : value.substr(first,last-first+1);
}
std::string one(const SherpaOnnxOnlineRecognizer* r,const std::vector<float>& source,const char* name){
    Stream stream(SherpaOnnxCreateOnlineStream(r),&SherpaOnnxDestroyOnlineStream);need(bool(stream),"Stream creation failed");
    emit("{\"kind\":\"case_start\",\"case\":"+quoted(name)+",\"frames\":"+std::to_string(source.size())+"}");
    size_t sent=0,resets=0;std::vector<std::string> finals;
    auto save=[&](const char* phase){
        auto value=text(r,stream.get());
        if(!value.empty()) finals.push_back("{\"text\":"+quoted(value.c_str())+",\"sent_frames\":"+std::to_string(sent)+",\"phase\":"+quoted(phase)+"}");
    };
    while(sent<source.size()){
        const auto n=std::min(push_frames,source.size()-sent);
        SherpaOnnxOnlineStreamAcceptWaveform(stream.get(),16000,source.data()+sent,static_cast<int32_t>(n));sent+=n;drain(r,stream.get());
        if(SherpaOnnxOnlineStreamIsEndpoint(r,stream.get())){save("endpoint");SherpaOnnxOnlineStreamReset(r,stream.get());++resets;}
    }
    std::vector<float> padding(10560,0.f);
    SherpaOnnxOnlineStreamAcceptWaveform(stream.get(),16000,padding.data(),static_cast<int32_t>(padding.size()));
    SherpaOnnxOnlineStreamInputFinished(stream.get());drain(r,stream.get());save("finish");
    std::string list="[";for(size_t i=0;i<finals.size();++i){if(i)list+=",";list+=finals[i];}list+="]";
    stream.reset();emit("{\"kind\":\"case_closed\",\"case\":"+quoted(name)+",\"frames\":"+std::to_string(source.size())+
        ",\"sent_frames\":"+std::to_string(sent)+",\"padding_frames\":10560,\"endpoint_resets\":"+std::to_string(resets)+
        ",\"stream_closed\":true,\"finals\":"+list+"}");return list;
}
}
int main(int argc,char** argv){
    try{
        need(argc==6,"Expected encoder decoder joiner tokens saved-WAV arguments");
        auto source=read_wav(argv[5]);
        SherpaOnnxOnlineRecognizerConfig c{};
        c.feat_config.sample_rate=16000;c.feat_config.feature_dim=80;
        c.model_config.transducer.encoder=argv[1];c.model_config.transducer.decoder=argv[2];c.model_config.transducer.joiner=argv[3];
        c.model_config.tokens=argv[4];c.model_config.num_threads=1;c.model_config.provider="cpu";
        c.decoding_method="greedy_search";c.max_active_paths=4;c.enable_endpoint=1;
        c.rule1_min_trailing_silence=2.4f;c.rule2_min_trailing_silence=1.2f;c.rule3_min_utterance_length=20.f;c.blank_penalty=0.f;
        emit("{\"kind\":\"start\",\"sample_rate\":16000,\"feature_dim\":80,\"push_frames\":1600,\"threads\":1,\"padding_frames\":10560,\"endpoint_rules\":[2.4,1.2,20],\"decoding\":\"greedy_search\",\"max_active_paths\":4,\"blank_penalty\":0,\"provider\":\"cpu\"}");
        Recognizer r(SherpaOnnxCreateOnlineRecognizer(&c),&SherpaOnnxDestroyOnlineRecognizer);need(bool(r),"Recognizer creation failed");
        one(r.get(),{},"empty");one(r.get(),std::vector<float>(source.begin(),source.begin()+1281),"short_tail");
        auto first=one(r.get(),source,"saved_source");auto repeat=one(r.get(),source,"saved_source_repeat");
        need(first!="[]" && first==repeat,"Fresh resident-stream final parity failed");r.reset();
        emit("{\"kind\":\"complete\",\"recognizer_closed\":true,\"state_parity\":true,\"CM5_tested\":false,\"GUI_validated\":false}");return 0;
    }catch(const std::exception& e){emit("{\"kind\":\"failure\",\"error\":"+quoted(e.what())+"}");return 1;}
}
