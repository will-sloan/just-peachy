"""Redact matched component evidence for handoff; see README.md."""
import argparse
from pathlib import Path

from prepare import HERE, bind, load
from run_embeddings import atomic


def main(root):
    records=[];summary=[]
    rosters=load(Path(root).parent/"ROSTERS.json")
    for encoder in ["E0","E1"]:
        base=Path(root)/encoder
        component=load(base/"RESULT.json")
        receipt=load(HERE/f"{encoder}_COMPONENT_RECEIPT.json")
        if bind(base/"RESULT.json")["sha256"]!=receipt["private_result"]["sha256"]:
            raise ValueError("Changed component result")
        records.append(receipt)
        for row in component["galleries"]:
            corrected={"encoder":encoder,**{k:v for k,v in row.items() if k not in {"gallery","scores","roster_id"}}}
            corrected["original_roster_intended_size"]=row["intended_size"]
            if row["matched_duration_diagnostic"]:
                roster=next(r for r in rosters["primary"] if r["mode"]==row["mode"] and r["domain"]==row["domain"])
                eligible=len(set(roster["intended_identities"]) & set(rosters["matched_5_15_30_clean_identities"]))
                corrected["intended_size"]=eligible
                corrected["unavailable_count"]=eligible-row["available_size"]
                corrected["original_roster_excluded_by_matched_design"]=row["intended_size"]-eligible
                corrected["metadata_correction_scope"]="Matched diagnostic eligible population separated from original intended roster; profile vectors and numerical scores unchanged"
            summary.append(corrected)
    if records[0]["window_denominator"]!=records[1]["window_denominator"]:
        raise ValueError("Embedding comparisons have different window denominators")
    report={"schema":"n2-matched-component-summary-v1","status":"ACTUALLY_RUN_COMPONENT_ONLY",
            "receipts":records,"rows":summary,
            "qualifications":["Same1194 predeclared waveform spans per encoder; no window failures",
                "Qwindows are evaluator-only mapped whole-source diagnostic spans, not model-selected online windows",
                "No model training, Q threshold tuning, audio-device access or personal gallery access",
                "Qhas192 roster-member windows and130 known-reference stranger windows for primary34-intended/24-available open gallery; both taps correlated",
                "Primary open gallery clean C has87 unique stranger sources, below predeclared100 minimum; no operational threshold admitted",
                "Processed C remains collection-only; all actual XVF query open naming gates reject",
                "Pairwise EER is descriptive and uses correlated within-person/window pairs; not an operational false-known probability",
                "Component CPU/RSS observations are desktop concurrent-campaign receipts, not isolated resource or CM5 2GB qualification"]}
    atomic(HERE/"COMPONENT_SUMMARY.json",report)
    lines=["# N2 matched speaker embedding component results","", "Both encoders actually processed the same 1,194 bound saved-waveform windows: 385 clean E, 367 clean C, 120 processed E captures and 322 evaluator-only query spans. Every window met the 0.5-second admission minimum. There were no failed/omitted windows. Each encoder produced 29 model-bound private research galleries; no personal gallery was accessed.","",
           "The following primary open-gallery results use 34 intended and 24 available members. Query component windows include both taps and are whole-source-support diagnostics; they are not the runtime's selected 0.5–2 second windows. Scores and margins are uncalibrated for processed query naming. Pairwise EER is descriptive, with correlated pairs.","",
           "| Encoder | E domain / position / stream | C pair EER | Q pair EER | Q known top-1 correct /192 | Q stranger windows |",
           "| --- | --- | ---: | ---: | ---: | ---: |"]
    for row in summary:
        if row["mode"]=="open" and not row["matched_duration_diagnostic"]:
            condition=f"{row['domain']} / {row['position'].rsplit('_',1)[-1]} / {row['stream']}"
            eer=lambda value:"unavailable" if value is None else f"{value*100:.2f}%"
            lines.append(f"| {row['encoder']} | {condition} | {eer(row['C_verification']['eer'])} | {eer(row['Q_verification_evaluator_only']['eer'])} | {row['Q_known_top1_correct_uncalibrated']} | {row['Q_known_reference_stranger_windows']} |")
    lines += ["", "The clean primary open roster had only 87 distinct stranger-source C clips, below the predeclared 100-clip minimum. Its C gate therefore rejects all names. Smaller selected rosters can support a clean-domain empirical C threshold, but clean C does not calibrate processed XVF queries. All operational open naming gates remain `UNCALIBRATED_REJECT_ALL`. Explicit closed-roster names are unverified assumptions, to be evaluated separately in the online observer.","",
              "E0 completed in %.1f seconds and E1 in %.1f seconds, with one CPU thread each. Their observed peak process RSS was %.1f and %.1f MiB respectively. E0's standard SpeakerModels object also loads the frozen Pyannote session, and long processed E captures enlarge memory arenas. These are component process observations during the campaign, not an isolated architecture benchmark or a 2-GB target qualification."%(records[0]["elapsed_seconds"],records[1]["elapsed_seconds"],records[0]["peak_observed_rss_bytes"]/1048576,records[1]["peak_observed_rss_bytes"]/1048576),"",
              "All clean 5/15/30 matched-population diagnostics, separate processed position/stream results, shortage denominators and source/model hashes are in COMPONENT_SUMMARY.json and the private component results. The observed differences do not establish integrated streaming superiority. Actual D0/D1-selected-window results belong to the common application runner and RuntimeGalleryObserver."]
    (HERE/"COMPONENT_RESULTS.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print({"status":"ACTUALLY_RUN_COMPONENT_ONLY","encoders":2,"conditions_each":29,"output":str(HERE/"COMPONENT_SUMMARY.json")})


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",default="G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/component")
    main(parser.parse_args().root)
