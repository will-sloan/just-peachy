"""Download optional inference model assets into the project cache."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from urllib.parse import urlsplit, urlunsplit
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_ROOT = PROJECT_ROOT / "models" / "cache"
ALLOWED_WHISPER_MODELS = frozenset(
    {"tiny", "tiny.en", "base", "base.en", "small", "small.en"}
)
SHERPA_ASR_ARCHIVE = "sherpa-onnx-streaming-zipformer-en-2023-06-26.tar.bz2"
SHERPA_ASR_DIRECTORY = "sherpa-onnx-streaming-zipformer-en-2023-06-26"
SHERPA_ASR_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    f"{SHERPA_ASR_ARCHIVE}"
)
SHERPA_ASR_SHA256 = "639e25b578e9e997131402199419c13a941f8e4e198e2da1ce57dbf5cf401282"
SHERPA_ASR_MARKERS = (
    "tokens.txt",
    "encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx",
    "decoder-epoch-99-avg-1-chunk-16-left-128.onnx",
    "joiner-epoch-99-avg-1-chunk-16-left-128.int8.onnx",
)
SHERPA_LIBRI_GIGA_ARCHIVE = "sherpa-onnx-streaming-zipformer-en-2023-06-21.tar.bz2"
SHERPA_LIBRI_GIGA_DIRECTORY = "sherpa-onnx-streaming-zipformer-en-2023-06-21"
SHERPA_LIBRI_GIGA_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    f"{SHERPA_LIBRI_GIGA_ARCHIVE}"
)
SHERPA_LIBRI_GIGA_ARCHIVE_SHA256 = (
    "455f40e556aa2b20ac9d3bffd603b58002075c1193b4070938540c11efe0a4da"
)
SHERPA_LIBRI_GIGA_MARKERS = (
    "tokens.txt",
    "encoder-epoch-99-avg-1.int8.onnx",
    "decoder-epoch-99-avg-1.onnx",
    "joiner-epoch-99-avg-1.int8.onnx",
)

VOSK_ASR_ARCHIVE = "vosk-model-small-en-us-0.15.zip"
VOSK_ASR_DIRECTORY = "vosk-model-small-en-us-0.15"
VOSK_ASR_URL = f"https://alphacephei.com/vosk/models/{VOSK_ASR_ARCHIVE}"
VOSK_ASR_SHA256 = "30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498"
VOSK_ASR_MARKERS = ("am/final.mdl", "conf/model.conf", "graph/HCLr.fst")

WENET_ASR_ARCHIVE = "librispeech_u2pp_conformer_exp.tar.gz"
WENET_ASR_DIRECTORY = "librispeech_u2pp_conformer_exp"
WENET_MODEL_REVISION = "9161c07e35d505087c98fef201a2c3ab0995e53a"
WENET_ASR_URL = (
    "https://huggingface.co/openspeech/wenet-models/resolve/"
    f"{WENET_MODEL_REVISION}/{WENET_ASR_ARCHIVE}"
)
WENET_ASR_SHA256 = "fa95c21b2e11b6c4c887cd5f92eeb4f9390069d4ac7cb7ea156e1594849135d9"
WENET_ASR_MARKERS = (
    "final.pt",
    "global_cmvn",
    "train.yaml",
    "train_960_unigram5000.model",
    "units.txt",
)

FASTER_WHISPER_REPOSITORY = "Systran/faster-whisper-tiny"
FASTER_WHISPER_REVISION = "d90ca5fe260221311c53c58e660288d3deb8d356"
FASTER_WHISPER_MARKERS = (
    "config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.txt",
)

SHERPA_VAD_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/silero_vad.onnx"
)
SHERPA_VAD_SHA256 = "9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6"
SHERPA_EMBEDDING_FILENAME = "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"
SHERPA_EMBEDDING_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    f"speaker-recongition-models/{SHERPA_EMBEDDING_FILENAME}"
)
SHERPA_EMBEDDING_SHA256 = (
    "1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b"
)
SHERPA_SEGMENTATION_ARCHIVE = "sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
SHERPA_SEGMENTATION_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    f"speaker-segmentation-models/{SHERPA_SEGMENTATION_ARCHIVE}"
)
SHERPA_SEGMENTATION_SHA256 = (
    "24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488"
)
WESPEAKER_ARCHIVE = "voxceleb_resnet221_LM.tar.gz"
WESPEAKER_ARCHIVE_DIRECTORY = "voxceleb_resnet221_LM"
WESPEAKER_SHA256 = "9462705bfafeed7b4a6585638a4d0140ddaf9338471198d014eb2579712f89f6"
WESPEAKER_MODEL_SHA256 = (
    "47d76239f1e865b273e31e30f691959061ff6565ed6c4e7be9639a65d9662eb5"
)
WESPEAKER_CONFIG_SHA256 = (
    "31511c8e6c60d96d40962e9a261dd8f752b01831b955192b5cbed8367276bbb5"
)
WESPEAKER_MODELSCOPE_INDEX = (
    "https://modelscope.cn/api/v1/datasets/wenet/wespeaker_pretrained_models/oss/tree"
)
NEMO_DIARIZATION_CONFIG_URL = (
    "https://raw.githubusercontent.com/NVIDIA/NeMo/v2.7.3/examples/speaker_tasks/"
    "diarization/conf/inference/diar_infer_meeting.yaml"
)

SHERPA_STREAMING_20M_ARCHIVE = (
    "sherpa-onnx-streaming-zipformer-en-20M-2023-02-17.tar.bz2"
)
SHERPA_STREAMING_20M_DIRECTORY = "sherpa-onnx-streaming-zipformer-en-20M-2023-02-17"
SHERPA_STREAMING_20M_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    f"{SHERPA_STREAMING_20M_ARCHIVE}"
)
SHERPA_STREAMING_20M_ARCHIVE_SHA256 = (
    "9c559283e8498d3fe95913c79ca1cb454bb26281ac2b102b41306c7d752765d9"
)
SHERPA_STREAMING_20M_MARKERS = (
    "tokens.txt",
    "encoder-epoch-99-avg-1.int8.onnx",
    "decoder-epoch-99-avg-1.int8.onnx",
    "joiner-epoch-99-avg-1.int8.onnx",
)
CAMPPLUS_FILENAME = "3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx"
CAMPPLUS_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
    f"speaker-recongition-models/{CAMPPLUS_FILENAME}"
)
CAMPPLUS_SHA256 = "357a834f702b80161e5b981182c038e18553c1f2ca752ed6cec2052365d4129b"
FSMN_BASE_URL = (
    "https://modelscope.cn/models/iic/"
    "speech_fsmn_vad_zh-cn-16k-common-onnx/resolve/master"
)
FSMN_FILES = {
    "am.mvn": "6820fef9687708c4fc3fab2530179c8fcea6262daa25514380056cd8f6eb1754",
    "config.yaml": "2ef334f2d7776edd86ed696296774f87550206c256bfabc597872ad861831589",
    "model_quant.onnx": "5289eb2aa3c9af2d7a4284bcfa7c3ceb81d360814ed4203239b6c5d0569da8a1",
}
MOONSHINE_STREAMING_ARCHES = {
    "tiny": "TINY_STREAMING",
    "small": "SMALL_STREAMING",
    "medium": "MEDIUM_STREAMING",
}


def file_sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest for one file."""

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(
    url: str,
    destination: Path,
    *,
    expected_sha256: str | None = None,
    refresh: bool = False,
) -> Path:
    """Download one public model asset and verify its immutable digest."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size > 0 and not refresh:
        if expected_sha256 and file_sha256(destination) != expected_sha256.lower():
            raise RuntimeError(
                f"cached asset failed SHA-256 verification: {destination}"
            )
        print(f"Using cached asset {destination}")
        return destination
    # Public model indexes may return temporary signed object-store URLs.
    # Query values are unnecessary for audit logs and may contain signatures.
    split_url = urlsplit(url)
    log_url = urlunsplit((split_url.scheme, split_url.netloc, split_url.path, "", ""))
    print(f"Downloading {log_url} to {destination}")
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "just-peachy/1"})
        with urllib.request.urlopen(request, timeout=60) as response:
            with temporary.open("wb") as stream:
                shutil.copyfileobj(response, stream, length=1024 * 1024)
        if temporary.stat().st_size == 0:
            raise RuntimeError(f"downloaded asset is empty: {url}")
        if expected_sha256 and file_sha256(temporary) != expected_sha256.lower():
            raise RuntimeError(f"downloaded asset failed SHA-256 verification: {url}")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def extract_tar_safely(archive: Path, destination: Path) -> None:
    """Extract an archive after rejecting traversal, links, and device entries."""

    destination_root = destination.resolve()
    with tarfile.open(archive, "r:*") as handle:
        for member in handle.getmembers():
            target = (destination / member.name).resolve()
            if not target.is_relative_to(destination_root):
                raise RuntimeError(f"unsafe archive member: {member.name}")
            if member.issym() or member.islnk() or member.isdev():
                raise RuntimeError(f"unsupported archive member: {member.name}")
        if sys.version_info >= (3, 12):
            handle.extractall(destination, filter="data")
        else:  # Python 3.10-3.11 use the explicit checks above.
            handle.extractall(destination)


def extract_zip_safely(archive: Path, destination: Path) -> None:
    """Extract a ZIP after rejecting traversal paths and symbolic links."""

    destination_root = destination.resolve()
    with zipfile.ZipFile(archive) as handle:
        for member in handle.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination_root):
                raise RuntimeError(f"unsafe archive member: {member.filename}")
            mode = (member.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                raise RuntimeError(f"unsupported archive member: {member.filename}")
        handle.extractall(destination)


def install_model_archive(
    archive: Path,
    *,
    destination: Path,
    archive_directory: str,
    markers: tuple[str, ...],
) -> Path:
    """Safely extract one model directory and verify every runtime marker."""

    if all((destination / marker).is_file() for marker in markers):
        print(f"Using cached model {destination}")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}-",
        dir=destination.parent,
    ) as temporary_directory:
        staging = Path(temporary_directory)
        if archive.suffix.lower() == ".zip":
            extract_zip_safely(archive, staging)
        else:
            extract_tar_safely(archive, staging)
        source = staging / archive_directory
        missing = [marker for marker in markers if not (source / marker).is_file()]
        if missing:
            raise RuntimeError(
                f"{archive.name} is missing required model assets: {', '.join(missing)}"
            )
        shutil.copytree(source, destination, dirs_exist_ok=True)
    missing = [marker for marker in markers if not (destination / marker).is_file()]
    if missing:
        raise RuntimeError(
            f"model extraction did not create required assets: {', '.join(missing)}"
        )
    return destination


def download_whisper(models: list[str], cache_root: Path) -> None:
    validate_whisper_models(models)
    import whisper

    destination = cache_root / "whisper"
    destination.mkdir(parents=True, exist_ok=True)
    available = set(whisper.available_models())
    for model_name in models:
        if model_name not in available:
            known = ", ".join(sorted(available))
            raise ValueError(
                f"unknown Whisper model {model_name!r}; available: {known}"
            )
        print(f"Downloading Whisper {model_name} to {destination}")
        model_urls = getattr(whisper, "_MODELS", {})
        downloader: Callable[..., object] | None = getattr(whisper, "_download", None)
        if model_name in model_urls and callable(downloader):
            downloader(model_urls[model_name], str(destination), False)
        else:
            model = whisper.load_model(
                model_name,
                device="cpu",
                download_root=str(destination),
            )
            del model
            gc.collect()


def validate_whisper_models(models: list[str]) -> None:
    """Reject every Whisper checkpoint outside the approved small-model set."""

    rejected = [model for model in models if model not in ALLOWED_WHISPER_MODELS]
    if rejected:
        allowed = ", ".join(sorted(ALLOWED_WHISPER_MODELS))
        raise ValueError(
            "Whisper model(s) are prohibited or unsupported: "
            f"{', '.join(rejected)}. Allowed models: {allowed}"
        )


def download_speechbrain(cache_root: Path, device: str) -> None:
    try:
        from speechbrain.inference.speaker import EncoderClassifier
    except Exception:
        from speechbrain.pretrained import EncoderClassifier
    from speechbrain.utils.fetching import LocalStrategy

    destination = cache_root / "speechbrain" / "spkrec-ecapa-voxceleb"
    destination.mkdir(parents=True, exist_ok=True)
    print(f"Downloading SpeechBrain ECAPA to {destination}")
    model = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(destination),
        run_opts={"device": device},
        local_strategy=LocalStrategy.COPY,
    )
    del model
    gc.collect()


def download_silero() -> None:
    from silero_vad import load_silero_vad

    print("Loading packaged Silero VAD assets")
    model = load_silero_vad()
    del model
    gc.collect()


def download_sherpa_asr(cache_root: Path) -> None:
    archive = download_file(
        SHERPA_ASR_URL,
        cache_root / "downloads" / SHERPA_ASR_ARCHIVE,
        expected_sha256=SHERPA_ASR_SHA256,
    )
    install_model_archive(
        archive,
        destination=cache_root / "sherpa_onnx" / "asr" / SHERPA_ASR_DIRECTORY,
        archive_directory=SHERPA_ASR_DIRECTORY,
        markers=SHERPA_ASR_MARKERS,
    )


def download_sherpa_libri_giga(cache_root: Path) -> None:
    archive = download_file(
        SHERPA_LIBRI_GIGA_URL,
        cache_root / "downloads" / SHERPA_LIBRI_GIGA_ARCHIVE,
        expected_sha256=SHERPA_LIBRI_GIGA_ARCHIVE_SHA256,
    )
    install_model_archive(
        archive,
        destination=(cache_root / "sherpa_onnx" / "asr" / SHERPA_LIBRI_GIGA_DIRECTORY),
        archive_directory=SHERPA_LIBRI_GIGA_DIRECTORY,
        markers=SHERPA_LIBRI_GIGA_MARKERS,
    )


def download_sherpa_streaming_20m(cache_root: Path) -> None:
    archive = download_file(
        SHERPA_STREAMING_20M_URL,
        cache_root / "downloads" / SHERPA_STREAMING_20M_ARCHIVE,
        expected_sha256=SHERPA_STREAMING_20M_ARCHIVE_SHA256,
    )
    install_model_archive(
        archive,
        destination=(
            cache_root / "sherpa_onnx" / "asr" / SHERPA_STREAMING_20M_DIRECTORY
        ),
        archive_directory=SHERPA_STREAMING_20M_DIRECTORY,
        markers=SHERPA_STREAMING_20M_MARKERS,
    )


def download_campplus(cache_root: Path) -> None:
    download_file(
        CAMPPLUS_URL,
        cache_root / "sherpa_onnx" / "speaker_embedding" / CAMPPLUS_FILENAME,
        expected_sha256=CAMPPLUS_SHA256,
    )


def download_fsmn_vad(cache_root: Path) -> None:
    destination = (
        cache_root / "funasr" / "vad" / "speech_fsmn_vad_zh-cn-16k-common-onnx"
    )
    for filename, digest in FSMN_FILES.items():
        download_file(
            f"{FSMN_BASE_URL}/{filename}",
            destination / filename,
            expected_sha256=digest,
        )


def download_moonshine_streaming(cache_root: Path, sizes: list[str]) -> None:
    if not sizes:
        return
    try:
        from moonshine_voice.download import get_model_for_language
        from moonshine_voice.moonshine_api import ModelArch
    except ImportError as exc:
        raise RuntimeError(
            "moonshine-voice must be installed before downloading Moonshine assets"
        ) from exc
    for size in sizes:
        architecture = getattr(ModelArch, MOONSHINE_STREAMING_ARCHES[size])
        path, _arch = get_model_for_language(
            "en", architecture, cache_root=cache_root / "moonshine"
        )
        print(f"Prepared Moonshine streaming {size}: {path}")


def download_edge_models(cache_root: Path) -> None:
    download_moonshine_streaming(cache_root, ["tiny", "small", "medium"])
    download_sherpa_libri_giga(cache_root)
    download_sherpa_streaming_20m(cache_root)
    download_campplus(cache_root)
    download_sherpa_embedding(cache_root)
    download_fsmn_vad(cache_root)


def download_vosk_asr(cache_root: Path) -> None:
    archive = download_file(
        VOSK_ASR_URL,
        cache_root / "downloads" / VOSK_ASR_ARCHIVE,
        expected_sha256=VOSK_ASR_SHA256,
    )
    install_model_archive(
        archive,
        destination=cache_root / "vosk" / "asr" / VOSK_ASR_DIRECTORY,
        archive_directory=VOSK_ASR_DIRECTORY,
        markers=VOSK_ASR_MARKERS,
    )


def download_wenet_asr(cache_root: Path) -> None:
    archive = download_file(
        WENET_ASR_URL,
        cache_root / "downloads" / WENET_ASR_ARCHIVE,
        expected_sha256=WENET_ASR_SHA256,
    )
    install_model_archive(
        archive,
        destination=cache_root / "wenet" / "asr" / WENET_ASR_DIRECTORY,
        archive_directory=WENET_ASR_DIRECTORY,
        markers=WENET_ASR_MARKERS,
    )


def download_faster_whisper_tiny(cache_root: Path) -> None:
    destination = cache_root / "faster_whisper" / "tiny"
    if all((destination / marker).is_file() for marker in FASTER_WHISPER_MARKERS):
        print(f"Using cached model {destination}")
        return
    from huggingface_hub import snapshot_download

    destination.mkdir(parents=True, exist_ok=True)
    print(
        f"Downloading {FASTER_WHISPER_REPOSITORY}@{FASTER_WHISPER_REVISION} "
        f"to {destination}"
    )
    snapshot_download(
        repo_id=FASTER_WHISPER_REPOSITORY,
        revision=FASTER_WHISPER_REVISION,
        local_dir=str(destination),
        allow_patterns=list(FASTER_WHISPER_MARKERS),
    )
    missing = [
        marker
        for marker in FASTER_WHISPER_MARKERS
        if not (destination / marker).is_file()
    ]
    if missing:
        raise RuntimeError(
            "Faster-Whisper snapshot is missing required assets: " + ", ".join(missing)
        )


def download_sherpa_vad(cache_root: Path) -> None:
    download_file(
        SHERPA_VAD_URL,
        cache_root / "sherpa_onnx" / "vad" / "silero_vad.onnx",
        expected_sha256=SHERPA_VAD_SHA256,
    )


def download_sherpa_embedding(cache_root: Path) -> None:
    download_file(
        SHERPA_EMBEDDING_URL,
        cache_root / "sherpa_onnx" / "speaker_embedding" / SHERPA_EMBEDDING_FILENAME,
        expected_sha256=SHERPA_EMBEDDING_SHA256,
    )


def download_sherpa_diarization(cache_root: Path) -> None:
    destination = (
        cache_root
        / "sherpa_onnx"
        / "diarization"
        / "sherpa-onnx-pyannote-segmentation-3-0"
    )
    archive = download_file(
        SHERPA_SEGMENTATION_URL,
        cache_root / "downloads" / SHERPA_SEGMENTATION_ARCHIVE,
        expected_sha256=SHERPA_SEGMENTATION_SHA256,
    )
    install_model_archive(
        archive,
        destination=destination,
        archive_directory="sherpa-onnx-pyannote-segmentation-3-0",
        markers=("model.onnx",),
    )


def download_wespeaker(cache_root: Path) -> None:
    destination = cache_root / "wespeaker" / "english"
    markers = ("avg_model.pt", "config.yaml")
    if (
        all((destination / marker).is_file() for marker in markers)
        and file_sha256(destination / "avg_model.pt") == WESPEAKER_MODEL_SHA256
        and file_sha256(destination / "config.yaml") == WESPEAKER_CONFIG_SHA256
    ):
        print(f"Using cached model {destination}")
        return
    request = urllib.request.Request(
        WESPEAKER_MODELSCOPE_INDEX,
        headers={"User-Agent": "just-peachy/1"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        index = json.load(response)
    entries = index.get("Data", []) if isinstance(index, dict) else []
    model_entry = next(
        (
            entry
            for entry in entries
            if isinstance(entry, dict) and entry.get("Key") == WESPEAKER_ARCHIVE
        ),
        None,
    )
    if not model_entry or not model_entry.get("Url"):
        raise RuntimeError(
            f"WeSpeaker ModelScope index did not contain {WESPEAKER_ARCHIVE}"
        )
    archive = download_file(
        str(model_entry["Url"]),
        cache_root / "downloads" / WESPEAKER_ARCHIVE,
        expected_sha256=WESPEAKER_SHA256,
    )
    install_model_archive(
        archive,
        destination=destination,
        archive_directory=WESPEAKER_ARCHIVE_DIRECTORY,
        markers=markers,
    )
    if file_sha256(destination / "avg_model.pt") != WESPEAKER_MODEL_SHA256:
        raise RuntimeError("WeSpeaker avg_model.pt failed SHA-256 verification")
    if file_sha256(destination / "config.yaml") != WESPEAKER_CONFIG_SHA256:
        raise RuntimeError("WeSpeaker config.yaml failed SHA-256 verification")


def download_nemo_config(cache_root: Path) -> None:
    download_file(
        NEMO_DIARIZATION_CONFIG_URL,
        cache_root / "nemo" / "diarization" / "config.yaml",
        refresh=True,
    )


def download_pyannote(cache_root: Path, token_env: str) -> None:
    from pyannote.audio import Pipeline

    token = os.environ.get(token_env)
    if not token:
        raise RuntimeError(
            f"{token_env} is not set; pyannote community model access requires "
            "a Hugging Face token"
        )
    destination = cache_root / "pyannote"
    destination.mkdir(parents=True, exist_ok=True)
    source = "pyannote/speaker-diarization-community-1"
    print(f"Downloading {source} to {destination}")
    try:
        pipeline = Pipeline.from_pretrained(
            source,
            token=token,
            cache_dir=str(destination),
        )
    except TypeError:
        pipeline = Pipeline.from_pretrained(
            source,
            use_auth_token=token,
            cache_dir=str(destination),
        )
    del pipeline
    gc.collect()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=DEFAULT_CACHE_ROOT,
        help="Shared model cache root.",
    )
    parser.add_argument(
        "--whisper",
        default="",
        help=(
            "Comma-separated approved OpenAI Whisper models: tiny, tiny.en, "
            "base, base.en, small, small.en."
        ),
    )
    parser.add_argument("--speechbrain-ecapa", action="store_true")
    parser.add_argument("--silero", action="store_true")
    parser.add_argument("--pyannote", action="store_true")
    parser.add_argument("--sherpa-asr", action="store_true")
    parser.add_argument("--sherpa-libri-giga", action="store_true")
    parser.add_argument("--vosk-asr", action="store_true")
    parser.add_argument("--wenet-asr", action="store_true")
    parser.add_argument("--faster-whisper-tiny", action="store_true")
    parser.add_argument("--sherpa-vad", action="store_true")
    parser.add_argument("--sherpa-speaker-embedding", action="store_true")
    parser.add_argument("--sherpa-diarization", action="store_true")
    parser.add_argument("--wespeaker", action="store_true")
    parser.add_argument("--nemo-config", action="store_true")
    parser.add_argument("--sherpa-streaming-20m", action="store_true")
    parser.add_argument("--campplus", action="store_true")
    parser.add_argument("--eres2net-base", action="store_true")
    parser.add_argument("--fsmn-vad", action="store_true")
    parser.add_argument(
        "--moonshine-streaming",
        default="",
        help="Comma-separated Moonshine English streaming sizes: tiny,small,medium.",
    )
    parser.add_argument(
        "--edge-models",
        action="store_true",
        help="Prepare every approved required edge component asset.",
    )
    parser.add_argument("--hf-token-env", default="PYANNOTE_AUTH_TOKEN")
    parser.add_argument(
        "--device",
        choices=("cpu", "cuda"),
        default="cpu",
        help=(
            "Device used while initializing models that must be loaded after download."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    whisper_models = [item.strip() for item in args.whisper.split(",") if item.strip()]
    try:
        validate_whisper_models(whisper_models)
    except ValueError as exc:
        print(f"[FAIL] Whisper policy: {exc}", file=sys.stderr)
        return 2
    cache_root = args.cache_root.expanduser().resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    moonshine_sizes = [
        item.strip().lower()
        for item in args.moonshine_streaming.split(",")
        if item.strip()
    ]
    unknown_moonshine = sorted(set(moonshine_sizes) - set(MOONSHINE_STREAMING_ARCHES))
    if unknown_moonshine:
        print(
            f"[FAIL] Unknown Moonshine streaming size(s): {unknown_moonshine}",
            file=sys.stderr,
        )
        return 2
    tasks: list[tuple[str, Callable[[], None]]] = []
    if whisper_models:
        tasks.append(("Whisper", lambda: download_whisper(whisper_models, cache_root)))
    if args.speechbrain_ecapa:
        tasks.append(
            ("SpeechBrain ECAPA", lambda: download_speechbrain(cache_root, args.device))
        )
    if args.silero:
        tasks.append(("Silero VAD", download_silero))
    if args.pyannote:
        tasks.append(
            ("pyannote", lambda: download_pyannote(cache_root, args.hf_token_env))
        )
    if args.sherpa_asr:
        tasks.append(("Sherpa-ONNX ASR", lambda: download_sherpa_asr(cache_root)))
    if args.sherpa_libri_giga:
        tasks.append(
            (
                "Sherpa-ONNX LibriSpeech+GigaSpeech Zipformer",
                lambda: download_sherpa_libri_giga(cache_root),
            )
        )
    if args.vosk_asr:
        tasks.append(("Vosk ASR", lambda: download_vosk_asr(cache_root)))
    if args.wenet_asr:
        tasks.append(("WeNet ASR", lambda: download_wenet_asr(cache_root)))
    if args.faster_whisper_tiny:
        tasks.append(
            (
                "Faster-Whisper Tiny ASR",
                lambda: download_faster_whisper_tiny(cache_root),
            )
        )
    if args.sherpa_vad:
        tasks.append(("Sherpa-ONNX VAD", lambda: download_sherpa_vad(cache_root)))
    if args.sherpa_speaker_embedding:
        tasks.append(
            (
                "Sherpa-ONNX speaker embedding",
                lambda: download_sherpa_embedding(cache_root),
            )
        )
    if args.sherpa_diarization:
        tasks.append(
            ("Sherpa-ONNX diarization", lambda: download_sherpa_diarization(cache_root))
        )
    if args.wespeaker:
        tasks.append(("WeSpeaker English", lambda: download_wespeaker(cache_root)))
    if args.nemo_config:
        tasks.append(
            (
                "NeMo meeting diarization example config (not model weights)",
                lambda: download_nemo_config(cache_root),
            )
        )
    if moonshine_sizes:
        tasks.append(
            (
                "Moonshine streaming English",
                lambda: download_moonshine_streaming(cache_root, moonshine_sizes),
            )
        )
    if args.sherpa_streaming_20m:
        tasks.append(
            (
                "Sherpa-ONNX streaming Zipformer 20M INT8",
                lambda: download_sherpa_streaming_20m(cache_root),
            )
        )
    if args.campplus:
        tasks.append(("CAM++ English VoxCeleb", lambda: download_campplus(cache_root)))
    if args.eres2net_base:
        tasks.append(("ERes2Net-base", lambda: download_sherpa_embedding(cache_root)))
    if args.fsmn_vad:
        tasks.append(("FSMN-VAD", lambda: download_fsmn_vad(cache_root)))
    if args.edge_models:
        tasks.append(
            ("Approved edge model bundle", lambda: download_edge_models(cache_root))
        )
    if not tasks:
        print(
            "No models selected. Choose an approved Whisper, SpeechBrain, Silero, "
            "Sherpa, Vosk, WeNet, WeSpeaker, pyannote, or NeMo option."
        )
        return 0

    failures: list[str] = []
    for label, task in tasks:
        try:
            task()
            print(f"[PASS] {label}")
        except Exception as exc:
            failures.append(f"{label}: {exc}")
            print(f"[FAIL] {label}: {exc}", file=sys.stderr)
    if failures:
        print("Model bootstrap completed with failures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Model bootstrap complete: {cache_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
