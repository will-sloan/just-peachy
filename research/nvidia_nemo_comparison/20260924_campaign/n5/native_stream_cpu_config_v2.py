"""Native QEMU invocation contract; README_NATIVE_STREAM_CPU_V2.md."""
from native_stream_review_v1 import require
from run_baseline_asr_cpu_v5 import check_cpu_help


def cpu_argv(original, cpu):
    require(cpu == 'cortex-a76', 'Only the admitted CPU is allowed')
    require(len(original) == 8 and original[1] == '-L' and original[3] == '-E'
            and original[4].startswith('LD_LIBRARY_PATH=') and '-cpu' not in original,
            'Unexpected native model command')
    return [original[0], '-cpu', cpu, *original[1:]]
