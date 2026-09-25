"""Preserve actual service geometry across NeMo's export reset; README_A1_PORTABLE.md."""
from dataclasses import asdict


def configure_service_export(service):
    encoder=service.asr_model.encoder
    before=asdict(encoder.streaming_cfg)
    if (before['cache_drop_size'],before['valid_out_len'])!=(1,1):
        raise ValueError('Expected the actual 80-ms service geometry before export')
    service.asr_model.set_export_config({'cache_support':True})
    # Pinned ASRModel.set_export_config calls setup_streaming_params() with no
    # arguments, resetting the service override. Reapply that exact override.
    encoder.setup_streaming_params(chunk_size=service.model_chunk_size//service.asr_model.cfg.encoder.subsampling_factor,
        shift_size=service.tokens_per_frame)
    if asdict(encoder.streaming_cfg)!=before:
        raise ValueError('Export changed the service streaming configuration')
    return before
