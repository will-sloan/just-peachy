// Exercise the actual patched ggml helper; see README_A76_V4.md.
#include "ggml-cpu-impl.h"
#include <cstdint>
#include <cstdio>

int main() {
    uint32_t state = 0x39592026;
    auto next = [&]() { state = state * 1664525u + 1013904223u; return state; };
    int different_native_cases = 0;
    for (int test = 0; test < 10016; ++test) {
        int8_t a[16], b[16];
        int32_t acc[4], expected[4], actual[4], ordinary[4];
        for (int j = 0; j < 16; ++j) {
            a[j] = test < 16 ? (j == test ? 1 : 0) : int(next() >> 24) - 128;
            b[j] = test < 16 ? 1 : int(next() >> 24) - 128;
        }
        for (int j = 0; j < 4; ++j) expected[j] = acc[j] = int(next() % 200001u) - 100000;
        // Generic helper groups adjacent pairs in each eight-byte half.
        for (int j = 0; j < 16; ++j) expected[(j / 2) % 4] += int(a[j]) * int(b[j]);
        vst1q_s32(actual, ggml_vdotq_s32(vld1q_s32(acc), vld1q_s8(a), vld1q_s8(b)));
        vst1q_s32(ordinary, vdotq_s32(vld1q_s32(acc), vld1q_s8(a), vld1q_s8(b)));
        bool differs = false;
        for (int j = 0; j < 4; ++j) {
            if (actual[j] != expected[j]) { std::fprintf(stderr, "lane mismatch case=%d lane=%d\n", test, j); return 1; }
            differs |= ordinary[j] != expected[j];
        }
        different_native_cases += differs;
    }
    if (!different_native_cases) return 2;
    std::printf("PASS 10016 exact generic-lane cases; ordinary-native differences=%d\n", different_native_cases);
    return 0;
}
