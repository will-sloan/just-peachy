"""Build the S6A proposal registry/resource ledger; no inference or hardware work.

See README_S6A_DESIGN.md for inputs, outputs and exact commands. This script
writes only report/design and never declares planned profiles executed.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, platform, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

REPO = Path(r"C:\Users\amiri\Documents\GitHub\just-peachy")
SIM = REPO / "XVF 3800 Testing/XVF Integration Real World RIRs/simulation"
APP = REPO / "Software Validation from Datasets/Evaluation Tool/app/edge_speech_pipeline"
PACK = SIM.parent / "Just_Peachy_S6_Joint_Pipeline_Pack_V2/Just_Peachy_S6_Joint_Pipeline_Pack_V2"
DEFAULT_REPORT = SIM / "reports/S6A/20260909T202250Z"
GiB = 1024**3

# Every ID has a specific state equation, actual extension point, latency
# accounting and complexity. Capital letters name the binding table below.
# These are hypotheses, not advertised implemented runtime controls.
SPECS = [
("J01","h+=dt if abs(u-u_anchor)>delta and fresh else h=0; propose if h>=p; voice conflict vetoes inheritance","X,T","T","p=0.3/0.6/1.0 s proposal persistence; available after delivered evidence","O(E*K*192), bounded h per track"),
("J02","g=max(0,g+innovation-kappa); propose when g>H; refractory timer prevents retriggers","X,T","T","accumulation delay measured from first innovation; no retroactive boundary","O(E), one CUSUM state per beam"),
("J03","z=w_v*voice_change+w_a*qualified_activity+w_x*fresh_innovation; require two nonredundant cue families, with audio-only rescue","S,E,X,T","T","max feature availability plus p; log delayed decisions","O(E*K*192), no additional neural calls if features unchanged"),
("J04","min assignment sum c(beam,track) with unmatched and duplicate-beam states; never birth solely from beam index","X,T","T","one delivered telemetry tick plus assignment computation","O(B^3), B<=4 observed beams and bounded tracks"),
("J05","u=cos(theta); spatial score=-min((u-u_k)^2/sigma^2,c); mixture retains folded ambiguity, no 0/180 wrap","X,T","T","current telemetry availability; no mandatory added lag","O(E*K), bounded moments per track"),
("P01","location_bonus=min(b_max,b0*exp(-silence/tau))*compatibility; zero on credible voice conflict","E,X,T","T","no deliberate wait; expiry uses source/receipt ages explicitly","O(E*K), 2 spatial moments per track"),
("P02","update anonymous sector center only from reliable observed bearings; person-sector link is reversible and voice-vetoed","X,T","T","map appears after causal accumulated evidence, never truth seats","O(E*K), max 16 sectors"),
("P03","voice_lr=eta_v; location_lr=eta_x; eta_v<eta_x and tau_voice>tau_location","E,X,T","T","new-location wait plus current voice availability","O(E*K*192), separate bounded voice/location states"),
("P04","ACTIVE->DORMANT after silence; DORMANT->ACTIVE only with voice score/margin; location prior expires independently","E,X,T","T","reentry waits for admitted voice window and comparison","O(E*K*192), max 16 dormant and active tracks total"),
("P05","new evidence creates provisional visitor; promote after unique admitted speech U>=U_min and repeat-compatible observation","E,T","T","promotion wait=unique evidence deficit, not elapsed silence","O(E*K*192), visitor count shares track cap"),
("E01","mu=normalize(sum_i q_i*v_i); q_i=clip(purity*nonclip*unique_fraction,0,1) and quarantine inconsistent updates","S,E,T","E","window end plus segmentation and embedding availability","O(E*K*192); reused vectors only when exact spans unchanged"),
("E02","L=.5 s initially; request next supported L in {.75,1,1.5,2,3} if ambiguity remains; never span a confirmed conflicting turn","S,E,T","E","L plus context/queue; skipped short turn stays a miss","N_embed(L,hop)*measured_t_embed(L), one shared graph"),
("E03","q_boundary=0 or tapered weight within causal delta of a proposed handoff; preserve rejected short-reply denominator","S,E,X,T","E","delta exclusion does not give future boundary knowledge; later correction is revision","changed spans require embeddings; track cost O(E*K*192)"),
("E04","request embed on uncertainty or fresh change, or time_since_last>=floor; token bucket bounds burst calls","S,E,X,T,R","E","periodic floor bounds discovery only if queue remains bounded","N_floor+N_burst calls, cap explicit; compare same budget audio-only schedule"),
("E05","store <=3 medoids/track; match with duration-aware acceptance and quarantine, rather than unrestricted max over history","E,T","T","no extra evidence wait beyond existing vectors","O(E*K*3*192), 16*3*192*4=36864 vector bytes"),
("M01","score_k=w_v*cos(v,mu_k)+w_x*location_k+w_t*recency_k; birth/Unknown competes explicitly","E,X,T","T","current feature availability only","O(E*K*192), scalar arithmetic"),
("M02","w_x(t)=cap*freshness*observed_consistency*voice_compatibility; energy is quality evidence, not independent probability","E,X,T","T","reliability window uses only received history; bounded age gate","O(E*K*192), rolling reliability states"),
("M03","p_t(k,l) proportional tempered_likelihood*sum transition*p_prev; preserve Unknown and ambiguous location mass","E,X,T","T","causal filter no smoothing; optional lag charged separately","O(E*K*L), bounded K<=16,L<=16"),
("M04","alpha_t(k,d) proportional observation*transition(duration); explicit short-turn and overlap/Unknown states","S,E,X,T","T","causal or named fixed lag; duration prior never removes denominator","O(E*K*D), D and lag capped"),
("M05","min sum cost_ij*x_ij with one-to-one constraints only for independently supported observations; unmatched/birth permitted","S,E,X,T","T","latest required observation plus assignment compute","O(K^3) worst case bounded K<=16"),
("R01","min-cost path over [t-lag,t] association graph; emit revision(old,new,available_at,lineage) without overwriting initial output","E,X,T,D","T","lag in {0,.5,1,2}; first-decision and revised metrics separate","O(E_window*K^2), event window and K bounded"),
("R02","cannot_link_ij decays exp(-dt/tau); create only after repeated clean voice conflict; allow expiry/appeal","S,E,T","T","conflict becomes usable only after confirming evidence arrives","O(E*K^2), bounded conflict matrix"),
("R03","one track cannot own two independent concurrent voice observations; beam count alone gives no cannot-link","S,E,X,T","E","overlap/context availability plus both actual vectors","possibly two embeddings per supported independent source; no fabricated separation"),
("R04","commit provisional merge as versioned node; retain parent prototypes until lag expires; split/rollback on clean conflict","E,T,D","T","rollback at later evidence time; wrong exposure retained","<=2 provisional snapshots/track, bounded revision horizon"),
("R05","commit label when cumulative unique support>=u and score/margin pass; transcript text emitted independently","E,T,D","T","explicit confirmation wait; stable wrong labels remain errors","O(E*K), bounded label state"),
("A01","endpoint_hint=handoff_persistent and audio_silence_confirmed; feed supported endpoint policy, never identity-triggered reset","A,S,X","A","native endpoint silence plus hint availability; compare diarization-only branch","fresh stateful ASR per distinct endpoint/reset history"),
("A02","admit weak speech evidence if segmentation OR bounded fresh-energy support; never gate journal/ASR audio","S,E,X","E","rescue waits for delivered energy/model result","new embedding inputs require compute; ASR unchanged if audio unchanged"),
("A03","ASR tap=a, speaker tap=b with shared source indices and measured lag; gains each once","A,S,E,I","I","max tap availability; unknown alignment makes joint timing LIMITED","one instance per model possible, two audio rings; no per-person decoders"),
("A04","tap_t=hysteretic argmax past_quality; switch only at explicit endpoint with overlap-free sample accounting","A,I,X","A","selection uses past only; decoder state transition charged","two stored input taps; chosen ASR branch fresh, optional overlap doubles cost"),
("A05","route two physical focused outputs; independently decode then suppress duplicates using causal evidence","A,S,E,X,I","H","new physical capture required; two streams have separate clocks","RESEARCH_DUAL_STREAM: up to 2 ASR streams plus leakage management"),
("U01","p_b=E_b/sum E; H=-sum p_b log p_b; use entropy/ratios as bounded confidence, zero/NaN explicit","X,T","T","single delivered energy packet, no calibration assumption","O(E*B), no extra model"),
("U02","r=dispersion(beams)+innovation; reduce trust on conflict but retain stable-wrong counterexample","X,T","T","rolling causal history length; lag charged if used","O(E*B), bounded rolling statistics"),
("U03","state=AVAILABLE/STALE/MISSING/RECOVERING; expiry by receipt age and monotonic sequence; repeated values not proof of staleness","X,T","T","reacquire after n delivered fresh packets, explicit delay","O(E), bounded last-sequence and age state"),
("U04","optional slow_context applied only if field available and documented valid; missing diagnostics => baseline fallback","X,S,T","H","historical AEC/AGC/RT60 unavailable; no invented timeline","DEFERRED_MISSING_INPUT: field acquisition/semantics required"),
("U05","motion_state gates spatial weight; no gyro yaw correction without observed calibrated orientation","X,T","H","settling delay after real movement; fixture timing separate","DEFERRED_MISSING_INPUT: no IMU/walking evidence in current bank"),
("D01","explicit stationary mode: anonymous sector label; voice veto for identity, folded-bearing ambiguity=>Unknown","X,E,T,D","T","mode setup event and current cue availability","O(E*K), no truth seat initialization"),
("D02","score only user-selected enrolled templates plus Unknown; reject by score, margin and unique evidence U","E,T","T","enrollment setup and U deadline included","O(E*G*192), G in {2,4,8,16}; gallery remains bounded"),
("D03","target_display=recognized_target AND policy; retain outsider/unknown internal transcripts and target misses","T,D","T","recognition availability plus display update","O(E), no extra neural branch"),
("D04","intervention(event_id,user_label,scope,expiry) alters later association; wrong correction has reversible lineage","T,D","T","human intervention delivery time; no retroactive automatic credit","O(E*K), bounded intervention records"),
("D05","arrow=fresh and qualified_speech and unambiguous; off-delay bounded; duplicate directions merged as display objects","S,X,D","T","speech availability plus arrow on/off hysteresis","O(E*B), UI cap two arrows does not assert two people"),
("Q01","derive speech posterior from actual powerset semantics; hysteresis gate on derived speech, with bounded fresh-energy additive term","S,X,E","E","10 s trailing context arrival plus model/queue; current tail events","same tensors reusable only if context fixed; changed admissions recompute embeddings"),
("Q02","next_seg=min(last_seg+periodic_floor,qualified_change_request); fixed 160000-sample input always","S,X,R","S","dispatch ceil-to-hop plus inference availability; no arbitrary shorter graph","N_seg=duration/hop; .5 vs .75 gives 1.5x calls before queue effects"),
("Q03","accept embedding only when supported contiguous span meets speech_fraction and exclusive_fraction; soft weight alternative","S,E,T","E","entire evidence span/context available before vector","recompute changed waveforms; hard-mask frontend unsupported unless separately proven"),
("Q04","short vector proposes; longer compatible vector confirms; union evidence disjoint accounting prevents double confidence","S,E,T","E",".5 s provisional, L confirmation plus compute; short replies retained as tentative","shared ReDim graph; two calls only when confirmation requested"),
("Q05","y=g*x; RMS_gate=r; test frozen r and gain-adjusted r=g*r0 with source x/gain provenance fixed","I,S,E,A","I","no per-scene future normalization; preprocessing causal","changed gained audio invalidates all three neural consumers"),
("Q06","threshold(L)=theta0+a/sqrt(max(U,epsilon)); margin and Unknown retained; fit only named exploratory calibration","E,T","T","U is admitted unique seconds, not overlapping summed duration","cheap replay O(E*K*192), calibration trial count exposed"),
("Q07","separate diarization boundary from ASR endpoint; compare persistent-cue advice at native silence confirmation vs same silence alone","A,S,X,T","A","first/final text and handoff advice separately timestamped","new ASR for changed resets; diarization-only can reuse exact words"),
("Q08","assign decoder-supported timed words to available speaker spans; uncertain timing=>span ambiguity, never truth alignment","A,T,D","T","word availability plus optional bounded revision lag","reused recognizer timing only if actually exported; no invented exact word times"),
("Q09","greedy vs installed modified_beam_search(max_active_paths=2/4); constant audio/endpoint then paced load","A,R","A","search/dispatch queue measured; encoder chunk unchanged","fresh ASR; worst cost measured, not presumed 2x or 4x"),
("Q10","pre-roll ring retains audio; optional speech rescue changes evidence only while continuous ASR preserves audio","S,E,X,I","E","rescue receipt time+window availability; pre-roll is past context","bounded <=1 s extra float ring=64000 bytes; added calls measured"),
("Q11","route tuple(ASR,segment,embed) over aligned O0/O1; compare same gain and source schedule","A,S,E,I","I","tap-specific capture/output lag explicitly bound","at most one instance per selected model; dual rings and caches local"),
("Q12","q_t=uncertainty score; allocate floor+bounded bursts; periodic audio-only probe ignores positional confidence","S,E,X,R","E","uncertainty/request time plus queue; skipped requests logged","token bucket bounds calls/min, no self-suppression without periodic probe"),
("Q13","prototype update eta=q_purity*unique_fraction*voice_consistency; hold suspect vector in quarantine until later clean support","S,E,T","T","quarantine creates delayed update not immediate correct decision","O(E*K*192), <=3 exemplars/track and bounded quarantine"),
("Q14","duration state has explicit brief-reply branch; occupancy prior cannot impose minimum speaker-turn length","S,T","T","brief branch available at first evidence; other durations charged","O(E*K*D), fixed duration bins"),
("Q15","name_commit iff score>=theta, margin>=m and U_unique>=u; outsider Unknown state explicit","E,T","T","first tentative vs committed name deadlines separately","one shared graph; G<=16 templates per explicit gallery experiment"),
("Q16","earliest-deadline-first optional scheduler with capture/ASR priority; bounded speaker queue and no hidden audio drop","A,S,E,R","R","measure queue age/process tree at paced input; drops exposed","resident model bank; thread pools 1/2; bounded queues"),
("Q17","emit raw partial now; punctuation once at native final; later speaker revision changes attribution only","A,D","T","punctuation compute isolated from identity wait","one punctuation model/worker; bounded pending finals"),
("Q18","if queue_age>q_hi reduce optional cadence; recover below q_lo; journal loss always fatal/explicit","S,E,R","R","fallback/recovery timestamps, never pretend skipped work complete","same resident models, lower optional duty cycle; target power unmeasured"),
("Q19","new fixed-beam captures plus existing Pyannote identify whether two streams add independent recoverable speech","A,S,E,X,I","H","new hardware evidence and availability needed","RESEARCH_DUAL_STREAM, resident memory/cost measured before recommendation"),
("Q20","fit interactions y=beta0+betaP*P+betaX*X+betaPX*P*X on paired bank; choose stable Pareto ranges","A,S,E,X,T,R","I","each candidate retains own evidence/compute delay, no single score hides it","20-30 profiles around cached recipe groups; exploratory not external validation"),
("N01","sensor_credit resets to zero after m clean voice-inconsistent cue events; recover only on independent audio agreement, with periodic no-cue audit","S,E,X,T","T","quarantine starts when contradiction is actually available; recovery delayed","O(E*K*192), bounded credit counter; no new neural if audio audit periodic"),
("N02","tail_reliability(age_of_speech_in_context) weights current segmentation, request refresh only with fresh XVF speech support; no backdating","S,X,R","S","fixed 10 s receptive input; true trailing frame offset measured","one graph; bounded extra refresh token; avoids permanent stale tail confidence"),
("N03","spatial_and_seg_support may propose identity update, but prototype version held until independent nonoverlapping later ReDim window agrees","S,E,X,T","E","two disjoint evidence arrivals, explicit confirmation delay","at most one pending prototype/track; added ReDim call cost bounded"),
("N04","endpoint_budget tracks recent false/rapid finalizations; suppress new XVF advice after budget exhausted while native endpoint remains enabled","A,S,X,R","A","advice token refill causal; native endpoint latency unchanged in fallback","fresh stateful ASR histories, O(E) budget state"),
("N05","per-track evidence debt d=max(0,U_required-U_unique); queue requests by debt/age, spatial confidence cannot zero debt","S,E,X,R,T","E","debt paid only after vector availability, not requested duration","CM5 single embedder queue with bounded debt and age fairness"),
("N06","freeze prototype on detected clipping/level transition; recover using compatible ungained score behavior or next clean vector, never future normalization","I,S,E,T","E","recovery wait until actual unclipped supported evidence","one shared graph; clipping detector O(samples), no audio repair claim"),
("N07","revisions use two budgets: maximum age L and maximum edits per utterance R; excess unresolved attribution remains explicit Unknown","A,T,D,R","T","bounded lag and correction burden; original wrong labels remain scored","CM5 bounded revision DAG O(utterances_in_L*K); no unbounded history"),
("N08","when freshness lost, reenter voice-only state from last committed audio-only prototype, not spatially contaminated fused mean","X,E,T","T","fallback instantaneous at expiry; later evidence may revise at current time","two small prototypes/track, 16*2*192*4=24576 bytes"),
]

BINDINGS = {
"I": {"component":"input/tap/gain","actual":["audio.py:AudioJournal.append","audio.py:WavSource","config.py:PipelineConfig.sample_rate"],"status":"WRAPPER_EXTENSION_REQUIRED_FOR_SPLIT_TAPS; original recipe is externally gained once","constraints":"16000 Hz mono; FLOAT/native PCM16 gained O0 read at unity; no future scene normalization"},
"A": {"component":"Sherpa ASR/punctuation","actual":["models.py:SherpaStream.__init__","models.py:SherpaStream.accept","models.py:SherpaStream.reset_endpoint","models.py:SherpaStream.finish","runtime.py:PipelineEngine._asr_loop"],"status":"NATIVE_ENDPOINT_FIELDS; decoder/search constants require opt-in plumbing and installed API verification","constraints":"encoder export chunk is fixed; reset only actual endpoint; punctuation final only; no truth hotwords"},
"S": {"component":"Pyannote segmentation","actual":["models.py:SpeakerModels.segment","models.py:POWERSET_TO_MULTILABEL","runtime.py:PipelineEngine._speaker_loop"],"status":"NATIVE_FIXED_GRAPH_AND_WRAPPER_POLICY","constraints":"160000 samples fixed; argmax seven powerset classes; baseline hard tail fraction .20; onset/offset config fields unused in original loop; local slots are not identities"},
"E": {"component":"ReDim evidence","actual":["models.py:SpeakerModels.embed","runtime.py:PipelineEngine._speaker_loop","config.py:PipelineConfig.embedding_window_sec","config.py:PipelineConfig.embedding_hop_sec","config.py:PipelineConfig.minimum_rms"],"status":"SUPPORTED_WAVEFORM_WINDOW_WRAPPER; every new length must pass actual graph probe","constraints":"waveform float32, >=8000 samples wrapper, 192 dimensional L2-normalized output; no unsupported frame mask; unique evidence union"},
"T": {"component":"tracker/identity","actual":["speakers.py:SpeakerTracker.update","speakers.py:ProfileStore.load","contracts.py:SpeakerDecision"],"status":"WRAPPER_POLICY_EXTENSION; baseline exact control retained","constraints":"cosine >=.35 original clustering; identity .5128856897354127/margin .03/elapsed2s baseline; new union-evidence policy distinct"},
"X": {"component":"XVF evidence","actual":["xvf.py:NoSpatialEvidence","contracts.py:SpatialEvidence"],"status":"CAUSAL_ADAPTER_EXTENSION; baseline fields inactive","constraints":"arrived raw/focused/selected direction and energy only; missing not silence; no scene geometry/true IDs; 0/180 linear ends not neighbors"},
"R": {"component":"runtime/resource","actual":["models.py:_ort_session","runtime.py:PipelineEngine._launch","runtime.py:PipelineEngine._emit","audio.py:MicrophoneSource.start"],"status":"THREAD_FIELDS_NATIVE; scheduler/bounds extensions separately tested","constraints":"capture reserve120s bounded; baseline SimpleQueue/events, clusters and disk journal have growth paths; CPU process-tree accounting required"},
"D": {"component":"display/event lineage","actual":["runtime.py:PipelineEngine._transcript_event","contracts.py:PipelineEvent","gui.py","text_format.py:finalize_punctuation_output"],"status":"WRAPPER_EXTENSION_FOR_LINEAGE_AND_REVISION","constraints":"do not hold readable text for name; preserve first emission and raw words; anonymous != enrolled naming"}
}
CACHE = {
"T":"Exact audio/model outputs and availability may be reused. Invalidate tracker/lineage/attribution and downstream scores; any scheduler or window mutation escalates to relevant neural branch.",
"E":"Rebuild evidence spans/quality from bound segmentation. Recompute every changed ReDim waveform; invalidate vectors, prototypes, tracking and attributed scores. Reuse ASR only if audio/decoder/endpoint history unchanged.",
"S":"Recompute segmentation for changed context/stride/input. Rebuild admissions and affected embeddings/tracks. Do not relabel cached tensor timestamps.",
"A":"Run complete stateful recognizer branch for changed audio, delivery, decoder or endpoint/reset history; preserve all final text, duplicates and omissions. Speaker features reusable only when independent and identical.",
"I":"Changed tap/gain/preprocessing invalidates all consumers of changed audio. Branch-specific exact hashes permit only unchanged branches to hit.",
"R":"Recompute paced availability/performance and validate numerical parity. Unchanged numerical outputs do not justify reusing timings.",
"H":"Missing physical/diagnostic input is not synthesized. New hardware branch in later authorized stage produces new captures and downstream cache identities."
}

# Values are prospective search domains, not claimed defaults or optima.
# Exact tested settings are bound from S6A effective-profile receipts.
DOMAINS = {
"I":{"tap":["O0","O1"],"original_gain":{"O0":1.4125375446227544,"O1":1.0},"gained_input_read_gain":1.0,
     "fixed_raw_gain_candidates":[1.0,1.4125375446227544],"split_route":"Requires separate explicit route tuple and measured saved-output alignment; current tap field declares supplied mono."},
"A":{"endpoint_pairs_sec":[[2.4,1.2],[1.6,.8]],"max_utterance_sec":[20],"host_dispatch_ms":[50,100],
     "decoder":["greedy_search","modified_beam_search"],"max_active_paths":[2,4],"blank_penalty":[0,.2],
     "native_binding":"research_profiles.py:ASRSettings -> ResearchProfile.apply -> models.py:SherpaStream.__init__; exact imported API check remains authoritative"},
"S":{"graph_input_samples":[160000],"segmentation_hop_sec":[.5,.75,1.0],
     "post_policy":["hard_argmax_fraction","posterior_hysteresis"],"onset":[.46,.55],"offset":[.40,.45],
     "hard_speech_fraction_threshold":[.20],"overlap_fraction_or_posterior_threshold":[.20,.30],
     "native_binding":"research_profiles.py:SegmentationSettings/segmentation_gate; onset/offset operate only in posterior policy"},
"E":{"window_sec":[.5,1.,1.5],"hop_sec":[.25,.5],"minimum_rms":[.001,.002,.004],
     "replay_rule":"Segmentation hop must be integer multiple of embedding dispatch in initial app. Actual length tests passed .5/.75/1/1.5/2/3s; no arbitrary mask support.",
     "native_binding":"research_profiles.py:EmbeddingSettings -> models.py:SpeakerModels.embed"},
"T":{"cosine_threshold":[.30,.35,.40],"ambiguity_margin":[.03,.06],"prototype_update_threshold":[.45,.55],
     "commit_unique_evidence_sec":[.5,1.,2.],"max_tracks":[16],"direction_match_deg":[20.,25.,35.],
     "direction_change_deg":[25.,35.,45.],"direction_persistence_sec":[.3,.75,1.0],
     "position_decay_sec":[6.,12.,24.],"spatial_weight":[0.,.06,.12],
     "native_binding":"research_tracking.py:TrackingConfig/ResearchTracker; wider algorithms in registry require explicit S6B implementation"},
"X":{"mode":["none","tracking_only","soft_energy","advisory","soft_energy_advisory"],
     "speech_assist_delta":[0.,.025,.05],"minimum_reliability":[.5,.75],"maximum_observed_or_delivery_age_sec":[.10,.25],
     "advisory_silence_sec":[.30,.50],"advisory_min_utterance_sec":[.5,1.],
     "native_binding":"research_profiles.py:XVFSettings/JsonSpatialProvider/EndpointAdvisor; source-age unavailable stays explicitly delivery-only"},
"R":{"ASR_threads":[1,2],"speaker_threads":[1,2],"punctuation_threads":[1],"capture_ms":[20],
     "raw_capture_reserve_sec":[120],"periodic_audio_probe_floor_sec":[.5,1.],"burst_hop_sec":[.25],
     "native_binding":"research_profiles.py:RuntimeSettings; future token-bucket/deadline scheduler is not implied by thread plumbing"},
"D":{"revision_horizon_sec":[0.,.5,1.,2.],"maximum_edits_per_utterance":[2],"maximum_pending_events":[256],
     "partial_display_min_interval_sec":[0.,.1,.2],"punctuation":["final_only"],
     "native_binding":"research_profiles.py:PunctuationSettings; future revision/UI controls require separately tested implementation"}
}

NEW = {
"N01":("Contradiction-triggered sensor credit quarantine","XVF trust should fall when fresh but stable bearings repeatedly contradict clean voice evidence.","A contaminated voice prototype can falsely discredit good geometry.","Stable wrong reflection, clean voice recovery, and same-bearing speaker replacement.","wrong merges, quarantine recovery, no-cue fallback parity"),
"N02":("Trailing-context reliability and bounded refresh","XVF activity may identify when stale trailing segmentation warrants an extra fixed-shape refresh.","Energy from music could trigger expensive refresh storms.","Same audio with stale/reordered energy, subsecond quiet interjection, long monologue.","short-reply admitted evidence, segmentation calls, queue age"),
"N03":("Independent evidence escrow for prototype changes","Require a second disjoint voice window before cue-assisted evidence alters a committed prototype.","Short replies may never confirm; tentative coverage must remain visible.","Contaminating overlap followed by clean return; one-window short replies.","prototype contamination, wrong merge exposure, never-confirmed replies"),
"N04":("Endpoint advice circuit breaker","Bound the damage of erroneous handoff advice by limiting advice-driven endpoint frequency.","Suppression may delay legitimate fast speaker handoffs.","False angle jumps mid-word, rapid backchannels, silence-only advice.","raw S/D/I, duplicate finals, finalization delay, breaker activation"),
"N05":("Unique-evidence debt scheduler","A shared CM5 embedder should allocate limited calls by evidence deficit and age so confident positions do not starve new voices.","High-debt noisy tracks can monopolize service without quotas.","Same-angle replacement, quiet short replies, competing noisy track.","unique evidence per track, starvation delay, calls/min, full queue/load"),
"N06":("Clipping-transition prototype freeze","Level changes should temporarily stop contaminated prototype updates without discarding text.","O1 clipping and natural loud speech may over-trigger freezing.","Paired tap/gain, abrupt level change, loud clean versus clipped speech.","wrong merges, evidence rejection, short-turn coverage, recovery delay"),
"N07":("Two-budget revision ledger","Bound both temporal revision horizon and number of edits so late labels cannot grow state or churn indefinitely.","Edit caps can preserve wrong committed labels; Unknown must remain possible.","Long uncertain sequence, adversarial alternating association, delayed ASR final.","initial/revised cpWER, correction count, worst wrong-label duration, RAM growth"),
"N08":("Clean fallback shadow prototype","Recover voice-only operation from an audio-only prototype when fused spatial history becomes unreliable.","Shadow prototype still relies on potentially wrong audio associations.","Freshness outage after false spatial merge, then clean moved return.","fallback parity, recovery time, extra state bytes, return consistency"),
}

# Up to 30 end-to-end profiles: no blind Cartesian product.
TRIALS = [
("B00","R0","B0_exact","off",[],"historical_exact_control"),
("B01","R0","voice_time","off",["E01"],"matched_architecture_parent"),
("B02","R0","angle_only","on",["D01","J05"],"spatial_diagnostic_not_identity"),
("B03","R0","sustained_change","on",["J01"],"B01"),
("B04","R0","decaying_memory","on",["P01"],"B01"),
("B05","R0","reliability_adaptive","on",["M02","U03"],"B01"),
("B06","R0","static_fusion","on",["M01"],"B01"),
("B07","R0","cusum_change","on",["J02"],"B01"),
("B08","R0","uncertain_bearing","on",["J05"],"B01"),
("B09","R0","dual_timescale_dormant","off",["P03","P04"],"B01"),
("B10","R0","dual_timescale_dormant","on",["P03","P04"],"B09"),
("B11","R0","robust_prototypes","off",["E05"],"B01"),
("B12","R0","conflict_rollback","off",["R02","R04"],"B01"),
("B13","R0","tempered_filter","off",["M03"],"B01"),
("B14","R0","tempered_filter","on",["M03"],"B13"),
("B15","R0","bounded_revision","off",["R01","N07"],"B01"),
("B16","R1","measured_A_component_bundle","off",["Q01","Q04","Q07"],"B01"),
("B17","R1","measured_A_component_bundle","on",["Q01","Q04","Q07","M02"],"B16"),
("B18","R2","purity_short","off",["Q03","Q13"],"B01"),
("B19","R2","purity_short","on",["Q03","Q13","N03"],"B18"),
("B20","R3","purity_long","off",["Q03","Q04","Q06"],"B18"),
("B21","R3","purity_long","on",["Q03","Q04","Q06","N03"],"B20"),
("B22","R4","endpoint_dispatch","off",["Q07","Q08"],"B01"),
("B23","R4","endpoint_dispatch","on",["Q07","N04"],"B22"),
("B24","R5","evidence_debt_budget","off",["Q12","Q16","N05"],"B01"),
("B25","R5","evidence_debt_budget","on",["Q12","Q16","N05","N01"],"B24"),
("B26","R6","gain_RMS","off",["Q05","N06"],"B01"),
("B27","R6","gain_RMS","on",["Q05","N06","M02"],"B26"),
("B28","R7","bounded_search_runtime","off",["Q09","Q16"],"B22"),
("B29","R7","bounded_search_runtime","on",["Q09","Q16","M02"],"B28"),
]
RECIPES = [
{"id":"R0","delta":"Original effective audio/ASR/segmentation/embedding recipe; exact B0 separate from new tracker.","new_neural":"Reuse compatible original features; missing exact vectors require native feature replay.","branches":"ASR original; segmentation original; .5/.25 ReDim"},
{"id":"R1","delta":"Bind the actual S6A joint bundle including adverse findings; do not claim it is optimal.","new_neural":"Reuse exact S6A compatible features on panel; recompute remaining all-240.","branches":"Actual tested settings from final effective profiles"},
{"id":"R2","delta":"Supported exclusive-speech policy at .5 s/.25 s, original ASR, no front-end mask.","new_neural":"New evidence admissions and affected short embeddings; same tensors only if same contexts.","branches":"Pyannote original tensors/postpolicy; short ReDim"},
{"id":"R3","delta":"Same purity policy as R2 with valid 1.0 s/.5 s evidence and duration-aware abstention; short provisional retained.","new_neural":"Actual longer vectors and cadence; exact common contexts may share segmentation.","branches":"R2 segmentation; new long ReDim"},
{"id":"R4","delta":"Native endpoint pair 1.6/.8 s, max20s; host dispatch50ms versus100ms where validated; diarization-only alternative.","new_neural":"Each distinct reset/chunk/advice history requires full Sherpa; no word re-slicing.","branches":"Endpoint/dispatch ASR; original speaker features when truly identical"},
{"id":"R5","delta":"Evidence-debt/floor scheduler: 1s periodic floor, .25s bounded bursts; resident CPU pools1/2 tested.","new_neural":"Changed evidence requests/availability need real embedding runs; cue-off must remove request influence too.","branches":"New adaptive speaker schedule; unchanged ASR only after parity"},
{"id":"R6","delta":"Compare baseline gain versus one causal fixed alternative and paired minimum_rms .001/.002/.004; source gain once.","new_neural":"Fresh all neural branches for changed audio; policy-only threshold comparison may reuse exact audio segmentation.","branches":"Gain/preprocess + RMS eligibility"},
{"id":"R7","delta":"Installed modified_beam_search max_active_paths2/4 versus greedy, host50/100ms and pools1/2.","new_neural":"Fresh stateful ASR per recipe; paired runtime reprofile and numerical parity mandatory.","branches":"Search/dispatch ASR; exact same speaker branch can hit"},
]

SOURCES = [
("Pyannote model card","https://huggingface.co/pyannote/segmentation-3.0","10 s mono 16 kHz and seven powerset classes; local H2 wrapper, not the full diarization pipeline, governs execution."),
("Pyannote 3.1.1 pipeline source","https://raw.githubusercontent.com/pyannote/pyannote-audio/3.1.1/pyannote/audio/pipelines/speaker_diarization.py","Reference powerset/postprocessing distinction; do not infer the installed custom wrapper API from generic pipelines."),
("ReDimNet2 authors","https://github.com/PalabraAI/redimnet2","Actual model family: PalabraAI ReDimNet2-B2. Local checkpoint, exported graph and wrapper bind the TF-style 72-mel frontend, supported input lengths and 192-vector normalization. The pack's older IDRnD/ReDimNet link is architectural background only."),
("Sherpa online endpoint example","https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/master/python-api-examples/speech-recognition-from-microphone-with-endpoint-detection.py","Endpoint/decoder interface reference; bound installed API determines supported arguments."),
("Sherpa Python documentation","https://k2-fsa.github.io/sherpa/onnx/python/index.html","CPU package and online recognition entry points; no assurance of current target-wheel or CM5 performance."),
("ONNX Runtime threading","https://onnxruntime.ai/docs/performance/tune-performance/threading.html","Intra-op count includes the calling thread; sequential graph mode and spinning affect contention. Installed version must verify supported options."),
("Raspberry Pi CM5 product","https://www.raspberrypi.com/products/compute-module-5/","ARM64 target family; the purchased 2 GB/32 GB/no-wireless configuration is a user/workbook binding, not a desktop measurement."),
("ONNX Runtime Raspberry Pi tutorial","https://onnxruntime.ai/docs/tutorials/iot-edge/rasp-pi-cv.html","Shows a Raspberry Pi deployment path for another model. Does not qualify this speech stack, weights, RAM or timing."),
("Windows process memory counters","https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex","PrivateUsage is private commit, distinct from resident working set. Preserve USS, RSS and private commit separately."),
("psutil memory API","https://psutil.io/api/","USS describes unique process memory; PSS shares pages proportionally where available. Current documentation discusses version8 changes; installed7.2.2 memory_full_info is the local API and is not upgraded here."),
]

def read_json(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def bind(path):
    path=Path(path); return {"path":str(path.resolve()),"bytes":path.stat().st_size,"sha256":sha(path)}
def atomic(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    temp.replace(path)
def write_text(path,text):
    Path(path).write_text(text,encoding="utf-8",newline="\n")

def make_registry(seed):
    source={x["id"]:x for x in seed["items"]}
    if len(source)!=60: raise ValueError("Expected all 60 distinct seed ideas")
    items=[]
    for ident,eq,modules,cache,latency,cost in SPECS:
        if ident in source: row=dict(source[ident])
        else:
            title,hyp,failure,test,metrics=NEW[ident]
            row={"number":len(items)+1,"id":ident,"family":"New cross-component mechanisms","title":title,"hypothesis":hyp,
                 "main_failure":failure,"discriminating_test":test,"primary_metrics":metrics,
                 "provenance":"S6A independent design contribution; hypothesis, not measured improvement"}
        module_ids=modules.split(",")
        row.update({"equation_or_state_change":eq,"components":[BINDINGS[x]["component"] for x in module_ids],
            "api_bindings":[{"binding_id":x,**BINDINGS[x]} for x in module_ids],
            "candidate_parameters":eq,"initial_parameter_domains":{x:DOMAINS[x] for x in module_ids},
            "domains_are_proposals":"Select coherent combinations under graph/cadence constraints; do not execute the full Cartesian product. Values do not assert sensor calibration or optimality.",
            "cue_disabled_parent":{"id":ident+"_X0","definition":
            "Same component settings, architecture, observed audio, compute budget and decision-delay policy; disable ALL XVF contribution including scheduling, endpoint advice, quality gates and prototype updates. A pure non-XVF candidate is its own metadata-off condition; compare additionally to B01 at the same recipe."},
            "expected_benefit":row["hypothesis"],"failure_hypothesis":row["main_failure"],
            "cache_invalidation":CACHE[cache],"latency_model":latency,"compute_estimate":cost,
            "target_memory_class":"RESEARCH_DUAL_STREAM" if ident in {"A05","Q19"} else "DEFERRED_MISSING_INPUT" if ident in {"U04","U05"} else "BOUNDED_SINGLE_MODEL_BANK",
            "acceptance_metrics":{"primary":row["primary_metrics"],"guardrails":[
                "Raw WER/CER, S/D/I and matched cpWER with all failures and unknowns retained.",
                "Wrong-person merge exposure and short-reply coverage reported beside continuity; all-unknown and one-person controls cannot win.",
                "Immediate and revised results use actual availability; no inferred exact latency where alignment absent.",
                "Measured full process-tree footprint/queue; deployment screen is provisional, not CM5 qualification."
            ],"decision_rule":"Exploratory Pareto comparison to exact B0 and matched parent on the same scenes/taps. Retain only after all-240 confirmation and expose adverse condition results. No automatic significance/generalization claim."},
            "implementation_status":"PROPOSED_NOT_IMPLEMENTED_BY_DESIGN_REGISTRY",
            "s6a_evidence_status":"Use executed component/cue receipts for tested constituents; this composite ID is not executed unless an exact effective profile/result binds it."})
        items.append(row)
    if {x["id"] for x in items if x["id"] in source} != set(source): raise ValueError("Lost seed idea")
    if len(items)<68 or len({x["id"] for x in items})!=len(items): raise ValueError("Registry invalid")
    return {"schema_version":1,"count":len(items),"seed_count":60,"new_count":len(NEW),"items":items}

def make_plan(report):
    trials=[]
    for ident,recipe,mechanism,cues,ideas,parent in TRIALS:
        trials.append({"profile_id":ident,"recipe_id":recipe,"mechanism":mechanism,"metadata":cues,"idea_ids":ideas,
            "comparison_parent":parent,"scene_count":240,"outputs":["O0","O1"],"scene_output_policy_runs":480,
            "status":"S6B_PLANNED_NOT_EXECUTED","selection":"Keep family pairs and all failures. Fixed S6A panel is debugging only; confirm retained general profiles all 240.",
            "cue_off_requirement":"For multi-stage candidates X0 must also disable cue-dependent windows, scheduling and endpoints, not just final score weight.",
            "execution_gate":"Implement native opt-in profile and observable-effect/cache/causality tests before scheduling. Bind exact settings; unsupported profile is explicit."})
    return {"schema_version":1,"status":"PROSPECTIVE_S6B_PLAN_NOT_EXECUTED","profile_count":len(trials),
        "maximum_policy_runs_if_all_profiles_retained":len(trials)*480,"expensive_recipe_families":RECIPES,
        "recipes_are_not_identical_cache_keys":"Cue-dependent scheduling/reset branches within a family produce distinct exact keys and must be executed separately.",
        "cost_model":{"formula":"wall_plan = sum_j(new_job_count_j * measured_median_wall_j) / measured_effective_concurrency_j + replay_seconds + validation + at_least_2700s_packaging",
            "historical_original_reference":{"source":str(SIM/"reports/S5/20260909T130308Z/FINAL_AUDIT.json"),
                "fresh_jobs":312,"wall_seconds":4683.936,"mean_seconds_per_job":4683.936/312,
                "480_equivalent_serial_seconds":480*4683.936/312,"scope":"S5 original fresh process CPU cost, not S6 resident or CM5 prediction"},
            "rough_original_equivalent_8_family_serial_seconds":8*480*4683.936/312,
            "warning":"This roughly 16-hour original-cost reference is not a commitment: longer evidence, modified beam search and cue-specific histories may exceed it. Replace with each S6A/B measured pilot before launch.",
            "stage_budget_seconds":86400,"packaging_reserve_seconds":2700,"new_storage_cap_GiB":120,
            "free_reserve_GiB":{"C":50,"G":75},"stop_admission":"Do not launch a job whose conservative observed ETA would consume the packaging reserve. Preserve pending profiles and exact resume."},
        "mandatory_interactions":[
            {"interaction":"speech/overlap x embedding duration","profiles":["B18","B19","B20","B21"]},
            {"interaction":"RMS/gain x evidence yield","profiles":["B01","B05","B26","B27"]},
            {"interaction":"evidence cadence x prototype thresholds","profiles":["B11","B20","B21","B24","B25"],"followup":"60-150 settings in C only after broad B evidence"},
            {"interaction":"direction persistence x endpoint/revision","profiles":["B03","B15","B22","B23"]},
            {"interaction":"location-memory decay x reentry","profiles":["B04","B09","B10"]},
            {"interaction":"decoder/chunk delivery x runtime budget","profiles":["B22","B23","B28","B29"]},
            {"interaction":"tap x segmentation/embedding input","profiles":["B16","B17","B18","B19","B20","B21"],"condition":"Both taps throughout. A true split tap branch needs saved measured lag and explicit route tuple; do not call whole-tap pairing a tested split-stream result."}],
        "planned_interaction_contrast":"For lower-is-better metric, (P1X1-P1X0)-(P0X1-P0X0); negative is incremental joint improvement. Pair exact panel/tap/reference support. Report all four raw metrics.",
        "extra_controls_outside_candidate_count":["One person for all","All unknown","Invalid/reordered/stale/missing metadata","Truth-ID rename","Identical prefix different future","Two host chunk patterns"],
        "deferred_inputs":["A05/Q19 physical focused streams","U04 missing historic AEC/AGC/RT60","U05 real motion/IMU","D02/D04 named assistance unless separately explicit gallery/intervention setup"],
        "profiles":trials}

def make_ledger(pack,report):
    bindings=read_json(pack/"reference/BASELINE_BINDINGS.json")
    models=[]
    for a in bindings["baseline"]["scientific_config"]["assets"]:
        p=Path(a["path"])
        models.append({**a,"disk_bytes_observed":p.stat().st_size,"hash_provenance":"Expected hash from baseline binding; active execution receipts validate model integrity, no redundant model rehash in design builder",
            "resident_instance_target":0 if a["component_id"].endswith(("tokens","bpe")) else 1,
            "resident_memory_bytes":None,"resident_memory_reason":"Disk size is not resident/private footprint; requires session/process-tree measurements."})
    asset_bytes=sum(x["disk_bytes_observed"] for x in models)
    sr=16000
    return {"schema_version":1,"target":{"board":"CM5","ram_GB":2,"emmc_GB":32,"wireless":False,"execution":"CPU/ARM64","qualification":"NOT_TESTED_ON_TARGET"},
        "screen":{"app_private_GiB_target":1.3,"explicit_review_above_GiB":1.5,
            "interpretation":"Provisional app headroom screen. Actual OS/UI/drivers/MemAvailable and sustained queue stability determine fit; >1.5 GiB is review, not automatic failure.",
            "target_RTF_proposal":0.8,"actual_target_RTF":None,"desktop_to_pi_scalar":None},
        "models":models,"model_and_token_disk_bytes":asset_bytes,"model_and_token_disk_MiB":asset_bytes/1024**2,
        "model_state":{"selected_model_instances":"One resident ASR recognizer (encoder+decoder+joiner), one Pyannote, one shared ReDim, one final-only punctuation; never one recognizer per person.",
            "baseline_behavior":"SpeakerModels owns both ONNX sessions under one lock; ASR/punctuation share SherpaStream. Baseline CLI creates new process each file.",
            "inference_workspaces_bytes":None,"python_native_heap_bytes":None,"runtime_libraries_bytes":None,
            "required_measurement":"Process-tree RSS, private resident USS, private committed bytes, shared/PSS when available, native allocations and OS available RAM sampled independently; do not sum duplicate RSS as unique footprint.",
            "Windows_semantics":"psutil7.2.2 memory_info.private is PrivateUsage committed memory, not USS/private resident footprint. memory_full_info.uss is recorded separately. Do not compare private commit directly to the provisional resident-footprint screen."},
        "worker_pools":{"historical":"ASR2, speaker2 per ORT session, punctuation1; ORT sequential/inter-op1",
            "candidate":"Resident shared models, bounded scheduler; test pool1/2 under paced input. ORT intra count includes caller, so sum of settings is not actual OS thread count.",
            "no_GPU_dependency":True,"actual_thread_count":None},
        "dynamic_buffers":[
            {"name":"capture raw reserve","status":"historical configured max120s","formula":"120*source_rate*1channel*4","bytes_at_16k":120*sr*4,"bytes_at_48k":120*48000*4,"caveat":"Numpy/queue objects add overhead; device source rate matters"},
            {"name":"segmentation rolling waveform","status":"fixed graph requirement","formula":"10*16000*4","payload_bytes":10*sr*4,"caveat":"Padding/concatenate can transiently duplicate arrays"},
            {"name":"3s evidence waveform","status":"maximum proposed candidate, not validated as optimal","formula":"3*16000*4","payload_bytes":3*sr*4},
            {"name":"1s preroll","status":"proposed optional","formula":"16000*4","payload_bytes":sr*4},
            {"name":"dual mono tap 10s rings","status":"research split tap proposal","formula":"2*10*16000*4","payload_bytes":2*10*sr*4},
            {"name":"tracks/prototypes","status":"proposed bound","formula":"16tracks*3prototypes*192dims*4bytes","vector_payload_bytes":16*3*192*4,"caveat":"Python metadata, revisions, gallery and conflict matrix additional"},
            {"name":"gallery","status":"explicit enrollment mode only; main S6A anonymous","formula":"16names*3prototypes*192*4","vector_payload_bytes":16*3*192*4},
            {"name":"revision queue","status":"proposed bound","max_horizon_sec":2,"max_events":256,"max_edits_per_utterance":2,"bytes":None},
            {"name":"baseline SimpleQueue/events and clusters","status":"UNBOUNDED_GROWTH_PATH","bytes":None,"required_change":"Bound in opt-in production candidate without hidden transcript/audio drops; test long-session pressure."}],
        "storage":{"emmc_nominal_bytes":32000000000,"OS_UI_runtime_bytes":None,"models_bytes":asset_bytes,
            "audio_PCM16_mono_bytes_per_sec":sr*2,"audio_PCM16_mono_bytes_per_hour":sr*2*3600,
            "float_mono_bytes_per_hour":sr*4*3600,"four_channel_float_bytes_per_hour":sr*4*4*3600,
            "six_channel_48k_PCM24_bytes_per_hour":48000*6*3*3600,
            "proposed_journal_cap_bytes":GiB,"mono_audio_only_hours_to_1GiB":GiB/(sr*2*3600),
            "write_rate_audio_only_bytes_per_sec":sr*2,"log_write_rate_bytes_per_sec":None,
            "eMMC_physical_write_amplification":None,"endurance_measured":False,
            "retention":"Bulk scene audio/features remain on desktop/G:. Future production journal <=1GiB with explicit export/rotation and visible disk-low policy; not deletion of acquisition evidence.",
            "headroom":"32GB is nominal total, not free space. Measure installed OS/runtime/display and update reserve; do not subtract guessed OS bytes.",
            "baseline_warning":"Append-only journal grows ~115.2MB/hour; event log and transcript add writes. No current production retention proof."},
        "ARM64_paths":{"local_exporter":str(APP/"assets.py"),"local_export_function":"export_pi_bundle",
            "local_guidance":str(APP.parents[1]/"deployment/edge_speech_pi/README.md"),
            "requirements_text_from_export":"numpy2.2.6 scipy1.15.3 soundfile0.13.1 sounddevice0.5.5 psutil7.2.2 onnxruntime1.29.0 sherpa-onnx1.13.4; verify exact current exporter and target wheel resolver",
            "lean_runtime":"No torch/torchaudio/pyannote.audio required for inference using bound ONNX graphs.",
            "target_test_gates":["64-bit Raspberry Pi OS and actual module/OS/kernel recorded","Wheels/import and exact graph hashes","Same-input numerical parity including frontend","Native USB audio no-drop and output route","Process tree/private/shared memory, OS available RAM","Sustained paced backlog and thermal/power","Disk low/rotation/restart recovery","GUI/display increment after headless baseline"],
            "status":"PORT_REQUIRES_WORK; no board/network/flashing actions in S6A"},
        "measurement_receipts":[],"evidence_boundary":"Analytic payload bounds and local disk metadata are measured/calculated here. Resident footprint and queue measurements are filled from S6A runtime receipts separately; all target performance remains untested."}

def workbook_receipt(path):
    if not path.exists(): return {"status":"NOT_PRESENT","path":str(path),"scope_authority":"S6A V2 prompt"}
    root=ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    ns={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paras=["".join(t.text or "" for t in p.findall(".//w:t",ns)) for p in root.findall(".//w:p",ns)]
    return {"status":"READ_CONTEXT_ONLY","binding":bind(path),"paragraphs":len(paras),
        "version":14,"relevant_context":[{"paragraph_index_zero_based":i,"text":t} for i,t in enumerate(paras)
            if 1440<=i<=1585 or (i<160 and any(k in t for k in ["Revision 14","CM5","S6A"]))],
        "preserved":"Word source is unchanged; no replacement Word file generated"}

def write_plan_md(out,plan):
    rows=["# Prospective S6B joint trial plan","","This is a costed design, not an executed S6B campaign. S6A executed evidence is attached separately and must determine the exact R1 recipe and adverse-case priorities before B begins.",
        "",f"{plan['profile_count']} end-to-end profiles, up to {plan['maximum_policy_runs_if_all_profiles_retained']:,} scene/output/policy results on the existing 240-scene bank. Both taps remain eligible. Eight recipe families are a grouping aid, not eight universal cache keys.",
        "","| Profile | Recipe | Mechanism | Cues | Parent |","|---|---|---|---|---|"]
    rows += [f"| {p['profile_id']} | {p['recipe_id']} | {p['mechanism']} | {p['metadata']} | {p['comparison_parent']} |" for p in plan["profiles"]]
    rows += ["","The exact original B0 is preserved separately from the new voice/time tracker. A matched X0 also removes metadata-dependent scheduling, endpoint advice, evidence admission and prototype changes. For each finalist add remove-angle, remove-energy, original-duration, original-endpoint and no-revision ablations where those are separable; count these additional comparisons explicitly.",
        "","| Recipe family | Concrete proposal and recomputation |","|---|---|"]
    rows += [f"| {r['id']} | {r['delta']} {r['new_neural']} |" for r in RECIPES]
    rows += ["","Cost and admission",
        "",
        "Historical S5 fresh jobs averaged 15.013 s/job. At that historical rate one 480-job recipe would take about 2.00 serial hours; eight original-cost equivalents about 16.01 hours before validation and packaging. This is a planning reference only: resident reuse may reduce overhead, modified search and separate cue-triggered histories may increase work. The actual S6A/B measured per-recipe throughput replaces these estimates before admission. No desktop-to-CM5 speed factor is used.",
        "",
        "B should freeze all concrete profile JSON and exact dependency keys before outcomes, measure the first balanced pilot for every expensive recipe, and stop admitting work before the 24-hour budget minus at least 45 minutes for packaging. Keep atomic complete/failed/pending lists. Partial work stays explicit and resumes by receipt rather than overwriting or silently narrowing the bank.",
        "",
        "Use paired O0/O1 counts, raw WER/CER, S/D/I, complete-overlap word recovery, cpWER, false merges, unknown/return/short-turn coverage, actual first/revised label timing, unique admitted evidence, full queue/load and process-tree memory on a Pareto table. Unknown ambient words are unscored, not hallucinations. This reused bank is exploratory; conditional resampling is not independent real-world confirmation.",
        "",
        "The requested interactions are bound in S6B_JOINT_PLAN.json. Both taps across segmentation/evidence recipes test tap interactions; a genuinely split ASR/embedding input adds an explicit aligned route tuple and cannot be claimed from whole-tap comparisons. Missing historical AEC/AGC/RT60, focused streams and real motion remain deferred. No current profile is a target-device recommendation."]
    rows += ["", "S6A constraints carried into this plan", ""]
    for finding in plan.get("s6a_design_consequences", []):
        rows.append("- " + finding["finding"] + ". " + finding["action"])
    if plan.get("actual_A_profiles_for_recipe_binding"):
        rows += ["", "The exact ten named A profile files are hash-bound in S6B_JOINT_PLAN.json. Recipe R1 binds P1X0/P1X1 as a measured reference to challenge, not an optimum. SEG_X1 positive-energy support remains a separate matched intervention."]
    if plan.get("full_bank_baseline"):
        pref=plan["full_bank_baseline"]["conditional_output_preference"]
        rows += ["", "Completed original-settings baseline: " + str(pref["baseline_text_favored_output"]) + " has lower pooled primary WER on this bank; O1 minus O0 is " + str(pref["primary_O1_minus_O0_wer_pp"]) + " percentage points. Both taps remain in B because tuning can change the tradeoff."]
    if plan.get("completed_reference_comparison"):
        ref=plan["completed_reference_comparison"]
        rows += ["", "Completed reference comparison informing B priorities", "",
                 "R5 changes cpWER versus its matched R1 parent by " + "; ".join(f"{r['stream']}: {r['R5_minus_R1_cpwer_pp']:+.3f} percentage points" for r in ref["matched_R5_R1"]) + ". ASR words and accepted embedding spans remain fixed. This modest descriptive gain does not establish short-reply benefit.",
                 "", "| Tap | R1 subsecond known modal / all | R5 subsecond known modal / all |", "|---|---|---|"]
        rows += [f"| {r['stream']} | {r['R1_known_modal']} / {r['source_turns']} | {r['R5_known_modal']} / {r['source_turns']} |" for r in ref["matched_R5_R1"]]
        rows += ["", "Known modal labels measure coverage, not correct identity. Keep every short or unassigned turn in the denominator. Compare cue candidates to their matched cue-off parent with shared availability; B0 remains the original end-to-end benchmark, but B0-to-replay differences combine tracker and availability policies. Prioritize coverage-aware prototype/commitment and fallback checks before treating aggregate cpWER as improvement."]
    if plan.get("panel_design_support"):
        panel=plan["panel_design_support"]
        rows += ["", f"The actual A panel contains {panel['scenes']} scenes: " + "; ".join(f"{name}: {count}" for name,count in panel['populations'].items()) + ".",
                 f"It has only {panel['subsecond_source_turns_per_tap']} subsecond source utterances per tap, compared with 40 complete-reference subsecond utterances per tap in the full-bank reference study. Presence of the short-turn condition is not a precise estimate of short-reply performance. Confirm duration/commitment candidates on the complete source-based short-turn population before promoting them."]
    if plan.get("final_probe_outcome_review"):
        final=plan["final_probe_outcome_review"]
        rows += ["", "Completed A component outcomes carried into B", "",
                 "All 720 final score files were independently rehashed and their pooled counts/factorial arithmetic checked. P0X0/B0 raw normalized words match on all 72 panel outputs. The following are observed screening tradeoffs, not production selections.",
                 "", "| Profile | Tap | Primary WER % | Complete-reference cpWER % | Embedding calls | Advisory endpoints |", "|---|---|---:|---:|---:|---:|"]
        for r in final["profile_rows"]:
            rows.append(f"| {r['profile_id']} | {r['stream']} | {r['primary_wer']*100:.3f} | {r['cpwer']*100:.3f} | {r['embedding_calls']} | {r['advisory_endpoint_count']} |")
        rows += ["", "Every row has the same 36 scenes, including 23 primary scenes/671 words and 29 complete-reference nonempty scenes/836 words. The six-overlap-scene denominator is 165 words; five incomplete scenes/146 target words stay separate; two empty controls have undefined WER.",
                 "", "P1X0 reduces cpWER versus P0X0 by 18.421 percentage points on O0 and 10.646 on O1 with unchanged raw words, while mixed-identity support rises and subsecond known-modal coverage falls to 1/2 O0 and 0/2 O1. EMBED_LONG retains 2/2 known modal labels despite no wholly contained window for either short utterance: waveform containment is a separate diagnostic, not label correctness.",
                 "", "The advisory cue route increases primary errors by 2/671 O0 and 4/671 O1 under both P0 and P1. The lexical factorial interaction is zero here; cpWER interaction changes sign between taps. Keep tracking-only and ASR-advice branches separate in B, preserve continuous ASR, and test circuit-breaker/false-jump safeguards.",
                 "", "SEG_X1 assistance is active and admits additional embeddings but leaves pooled cpWER and words unchanged versus SEG_X0. Sparse cadence/RMS reduces embedding calls while worsening cpWER. Preserve these as cost/coverage hypotheses with matched parents, rather than declaring improvement from activation or fewer calls.",
                 "", "INDEPENDENT_FINAL_REVIEW.json binds all final sources, exact arithmetic checks, detailed short-turn rows and the limits of this review. It does not repeat neural inference or claim population generalization."]
    write_text(out/"S6B_JOINT_TRIAL_PLAN.md","\n".join(rows)+"\n")

def review_runtime_eof(out):
    """Independently execute real ASR loop with finite journal/fake decoder.

    This reproduces the tail-clock bug without any neural or hardware work.
    """
    import time
    import numpy as np
    sys.path.insert(0,str(APP.parents[1]))
    from app.edge_speech_pipeline.runtime import PipelineEngine
    from app.edge_speech_pipeline.research_profiles import ResearchProfile
    from app.edge_speech_pipeline.config import PipelineConfig
    observed=np.linspace(-.1,.1,1707,dtype=np.float32)
    class Journal:
        finished=True
        committed_samples=len(observed)
        duration_sec=len(observed)/16000
        def read(self,cursor,maximum_samples):
            return observed[cursor:cursor+maximum_samples]
    class Decoder:
        utterance_index=0
        decode_ms=7.
        def __init__(self): self.parts=[]
        def accept(self,samples):
            self.parts.append(samples.copy())
            return "",False
        def finish(self): return "retained final words"
        def punctuate(self,text):
            return {"text":text+".","compute_ms":3.,"status":"learned","terminal_fallback":None}
    e=object.__new__(PipelineEngine)
    e.config=PipelineConfig()
    e._research_profile=ResearchProfile()
    e._journal=Journal()
    e._research_asr_available_sec=0.
    e._started_monotonic=time.perf_counter()
    e._telemetry={}
    events=[];finals=[];failures=[]
    e._emit=lambda kind,source,payload:events.append({"kind":kind,"source":source,"payload":payload})
    e._fail=lambda *args:failures.append(args)
    def punctuation(result):
        e._research_asr_available_sec+=result["compute_ms"]/1000.
    e._record_punctuation=punctuation
    e._transcript_event=lambda text,source,**kwargs:finals.append({"text":text,"source":source,"available":e._research_asr_available_sec,**kwargs})
    decoder=Decoder()
    PipelineEngine._asr_loop(e,decoder)
    assert not failures,failures
    assert np.array_equal(np.concatenate(decoder.parts),observed),"lost/duplicated tail samples"
    tails=[r for r in events if r["kind"]=="research_asr_tail_dispatch"]
    drains=[r for r in events if r["kind"]=="research_asr_drain"]
    assert len(tails)==len(drains)==1
    assert tails[0]["payload"]["samples"]==107
    assert tails[0]["payload"]["modeled_available_at_sec"]>=Journal.duration_sec+.007
    assert drains[0]["payload"]["modeled_available_at_sec"]>=tails[0]["payload"]["modeled_available_at_sec"]
    assert drains[0]["payload"]["padding_is_observed_audio"] is False
    assert len(finals)==1 and finals[0]["source"]==Journal.duration_sec
    assert finals[0]["available"]>=drains[0]["payload"]["modeled_available_at_sec"]+.003
    result={"status":"PASS","test":"actual runtime ASR loop full block plus 107-sample tail and EOF drain",
        "no_neural_inference":True,"python":sys.executable,"runtime_source":bind(APP/"runtime.py"),
        "observed_samples":len(observed),"accepted_block_samples":[len(p) for p in decoder.parts],
        "source_duration_sec":Journal.duration_sec,"events":events,"finals":finals,
        "scope":"Behavioral availability/sample accounting test with deterministic fake decoder, not ASR accuracy or live latency."}
    atomic(out/"INDEPENDENT_EOF_REVIEW.json",result)
    return result

def independent_tracking_duration_review(out):
    """Synthetic code-path disproof; no neural inference or accuracy claim."""
    import numpy as np
    sys.path.insert(0, str(APP.parents[1]))
    from app.edge_speech_pipeline.research_tracking import ResearchTracker, TrackingConfig, SpatialObservation
    a = np.zeros(192, np.float32); a[0] = 1
    b = np.zeros(192, np.float32); b[1] = 1
    cases = {}
    for window in (.5, 1.):
        tracker = ResearchTracker(TrackingConfig(mode="sustained_angle", commit_evidence_sec=1.))
        schedule = [(0., .5, a, 10.), (.25, .75, a, 10.), (.5, 1., a, 10.), (.75, 1.25, b, 100.), (1., 1.5, a, 10.)] if window == .5 else [(0., 1., a, 10.), (.5, 1.5, b, 100.), (1., 2., a, 10.)]
        decisions = []
        for sequence, (start, end, vector, angle) in enumerate(schedule):
            observation = SpatialObservation(angle, end, 1., 1., True, sequence, start, end)
            decisions.append(tracker.update(vector, start, end, end+.01, observation))
        snapshot = tracker.snapshot()
        cases[str(window)] = {"embedding_window_sec": window, "commit_evidence_sec": 1.,
            "decision_states": [x["state"] for x in decisions],
            "splits": snapshot["splits"], "merges": snapshot["merges"], "revisions": snapshot["revisions"],
            "lineage": [x for decision in decisions for x in decision["lineage"]],
            "first_decisions_rewritten": any(x["first_decision_rewritten"] for x in decisions)}
    assert cases["0.5"]["merges"] == 1 and cases["0.5"]["revisions"] == 1
    assert cases["1.0"]["splits"] == 1 and cases["1.0"]["merges"] == cases["1.0"]["revisions"] == 0
    assert not any(c["first_decisions_rewritten"] for c in cases.values())
    result = {"status": "PASS_CONDITIONAL_INACTIVITY_CONFIRMED", "tracker_code": bind(APP/"research_tracking.py"),
        "cases": cases, "scope": "Orthogonal synthetic 192-vectors prove implemented code paths only. A 1s window immediately commits at a 1s threshold and blocks provisional reconciliation. No bank accuracy, real speaker correctness or transcript/GUI revision claim.",
        "neural_inference_calls": 0}
    atomic(out/"INDEPENDENT_TRACKING_DURATION_REVIEW.json", result)
    return result


def concrete_trial_settings(plan, profiles):
    """Give every planned row numeric settings and an explicit implementation gate."""
    if not profiles:
        return
    base = profiles["P0X0"]["settings"]
    future = {
        "B06": {"extension": "static_location_prior_control", "location_weight": .12, "voice_veto_cosine": .20, "location_expiry_sec": None},
        "B07": {"extension": "angular_innovation_cusum", "reference_angle_change_deg": 15., "threshold_deg_updates": 50., "refractory_sec": 1., "minimum_reliability": .5},
        "B08": {"extension": "folded_uncertain_bearing_likelihood", "spatial_weight": .12, "native_sigma_deg": 20., "score_clip": 1., "manual_label_interval_used_as_predictor": False},
        "B09": {"extension": "dual_timescale_dormant_reentry", "voice_update_rate": .05, "position_update_rate": .20, "position_decay_sec": 12., "dormant_after_sec": 3., "voice_memory_sec": 120.},
        "B10": {"extension": "dual_timescale_dormant_reentry", "voice_update_rate": .05, "position_update_rate": .20, "position_decay_sec": 12., "dormant_after_sec": 3., "voice_memory_sec": 120.},
        "B11": {"extension": "robust_multi_prototype", "max_prototypes_per_track": 3, "prototype_update_cosine": .55, "confirmation_unique_sec": 1.5, "conflict_quarantine_sec": 2.},
        "B12": {"extension": "prototype_transaction_rollback", "pending_updates_per_track": 1, "confirmation_unique_sec": 1., "conflict_cosine": .20, "clean_shadow_prototypes_per_track": 1},
        "B13": {"extension": "tempered_voice_filter", "max_hypotheses": 16, "voice_temperature": 2., "spatial_weight": 0., "probability_floor": .001, "commit_posterior": .80, "unknown_posterior_below": .60},
        "B14": {"extension": "tempered_voice_filter", "max_hypotheses": 16, "voice_temperature": 2., "spatial_weight": .12, "probability_floor": .001, "commit_posterior": .80, "unknown_posterior_below": .60},
        "B15": {"extension": "bounded_fixed_lag_label_revision", "horizon_sec": 2., "max_records": 64, "max_edits_per_utterance": 2, "minimum_disjoint_confirmation_sec": 1., "original_decisions_immutable": True},
        "B18": {"extension": "exclusive_speech_contiguous_window", "speech_posterior_min": .60, "overlap_posterior_max": .10, "local_slot_dominance_min": .85, "short_reply_provisional": True},
        "B19": {"extension": "exclusive_speech_contiguous_window", "speech_posterior_min": .60, "overlap_posterior_max": .10, "local_slot_dominance_min": .85, "short_reply_provisional": True},
        "B20": {"extension": "exclusive_speech_contiguous_window", "speech_posterior_min": .60, "overlap_posterior_max": .10, "local_slot_dominance_min": .85, "short_reply_provisional": True},
        "B21": {"extension": "exclusive_speech_contiguous_window", "speech_posterior_min": .60, "overlap_posterior_max": .10, "local_slot_dominance_min": .85, "short_reply_provisional": True},
        "B24": {"extension": "unique_evidence_debt_scheduler", "minimum_audio_only_probe_interval_sec": 1., "max_evidence_debt_sec": 1.5, "speaker_deadline_ms": 150., "tokens_sec_per_audio_sec": .15, "unknown_and_conflict_priority": True},
        "B25": {"extension": "unique_evidence_debt_scheduler", "minimum_audio_only_probe_interval_sec": 1., "max_evidence_debt_sec": 1.5, "speaker_deadline_ms": 150., "tokens_sec_per_audio_sec": .15, "unknown_and_conflict_priority": True}}
    for trial in plan["profiles"]:
        key = trial["profile_id"]
        if key == "B00":
            trial["exact_execution"] = {"route": "Existing unchanged no-profile original B0 runner and bound baseline journals", "new_native_profile": None,
                "ready_now": True, "scope": "480 exact original results already available after baseline completion; never substitute the new voice/time tracker."}
            continue
        source_id = "P1X1" if key == "B17" else "P1X0" if key == "B16" else "P0X0"
        profile = json.loads(json.dumps(profiles[source_id]["settings"]))
        profile["profile_id"] = "S6B_" + key
        on = trial["metadata"] == "on"
        if key not in {"B16", "B17"}:
            profile["tracker"]["mode"] = "reliability_adaptive" if on else "voice_time"
            profile["xvf"]["mode"] = "tracking_only" if on else "none"
        modes = {"B02": "angle_diagnostic", "B03": "sustained_angle", "B04": "decaying_memory", "B05": "reliability_adaptive"}
        if key in modes:
            profile["tracker"]["mode"] = modes[key]
        if key in {"B18", "B19", "B20", "B21"}:
            profile["segmentation"]["post_policy"] = "posterior_hysteresis"
            profile["segmentation"]["hop_sec"] = .5
        if key in {"B20", "B21", "B24", "B25"}:
            profile["embedding"].update(window_sec=1., hop_sec=.5)
            profile["segmentation"]["hop_sec"] = .5
            profile["tracker"]["commit_evidence_sec"] = 1.5
        if key in {"B22", "B23"}:
            profile["asr"].update(endpoint_rule1_silence_sec=1.6, endpoint_rule2_silence_sec=.8, journal_read_ms=50)
            profile["xvf"]["mode"] = "advisory" if on else "none"
        if key in {"B26", "B27"}:
            profile["embedding"]["minimum_rms"] = .001
        if key in {"B28", "B29"}:
            profile["asr"].update(decoding_method="modified_beam_search", max_active_paths=2, journal_read_ms=50)
            profile["runtime"].update(asr_threads=1, speaker_threads=1, punctuation_threads=1)
            profile["xvf"]["mode"] = "advisory" if on else "none"
        extension = future.get(key)
        preparation = {"input": "historically gained native PCM16 journal / equivalent prepared file", "O0_raw_gain_once": 1.4125375446227544,
                       "O1_raw_gain_once": 1., "native_profile_gain": 1., "already_gained": True}
        if key in {"B26", "B27"}:
            preparation.update(input="new host adapter from existing raw processed capture; preserve original", O0_raw_gain_once=1.,
                               reason="Explicit gain/RMS interaction control; not a reinterpretation of baseline +3dB")
        trial["exact_execution"] = {"native_base_profile": profile, "native_fields_supported_now": True,
            "additional_policy_extension": extension, "extension_implemented_now": False if extension else None,
            "ready_now": extension is None, "audio_preparation": preparation,
            "command_contract": 'Existing app CLI: python -m app.edge_speech_pipeline.cli file <prepared_mono_16k.wav> --accelerated --research-profile <validated_profile.json>; add --research-telemetry <sanitized.jsonl> only for enabled cues.',
            "preconditions": ["Validate native JSON with ResearchProfile.from_dict before launch", "Bind each exact input/gain/feature/cache lineage",
                             "When additional_policy_extension is non-null, implement and effect-test it first; the native base alone does NOT execute this candidate",
                             "Use measured compute/source delivery and explicit original/revision exposure; any accelerated cross-worker race stays a measured desktop limitation"]}
    plan["concrete_parameter_scope"] = "Numerical starting proposals, not tuned estimates. Every candidate has a native JSON base and any separately named unsupported extension; unsupported candidates cannot run by silently dropping extension fields."


def attach_measured_evidence(report, registry, plan, ledger):
    """Attach available bound receipts without turning proposals into executed work."""
    evidence = {};captures=[]
    for name in ("COMPONENT_MAP.md", "PARAMETER_BINDINGS.json", "REDIM_FRONTEND_BINDING.json",
                 "COMPONENT_API_TESTS_V2.json", "profiles/PROFILE_INDEX.json", "PROBE_PANEL.json",
                 "COMPONENT_PLUMBING_RECEIPT.json", "CAUSALITY_DELIVERY_RECEIPT.json", "RUNTIME_RESOURCE_NOTES.md",
                 "NATIVE_CACHE_MUTATION_RECEIPT.json", "PROBE_RESUME_GUARD_TESTS.json", "PROBE_RESUME_GUARD_LATEST.json",
                 "CUE_FOUNDATION.json", "CUE_FEATURE_B0_PARITY.json", "CUE_REAL_FEATURE_CAUSALITY.json",
                 "REFERENCE_PROFILE_RECEIPT.json", "CUE_REFERENCE_COVERAGE_PARITY.json", "CUE_OBSERVED_REVISIONS.json",
                 "COMPONENT_PROBE_SUMMARY.json", "PROBE_ANALYSIS_RECEIPT.json",
                 "probe_results/PROBE_REPORT_RECEIPT.json",
                 "RUNTIME_EXPERIMENT_V1_LIBRARY_DEFAULTS.json", "RUNTIME_EXPERIMENT.json",
                 "baseline_results/BASELINE_RESULTS.json", "baseline_results/AGGREGATION_RECEIPT.json"):
        path = report / name
        if path.exists():
            original_path=path
            if name in {"COMPONENT_MAP.md","PARAMETER_BINDINGS.json","COMPONENT_PLUMBING_RECEIPT.json"}:
                path=report/"design/component_inputs"/name
                path.parent.mkdir(parents=True,exist_ok=True)
                if not path.exists():path.write_bytes(original_path.read_bytes())
                captures.append({"original_source_path":str(original_path),"captured_sha256":bind(path)["sha256"],"immutable_copy":bind(path)})
            item = {"binding": bind(path), "interpretation": "Source receipt's status and population are authoritative."}
            if original_path!=path:
                item["interpretation"]="Immutable component input as read for design. Live component maps remain human-facing authority; later evidence-link updates do not rewrite this captured version. Historical nested bindings retain their original context."
            if path.suffix == ".json":
                value = read_json(path)
                item["status"] = value.get("status") if isinstance(value, dict) else "PROFILE_INDEX"
            evidence[name] = item
    if captures:
        capture_path=report/"design/component_inputs/CAPTURE_INDEX.json"
        atomic(capture_path,{"status":"PRESERVED_DESIGN_INPUT_VERSIONS","rows":captures,"scope":"Exact byte copies break the design-to-final-component-audit metadata cycle. They are historical input versions, not replacement current component maps."})
        evidence["component_inputs/CAPTURE_INDEX.json"]={"binding":bind(capture_path),"interpretation":"Original-source/hash to immutable design-input mapping."}
    registry["actual_component_evidence"] = evidence
    registry["model_identity_correction"] = "Installed ReDim is PalabraAI ReDimNet2-B2. No checkpoint/model was changed. Older ReDimNet documentation alone is not the actual frontend specification."
    plan["s6a_evidence_bindings"] = evidence
    plan["parameter_binding_authority"] = str(report / "PARAMETER_BINDINGS.json")
    profiles = {}
    for key in ("P0X0", "P0X1", "P1X0", "P1X1", "SEG_X0", "SEG_X1", "EMBED_LONG", "EMBED_CADENCE_QUALITY", "ENDPOINT_X0", "ENDPOINT_X1"):
        path = report / "profiles" / (key + ".json")
        if path.exists():
            profiles[key] = {"binding": bind(path), "settings": read_json(path)}
    plan["actual_A_profiles_for_recipe_binding"] = profiles
    concrete_trial_settings(plan,profiles)
    for recipe in plan["expensive_recipe_families"]:
        if recipe["id"] == "R1":
            recipe["exact_A_settings"] = {k: profiles[k] for k in ("P1X0", "P1X1") if k in profiles}
            recipe["interpretation"] = "Measured A bundle as a reference to challenge in B, not a selected optimum. Preserve exact off/on mechanisms; soft-energy SEG_X1 is a separate intervention."
    findings = [
        {"finding": "Current powerset log-score semantics and valid graph lengths",
         "action": "Use valid posterior policy and contiguous ReDim windows only. Graph shortening, frame masks and neural pooling changes are unsupported.",
         "ideas": ["Q01", "Q04", "Q05"]},
        {"finding": "RMS gate reads the dispatch block, not the complete embedding waveform",
         "action": "Treat cadence x RMS as a coupled gate. A full-window RMS gate is a new policy, not an existing binding.",
         "ideas": ["Q04", "Q05", "Q06", "N02", "N05"]},
        {"finding": "P1 window1.0s equals commit-evidence1.0s; new branches immediately commit",
         "action": "Current reconciliation requires a provisional branch, so P1 cannot merge/revise through that path. Preserve actual zero counts; B must vary commit evidence above initial window to test delayed reconciliation.",
         "ideas": ["Q04", "Q07", "N03", "N07"]},
        {"finding": "Sparse observations can show sampled persistence but do not prove continuous DSP stability",
         "action": "Freshness checks retain both observed source age and delivery age; direction-persistence continuity is a separate cadence constraint.",
         "ideas": ["N01", "N04"]},
        {"finding": "Stable direction can remain wrong on a shared physical trace",
         "action": "Prioritize wrong-stable-cue quarantine, audio-only fallback and same-bearing speaker replacement controls. Never multiply correlated beam confidence as independent likelihoods.",
         "ideas": ["N01", "N03", "N08"]},
        {"finding": "Windows private commit is not resident USS",
         "action": "Use measured USS/RSS/shared distinctions and actual controlled library/thread settings. No desktop-to-CM5 conversion.",
         "ideas": ["N05", "N07"]}]
    reference=report/"REFERENCE_PROFILE_RECEIPT.json"
    if reference.exists() and read_json(reference).get("status")=="COMPLETE":
        value=read_json(reference)
        table_bindings={Path(b["path"]).name:b for b in value["tables"]}
        reference_tables={}
        for name in ("REFERENCE_PROFILE_RESULTS.csv","REFERENCE_SHORT_TURN_RESULTS.csv"):
            binding=table_bindings[name]
            assert bind(binding["path"])["sha256"]==binding["sha256"], name
            with Path(binding["path"]).open(encoding="utf-8-sig",newline="") as handle:
                reference_tables[name]=list(csv.DictReader(handle))
        matched=[]
        for stream in ("O0","O1"):
            pair={r["profile"]:r for r in reference_tables["REFERENCE_PROFILE_RESULTS.csv"] if r["stream"]==stream and r["population"]=="ALL_COMPLETE_NONEMPTY" and r["profile"] in ("R1_voice_time","R5_reliability_adaptive")}
            r1,r5=pair["R1_voice_time"],pair["R5_reliability_adaptive"]
            assert int(r1["cp_reference_words"])==int(r5["cp_reference_words"]) and int(r1["scenes"])==int(r5["scenes"])
            short={}
            for profile in pair:
                chosen=[r for r in reference_tables["REFERENCE_SHORT_TURN_RESULTS.csv"] if r["stream"]==stream and r["profile"]==profile and r["population"] in ("PRIMARY_NONOVERLAP","COMPLETE_OVERLAP") and r["duration_bin"]=="<1s"]
                short[profile]={k:sum(int(r[k]) for r in chosen) for k in ("source_turns","turns_with_known_modal_label")}
            assert short["R1_voice_time"]["source_turns"]==short["R5_reliability_adaptive"]["source_turns"]
            matched.append({"stream":stream,"complete_reference_scenes":int(r1["scenes"]),"cp_reference_words":int(r1["cp_reference_words"]),
                "R1_cp_errors":int(r1["cp_errors"]),"R5_cp_errors":int(r5["cp_errors"]),
                "R5_minus_R1_cpwer_pp":100*(int(r5["cp_errors"])-int(r1["cp_errors"]))/int(r1["cp_reference_words"]),
                "source_turns":short["R1_voice_time"]["source_turns"],"R1_known_modal":short["R1_voice_time"]["turns_with_known_modal_label"],"R5_known_modal":short["R5_reliability_adaptive"]["turns_with_known_modal_label"]})
        plan["completed_reference_comparison"]={"receipt":bind(reference),"table_bindings":[table_bindings[n] for n in reference_tables],"matched_R5_R1":matched,
            "scope":"Complete-reference matched replay; unchanged native words, actual accepted vectors and shared modeled availability. Known modal is coverage, not identity correctness. B0 uses a different availability convention."}
        panel_path=report/"PROBE_PANEL.json"
        if panel_path.exists():
            case_ids=set(read_json(panel_path)["case_ids"])
            selected=[r for r in reference_tables["REFERENCE_SHORT_TURN_RESULTS.csv"] if r["profile"]=="B0" and r["stream"]=="O0" and r["case_id"] in case_ids]
            case_population={r["case_id"]:r["population"] for r in selected}
            assert set(case_population)==case_ids
            assert all(case_population[r["case_id"]]==r["population"] for r in selected)
            counts={p:sum(value==p for value in case_population.values()) for p in sorted(set(case_population.values()))}
            plan["panel_design_support"]={"panel":bind(panel_path),"source_table":table_bindings["REFERENCE_SHORT_TURN_RESULTS.csv"],"scenes":len(case_ids),"populations":counts,
                "subsecond_source_turns_per_tap":sum(int(r["source_turns"]) for r in selected if r["duration_bin"]=="<1s"),
                "scope":"Input/source-coverage count only. Repeating the same sources across ten profiles/two taps does not enlarge the independent short-turn population."}
        findings.append({"finding":"Modest R5-vs-R1 aggregate cpWER gain coexists with O1 subsecond known-label loss; angle diagnostic abstention is high",
            "action":"Preserve cpWER, unknown/mixed support, returns and short-reply denominators separately. Prioritize evidence escrow, duration/commitment, wrong-cue quarantine and fallback; do not select a tracker on cpWER or continuity alone.",
            "ideas":["P05","R05","Q04","Q07","N01","N03","N05","N07","N08"]})
    plan["s6a_design_consequences"] = findings
    registry["s6a_design_consequences"] = findings
    for item in registry["items"]:
        item["observed_constraints"] = [f for f in findings if item["id"] in f["ideas"]]
    baseline = report / "baseline_results/BASELINE_RESULTS.json"
    if baseline.exists():
        value = read_json(baseline)
        if value["status"] == "COMPLETE_480_BASELINE":
            plan["full_bank_baseline"] = {"binding": bind(baseline), "conditional_output_preference": value["conditional_output_preference"],
                "scored_outputs": value["scored_outputs"], "historical_split_is_holdout": False}
    summary = report / "COMPONENT_PROBE_SUMMARY.json"
    if summary.exists():
        value = read_json(summary)
        if value.get("status") == "COMPLETE":
            plan["completed_component_panel"] = {"binding": bind(summary), "requested": value.get("requested"), "complete": value.get("complete"),
                "profiles": value.get("profiles"), "scope": "Bounded exploratory panel; no global winner or target qualification follows automatically."}
    runtime = []
    for name in ("RUNTIME_EXPERIMENT_V1_LIBRARY_DEFAULTS.json", "RUNTIME_EXPERIMENT.json"):
        path = report / name
        if path.exists():
            value = read_json(path)
            if value.get("status") == "COMPLETE":
                runtime.append({"binding": bind(path), "status": value["status"],
                    "library_pool_scope": value.get("library_pool_scope", "See source receipt; do not assume controlled numeric pools."),
                    "numeric_environment": value.get("numeric_environment"), "source_scope": value.get("scope"),
                    "memory_semantics": value.get("memory_semantics"),
                    "rows": value.get("rows", []),
                    "scope": "Paced desktop file-input engineering only. Process-tree USS is private resident; RSS sum upper bound and RSS-minus-USS shared estimate are nonunique; private commit is virtual committed backing. None establishes CM5 fit or RTF."})
    ledger["measurement_receipts"] = runtime
    ledger["logged_phase_cost_scope"]={"meaning":"Instrumented model-phase times, not exhaustive full-pipeline CPU time or calibrated end-to-end latency.",
        "excluded_or_not_fully_separately_timed":["parts of wrapper preprocessing/postprocessing", "powerset_posteriors after the segmentation timer", "gating", "tracking", "endpoint advice/reset", "formatting and event I/O"],
        "interpretation":"Keep complete child/session wall time, paced queues, sample coverage and process resources separate. Model loading and punctuation use their explicit fields. Do not sum logged phases and call it total pipeline compute or target RTF."}
    controlled = [r for r in runtime if r["binding"]["path"].endswith("RUNTIME_EXPERIMENT.json") and r.get("numeric_environment") and all(v == "1" for v in r["numeric_environment"].values())]
    if controlled:
        measured = controlled[-1]
        ledger["primary_desktop_paced_evidence"] = {"binding": measured["binding"], "rows": measured["rows"],
            "numeric_environment": measured["numeric_environment"], "memory_semantics": measured["memory_semantics"],
            "version_comparison_limit": "V1 and V2 differ in application revision as well as numeric-pool settings. Cross-version resource changes are not isolated causal effects of pool limits."}
        ledger["worker_pools"]["actual_thread_count"] = [{"job_id": r["job_id"], "observed_process_tree_peak_threads": r.get("peak_observed_tree_threads")} for r in measured["rows"]]
        ledger["storage"]["measured_desktop_process_write_bytes_per_audio_sec"] = [{"job_id": r["job_id"], "value": r.get("io_write_bytes_per_audio_sec")} for r in measured["rows"]]
        ledger["storage"]["measured_write_scope"] = "Sampled desktop process writes including PCM journal, research event vectors and receipts; not pure log bytes, physical eMMC writes or endurance. Production logging can differ."
    ledger["measurement_evidence_bindings"] = evidence
    ledger["actual_research_tracker_state"] = {"max_tracks": 16, "prototype_payload_bytes": 16*192*4,
        "revision_records_max": 64, "revision_horizon_sec": 2,
        "scope": "Current bounded tracker payload only; Python object overhead not measured separately. Proposed multi-prototype and 256-event revision alternatives remain prospective."}
    ledger["evidence_boundary"] = "Model disk metadata, analytic payload bounds and attached desktop paced samples are distinct. Only controlled final runtime receipts should support thread/cadence comparisons. ARM64 target memory, load, thermal, write endurance and long-session behavior remain untested."
    return evidence


def attach_final_probe_review(report, out, registry, plan, ledger):
    """Independently pool bound native scores and carry adverse results into B."""
    analysis_path=report/"PROBE_ANALYSIS_RECEIPT.json"
    detail_path=report/"probe_results/PROBE_REPORT_RECEIPT.json"
    if not (analysis_path.exists() and detail_path.exists()): return
    analysis,detail=read_json(analysis_path),read_json(detail_path)
    if analysis.get("status")!="COMPLETE" or detail.get("status")!="COMPLETE": return
    assert analysis["complete"]==720 and detail["native_v2_outputs"]==720
    summary=read_json(report/"COMPONENT_PROBE_SUMMARY.json")
    assert summary["status"]=="COMPLETE" and summary["complete"]==720
    supplied={(r["profile_id"],r["stream"]):r for r in summary["profiles"]}
    assert len(supplied)==20
    tables={Path(b["path"]).name:b for b in detail["tables"]}
    for binding in detail["inputs"]+detail["tables"]:
        assert bind(binding["path"])["sha256"]==binding["sha256"],binding["path"]
    groups={};seen=set();score_bindings=[];populations={};phase_cost_checks=0
    for row in analysis["rows"]:
        assert row["status"]=="COMPLETE"
        b=row["result"];assert bind(b["path"])["sha256"]==b["sha256"]
        record=read_json(b["path"]);score_bindings.append(b)
        key=(record["profile_id"],record["stream"]);identity=(key,record["case_id"])
        assert identity not in seen;seen.add(identity)
        assert all(row[k]==record[k] for k in ("profile_id","stream","case_id"))
        group=groups.setdefault(key,{"cases":set(),"population_counts":{},"primary_errors":0,"primary_reference_words":0,"overlap_errors":0,"overlap_reference_words":0,"ambient_target_only_errors":0,"ambient_target_only_reference_words":0,"cpwer_errors":0,"cpwer_reference_words":0,"embedding_calls":0,"advisory_endpoint_count":0,"speech_assisted_segmentation_calls":0,"model_wall_s":0.})
        group["cases"].add(record["case_id"])
        pop=record["population"];group["population_counts"][pop]=group["population_counts"].get(pop,0)+1
        previous=populations.setdefault(record["case_id"],pop);assert previous==pop
        metrics=record["metrics"];text=metrics["text_metrics"]
        route={"primary_nonoverlap":("primary","text"),"overlap_complete":("overlap","overlap_mimo"),"ambient_incomplete":("ambient_target_only","target_only_text")}.get(pop)
        if route:
            prefix,name=route;wc=text[name]["word_counts"]
            assert wc["errors"]==wc["substitutions"]+wc["deletions"]+wc["insertions"]
            group[prefix+"_errors"]+=wc["errors"];group[prefix+"_reference_words"]+=wc["reference_words"]
        else:assert pop=="strict_empty" and text["text"]["wer"] is None
        cp=text.get("attributed_cpwer",{}).get("word_counts")
        if pop in ("primary_nonoverlap","overlap_complete"):
            assert cp and cp["reference_words"]>0
            group["cpwer_errors"]+=cp["errors"];group["cpwer_reference_words"]+=cp["reference_words"]
        else:assert not cp,"Incomplete/empty references must not enter complete-reference cpWER"
        for name in ("embedding_calls","advisory_endpoint_count","speech_assisted_segmentation_calls"):group[name]+=metrics[name]
        group["model_wall_s"]+=record["model_wall_s"]
        assert math.isclose(metrics["asr_compute_s"],sum(metrics[n] for n in ("asr_regular_dispatch_compute_s","asr_tail_dispatch_compute_s","asr_drain_compute_s")),abs_tol=1e-7)
        phase_cost_checks+=1
    assert len(seen)==720 and len(populations)==36
    expected={"primary_nonoverlap":23,"overlap_complete":6,"ambient_incomplete":5,"strict_empty":2}
    for key,group in groups.items():
        assert len(group["cases"])==36 and group["population_counts"]==expected
        assert (group["primary_reference_words"],group["overlap_reference_words"],group["ambient_target_only_reference_words"],group["cpwer_reference_words"])==(671,165,146,836)
        for name,value in group.items():
            if name in ("cases","population_counts"):continue
            assert math.isclose(float(supplied[key][name]),value,abs_tol=1e-7),(key,name)
    factorial=summary["factorial"]
    for row in factorial:
        assert row["all_four_complete"]
        original=supplied[("P0X1",row["stream"])][row["metric"]]-supplied[("P0X0",row["stream"])][row["metric"]]
        tuned=supplied[("P1X1",row["stream"])][row["metric"]]-supplied[("P1X0",row["stream"])][row["metric"]]
        assert math.isclose(row["original_cue_increment"],original,abs_tol=1e-10)
        assert math.isclose(row["tuned_cue_increment"],tuned,abs_tol=1e-10)
        assert math.isclose(row["interaction_tuned_minus_original_cue_increment"],tuned-original,abs_tol=1e-10)
    assert detail["P0X0_B0_lexical_parity"]=={"outputs":72,"exact_words":72,"different_words":[]}
    with Path(tables["SOURCE_SHORT_TURN_COVERAGE.csv"]["path"]).open(encoding="utf-8-sig",newline="") as handle:
        short=[r for r in csv.DictReader(handle) if r["population"]=="primary_nonoverlap" and r["whole_clip_bin"]=="<1s"]
    assert len(short)==20 and all(int(r["identity_source_turns"])==2 for r in short)
    findings=[
        {"finding":"P1X0 reduces panel cpWER with unchanged raw words, but short-turn identity coverage and mixed support regress",
         "action":"Challenge the bundle against EMBED_LONG and original cadence/post-policy controls. P1X0 known-modal coverage is only 1/2 O0 and 0/2 O1 versus 2/2 for P0X0. Keep all source turns and wrong-label exposure; no global winner follows.","ideas":["E02","Q04","Q07","N03","N05","N07"]},
        {"finding":"Advisory cue routes activate actual endpoints and increase lexical errors on both taps",
         "action":"Preserve continuous audio-only ASR and separate tracking-only from endpoint advice in B. Test false-jump/silence safeguards and circuit-breaker limits, using full raw S/D/I rather than attribution-only gains.","ideas":["A01","Q08","Q09","N04"]},
        {"finding":"Soft energy assistance changes admitted embedding work and unknown support, with unchanged aggregate cpWER/words",
         "action":"Measure incremental evidence, purity and short/unknown coverage against its matched SEG_X0 parent. An active assistance counter is capability evidence, not demonstrated lexical/attribution benefit.","ideas":["A02","Q01","Q05","N02","N03"]},
        {"finding":"Sparse cadence/RMS reduces embedding calls but worsens aggregate cpWER versus P0X0",
         "action":"Retain it as a cost/coverage tradeoff to challenge with debt scheduling and matched budgets; do not treat fewer calls alone as a deployment improvement.","ideas":["E04","Q05","N05"]},
        {"finding":"No wholly contained 1-second embedding fits the two subsecond utterances, yet EMBED_LONG retains two known modal labels",
         "action":"Report waveform containment, available identity support, modal label and correctness separately. Containment failure is not synonymous with a missed label; only two panel source turns cannot establish a stable short-reply rate.","ideas":["E02","Q04","N03"]}]
    plan["s6a_design_consequences"].extend(findings)
    registry["s6a_design_consequences"]=plan["s6a_design_consequences"]
    for item in registry["items"]:
        item["observed_constraints"]=[f for f in plan["s6a_design_consequences"] if item["id"] in f["ideas"]]
    reviewed={"status":"PASS_COMPLETE_720_INDEPENDENT_AGGREGATION","analysis":bind(analysis_path),"supplemental":bind(detail_path),
        "summary":bind(report/"COMPONENT_PROBE_SUMMARY.json"),"score_outputs_rehashed":score_bindings,"unique_profile_scene_tap_outputs":len(seen),
        "profiles_times_taps":len(groups),"scenes_per_profile_tap":36,"population_counts_per_profile_tap":expected,
        "reference_words":{"primary":671,"overlap":165,"ambient_target_only":146,"complete_cpwer":836},
        "all_summary_pooled_counts_match":True,"factorial_rows_checked":len(factorial),"ASR_tail_drain_cost_identities_checked":phase_cost_checks,
        "P0X0_B0_lexical_parity":detail["P0X0_B0_lexical_parity"],"short_turn_table":tables["SOURCE_SHORT_TURN_COVERAGE.csv"],
        "panel_subsecond_rows":short,"outcome_findings":findings,"code":bind(__file__),"utc":datetime.now(timezone.utc).isoformat(),
        "scope":"Independent re-pooling of all bound final score JSON and paired factorial arithmetic; not rerunning ASR/MeetEval or proving population causality. Source timing, worker scheduling, short sample size and phase-cost omissions remain explicit."}
    atomic(out/"INDEPENDENT_FINAL_REVIEW.json",reviewed)
    plan["final_probe_outcome_review"]={"binding":bind(out/"INDEPENDENT_FINAL_REVIEW.json"),"findings":findings,"short_turns":short,
        "population_scope":expected,"profile_rows":summary["profiles"],"factorial":factorial}
    ledger["completed_native_panel_child_wall"]={"source":bind(analysis_path),"jobs":720,"summed_child_wall_s":sum(g["model_wall_s"] for g in groups.values()),
        "per_profile_tap":[{"profile_id":key[0],"stream":key[1],"jobs":36,"summed_child_wall_s":g["model_wall_s"],"mean_child_wall_s":g["model_wall_s"]/36} for key,g in sorted(groups.items())],
        "scope":"Observed complete child wall includes loading/overhead under concurrent desktop research load. Sum is not coordinator elapsed, CPU-seconds, target RTF or guaranteed B throughput. Fresh per-recipe admission pilots remain necessary."}


def write_ledger_md(out, ledger):
    rows=["# CM5 target resource ledger", "",
          "Target: 2 GB CM5, 32 GB eMMC, ARM64 CPU. **Not tested on target.** Desktop measurements and analytic payload bounds remain separate.", "",
          f"Bound model/token files total {ledger['model_and_token_disk_bytes']:,} bytes ({ledger['model_and_token_disk_MiB']:.2f} MiB). Disk bytes do not equal resident RAM. The intended runtime shares one instance of each model rather than creating one ASR recognizer per speaker.", "",
          "| Asset | Disk bytes | Resident bytes |", "|---|---:|---|"]
    for model in ledger["models"]:
        rows.append(f"| {model['component_id']} | {model['disk_bytes_observed']:,} | Not isolated per model |")
    measured=ledger.get("primary_desktop_paced_evidence")
    if measured:
        rows+=["", "Controlled paced desktop screen", "",
               "Four sequential full-engine jobs used the same 89.390875-second measured gained O0 input at unity. OMP/OpenBLAS/MKL/NumExpr were each limited to one thread. Concurrent research load remained on the desktop. Source receipt records parity, model loading and process closure.", "",
               "| Job | Logged model-phase s | Peak USS MiB | RSS sum upper bound MiB | Private commit MiB | Peak threads | Writes bytes/audio s |",
               "|---|---:|---:|---:|---:|---:|---:|"]
        for r in measured["rows"]:
            rows.append(f"| {r['job_id']} | {r['model_compute_sec']:.3f} | {r['peak_private_resident_uss_sum_bytes']/2**20:.2f} | {r['peak_rss_sum_upper_bound_bytes']/2**20:.2f} | {r['peak_windows_private_commit_sum_bytes']/2**20:.2f} | {r.get('peak_observed_tree_threads')} | {r['io_write_bytes_per_audio_sec']:.1f} |")
        rows += ["", "Logged model-phase times are not exhaustive pipeline compute. Some wrapper preprocessing/postprocessing, gating, tracking, endpoint advice/reset, formatting and event I/O are outside these timers; segmentation timing stops before powerset_posteriors. Keep child/session wall time, loading, paced queue measurements and process resources distinct. The sum of phases is not full-pipeline RTF or calibrated latency.",
                 "USS measures private resident pages. RSS sums can double-count shared pages. RSS minus USS is a nonunique shared estimate; PSS is unavailable on this Windows host. Private commit measures committed virtual backing, not resident physical RAM. Per-model allocations are not isolated by these whole-process samples.",
                 "Observed backlog maxima are 0.10 seconds for ASR and 0.30 seconds for the speaker lane on this paced fixture; no dropped frames were reported. These bounded desktop queues and compute times do not establish CM5 capacity, sustained thermal behavior or live hardware latency.",
                 "V1 with inherited library defaults is retained separately. V1/V2 also used different application revisions, so their differences cannot be assigned solely to numeric-pool limits."]
    rows += ["", "Payload and storage bounds", "",
             "| Buffer or store | Analytic payload bound | Limitation |", "|---|---|---|"]
    for r in ledger["dynamic_buffers"]:
        amount=r.get("payload_bytes",r.get("vector_payload_bytes",r.get("bytes_at_16k",r.get("bytes"))))
        rows.append("| "+r["name"]+" | "+(f"{amount:,} bytes" if isinstance(amount,int) else "Unmeasured / policy dependent")+" | "+str(r.get("caveat") or r.get("required_change") or r["status"])+" |")
    rows += ["", "The current tracker bounds16 prototypes and64 recent revision records; Python objects and total event/journal growth are separate. Multi-prototype, bounded production event queues and retention changes remain proposed work.",
             f"Mono16k PCM16 audio alone writes {ledger['storage']['audio_PCM16_mono_bytes_per_hour']:,} bytes/hour. A proposed1GiB audio-only cap fills in {ledger['storage']['mono_audio_only_hours_to_1GiB']:.2f} hours before logs. Measured process write counts also include research vectors/events and are not physical eMMC writes.",
             "32GB is the nominal eMMC total. Installed OS, libraries, UI/display, update reserve, writable filesystems, write amplification and endurance are unmeasured on target; no assumed free-space subtraction is used.",
             "", "Target gates", "",
             "The ≤1.3GiB application screen and >1.5GiB review level are provisional planning limits, not a qualification. Validate the existing ARM64 exporter/runtime paths in the JSON ledger, exact graph hashes and imports, same-input numerical parity, actual USB no-drop behavior, process/private/shared memory plus OS MemAvailable, sustained queue stability, thermal/power behavior, disk-low recovery and GUI increment. No guessed desktop-to-CM5 speed factor is used.",
             "", "TARGET_RESOURCE_LEDGER.json contains exact byte formulas, source bindings, V1/V2 rows, model assets, runtime paths and deferred measurements. No board was contacted, flashed or tested.", ""]
    if ledger.get("completed_native_panel_child_wall"):
        panel=ledger["completed_native_panel_child_wall"]
        rows += ["", "Completed native panel cost context", "",
                 f"The 720 native jobs sum to {panel['summed_child_wall_s']:.3f} child-wall seconds, averaging {panel['summed_child_wall_s']/720:.3f} seconds per job across these profiles. This includes per-child loading/overhead under concurrent desktop research load. It is not coordinator elapsed, CPU-seconds, summed model-phase cost or CM5 RTF. The JSON retains each profile/tap mean; a fresh balanced recipe pilot still controls B admission."]
    write_text(out/"TARGET_RESOURCE_LEDGER.md","\n".join(rows))


def review_probe_comparisons(report, out):
    """Read-only parameter/behavior audit; replay at most 12 existing vector caches."""
    import numpy as np
    from dataclasses import asdict
    sys.path.insert(0, str(APP.parents[1]))
    from app.edge_speech_pipeline.research_tracking import ResearchTracker, TrackingConfig
    from app.edge_speech_pipeline.research_profiles import ResearchProfile
    index = read_json(report/"profiles/PROFILE_INDEX.json")
    profiles = {p["profile_id"]: read_json(p["path"]) for p in index}
    def leaves(value, prefix=""):
        result={}
        for key, v in value.items():
            name=prefix+key
            if isinstance(v,dict): result.update(leaves(v,name+"."))
            else: result[name]=v
        return result
    pairs=[("P0X0","P0X1"),("P1X0","P1X1"),("P0X0","P1X0"),("P0X1","P1X1"),
           ("P0X0","SEG_X0"),("SEG_X0","SEG_X1"),("P0X0","EMBED_LONG"),
           ("P0X0","EMBED_CADENCE_QUALITY"),("P0X0","ENDPOINT_X0"),("ENDPOINT_X0","ENDPOINT_X1")]
    diffs=[]
    for a,b in pairs:
        left,right=leaves(profiles[a]),leaves(profiles[b])
        diff={k:{"parent":left.get(k),"candidate":right.get(k)} for k in sorted(set(left)|set(right))
              if k!="profile_id" and left.get(k)!=right.get(k)}
        diffs.append({"parent":a,"candidate":b,"field_differences":diff})
    def diff_for(a,b): return next(x["field_differences"] for x in diffs if x["parent"]==a and x["candidate"]==b)
    assert diff_for("P0X0","P0X1")==diff_for("P1X0","P1X1")=={"xvf.mode":{"parent":"none","candidate":"advisory"}}
    assert diff_for("P0X0","P1X0")==diff_for("P0X1","P1X1")
    assert set(diff_for("P0X0","SEG_X0"))=={"tracker.mode","segmentation.hop_sec","segmentation.post_policy"}
    settings=asdict(ResearchProfile.from_dict(profiles["P0X0"]).tracker)
    settings={k:v for k,v in settings.items() if not k.startswith("identity_")}
    receipt=read_json(report/"CUE_REAL_FEATURE_CAUSALITY.json")
    replay_rows=[]
    for row in receipt["rows"][:12]:
        meta_path=Path(row["feature_binding"]["path"])
        assert sha(meta_path)==row["feature_binding"]["sha256"]
        meta=read_json(meta_path)
        vector_path=Path(meta["vectors"]["path"])
        assert sha(vector_path)==meta["vectors"]["sha256"]
        with np.load(vector_path,allow_pickle=False) as cache:
            vectors=cache["vectors"]
        assert vectors.shape==(len(meta["features"]),192)
        trackers={mode:ResearchTracker(TrackingConfig(**{**settings,"mode":mode}))
                  for mode in ("voice_time","reliability_adaptive")}
        decision_digests=[]
        for f,v in zip(meta["features"],vectors):
            results={mode:tracker.update(v,f["source_start_sec"],f["source_end_sec"],f["available_at_sec"],
                                        spatial=None,speech=f["speech"],overlap=f["overlap"])
                     for mode,tracker in trackers.items()}
            stripped=[{k:value for k,value in results[mode].items() if k!="mode"} for mode in trackers]
            assert stripped[0]==stripped[1], "Cue-disabled tracker behavior differs"
            decision_digests.append(hashlib.sha256(json.dumps(stripped[0],sort_keys=True,separators=(",",":")).encode()).hexdigest())
        snapshots=[t.snapshot() for t in trackers.values()]
        for value in snapshots: value["config"].pop("mode")
        assert snapshots[0]==snapshots[1]
        replay_rows.append({"case_id":meta["case_id"],"stream":meta["stream"],"feature_count":len(meta["features"]),
            "feature_metadata":bind(meta_path),"vector_binding":meta["vectors"],"exact_except_diagnostic_mode":True,
            "snapshot_exact_except_config_mode":True,
            "decision_sequence_digest":hashlib.sha256("".join(decision_digests).encode()).hexdigest()})
    notes=[
        "With xvf.mode=none, runtime passes spatial=None even when a provider exists. For identical admitted vectors/times, voice_time and reliability_adaptive execute the same voice association, ambiguity, unique-evidence, prototype, capacity, commitment and lineage paths; only diagnostic mode differs.",
        "SEG_X0 versus P0X0 changes segmentation posterior policy AND segmentation hop .75 to .5 seconds. The disabled-cue tracker mode difference has no numerical association effect. This is a segmentation bundle, not an isolated threshold test.",
        "SEG_X1 versus SEG_X0 changes only the soft-energy route. Voice_time ignores spatial identity evidence, and no advisor is enabled. Any effect propagates through posterior assistance, changed admission/spans and downstream evidence.",
        "The P0/P1 x X0/X1 factorial has identical P deltas across X and identical X deltas across P. X enables both spatial association and silence-guarded possible ASR endpoint advice. It is a cue-route bundle; endpoint counts and raw words must distinguish actual activation from nominal availability.",
        "P1 versus P0 jointly changes segmentation policy/hop, embedding window/hop, endpoint rules1/2 and host journal dispatch. The difference-in-differences estimates that bundle's conditional interaction with the cue route on the same panel/tap, not a single component causal effect.",
        "EMBED_LONG versus P0X0 changes only contiguous window .5 to1s; longer startup wait, overlapping-span content, compute and immediate1s commitment are real downstream consequences, not an independently calibrated threshold.",
        "EMBED_CADENCE_QUALITY changes BOTH evidence dispatch .25 to.75s and minimum RMS .002 to.001. RMS is calculated on that dispatch block, so its waveform support changes too. Do not isolate cadence, quality or duration effects from this bundled comparison.",
        "ENDPOINT_X0 versus P0X0 changes both silence rules and host dispatch100 to50ms. ENDPOINT_X1 additionally enables the same combined tracking/advice route. It is not an endpoint-only spatial treatment.",
        "B0 versus P0X0 uses different anonymous tracker/evidence logic and research transcript history/instrumentation. Same ASR settings do not prove lexical parity; the root's measured per-case lexical comparison is required.",
        "Cached tracker equivalence is deterministic for supplied features. Actual first transcript labels also depend on which concurrent speaker events already exist at ASR emission, even after modeled source-age checks. Do not convert this into full-app chunk/prefix invariance or calibrated GUI latency.",
        "Track label_revision records do not revise native transcript rows, which retain label_revision_of=null and original first labels. Count tracker lineage and actual revised transcript/GUI exposures separately.",
        "Both taps share one physical XVF trace. Room/speaker/source/prompt/RIR/noise reuse and previously observed cases prohibit independent holdout or population-causal claims."
    ]
    result={"status":"COMPLETE_BOUNDED_COMPARISON_AUDIT","profiles":len(profiles),"parameter_differences":diffs,
        "factorial_component_delta_equal_across_cue_modes":True,"factorial_cue_delta_equal_across_component_modes":True,
        "cue_disabled_tracker_replays":replay_rows,"equivalent_decisions":sum(r["feature_count"] for r in replay_rows),
        "interpretation_notes":notes,"inputs":[bind(report/"profiles/PROFILE_INDEX.json")]+[bind(p["path"]) for p in index],
        "code":[bind(APP/name) for name in ("runtime.py","research_profiles.py","research_tracking.py")],
        "neural_inference_calls":0,"audio_payloads_opened":0,"vectors_copied_to_report":False}
    atomic(out/"PROBE_COMPARISON_AUDIT.json",result)
    write_text(out/"PROBE_COMPARISON_AUDIT.md","# Independent probe comparison audit\n\n"
        +f"Ten frozen profiles reviewed. {result['equivalent_decisions']} existing feature decisions across {len(replay_rows)} bounded cases gave exactly equal disabled-cue tracker behavior after removing only the diagnostic mode field. No new neural runs or audio reads.\n\n"
        +"\n\n".join("- "+n for n in notes)+"\n")
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--report",type=Path,default=DEFAULT_REPORT)
    parser.add_argument("--pack",type=Path,default=PACK)
    parser.add_argument("--workbook",type=Path,default=Path(r"C:\Users\amiri\Downloads\XVF_Measurement_V14.docx"))
    parser.add_argument("--review-runtime",action="store_true",help="Run independent actual-loop EOF accounting fixture without model inference")
    parser.add_argument("--validate-native-plans",action="store_true",help="Validate all proposed native JSON foundations against actual ResearchProfile; does not implement optional policy extensions")
    parser.add_argument("--review-probes",action="store_true",help="Audit frozen profile contrasts and replay up to12 existing vector caches; no inference")
    args=parser.parse_args()
    out=args.report/"design"; out.mkdir(parents=True,exist_ok=True)
    seed=read_json(args.pack/"IDEA_REGISTRY_SEED.json")
    registry=make_registry(seed); plan=make_plan(args.report); ledger=make_ledger(args.pack,args.report)
    attach_measured_evidence(args.report,registry,plan,ledger)
    attach_final_probe_review(args.report,out,registry,plan,ledger)
    if args.validate_native_plans:
        sys.path.insert(0,str(APP.parents[1]))
        from app.edge_speech_pipeline.research_profiles import ResearchProfile
        validations=[]
        for trial in plan["profiles"]:
            native=trial["exact_execution"].get("native_base_profile")
            if native is not None:
                checked=ResearchProfile.from_dict(native)
                validations.append({"profile_id":trial["profile_id"],"native_profile_sha256":checked.digest(),"status":"PASS_NATIVE_SCHEMA_ONLY","extension_still_requires_implementation":trial["exact_execution"].get("additional_policy_extension") is not None})
        atomic(out/"PLANNED_NATIVE_SCHEMA_VALIDATION.json",{"status":"PASS","native_profile_count":len(validations),"validator":bind(APP/"research_profiles.py"),"rows":validations,"inference_calls":0,"S6B_started":False})
    atomic(out/"IDEA_REGISTRY_EXTENDED.json",registry)
    atomic(out/"S6B_JOINT_PLAN.json",plan)
    atomic(out/"TARGET_RESOURCE_LEDGER.json",ledger)
    write_ledger_md(out,ledger)
    atomic(out/"WORKBOOK_CONTEXT_RECEIPT.json",workbook_receipt(args.workbook))
    write_plan_md(out,plan)
    with (out/"IDEA_REGISTRY_SUMMARY.csv").open("w",encoding="utf-8",newline="") as f:
        fields=["id","title","equation_or_state_change","latency_model","compute_estimate","target_memory_class","implementation_status"]
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader()
        for row in registry["items"]: writer.writerow({k:row[k] for k in fields})
    source_rows=["# Technical source checks","","Primary references were checked on 9 September 2026. They motivate interpretation; the installed local implementation, graph inspection and execution receipts determine actual support.",""]
    for title,url,note in SOURCES: source_rows.append(f"- [{title}]({url}): {note}")
    source_rows += ["","No new dependency, model, hardware, board setup or document edit was performed by this builder. The current workbook is separately hash-bound and read for context. Model disk bytes are local file metadata; runtime and ARM64 claims require their own measurements."]
    write_text(out/"TECHNICAL_SOURCES.md","\n".join(source_rows)+"\n")
    if args.review_runtime:
        review_runtime_eof(out)
        independent_tracking_duration_review(out)
    if args.review_probes:
        review_probe_comparisons(args.report,out)
    atomic(out/"DESIGN_BUILD_RECEIPT.json",{
        "status":"PASS_STRUCTURAL_VALIDATION","utc":datetime.now(timezone.utc).isoformat(),"builder":bind(__file__),
        "inputs":[bind(args.pack/"IDEA_REGISTRY_SEED.json"),bind(args.pack/"reference/BASELINE_BINDINGS.json")]+[item["binding"] for item in registry.get("actual_component_evidence",{}).values()],
        "count":len(registry["items"]),"seed_preserved":60,"new_distinct":8,"plan_profiles":len(plan["profiles"]),
        "all_required_fields_present":True,"not_executed":"This validates the registry/plan structure, not any neural variant or target resource estimate.",
        "outputs":[bind(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!="DESIGN_BUILD_RECEIPT.json"]})
    print(json.dumps({"status":"PASS_STRUCTURAL_VALIDATION","output":str(out),"ideas":len(registry["items"]),"profiles":len(plan["profiles"]),"model_disk_bytes":ledger["model_and_token_disk_bytes"]}))

if __name__=="__main__": main()
