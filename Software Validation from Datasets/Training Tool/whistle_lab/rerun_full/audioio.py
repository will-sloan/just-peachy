"""Reuse the audited explicit-channel audio loader."""
from runtime import shared
load_audio = shared("audioio").load_audio
