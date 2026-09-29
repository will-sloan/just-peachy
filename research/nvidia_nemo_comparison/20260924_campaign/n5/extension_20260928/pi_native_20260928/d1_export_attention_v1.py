"""Process-local dense export adapter. See README_D1_ONNX_EXPORT_V2.md."""
from contextlib import contextmanager


@contextmanager
def dense_export_attention(model):
    import torch
    from nemo.collections.asr.modules import transformer_encoder as encoder
    from nemo.collections.asr.modules import transformer_encoder_utils as utils
    assert model.encoder.self_attention_model=='rope' and model.encoder.attn_mode=='full'
    assert not getattr(model.encoder,'causal_tail_len',0)
    old_mask=encoder.create_block_mask;old_attention=utils._get_flex_attention

    def dense_mask(mask_mod,B,H,Q_LEN,KV_LEN,device,**unused):
        assert H==1
        b=torch.arange(B,device=device).view(-1,1,1,1)
        q=torch.arange(Q_LEN,device=device).view(1,1,-1,1)
        k=torch.arange(KV_LEN,device=device).view(1,1,1,-1)
        # Evaluate the original key-padding predicate with broadcast indices.
        return mask_mod(b,0,q,k)

    def attention(q,k,v,block_mask=None,score_mod=None,**unused):
        assert score_mod is None,'Only the pinned RoPE attention is admitted'
        scores=torch.matmul(q,k.transpose(-2,-1))*(q.shape[-1]**-0.5)
        if block_mask is not None:scores=scores.masked_fill(~block_mask,float('-inf'))
        return torch.matmul(torch.softmax(scores,dim=-1),v)

    encoder.create_block_mask=dense_mask
    utils._get_flex_attention=lambda ignored:attention
    try:yield
    finally:
        encoder.create_block_mask=old_mask
        utils._get_flex_attention=old_attention
