"""S6D accepted mono listening and estimated-support pacing audit.

See s6d_listening_README.md for inputs, outputs and both Windows shells.
No playback, device access, neural inference, resampling or waveform writes.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import html
import json
import math
from pathlib import Path
import sys
import wave

sys.dont_write_bytecode = True


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def bind(path, expected=None):
    path = Path(path)
    before = path.stat()
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), str(path)
    assert expected is None or h.hexdigest() == expected, "SHA mismatch: " + str(path)
    return {"path": str(path), "sha256": h.hexdigest(), "bytes": before.st_size}


def verify(bound):
    result = bind(bound["path"], bound["sha256"])
    assert result["bytes"] == bound["bytes"], str(bound)
    return result


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")


def csv_write(path, rows, fields=None):
    with Path(path).open("x", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]))
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                        for k, v in row.items()})


def union(intervals):
    result = []
    for a, b in sorted(intervals):
        assert a <= b
        if a == b:
            continue
        if result and a <= result[-1][1]:
            result[-1][1] = max(result[-1][1], b)
        else:
            result.append([a, b])
    return result


def measure(intervals):
    return sum(b - a for a, b in union(intervals))


def simultaneous(by_actor, threshold=2):
    changes = defaultdict(int)
    for intervals in by_actor.values():
        for a, b in union(intervals):
            changes[a] += 1
            changes[b] -= 1
    count, last, total = 0, None, 0
    for point, delta in sorted(changes.items()):
        if last is not None and count >= threshold:
            total += point - last
        count += delta
        last = point
    assert count == 0
    return total


def stats(values):
    import numpy as np
    values = list(values)
    if not values:
        return {"n": 0, "min": None, "p50": None, "p95": None, "max": None, "sum": 0}
    return {"n": len(values), "min": min(values), "p50": float(np.quantile(values, .5)),
            "p95": float(np.quantile(values, .95)), "max": max(values), "sum": sum(values)}


def checks():
    assert union([[1, 3], [2, 4], [4, 5], [8, 9]]) == [[1, 5], [8, 9]]
    assert measure([[0, 2], [1, 3]]) == 3
    assert simultaneous({"A": [[0, 2], [1, 3]], "B": [[2, 4]]}) == 1
    assert simultaneous({"A": [[0, 2]], "B": [[2, 4]]}) == 0
    assert simultaneous({"A": [[0, 5]], "B": [[1, 4]], "C": [[2, 3]]}) == 3
    assert measure([]) == 0
    return ["overlapping and touching intervals union", "unique-actor overlap, no double-counted same voice",
            "half-open boundary tie", "three-speaker overlap union", "empty support population"]


def build(args):
    import numpy as np
    import soundfile as sf
    sim, out, report, pack = args.sim.resolve(), args.output.resolve(), args.report.resolve(), args.pack.resolve()
    assert not out.exists(), "Choose a new output suffix; existing listening evidence is immutable"
    assert not (report / "listening" / "LISTENING_VALIDATION.json").exists()
    accepted_path = sim / "reports/S4_5/20260909T031300Z/ACCEPTED_CAPTURES_COMPACT.json"
    scene_path = sim / "scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json"
    input_path = sim / "reports/S6B/20260909T230840Z/INPUT_INDEX.json"
    expected_path = pack / "SCENE_LISTENING_INDEX_EXPECTED.csv"
    accepted = read(accepted_path)["canonical"]
    assert accepted["status"] == "COMPLETE" and accepted["accepted_count"] == 240
    captures = {r["case_id"]: r for r in accepted["accepted"]}
    scenes = {r["case_id"]: r for r in read(scene_path)["scenes"]}
    source_index = read(input_path)
    assert source_index["status"] == "COMPLETE"
    inputs = {(r["case_id"], r["stream"]): r for r in source_index["rows"]}
    with expected_path.open(encoding="utf-8-sig", newline="") as f:
        expected = {r["case_id"]: r for r in csv.DictReader(f)}
    assert len(inputs) == 480 and len(captures) == len(scenes) == len(expected) == 240
    assert set(captures) == set(scenes) == set(expected)
    assert set(inputs) == {(cid, tap) for cid in scenes for tap in ("O0", "O1")}
    authorities = {k: bind(v) for k, v in {"accepted_manifest": accepted_path, "scene_manifest": scene_path,
        "input_index": input_path, "pack_expected_index": expected_path,
        "code": Path(__file__), "readme": Path(__file__).with_name("s6d_listening_README.md"),
        "source_level_policy": sim / "reports/S4_5/20260909T031300Z/SOURCE_LEVEL_POLICY.json",
        "historical_adapter_code": sim / "scripts/s4_h2_run.py"}.items()}
    rows, audio_rows, reused_support, receipt_cache = [], [], {}, {}
    for number, cid in enumerate(sorted(scenes), 1):
        scene, admitted = scenes[cid], captures[cid]
        assert admitted["integrity_status"] == "PASS"
        case_bound = verify(admitted["case_result"])
        assert case_bound["sha256"] == expected[cid]["case_receipt_sha256"]
        capture = read(case_bound["path"])
        assert capture["status"] == "PASS" and capture["case_id"] == cid and capture["final_recipe_capture"]
        assert capture["input_scene_sha256"] == scene["canonical_audio"]["sha256"] == admitted["input_scene_sha256"]
        assert capture["recipe"] == admitted["recipe"]
        support_bound = verify(inputs[cid, "O0"]["support"])
        assert inputs[cid, "O1"]["support"] == inputs[cid, "O0"]["support"]
        support_doc = read(support_bound["path"])
        support = support_doc["support"]
        assert support["case_id"] == cid
        assert support_doc["provenance"]["capture"]["sha256"] == case_bound["sha256"]
        assert support_doc["provenance"]["scene_manifest"]["sha256"] == authorities["scene_manifest"]["sha256"]
        reused_support[cid] = support
        streams = {}
        for tap in ("O0", "O1"):
            source = inputs[cid, tap]
            raw_bound = verify(capture["output_audio"][tap])
            assert raw_bound == {k: source["raw_audio"][k] for k in ("path", "sha256", "bytes")}
            adapter_bound = verify(source["audio"])
            assert adapter_bound["path"] == expected[cid][tap + "_expected_path"]
            raw_info, adapter_info = sf.info(raw_bound["path"]), sf.info(adapter_bound["path"])
            assert raw_info.channels == adapter_info.channels == 1
            assert raw_info.samplerate == adapter_info.samplerate == 16000
            assert raw_info.subtype == "PCM_24" and adapter_info.subtype == "PCM_16"
            assert raw_info.frames == adapter_info.frames == capture["framing"]["decoded_frames"]
            assert abs(adapter_info.duration - source["duration_sec"]) < 1e-9
            with wave.open(adapter_bound["path"], "rb") as w:
                assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getcomptype()) == (1, 2, 16000, "NONE")
                pcm_bytes = w.readframes(w.getnframes())
                assert len(pcm_bytes) == 2 * w.getnframes()
            pcm_sha = hashlib.sha256(pcm_bytes).hexdigest()
            assert pcm_sha == source["audio_pcm_sha256"] == source["baseline_journal"]["sha256"]
            gain = 10 ** (3 / 20) if tap == "O0" else 1.0
            assert abs(source["historical_gain_applied_once"] - gain) < 1e-12
            assert source["input_gain"] == 1.0 and source["already_gained"] is True
            chain = []
            for bound in source["baseline_receipt_chain"]:
                if bound["path"] not in receipt_cache:
                    receipt_cache[bound["path"]] = verify(bound)
                chain.append(receipt_cache[bound["path"]])
            origin = read(chain[-1]["path"])
            assert origin["status"] == "COMPLETE"
            assert origin["raw_audio"]["sha256"] == raw_bound["sha256"]
            assert abs(origin["adapter"]["gain_scalar"] - gain) < 1e-12
            raw_values, rate = sf.read(raw_bound["path"], dtype="float32")
            assert np.isfinite(raw_values).all() and rate == 16000
            gained = (raw_values.astype(np.float64) * gain).astype(np.float32)
            expected_pcm = np.round(np.clip(gained, -1.0, 0.999969) * 32768.0).astype("<i2")
            assert hashlib.sha256(expected_pcm.tobytes()).hexdigest() == pcm_sha, cid + "/" + tap + " exact gain-once conversion"
            mapping = support["output_mappings"][tap]
            assert mapping["capture_minus_source_offset_samples"] == capture["payload"]["capture_minus_source_offset_samples"]
            streams[tap] = {"accepted_raw": raw_bound, "prepared_pcm16": adapter_bound,
                "pcm_sha256": pcm_sha, "sample_rate_hz": 16000, "channels": 1,
                "frames": adapter_info.frames, "duration_s": adapter_info.duration,
                "raw_subtype": raw_info.subtype, "listening_subtype": adapter_info.subtype,
                "historical_adapter_gain_db": 3 if tap == "O0" else 0, "listening_added_gain_db": 0,
                "raw_to_prepared_exact_gain_once_pcm16_match": True, "receipt_chain": chain,
                "timing": mapping, "prepared_peak_fs": float(np.max(np.abs(expected_pcm.astype(np.int32)))) / 32768,
                "prepared_rms_fs": float(np.sqrt(np.mean((expected_pcm.astype(np.float64) / 32768) ** 2))),
                "journal_clipped_input_samples": int(np.count_nonzero((gained < -1.0) | (gained > 0.999969)))}
            audio_rows.append({"case_id": cid, "stream": tap, "family": scene["family_id"],
                "raw_path": raw_bound["path"], "raw_sha256": raw_bound["sha256"],
                "prepared_path": adapter_bound["path"], "prepared_sha256": adapter_bound["sha256"],
                "pcm_sha256": pcm_sha, "frames": adapter_info.frames, "rate": 16000, "channels": 1,
                "gain_db_once": 3 if tap == "O0" else 0, "exact_transform_verified": True,
                "case_result_path": case_bound["path"], "case_result_sha256": case_bound["sha256"]})
        turns = []
        for turn in support["turns"]:
            segment = scene["segments"][turn["segment_index"]]
            assert segment["source_id"] == turn["source_id"]
            turns.append({**turn, "transcript": segment.get("transcript"),
                "transcript_sha256": segment.get("transcript_sha256"),
                "preparation_gain_scalar": segment.get("preparation_gain_scalar"),
                "relative_source_db": segment.get("relative_source_db"),
                "source_start_sample": segment.get("source_start_sample"),
                "source_stop_sample": segment.get("source_stop_sample"),
                "word_times": segment.get("word_times")})
        rows.append({"case_id": cid, "family_id": scene["family_id"], "family": scene["family"],
            "room_pose": scene["receiver_configuration"], "cast": scene["cast"],
            "scene_duration_s": scene["duration_s"], "historical_split": scene["split"],
            "historical_task_scoring_allowed": admitted["task_scoring_allowed"],
            "current_all240_scope": "S6D V2 explicitly authorizes all240; original 60 reserve flags remain historical strata",
            "accepted_capture": case_bound, "capture_recipe": capture["recipe"],
            "capture_code_key": capture["code_key"], "canonical_input": scene["canonical_audio"],
            "source_support_binding": support_bound, "all_speaker_references": scene["all_speaker_references"],
            "all_speaker_reference_complete": scene["all_speaker_reference_complete"],
            "overlap_scoring_limited": scene["overlap_scoring_limited"],
            "coverage_limitations": scene["coverage_limitations"], "turns": turns,
            "noise_policy": scene["noise_policy"], "noise_details": scene["noise_details"],
            "noise_events": support["noise_events"], "speech_interference_details": scene["speech_interference_details"],
            "relative_source_level_db": scene["relative_source_level_db"],
            "common_family_headroom_scalar": scene["common_family_headroom_scalar"], "streams": streams})
        if number % 40 == 0:
            print(json.dumps({"stage": "verify_accepted_listening", "done_scenes": number, "total": 240}), flush=True)
    out.mkdir(parents=True)
    save(out / "SCENE_AUDIO_INDEX.json", {"schema": "s6d_listening_v1", "authorities": authorities, "scenes": rows})
    compact = [{"case_id": r["case_id"], "family": r["family_id"], "family_description": r["family"],
        "room_pose": r["room_pose"], "voices": r["cast"], "scene_duration_s": r["scene_duration_s"],
        "corpus_quality": sorted({(t["dataset"], t["quality_partition"]) for t in r["turns"]}),
        "scheduled_turns_source_clock": [{"speaker": t["speaker_key"], "start": t["source_start_sample"] / 16000,
            "stop": t["source_stop_sample"] / 16000, "source_id": t["source_id"]} for t in r["turns"]],
        "noise": r["noise_policy"], "noise_details": r["noise_details"],
        "reference_complete": r["all_speaker_reference_complete"], "overlap_limited": r["overlap_scoring_limited"],
        "O0_prepared": r["streams"]["O0"]["prepared_pcm16"]["path"], "O1_prepared": r["streams"]["O1"]["prepared_pcm16"]["path"],
        "O0_raw": r["streams"]["O0"]["accepted_raw"]["path"], "O1_raw": r["streams"]["O1"]["accepted_raw"]["path"],
        "accepted_case_result": r["accepted_capture"]["path"], "transcripts": r["all_speaker_references"],
        "source_support": r["source_support_binding"]["path"]} for r in rows]
    csv_write(out / "SCENE_AUDIO_INDEX.csv", compact)
    csv_write(out / "AUDIO_VERIFICATION.csv", audio_rows)
    # Predeclared balanced selection: one ordinary case per family, plus corpus/edge controls.
    starters = {f"S45_{family:02d}_01" for family in range(1, 13)} | {
        "S45_01_06", "S45_03_07", "S45_04_05", "S45_06_07", "S45_08_07", "S45_11_13", "S45_12_20"}
    assert starters <= set(scenes)
    for tap in ("O0", "O1"):
        lines = ["#EXTM3U"]
        for r in rows:
            lines += [f'#EXTINF:{r["streams"][tap]["duration_s"]:.6f},{r["case_id"]} | {r["family"]} | {tap}',
                      r["streams"][tap]["prepared_pcm16"]["path"]]
        (out / ("LISTEN_" + tap + ".m3u8")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    lines = ["#EXTM3U"]
    for r in rows:
        if r["case_id"] in starters:
            for tap in ("O0", "O1"):
                lines += [f'#EXTINF:{r["streams"][tap]["duration_s"]:.6f},{r["case_id"]} | {tap} | {r["family"]}',
                          r["streams"][tap]["prepared_pcm16"]["path"]]
    (out / "LISTEN_STARTER_PAIRED.m3u8").write_text("\n".join(lines) + "\n", encoding="utf-8")
    csv_write(out / "LISTENING_NOTES.csv", [{"case_id": r["case_id"], "tap": tap, "listener": "",
        "listened_utc": "", "pacing": "", "pauses": "", "voices": "", "reverb_noise": "",
        "clipping": "", "observed_anomalies": "", "playback_volume": "", "notes": ""}
        for r in rows for tap in ("O0", "O1")])
    render_html(out, rows, starters)
    readme = make_readme(out)
    (out / "LISTENING_README.md").write_text(readme, encoding="utf-8")
    (report / "listening").mkdir(parents=True, exist_ok=True)
    (report / "listening/LISTENING_README.md").write_text(readme, encoding="utf-8")
    csv_write(report / "listening/COMPACT_LISTENING_INDEX.csv", [{"case_id": r["case_id"], "family": r["family_id"],
        "room": r["room_pose"]["room_table"], "starter": r["case_id"] in starters,
        "O0_path": r["streams"]["O0"]["prepared_pcm16"]["path"],
        "O1_path": r["streams"]["O1"]["prepared_pcm16"]["path"],
        "O0_sha256": r["streams"]["O0"]["prepared_pcm16"]["sha256"],
        "O1_sha256": r["streams"]["O1"]["prepared_pcm16"]["sha256"]} for r in rows])
    validation = {"status": "PASS", "scope": "accepted historical all240 O0/O1 playable PCM16 binding; no new capture or model results",
        "created_utc": datetime.now(timezone.utc).isoformat(), "index": str(out / "index.html"),
        "scenes": 240, "prepared_mono_files": 480, "raw_mono_hashes_verified": 480,
        "exact_gain_once_pcm_payloads_verified": 480, "new_audio_files": 0,
        "human_listening_performed": False, "autoplay": False, "external_requests": False,
        "estimated_playable_one_tap_seconds": sum(r["streams"]["O0"]["duration_s"] for r in rows),
        "starter_cases": sorted(starters), "starter_corpus_quality": sorted({(t["dataset"], t["quality_partition"])
            for r in rows if r["case_id"] in starters for t in r["turns"]}),
        "checks": checks(), "authorities": authorities,
        "output_files": [bind(p) for p in sorted(out.iterdir()) if p.is_file()]}
    save(report / "listening/LISTENING_VALIDATION.json", validation)
    print(json.dumps({"stage": "LISTENING_READY", "index": str(out / "index.html"), "scenes": 240,
                      "mono_files": 480, "new_audio_bytes": 0}), flush=True)
    pacing(report, rows, authorities)


def render_html(out, rows, starters):
    e = html.escape
    cards = []
    for r in rows:
        cid = r["case_id"]
        controls = []
        for tap in ("O0", "O1"):
            s = r["streams"][tap]
            uri = Path(s["prepared_pcm16"]["path"]).as_uri()
            raw_uri = Path(s["accepted_raw"]["path"]).as_uri()
            controls.append(f'<div class="tap"><b>{tap}: {"ASR +3 dB once" if tap == "O0" else "postprocessed unity"}</b>'
                f'<audio controls preload="none" data-tap="{tap}" src="{e(uri)}"></audio>'
                f'<a href="{e(uri)}">Open prepared mono</a> · <a href="{e(raw_uri)}">Accepted raw mono</a>'
                f'<p class="path">{e(s["prepared_pcm16"]["path"])}</p></div>')
        transcripts = []
        for t in r["turns"]:
            intervals = t["file_support"]
            if not intervals:
                continue
            # file_support already includes preserved RIR origin; add only saved transport + DSP map.
            start, stop = intervals[0][0], intervals[-1][1]
            times = {tap: [(start + r["streams"][tap]["timing"]["source_with_rir_to_output_offset_samples"]) / 16000,
                           (stop + r["streams"][tap]["timing"]["source_with_rir_to_output_offset_samples"]) / 16000]
                     for tap in ("O0", "O1")}
            transcripts.append(f'<li data-times="{e(json.dumps(times), quote=True)}"><b>{e(t["participant_id"])} · '
                f'{times["O0"][0]:.2f}–{times["O0"][1]:.2f}s O0</b> '
                f'{e(t.get("transcript") or "[Source transcript unavailable]")}'
                f'<small>{e(t["dataset"])} / {e(t["quality_partition"])} · {e(t["source_id"])}</small></li>')
        cards.append(f'<article data-starter="{str(cid in starters).lower()}"><h2>{cid} · {e(r["family"])}</h2>'
            f'<p>{e(r["room_pose"]["room_table"])} · {e(r["room_pose"]["orientation"])} · '
            f'{r["scene_duration_s"]}s source scene · references {"complete" if r["all_speaker_reference_complete"] else "INCOMPLETE"}</p>'
            f'<p class="metadata">{e(str(r["cast"]))} · Noise: {e(str(r["noise_policy"]))}</p>'
            f'<div class="pair">{"".join(controls)}</div><button class="sync" type="button">Pause and align the other tap to this position</button>'
            '<p class="position">Position: 0.00s</p><details class="transcript"><summary>Source transcripts and approximate timing</summary>'
            f'<ol>{"".join(transcripts)}</ol><p>20 ms source activity estimate and saved approximate per-tap alignment; no exact word/phonetic timing. '
            f'All intended source text is retained even when the auto output suppresses a voice.</p></details>'
            f'<details><summary>Reference limitations</summary><p>{e(str(r["coverage_limitations"]))}</p></details></article>')
    document = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; media-src file:; img-src 'none'; connect-src 'none'">
<title>S6D · All 240 mono pairs</title><style>
body{font:16px/1.5 system-ui,sans-serif;background:#f6f3ee;color:#242321;margin:0}header,main{max-width:1100px;margin:auto;padding:24px}
header{background:#e9eee7}h1{margin:0 0 12px}h2{font-size:1.2rem}.toolbar{display:flex;gap:15px;align-items:center;flex-wrap:wrap}
input[type=search]{padding:9px;width:320px}button,select{padding:8px}article{background:white;border:1px solid #d8d3cc;border-radius:10px;padding:20px;margin-bottom:18px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}.tap{min-width:0}audio{display:block;width:100%;margin:12px 0}.path{font:12px monospace;overflow-wrap:anywhere}
.metadata,small{color:#5b5852;font-size:13px}small{display:block}li{padding:8px;margin:3px 0}li.active{background:#fff0b0;outline:1px solid #d8bd43}
summary{cursor:pointer}details{margin-top:14px}.position{font-variant-numeric:tabular-nums}.hidden{display:none}a{color:#205e78}@media(max-width:700px){.pair{grid-template-columns:1fr}}
</style></head><body><header><h1>All 240 scenes · O0 / O1</h1>
<p>Real corpus voices, artificial turn schedules and measured static acoustic paths. 480 verified mono PCM16 files; no audio was generated or changed.</p>
<p>Start quietly, at 1× speed. O0 already has the historical +3 dB once; O1 is unity. Player volume applies only during listening. Gaps and tails are preserved.</p>
<p><a href="LISTENING_README.md">Listening guide</a> · <a href="LISTEN_O0.m3u8">All O0</a> · <a href="LISTEN_O1.m3u8">All O1</a> · <a href="LISTEN_STARTER_PAIRED.m3u8">Balanced starter pairs</a> · <a href="LISTENING_NOTES.csv">Empty listening notes</a></p>
<div class="toolbar"><input id="query" type="search" aria-label="Search scenes" placeholder="Search scene, room, corpus, words…">
<select id="selection" aria-label="Scene set"><option value="starter">Balanced starter</option><option value="all">All 240 scenes</option></select>
<label>Player volume <input id="volume" type="range" min="0" max="100" value="15"><output id="level">15%</output></label>
<button id="transcripts" type="button">Show transcripts</button><span id="count"></span></div>
<p>If embedded playback fails, use the prepared mono links or copy the displayed path into Explorer; VLC can open the M3U8 files. Open this HTML as a local file. Never play packed transport or multichannel debug audio.</p></header><main>''' + "\n".join(cards) + '''</main><script>
const cards=[...document.querySelectorAll('article')], players=[...document.querySelectorAll('audio')];
let last=null; const volume=document.getElementById('volume');
function setVolume(){players.forEach(a=>a.volume=Number(volume.value)/100);document.getElementById('level').textContent=volume.value+'%'}
setVolume();volume.addEventListener('input',setVolume);
players.forEach(a=>{a.playbackRate=1;a.addEventListener('play',()=>{players.forEach(b=>{if(b!==a)b.pause()});last=a});
a.addEventListener('timeupdate',()=>{const card=a.closest('article');card.querySelector('.position').textContent=a.dataset.tap+' position: '+a.currentTime.toFixed(2)+'s';
card.querySelectorAll('li[data-times]').forEach(li=>{const t=JSON.parse(li.dataset.times)[a.dataset.tap];li.classList.toggle('active',a.currentTime>=t[0]&&a.currentTime<t[1])})})});
cards.forEach(card=>card.querySelector('.sync').addEventListener('click',()=>{const pair=[...card.querySelectorAll('audio')];const from=pair.includes(last)?last:pair[0];const time=from.currentTime;pair.forEach(a=>{a.pause();if(a!==from){if(a.readyState>=1)a.currentTime=Math.min(time,a.duration);else{a.addEventListener('loadedmetadata',()=>{a.currentTime=Math.min(time,a.duration)},{once:true});a.load()}}});card.querySelector('.position').textContent='Aligned at '+time.toFixed(2)+'s; press Play for either tap.'}));
function filter(){const q=document.getElementById('query').value.toLowerCase(), all=document.getElementById('selection').value==='all';let n=0;cards.forEach(c=>{const shown=(all||c.dataset.starter==='true')&&c.textContent.toLowerCase().includes(q);c.classList.toggle('hidden',!shown);if(shown)n++});document.getElementById('count').textContent=n+' scenes'}
document.getElementById('query').addEventListener('input',filter);document.getElementById('selection').addEventListener('change',filter);filter();
document.getElementById('transcripts').addEventListener('click',e=>{const show=e.target.textContent==='Show transcripts';document.querySelectorAll('.transcript').forEach(d=>d.open=show);e.target.textContent=show?'Hide transcripts':'Show transcripts'});
</script></body></html>'''
    assert "autoplay" not in document.lower()
    assert "https://" not in document and "http://" not in document
    (out / "index.html").write_text(document, encoding="utf-8")


def make_readme(out):
    return f'''# S6D historical all-240 listening access

Open `{out / 'index.html'}` directly in a local browser. Select All 240 scenes to expose the whole bank; the initial balanced starter contains every family, overlap, short replies, relocation, music and corpus/quality strata. S45_08_07 is the known C105 ordering case; its presence is a failure-case reminder, not an audible-model-outcome claim. The playlists preserve case order and each scene's original chronology, silence and tails. Starter alternates O0 then O1 for each case. Cross-drive playlist paths are absolute; keep C: and G: mounted at their recorded locations.

Use 1× playback and start at low player volume (HTML default 15%). The prepared files are verified historical mono 16 kHz PCM16 journal WAVs. O0 contains +3 dB exactly once; O1 is unity. Raw links point only to accepted decoded mono PCM24 captures. No extra gain, normalization, resampling, shift, trimming or audio copy was applied. The exact historical float32 gain → clip/round PCM16 transform was independently compared sample-for-sample against all 480 prepared payloads. A quantized journal is a listening/model-input derivative, not the raw archive.

Never play packed carrier transport, injected microphone vectors or six-channel debug audio through speakers/headphones. Those files are deliberately absent from these playlists and HTML players. Nothing plays on page load. The sync button pauses and aligns the pair at the same sample-clock position; press Play to listen. The player pauses the other taps when one starts. Volume changes affect playback only and never evaluation files.

Transcript times use the frozen S6A file/support mapping: the 50 ms RIR origin is already represented, followed only by the saved per-tap transport/DSP offset. No offset was added to audio. Timing is approximate source activity on a 20 ms grid, not exact word or phonetic alignment. Read all intended transcripts even when the automatic beam may have suppressed a speaker. Incomplete ambient/all-speaker references remain visibly incomplete. Source IDs, roles and voices come from the accepted scene manifest; they are not model predictions.

These are real recorded corpus voices with artificial turn schedules and measured static acoustic paths. Common Voice older-cohort metadata, original CMU ARCTIC and HiFi clean/other are separate descriptive strata. The 2,830.589258 summed whole-probe seconds are not speech-active union and do not imply a silence percentage. The associated PACING_AUDIT uses bound estimated activity support and reports limitations. Concatenated historical outputs reset XVF state between captured scenes; they do not demonstrate an uninterrupted physical dinner.

`SCENE_AUDIO_INDEX.json` contains complete source/support/accepted-raw/adapter/recipe/hash bindings, reference text and timing. CSV is the flat human index. `AUDIO_VERIFICATION.csv` has 480 exact hash/format/gain checks. `LISTENING_NOTES.csv` has empty human fields; no human listening judgments were invented. If a browser blocks cross-drive local audio, use Open prepared mono, copy the displayed Windows path into Explorer, or open an M3U8 in a local media player such as VLC. No server, install or external request is needed.

Regeneration is documented in `simulation/scripts/s6d_listening_README.md`. Use a new output suffix; existing evidence and completed validation receipts are never overwritten.
'''


def pacing(report, rows, authorities):
    out = report / "pacing"
    out.mkdir(parents=True, exist_ok=True)
    per_scene, per_turn, gaps, pauses = [], [], [], []
    source_reuse, corpus_instances, missing = Counter(), Counter(), []
    for r in rows:
        by_actor, active_intervals, whole_intervals = defaultdict(list), [], []
        turn_order = []
        for t in r["turns"]:
            source_reuse[t["source_id"]] += 1
            corpus_instances[t["dataset"] + "/" + t["quality_partition"]] += 1
            whole_intervals.extend(t["file_support"])
            active = union(t["active_ranges"]) if t["activity_available"] else []
            if not t["activity_available"]:
                missing.append({"case_id": r["case_id"], "source_id": t["source_id"]})
            active_intervals.extend(active)
            by_actor[t["speaker_key"]].extend(active)
            for left, right in zip(active, active[1:]):
                pauses.append({"case_id": r["case_id"], "source_id": t["source_id"], "pause_s": (right[0] - left[1]) / 16000})
            if active:
                turn_order.append((t, active[0][0], active[-1][1]))
            per_turn.append({"case_id": r["case_id"], "family": r["family_id"], "source_id": t["source_id"],
                "speaker_key": t["speaker_key"], "dataset": t["dataset"], "quality": t["quality_partition"],
                "whole_clip_s": t["whole_clip_duration_s"], "estimated_active_s": measure(active) / 16000,
                "estimated_first_to_last_support_s": (active[-1][1] - active[0][0]) / 16000 if active else None,
                "within_clip_leading_support_gap_s": (active[0][0] - t["file_support"][0][0]) / 16000 if active else None,
                "within_clip_trailing_support_gap_s": (t["file_support"][-1][1] - active[-1][1]) / 16000 if active else None,
                "preparation_gain_scalar": t["preparation_gain_scalar"], "relative_source_db": t["relative_source_db"],
                "common_family_headroom_scalar": r["common_family_headroom_scalar"],
                "scene_relative_source_level_db": r["relative_source_level_db"]})
        for left, right in zip(sorted(turn_order, key=lambda x: x[1]), sorted(turn_order, key=lambda x: x[1])[1:]):
            if left[0]["speaker_key"] != right[0]["speaker_key"]:
                gaps.append({"case_id": r["case_id"], "from_source": left[0]["source_id"],
                    "to_source": right[0]["source_id"], "estimated_handoff_gap_s": (right[1] - left[2]) / 16000})
        united, whole = union(active_intervals), union(whole_intervals)
        activity_s = measure(united) / 16000
        overlap_s = simultaneous(by_actor) / 16000
        assert overlap_s <= activity_s <= r["scene_duration_s"]
        per_scene.append({"case_id": r["case_id"], "family": r["family_id"], "room": r["room_pose"]["room_table"],
            "pose": r["room_pose"]["orientation"], "obstructed": r["room_pose"]["obstructed"],
            "scene_s": r["scene_duration_s"], "estimated_active_union_s": activity_s,
            "estimated_distinct_voice_overlap_s": overlap_s,
            "estimated_activity_duty_fraction": activity_s / r["scene_duration_s"],
            "summed_whole_probe_s": sum(t["whole_clip_duration_s"] for t in r["turns"]),
            "whole_file_support_union_s": measure(whole) / 16000,
            "scene_lead_to_first_whole_probe_s": whole[0][0] / 16000 if whole else None,
            "scene_tail_after_last_whole_probe_s": r["scene_duration_s"] - whole[-1][1] / 16000 if whole else None,
            "scene_lead_to_first_estimated_activity_s": united[0][0] / 16000 if united else None,
            "scene_tail_after_last_estimated_activity_s": r["scene_duration_s"] - united[-1][1] / 16000 if united else None,
            "speaking_turn_instances": len(r["turns"]), "all_speaker_reference_complete": r["all_speaker_reference_complete"],
            "overlap_scoring_limited": r["overlap_scoring_limited"], "noise_policy": r["noise_policy"]})
    total = sum(r["scene_s"] for r in per_scene)
    active = sum(r["estimated_active_union_s"] for r in per_scene)
    overlap = sum(r["estimated_distinct_voice_overlap_s"] for r in per_scene)
    whole_sum = sum(r["summed_whole_probe_s"] for r in per_scene)
    assert total == 10967
    assert abs(whole_sum - 2830.589258) < .001
    grouped = {}
    for field in ("family", "room", "pose", "obstructed"):
        groups = defaultdict(list)
        for r in per_scene:
            groups[str(r[field])].append(r)
        grouped[field] = {key: {"scenes": len(values), "scene_s": sum(v["scene_s"] for v in values),
            "estimated_active_union_s": sum(v["estimated_active_union_s"] for v in values),
            "estimated_distinct_voice_overlap_s": sum(v["estimated_distinct_voice_overlap_s"] for v in values)}
            for key, values in groups.items()}
    audit = {"schema": "s6d_estimated_reference_pacing_v1", "status": "COMPLETE_WITH_REFERENCE_LIMITATIONS",
        "created_utc": datetime.now(timezone.utc).isoformat(), "authorities": authorities,
        "source_support_bindings_sha256": hashlib.sha256(json.dumps([r["source_support_binding"] for r in rows], sort_keys=True).encode()).hexdigest(),
        "scenes": 240, "scene_seconds": total, "summed_whole_probe_seconds": whole_sum,
        "estimated_speaking_support_union_seconds": active, "estimated_distinct_voice_overlap_seconds": overlap,
        "estimated_speaking_support_duty_fraction": active / total,
        "estimated_overlap_fraction_scene_time": overlap / total,
        "estimated_overlap_fraction_supported_speech_time": overlap / active,
        "missing_activity_instances": missing, "precise_silence_percentage": None,
        "human_listening_judgments": None, "new_stress_derivatives": 0,
        "method": "Frozen source preparation/scoring activity on 20 ms frames; union per scene, and overlap of >=2 unique speaker_key supports; no neural VAD or fresh ground truth. Source-with-RIR clock, all instances counted once. Whole probes and estimated active supports are separate.",
        "activity_estimator": "frame_rms_20ms_p95_minus25dB_absolute_floor_minus50dBFS_v1",
        "limitations": ["Broad energy support, not exact speech or word/phonetic alignment; background unknown speech and source-internal noise can remain unlabelled.",
            "Outside estimated support is not measured acoustic silence; includes padding, noise, reverb tails, estimator errors and source-internal pauses.",
            "Adjacent-start turn handoff gaps can be negative; overlap union uses unique actors and is a separate denominator.",
            "Within-source gaps on a 20 ms energy grid include interword/consonant gaps; they are not all conversational pauses.",
            "Real corpus recordings, artificial schedules, static measured acoustic paths; no causal demographic claims.",
            "Historical capture state resets between scenes; no uninterrupted physical conversation is established by playlists or concatenated outputs.",
            "No human listening feedback collected. Pacing derivatives are left uncreated until a specific paired hypothesis is selected."],
        "reference_complete_scenes": sum(r["all_speaker_reference_complete"] for r in rows),
        "overlap_scoring_limited_scenes": sum(r["overlap_scoring_limited"] for r in rows),
        "whole_probe_duration_s": stats(t["whole_clip_s"] for t in per_turn),
        "turn_active_duration_s": stats(t["estimated_active_s"] for t in per_turn),
        "turn_first_to_last_support_s": stats(t["estimated_first_to_last_support_s"] for t in per_turn if t["estimated_first_to_last_support_s"] is not None),
        "handoff_gap_s": stats(g["estimated_handoff_gap_s"] for g in gaps),
        "negative_handoff_gaps": sum(g["estimated_handoff_gap_s"] < 0 for g in gaps),
        "within_source_support_gap_s": stats(p["pause_s"] for p in pauses),
        "lead_padding_to_first_whole_probe_s": stats(r["scene_lead_to_first_whole_probe_s"] for r in per_scene if r["scene_lead_to_first_whole_probe_s"] is not None),
        "tail_padding_after_last_whole_probe_s": stats(r["scene_tail_after_last_whole_probe_s"] for r in per_scene if r["scene_tail_after_last_whole_probe_s"] is not None),
        "source_reuse": {"unique_source_clips": len(source_reuse), "utterance_instances": sum(source_reuse.values()),
            "instance_count_distribution": dict(Counter(source_reuse.values())), "highest_reuse": source_reuse.most_common(12)},
        "corpus_quality_instances": dict(corpus_instances), "coverage": grouped,
        "prepared_audio_levels": {tap: {"peak_fs": stats(r["streams"][tap]["prepared_peak_fs"] for r in rows),
            "rms_fs": stats(r["streams"][tap]["prepared_rms_fs"] for r in rows),
            "journal_clipped_input_samples": sum(r["streams"][tap]["journal_clipped_input_samples"] for r in rows)} for tap in ("O0", "O1")},
        "source_level_policy": authorities["source_level_policy"], "checks": checks()}
    csv_write(out / "PACING_PER_SCENE.csv", per_scene)
    csv_write(out / "PACING_PER_TURN.csv", per_turn)
    csv_write(out / "HANDOFF_GAPS.csv", gaps)
    csv_write(out / "WITHIN_SOURCE_SUPPORT_GAPS.csv", pauses)
    csv_write(out / "SOURCE_REUSE.csv", [{"source_id": k, "instances": v} for k, v in sorted(source_reuse.items())])
    save(out / "PACING_AUDIT.json", audit)
    (out / "PACING_README.md").write_text(f'''# Estimated support pacing audit

240 scenes total {total:,.0f} source seconds. Summed whole-probe duration is {whole_sum:,.6f}s; the estimated speaking-support union is {active:,.3f}s, with {overlap:,.3f}s of distinct-voice overlap. The supported duty fraction is {active / total:.4%}. These are broad 20 ms energy-support estimates reused from bound source activity; no precise silence percentage is claimed.

Whole probe length includes source-internal silence and overlap between utterances. Per-scene unions avoid double counting; overlap requires different speaker keys. Read all limitations in PACING_AUDIT.json. Scene padding to first/last whole probe, source-internal support gaps, inter-actor handoffs, levels, corpus partitions, room/family coverage and reuse are separate tables. Long lead/tail durations and limited simultaneous voice support constrain dialogue realism. No fresh models, human judgments or stress derivatives were produced.

Inputs and reproduction: see simulation/scripts/s6d_listening_README.md; run the build with a new output/report location. Output CSVs preserve every case and source instance, including limited/incomplete references.
''', encoding="utf-8")
    print(json.dumps({"stage": "PACING_READY", "audit": str(out / "PACING_AUDIT.json"),
        "scene_seconds": total, "estimated_active_union_seconds": active, "estimated_overlap_seconds": overlap}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim", type=Path, required=True)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args())
