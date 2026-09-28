"""Create private, source-bound listening examples from existing mono captures."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil

import numpy as np
import soundfile as sf

ACOUSTIC = Path(r"C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs")
SIM = ACOUSTIC / "simulation"
LIBRARY = SIM / "listening/S45_all240_v1"
SCENES = SIM / "scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json"
REFERENCES = LIBRARY / "S6D_same_pass_v1/AUDIO_REFERENCES.json"
SELECTION = [
    ("S45_11_01", "babble", "Competing voices: three-speaker babble proxy",
     "One intended speaker and two overlapping background talkers. This is a constructed speech-interference example, not a recording of a crowded restaurant.",
     "Listen for whether the intended voice remains intelligible, which competing voices survive, and whether the selected voice changes."),
    ("S45_10_05", "cooking", "Speech plus cooking noise: 10 dB input SNR",
     "A recorded Frying Chicken noise source is mixed with speech through measured room paths. It is a cooking-noise proxy, not an actual kitchen conversation.",
     "Listen for the continuous noise underneath words and during pauses, and whether consonants become muffled."),
    ("S45_10_02", "transients", "Speech plus short coin-drop sounds: 10 dB input SNR",
     "A recorded Coin Drop event is placed at three speech turns. This tests intermittent impacts separately from competing voices or steady noise.",
     "Listen for the brief impacts, missed syllables around them, and any abrupt change in the background."),
]


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def verify(ref):
    path = Path(ref["path"])
    assert path.stat().st_size == ref["bytes"], path
    assert sha(path) == ref["sha256"], path
    return path


def audio(filename, label):
    return (f'<div class="tap"><strong>{html.escape(label)}</strong>'
            f'<audio controls preload="metadata" src="{filename}"></audio>'
            f'<a href="{filename}">Open WAV</a></div>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise SystemExit("Output exists; choose a new suffix to preserve evidence.")
    out.mkdir(parents=True)
    manifest = json.loads(SCENES.read_text(encoding="utf-8-sig"))
    refs = json.loads(REFERENCES.read_text(encoding="utf-8-sig"))
    scenes = {row["case_id"]: row for row in manifest["scenes"]}
    receipt = {"schema": "private-listening-examples.v1", "sources": [],
               "scene_manifest_sha256": sha(SCENES), "references_sha256": sha(REFERENCES),
               "playback_performed": False, "human_listening_judgments": None,
               "new_capture": False, "model_evaluation": False,
               "measured_noise_attenuation_db": None, "stage_acceptance_granted": False}
    cards = []
    for cid, slug, title, explanation, listen_for in SELECTION:
        scene = scenes[cid]
        matches = [r for r in refs["rows"] if r["case_id"] == cid and r["profile"] == "P_MAIN6"]
        assert len(matches) == 1
        row = matches[0]
        verify(row["case_result"])
        players = []
        for tap, label in (("auto_asr_raw", "XVF Auto ASR output"), ("auto_pp_raw", "XVF Auto postprocessed output")):
            matching = [r for r in row["audio"] if Path(r["path"]).stem == tap]
            assert len(matching) == 1
            src = verify(matching[0])
            info = sf.info(src)
            assert (info.channels, info.samplerate, info.subtype, info.frames) == (1, 16000, "PCM_24", row["frames"])
            filename = f"{slug}_{tap}.wav"
            dest = out / filename
            shutil.copyfile(src, dest)
            assert sha(dest) == matching[0]["sha256"]
            samples, rate = sf.read(dest, dtype="float64")
            assert np.isfinite(samples).all() and np.max(np.abs(samples)) <= 1
            receipt["sources"].append({"case_id": cid, "tap": tap, **matching[0],
                "copy": filename, "copy_sha256": sha(dest), "duration_s": info.duration,
                "transformation": "byte-exact copy; unity gain; no trimming or normalization"})
            players.append(audio(filename, label))
        turns = "".join(f'<li>{html.escape(t["participant_id"])} ({html.escape(t["role"])}), source '
                        f'{t["start_sample"]/16000:.1f}–{t["stop_sample"]/16000:.1f} s: '
                        f'{html.escape(t["transcript"])}</li>' for t in scene["all_speaker_references"])
        noise_ids = sorted({s["source_id"] for s in scene["segments"] if s["kind"] == "real_noise"})
        credits = " ".join(manifest["selected_noise"][n]["attribution"] for n in noise_ids)
        cards.append(f'<section><h2>{html.escape(title)}</h2><p>{html.escape(explanation)}</p>'
                     f'<p><b>Listen for:</b> {html.escape(listen_for)}</p><div class="pair">{"".join(players)}</div>'
                     '<button class="sync" type="button">Pause and align both players to the first player</button>'
                     f'<details><summary>Intended speech, source timing and credits — {cid}</summary><ul>{turns}</ul>'
                     '<p>Source times are approximate listening guides. The stored outputs include transport/DSP timing; '
                     'no exact source-to-output alignment is claimed here. The pair shares the stored capture clock. '
                     'All original pauses and tails are retained.</p>'
                     f'<p>{html.escape(credits)}</p></details></section>')

    # A short, already annotated pre-excitation window from an actual cafeteria.
    run_id = "JPXVF_P1_R04_T01_D01_S01_UPR_NAT_CU_R06"
    run = ACOUSTIC / "XVF_MEASUREMENT_WORK/experiments" / run_id / "02_raw/pass_01_amplified"
    checksum_lines = (run / "SHA256SUMS.txt").read_text(encoding="utf-8-sig").splitlines()
    config = json.loads((run / "capture_configuration.json").read_text(encoding="utf-8-sig"))
    assert config["channel_order"][1:3] == ["processed_auto", "amplified_MIC0"]
    assert config["source_position_from_user"]["room_name"] == "Loeb Caf"
    ambient_players = []
    for original, slug, label in (("MIC0.wav", "microphone", "Amplified MIC0 — before beamforming"),
                                  ("processed_auto.wav", "processed", "XVF processed_auto output")):
        src = run / original
        expected = [line.split()[0] for line in checksum_lines if line.split()[-1] == original]
        assert len(expected) == 1 and sha(src) == expected[0]
        info = sf.info(src)
        assert (info.channels, info.samplerate, info.subtype) == (1, 16000, "PCM_24")
        samples, _ = sf.read(src, start=4000, stop=16000, dtype="float64")
        assert samples.shape == (12000,) and np.isfinite(samples).all()
        for gain_db in (0, 24):
            filename = f"real_cafeteria_{slug}_{gain_db}dB.wav"
            derived = samples * 10 ** (gain_db / 20)
            assert np.max(np.abs(derived)) < 1, "Refuse clipping"
            sf.write(out / filename, derived, 16000, subtype="PCM_24")
            reread, rate = sf.read(out / filename, dtype="float64")
            assert rate == 16000 and len(reread) == 12000
            assert np.max(np.abs(reread-derived)) <= 2 ** -23
            receipt["sources"].append({"run_id": run_id, "source": str(src), "source_sha256": expected[0],
                "copy": filename, "copy_sha256": sha(out / filename), "crop_samples": [4000, 16000],
                "duration_s": .75, "gain_db": gain_db, "clipping_samples": 0,
                "transformation": "single contiguous crop and declared scalar; PCM24; no denoising, looping or normalization"})
            if gain_db == 24:
                ambient_players.append(audio(filename, label + " · +24 dB listening gain"))
    cards.append('<section><h2>Actual Loeb cafeteria ambience — limited 0.75-second excerpt</h2>'
                 '<p>Recorded on September 7, 2026. This is the annotated 0.25–1.00 s pre-excitation window '
                 'from a room-measurement take, not a natural conversation. It is too short to establish '
                 'restaurant noise removal or sustained speech quality. The original take is marked RETAKE '
                 'and remains scientifically unqualified.</p>'
                 '<p>Both players below have the same +24 dB added listening gain, with no clipping. '
                 'The underlying raw/processed paths have different gain and processing, so their level '
                 'difference is not a calibrated attenuation measurement. Processing delay is not aligned.</p>'
                 f'<div class="pair">{"".join(ambient_players)}</div>'
                 '<p>Original-level excerpts: <a href="real_cafeteria_microphone_0dB.wav">MIC0</a> · '
                 '<a href="real_cafeteria_processed_0dB.wav">processed_auto</a>. '
                 'No test sweeps, packed carriers or multichannel files are included.</p></section>')
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>XVF3800 — babble and background-noise listening</title>
<style>body{font:17px/1.55 system-ui,sans-serif;max-width:1000px;margin:40px auto;padding:0 22px;color:#20302e;background:#f4f6f3}h1{line-height:1.2}section{background:white;padding:22px;margin:22px 0;border-radius:12px}h2{font-size:1.3em}.pair{display:flex;gap:24px;flex-wrap:wrap}.tap{flex:1;min-width:260px}.tap strong{display:block}audio{width:100%;margin:12px 0}a{color:#08645a}button{padding:8px 12px;margin:16px 0}details{font-size:.9em}small{color:#58635f}</style>
<h1>XVF3800: what survives the processing?</h1>
<p>Three simulated scenes passed through real XVF hardware, plus one very short recording of actual cafeteria ambience. Start at low volume and compare the same passage. Nothing plays automatically.</p>
<p><b>Babble is competing speech.</b> Cooking noise and impacts are different interference categories; assess each separately. Judge intended-word clarity as well as how quiet the background sounds. A quieter output can also lose speech.</p>
<p>The ASR and postprocessed taps are <b>both processed XVF outputs</b>. “raw” in these filenames means the archived capture has no later listening gain, not an untreated microphone. These examples do not establish a before/after suppression figure, a current app routing configuration, or real-restaurant performance.</p>
'''+"\n".join(cards)+'''<section><h2>Next real-world comparison</h2><p>After reconnection: record the same continuous scene simultaneously from an amplified microphone reference, Auto ASR and Auto postprocessed taps. Include nearby speech against restaurant babble, a separate steady-noise setting, brief impacts, and natural pauses. Retain original time and levels, fix and log device settings, and use identical added gain for paired listening copies. Preserve desired nearby speakers as well as the main speaker. Assess background intrusions, intelligibility and clipped or lost words; record no unrelated private conversations deliberately.</p><p>Existing synthetic examples remain diagnostic material. Freeze candidate settings before held-out real-world testing. New venue capture and hardware operation have not been performed by this builder.</p></section>
<script>const players=[...document.querySelectorAll('audio')];for(const a of players){a.volume=.15;a.addEventListener('play',()=>players.filter(b=>b!==a).forEach(b=>b.pause()));}document.querySelectorAll('.sync').forEach(button=>button.onclick=()=>{const p=[...button.closest('section').querySelectorAll('audio')];const t=p[0].currentTime;p.forEach(a=>{a.pause();if(a.readyState>0)a.currentTime=Math.min(t,a.duration||t);});});</script></html>'''
    (out / "index.html").write_text(document, encoding="utf-8")
    receipt["generated_bytes"] = sum(p.stat().st_size for p in out.iterdir())
    receipt["output_html_sha256"] = sha(out / "index.html")
    (out / "PROVENANCE.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"status": "EXAMPLES_PREPARED_NOT_LISTENING_RATED", "output": str(out),
                      "audio_files": len(receipt["sources"]), "bytes": receipt["generated_bytes"]}))


if __name__ == "__main__":
    main()
