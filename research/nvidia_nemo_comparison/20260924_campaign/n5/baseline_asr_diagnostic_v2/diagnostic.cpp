// Investigation only. See README.md. Preserve the V1 implementation unchanged.
#define main preserved_baseline_v1_main
#include "../baseline_arm64_asr_v1.cpp"
#undef main

int main(int argc,char** argv){
    try{
        need(argc==6,"Expected encoder decoder joiner tokens saved-WAV");
        auto source=read_wav(argv[5]);
        uint64_t fnv=14695981039346656037ULL;double squares=0;float peak=0;size_t nonzero=0;
        for(float value:source){
            uint32_t bits=0;std::memcpy(&bits,&value,4);
            for(unsigned shift=0;shift<32;shift+=8){fnv^=(bits>>shift)&255;fnv*=1099511628211ULL;}
            squares+=double(value)*value;peak=std::max(peak,std::abs(value));nonzero+=value!=0;
        }
        std::ostringstream info;
        info<<std::setprecision(17)<<"{\"kind\":\"diagnostic_input\",\"frames\":"<<source.size()
            <<",\"nonzero\":"<<nonzero<<",\"peak\":"<<peak<<",\"sum_squares\":"<<squares
            <<",\"f32_le_fnv1a64\":\""<<std::hex<<fnv<<"\",\"sherpa_version\":"<<quoted(SherpaOnnxGetVersionStr())
            <<",\"sherpa_git\":"<<quoted(SherpaOnnxGetGitSha1())<<",\"sherpa_date\":"<<quoted(SherpaOnnxGetGitDate())<<"}";
        emit(info.str());
        SherpaOnnxOnlineRecognizerConfig c{};
        c.feat_config.sample_rate=16000;c.feat_config.feature_dim=80;
        c.model_config.transducer.encoder=argv[1];c.model_config.transducer.decoder=argv[2];c.model_config.transducer.joiner=argv[3];
        c.model_config.tokens=argv[4];c.model_config.num_threads=1;c.model_config.provider="cpu";c.model_config.debug=1;
        c.decoding_method="greedy_search";c.max_active_paths=4;c.enable_endpoint=1;
        c.rule1_min_trailing_silence=2.4f;c.rule2_min_trailing_silence=1.2f;c.rule3_min_utterance_length=20.f;c.blank_penalty=0.f;
        // A fresh recognizer without the preceding empty/short streams isolates
        // initialization order. It does not retest the full V1 state contract.
        Recognizer r(SherpaOnnxCreateOnlineRecognizer(&c),&SherpaOnnxDestroyOnlineRecognizer);need(bool(r),"Recognizer creation failed");
        auto finals=one(r.get(),source,"fresh_full_source");r.reset();
        emit(std::string("{\"kind\":\"diagnostic_complete\",\"recognizer_closed\":true,\"nonempty\":")+
            (finals=="[]" ? "false" : "true")+",\"acceptance\":false,\"CM5_tested\":false}");return 0;
    }catch(const std::exception& e){emit("{\"kind\":\"failure\",\"error\":"+quoted(e.what())+"}");return 1;}
}
