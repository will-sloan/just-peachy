"""Content-addressed caches for the incremental full-pipeline runtime.

The cache identity is deliberately stricter than the older batch embedding
cache.  A vector is reusable only when its role, exact audio content/range,
window policy, preprocessing, model identity, and component configuration all
match.  Paths and display labels are provenance, not identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Mapping, Sequence
import uuid


CACHE_KEY_SCHEMA = "full-pipeline-content-cache-key.v1"
CACHE_ENTRY_SCHEMA = "full-pipeline-content-cache-entry.v1"
RUNTIME_CACHE_KEY_SCHEMA = "full-pipeline-runtime-cache-key.v1"


@dataclass(frozen=True)
class RuntimeCacheSpec:
    """Locked semantics for one reusable full-pipeline cache product."""

    cache_kind: str
    role: str
    source_contract: str
    allowed_source_modes: frozenset[str]
    allowed_upstream_kinds: frozenset[str]
    required_upstream_groups: tuple[frozenset[str], ...] = ()
    payload_scope: str = "deterministic_result"
    stores_decoded_audio: bool = False
    caches_live_microphone_audio_by_default: bool = False
    replays_partial_event_timing: bool = False


RUNTIME_CACHE_CATALOG: Mapping[str, RuntimeCacheSpec] = {
    "decoded_resampled_audio": RuntimeCacheSpec(
        cache_kind="decoded_resampled_audio",
        role="decoded_resampled_audio",
        source_contract="audio_range",
        allowed_source_modes=frozenset(
            {"replay_file", "dataset", "enrollment", "live_microphone"}
        ),
        allowed_upstream_kinds=frozenset(),
        payload_scope="decoded_resampled_audio_only",
        stores_decoded_audio=True,
    ),
    "pyannote_segmentation": RuntimeCacheSpec(
        cache_kind="pyannote_segmentation",
        role="anonymous_diarization_segmentation",
        source_contract="audio_range",
        allowed_source_modes=frozenset({"replay_file", "dataset", "live_microphone"}),
        allowed_upstream_kinds=frozenset({"decoded_resampled_audio"}),
        required_upstream_groups=(frozenset({"decoded_resampled_audio"}),),
    ),
    "diarization_windows": RuntimeCacheSpec(
        cache_kind="diarization_windows",
        role="anonymous_diarization_windows",
        source_contract="audio_range",
        allowed_source_modes=frozenset({"replay_file", "dataset", "live_microphone"}),
        allowed_upstream_kinds=frozenset({"pyannote_segmentation"}),
        required_upstream_groups=(frozenset({"pyannote_segmentation"}),),
    ),
    "diarization_embeddings": RuntimeCacheSpec(
        cache_kind="diarization_embeddings",
        role="anonymous_diarization",
        source_contract="audio_range",
        allowed_source_modes=frozenset({"replay_file", "dataset", "live_microphone"}),
        allowed_upstream_kinds=frozenset({"diarization_windows"}),
        required_upstream_groups=(frozenset({"diarization_windows"}),),
        payload_scope="diarization_embedding_vector",
    ),
    "identity_embeddings": RuntimeCacheSpec(
        cache_kind="identity_embeddings",
        role="identity_matching",
        source_contract="audio_range",
        allowed_source_modes=frozenset({"replay_file", "dataset", "live_microphone"}),
        allowed_upstream_kinds=frozenset({"diarization_windows"}),
        required_upstream_groups=(frozenset({"diarization_windows"}),),
        payload_scope="identity_probe_embedding_vector",
    ),
    "enrollment_embeddings": RuntimeCacheSpec(
        cache_kind="enrollment_embeddings",
        role="enrollment_embedding",
        source_contract="audio_range",
        allowed_source_modes=frozenset({"enrollment"}),
        allowed_upstream_kinds=frozenset({"decoded_resampled_audio"}),
        required_upstream_groups=(frozenset({"decoded_resampled_audio"}),),
        payload_scope="biometric_enrollment_embedding_vector",
    ),
    "asr_finalized_results": RuntimeCacheSpec(
        cache_kind="asr_finalized_results",
        role="asr_finalized_result",
        source_contract="audio_range",
        allowed_source_modes=frozenset({"replay_file", "dataset", "live_microphone"}),
        allowed_upstream_kinds=frozenset({"decoded_resampled_audio"}),
        required_upstream_groups=(frozenset({"decoded_resampled_audio"}),),
        payload_scope="finalized_result_only_no_partial_timing_replay",
        replays_partial_event_timing=False,
    ),
    "score_matrices": RuntimeCacheSpec(
        cache_kind="score_matrices",
        role="speaker_score_matrix",
        source_contract="probe_and_reference_sets",
        allowed_source_modes=frozenset({"aggregate"}),
        allowed_upstream_kinds=frozenset(
            {
                "diarization_embeddings",
                "identity_embeddings",
                "enrollment_embeddings",
            }
        ),
        required_upstream_groups=(
            frozenset(
                {
                    "diarization_embeddings",
                    "identity_embeddings",
                    "enrollment_embeddings",
                }
            ),
        ),
        payload_scope="raw_score_matrix_with_explicit_score_type",
    ),
}


class CacheContractError(ValueError):
    """Raised when a cache identity or stored entry is incomplete."""


def canonical_json(value: object) -> str:
    """Return the stable JSON representation used for cache identities."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_digest(value: object, field_name: str) -> str:
    digest = str(value).lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise CacheContractError(f"{field_name} must be a SHA-256 digest")
    return digest


@dataclass(frozen=True)
class ResultAffectingIdentity:
    """Named, self-hashed parameters that can change a cached result."""

    identity_id: str
    parameters: Mapping[str, object]

    def __post_init__(self) -> None:
        identity_id = str(self.identity_id).strip()
        if not identity_id:
            raise CacheContractError("identity_id must be non-empty")
        if not isinstance(self.parameters, Mapping) or not self.parameters:
            raise CacheContractError("identity parameters must be a non-empty mapping")
        try:
            parameters = json.loads(canonical_json(dict(self.parameters)))
        except (TypeError, ValueError) as exc:
            raise CacheContractError("identity parameters must be finite JSON") from exc
        if not isinstance(parameters, dict) or not parameters:
            raise CacheContractError("identity parameters must be a non-empty object")
        object.__setattr__(self, "identity_id", identity_id)
        object.__setattr__(self, "parameters", parameters)

    @property
    def digest(self) -> str:
        return canonical_sha256(
            {"identity_id": self.identity_id, "parameters": self.parameters}
        )

    def to_jsonable(self) -> dict[str, object]:
        return {
            "identity_id": self.identity_id,
            "identity_sha256": self.digest,
            "parameters": dict(self.parameters),
        }


@dataclass(frozen=True)
class CacheDependency:
    """Typed upstream cache key used to reject cross-role substitution."""

    cache_kind: str
    cache_key_sha256: str

    def __post_init__(self) -> None:
        if self.cache_kind not in RUNTIME_CACHE_CATALOG:
            raise CacheContractError(
                f"unsupported upstream cache kind: {self.cache_kind}"
            )
        object.__setattr__(
            self,
            "cache_key_sha256",
            _sha256_digest(self.cache_key_sha256, "cache_key_sha256"),
        )

    def to_jsonable(self) -> dict[str, str]:
        return {
            "cache_kind": self.cache_kind,
            "cache_key_sha256": self.cache_key_sha256,
        }


@dataclass(frozen=True)
class RuntimeCacheKey:
    """Catalog-bound cache identity for one of the eight reusable products."""

    cache_kind: str
    source_mode: str
    source_identity: ResultAffectingIdentity
    window_identity: ResultAffectingIdentity
    preprocessing_identity: ResultAffectingIdentity
    producer_identity: ResultAffectingIdentity
    configuration_identity: ResultAffectingIdentity
    upstream_dependencies: tuple[CacheDependency, ...] = ()
    live_microphone_audio_opt_in: bool = False
    schema_version: str = RUNTIME_CACHE_KEY_SCHEMA

    def __post_init__(self) -> None:
        spec = runtime_cache_spec(self.cache_kind)
        if self.source_mode not in spec.allowed_source_modes:
            raise CacheContractError(
                f"source mode {self.source_mode!r} is not valid for {self.cache_kind}"
            )
        for field_name in (
            "source_identity",
            "window_identity",
            "preprocessing_identity",
            "producer_identity",
            "configuration_identity",
        ):
            if not isinstance(getattr(self, field_name), ResultAffectingIdentity):
                raise CacheContractError(
                    f"{field_name} must be a ResultAffectingIdentity"
                )
        dependencies = tuple(self.upstream_dependencies)
        if any(not isinstance(value, CacheDependency) for value in dependencies):
            raise CacheContractError(
                "upstream_dependencies must contain CacheDependency values"
            )
        identities = {
            (value.cache_kind, value.cache_key_sha256) for value in dependencies
        }
        if len(identities) != len(dependencies):
            raise CacheContractError("upstream cache dependencies must be unique")
        observed_kinds = {value.cache_kind for value in dependencies}
        unsupported = observed_kinds - spec.allowed_upstream_kinds
        if unsupported:
            raise CacheContractError(
                f"unsupported upstream cache kinds for {self.cache_kind}: "
                f"{sorted(unsupported)}"
            )
        for group in spec.required_upstream_groups:
            if not observed_kinds.intersection(group):
                raise CacheContractError(
                    f"{self.cache_kind} requires an upstream cache kind from "
                    f"{sorted(group)}"
                )
        if self.live_microphone_audio_opt_in and (
            self.source_mode != "live_microphone" or not spec.stores_decoded_audio
        ):
            raise CacheContractError(
                "live microphone audio opt-in is only valid for decoded audio"
            )
        if (
            spec.stores_decoded_audio
            and self.source_mode == "live_microphone"
            and not self.live_microphone_audio_opt_in
        ):
            raise CacheContractError(
                "decoded live microphone audio caching requires explicit opt-in"
            )
        _validate_runtime_source(spec, self.source_identity)
        object.__setattr__(self, "upstream_dependencies", dependencies)

    @property
    def artifact_kind(self) -> str:
        return self.cache_kind

    @property
    def role(self) -> str:
        return runtime_cache_spec(self.cache_kind).role

    def to_jsonable(self) -> dict[str, object]:
        spec = runtime_cache_spec(self.cache_kind)
        return {
            "schema_version": self.schema_version,
            "cache_kind": self.cache_kind,
            "artifact_kind": self.artifact_kind,
            "role": self.role,
            "source_mode": self.source_mode,
            "source_identity": self.source_identity.to_jsonable(),
            "window_identity": self.window_identity.to_jsonable(),
            "preprocessing_identity": self.preprocessing_identity.to_jsonable(),
            "producer_identity": self.producer_identity.to_jsonable(),
            "configuration_identity": self.configuration_identity.to_jsonable(),
            "upstream_dependencies": [
                value.to_jsonable() for value in self.upstream_dependencies
            ],
            "payload_scope": spec.payload_scope,
            "replays_partial_event_timing": spec.replays_partial_event_timing,
            "live_microphone_audio_opt_in": self.live_microphone_audio_opt_in,
        }

    @property
    def digest(self) -> str:
        return canonical_sha256(self.to_jsonable())


def runtime_cache_spec(cache_kind: str) -> RuntimeCacheSpec:
    """Return one declared cache contract or reject an invented kind."""

    try:
        return RUNTIME_CACHE_CATALOG[str(cache_kind)]
    except KeyError as exc:
        raise CacheContractError(
            f"unsupported runtime cache kind: {cache_kind}"
        ) from exc


def result_affecting_identity(
    identity_id: str, parameters: Mapping[str, object]
) -> ResultAffectingIdentity:
    """Build one immutable-in-practice result-affecting identity block."""

    return ResultAffectingIdentity(identity_id, dict(parameters))


def audio_source_identity(
    *,
    audio_sha256: str,
    start_sample: int,
    end_sample: int,
    sample_rate_hz: int,
    source_id: str = "source_audio",
    parameters: Mapping[str, object] | None = None,
) -> ResultAffectingIdentity:
    """Build the strict source contract shared by audio-derived cache kinds."""

    extras = dict(parameters or {})
    reserved = {"audio_sha256", "start_sample", "end_sample", "sample_rate_hz"}
    overlap = reserved.intersection(extras)
    if overlap:
        raise CacheContractError(
            f"audio source parameters repeat reserved fields: {sorted(overlap)}"
        )
    return ResultAffectingIdentity(
        source_id,
        {
            "audio_sha256": _sha256_digest(audio_sha256, "audio_sha256"),
            "start_sample": start_sample,
            "end_sample": end_sample,
            "sample_rate_hz": sample_rate_hz,
            **extras,
        },
    )


def score_matrix_source_identity(
    *,
    probe_set_sha256: str,
    reference_set_sha256: str,
    source_id: str = "score_matrix_inputs",
    parameters: Mapping[str, object] | None = None,
) -> ResultAffectingIdentity:
    """Bind score matrices to complete probe and reference set identities."""

    extras = dict(parameters or {})
    reserved = {"probe_set_sha256", "reference_set_sha256"}
    overlap = reserved.intersection(extras)
    if overlap:
        raise CacheContractError(
            f"score-matrix parameters repeat reserved fields: {sorted(overlap)}"
        )
    return ResultAffectingIdentity(
        source_id,
        {
            "probe_set_sha256": _sha256_digest(probe_set_sha256, "probe_set_sha256"),
            "reference_set_sha256": _sha256_digest(
                reference_set_sha256, "reference_set_sha256"
            ),
            **extras,
        },
    )


def cache_dependency(key: RuntimeCacheKey) -> CacheDependency:
    """Create a typed dependency without dropping its cache role."""

    if not isinstance(key, RuntimeCacheKey):
        raise CacheContractError("typed dependencies require a RuntimeCacheKey")
    return CacheDependency(key.cache_kind, key.digest)


def make_runtime_cache_key(
    *,
    cache_kind: str,
    source_mode: str,
    source_identity: ResultAffectingIdentity,
    window_identity: ResultAffectingIdentity,
    preprocessing_identity: ResultAffectingIdentity,
    producer_identity: ResultAffectingIdentity,
    configuration_identity: ResultAffectingIdentity,
    upstream_dependencies: Sequence[CacheDependency] = (),
    allow_live_microphone_audio: bool = False,
) -> RuntimeCacheKey:
    """Build a catalog-bound key with stage and role-safe dependencies."""

    return RuntimeCacheKey(
        cache_kind=str(cache_kind),
        source_mode=str(source_mode),
        source_identity=source_identity,
        window_identity=window_identity,
        preprocessing_identity=preprocessing_identity,
        producer_identity=producer_identity,
        configuration_identity=configuration_identity,
        upstream_dependencies=tuple(upstream_dependencies),
        live_microphone_audio_opt_in=bool(allow_live_microphone_audio),
    )


def _validate_runtime_source(
    spec: RuntimeCacheSpec, source_identity: ResultAffectingIdentity
) -> None:
    parameters = source_identity.parameters
    if spec.source_contract == "audio_range":
        required = {"audio_sha256", "start_sample", "end_sample", "sample_rate_hz"}
        missing = required - set(parameters)
        if missing:
            raise CacheContractError(
                f"audio source identity is missing fields: {sorted(missing)}"
            )
        _sha256_digest(parameters["audio_sha256"], "audio_sha256")
        start = parameters["start_sample"]
        end = parameters["end_sample"]
        rate = parameters["sample_rate_hz"]
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or start < 0
            or isinstance(end, bool)
            or not isinstance(end, int)
            or end <= start
        ):
            raise CacheContractError(
                "audio source sample range must be non-empty and increasing"
            )
        if isinstance(rate, bool) or not isinstance(rate, int) or rate <= 0:
            raise CacheContractError("audio source sample rate must be positive")
        return
    if spec.source_contract == "probe_and_reference_sets":
        required = {"probe_set_sha256", "reference_set_sha256"}
        missing = required - set(parameters)
        if missing:
            raise CacheContractError(
                f"score-matrix source identity is missing fields: {sorted(missing)}"
            )
        for name in sorted(required):
            _sha256_digest(parameters[name], name)
        return
    raise CacheContractError(f"unsupported source contract: {spec.source_contract}")


@dataclass(frozen=True)
class CacheKey:
    """Every result-affecting input needed to reuse one runtime artifact."""

    artifact_kind: str
    role: str
    source_audio_sha256: str
    source_start_sample: int
    source_end_sample: int
    sample_rate_hz: int
    window_identity: Mapping[str, object]
    preprocessing_identity: Mapping[str, object]
    model_identity: Mapping[str, object]
    configuration_identity: Mapping[str, object]
    upstream_cache_keys: tuple[str, ...] = ()
    schema_version: str = CACHE_KEY_SCHEMA

    def __post_init__(self) -> None:
        for name in ("artifact_kind", "role"):
            if not str(getattr(self, name)).strip():
                raise CacheContractError(f"{name} must be non-empty")
        digest = str(self.source_audio_sha256).lower()
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise CacheContractError("source_audio_sha256 must be a SHA-256 digest")
        object.__setattr__(self, "source_audio_sha256", digest)
        if (
            self.source_start_sample < 0
            or self.source_end_sample <= self.source_start_sample
        ):
            raise CacheContractError(
                "source sample range must be non-empty and increasing"
            )
        if self.sample_rate_hz <= 0:
            raise CacheContractError("sample_rate_hz must be positive")
        for name in (
            "window_identity",
            "preprocessing_identity",
            "model_identity",
            "configuration_identity",
        ):
            value = getattr(self, name)
            if not isinstance(value, Mapping) or not value:
                raise CacheContractError(f"{name} must be a non-empty mapping")
        for key in self.upstream_cache_keys:
            if len(key) != 64 or any(
                character not in "0123456789abcdef" for character in key.lower()
            ):
                raise CacheContractError(
                    "upstream_cache_keys must contain SHA-256 digests"
                )

    def to_jsonable(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "artifact_kind": self.artifact_kind,
            "role": self.role,
            "source_audio_sha256": self.source_audio_sha256,
            "source_start_sample": self.source_start_sample,
            "source_end_sample": self.source_end_sample,
            "sample_rate_hz": self.sample_rate_hz,
            "window_identity": dict(self.window_identity),
            "preprocessing_identity": dict(self.preprocessing_identity),
            "model_identity": dict(self.model_identity),
            "configuration_identity": dict(self.configuration_identity),
            "upstream_cache_keys": list(self.upstream_cache_keys),
        }

    @property
    def digest(self) -> str:
        return canonical_sha256(self.to_jsonable())


def make_cache_key(
    *,
    artifact_kind: str,
    role: str,
    source_audio_sha256: str,
    source_start_sample: int,
    source_end_sample: int,
    sample_rate_hz: int,
    window_identity: Mapping[str, object],
    preprocessing_identity: Mapping[str, object],
    model_identity: Mapping[str, object],
    configuration_identity: Mapping[str, object],
    upstream_cache_keys: Sequence[str] = (),
) -> CacheKey:
    """Construct a strict cache key with a convenient public function."""

    return CacheKey(
        artifact_kind=artifact_kind,
        role=role,
        source_audio_sha256=source_audio_sha256,
        source_start_sample=source_start_sample,
        source_end_sample=source_end_sample,
        sample_rate_hz=sample_rate_hz,
        window_identity=dict(window_identity),
        preprocessing_identity=dict(preprocessing_identity),
        model_identity=dict(model_identity),
        configuration_identity=dict(configuration_identity),
        upstream_cache_keys=tuple(str(value).lower() for value in upstream_cache_keys),
    )


@dataclass
class ContentAddressedCache:
    """Small atomic JSON cache suitable for coordinator/worker exchange."""

    root: Path
    replace_attempts: int = 40
    _published: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        self.root = Path(self.root).expanduser().resolve()
        if self.replace_attempts < 1:
            raise CacheContractError("replace_attempts must be positive")

    def path_for(self, key: CacheKey | RuntimeCacheKey | str) -> Path:
        digest = (
            key.digest
            if isinstance(key, (CacheKey, RuntimeCacheKey))
            else str(key).lower()
        )
        digest = _sha256_digest(digest, "cache digest")
        return self.root / digest[:2] / f"{digest}.json"

    def load(self, key: CacheKey | RuntimeCacheKey) -> object | None:
        path = self.path_for(key)
        if not path.is_file():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise CacheContractError(f"cache entry is not an object: {path}")
        if value.get("schema_version") != CACHE_ENTRY_SCHEMA:
            raise CacheContractError(f"unsupported cache entry schema: {path}")
        if value.get("cache_key") != key.digest:
            raise CacheContractError(f"cache key mismatch: {path}")
        if value.get("identity") != key.to_jsonable():
            raise CacheContractError(f"cache identity mismatch: {path}")
        payload = value.get("payload")
        if canonical_sha256(payload) != value.get("payload_sha256"):
            raise CacheContractError(f"cache payload checksum mismatch: {path}")
        return payload

    def publish(self, key: CacheKey | RuntimeCacheKey, payload: object) -> Path:
        """Atomically publish one complete entry; identical writers may race safely."""

        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "schema_version": CACHE_ENTRY_SCHEMA,
            "cache_key": key.digest,
            "identity": key.to_jsonable(),
            "payload_sha256": canonical_sha256(payload),
            "payload": payload,
        }
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(entry, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        last_error: PermissionError | None = None
        try:
            for attempt in range(self.replace_attempts):
                try:
                    os.replace(temporary, path)
                    self._published.add(key.digest)
                    return path
                except PermissionError as exc:
                    last_error = exc
                    time.sleep(min(0.5, 0.01 * (attempt + 1)))
            assert last_error is not None
            raise last_error
        finally:
            temporary.unlink(missing_ok=True)
