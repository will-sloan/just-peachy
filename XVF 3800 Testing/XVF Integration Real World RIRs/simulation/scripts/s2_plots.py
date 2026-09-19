"""Compact aggregate QC and a few notable-record plots, from saved evidence only."""
import argparse, time
from pathlib import Path
import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from s0_common import read,save

COLORS=["#1672b8","#e47c20","#249759","#a052a4"]

def render(report):
    report=Path(report);start=time.monotonic()
    active=read(report/"ACTIVE_INPUTS.json")["recordings"]
    ms=[read(report/"records"/(r["run_id"]+".json")) for r in active]
    good=[m for m in ms if m["status"]!="FAILED"]
    rooms=list(dict.fromkeys(m["geometry"]["room_table"] for m in good))
    roomcolors={r:plt.get_cmap("tab10")(i) for i,r in enumerate(rooms)}
    folder=report/"plots";folder.mkdir(exist_ok=True)
    fig,ax=plt.subplots(2,2,figsize=(14,9),layout="constrained")
    x=np.arange(1,len(good)+1)
    colors=[roomcolors[m["geometry"]["room_table"]] for m in good]
    ax[0,0].scatter(x,[m["clock"]["selected_ppm"] for m in good],c=colors,s=13)
    fallback=[(i+1,m) for i,m in enumerate(good) if m["clock"]["status"]=="CONSERVATIVE_ZERO_FALLBACK"]
    if fallback:
        ax[0,0].scatter([i for i,m in fallback],[m["clock"]["selected_ppm"] for i,m in fallback],facecolors="none",edgecolors="#bf2727",s=70,label="Conservative fallback")
        ax[0,0].legend(fontsize=8)
    ax[0,0].set(title="One selected clock per recording",xlabel="Active-manifest order",ylabel="Common clock mismatch (ppm)")
    for room in rooms:
        group=[m for m in good if m["geometry"]["room_table"]==room]
        ax[0,1].scatter([m["geometry"]["source_distance_m_effective"] for m in group],
                       [m["response"]["candidate_duration_sec"] for m in group],label=room,c=[roomcolors[room]],s=18)
    ax[0,1].set(title="Stored duration versus recorded distance (descriptive)",xlabel="Effective recorded distance (m)",ylabel="Stored RIR duration (s)")
    ax[0,1].legend(fontsize=7)
    ax[1,0].scatter(x,[max(m["same_sweep_reconstruction"]["relative_residual_energy_db"]) for m in good],c=colors,s=13)
    ax[1,0].axhline(-15,linestyle="--",color="#a44444")
    ax[1,0].set(title="Worst-channel internal reconstruction residual",xlabel="Active-manifest order",ylabel="Error / observed energy (dB)")
    statuses=["EXTRACTED","EXTRACTED_WITH_LIMITATIONS","FAILED"];offset=np.zeros(len(rooms))
    for status,color in zip(statuses,["#238657","#e2a037","#bd3434"]):
        counts=np.array([sum(m["status"]==status and m["geometry"]["room_table"]==room for m in ms) for room in rooms])
        ax[1,1].barh(np.arange(len(rooms)),counts,left=offset,label=status,color=color);offset+=counts
    ax[1,1].set_yticks(np.arange(len(rooms)),rooms,fontsize=8)
    ax[1,1].set(title="Offline extraction outcomes",xlabel="Recordings");ax[1,1].legend(fontsize=7)
    for a in ax.flat:a.grid(alpha=.15)
    fig.suptitle("Canonical 121-record RIR library • offline extraction only\nNo hardware replay or independent acoustic validation",fontsize=14)
    fig.savefig(folder/"01_library_overview.png",dpi=140);plt.close(fig)
    margins=np.array([[min(b["sweep_plus_noise_to_pre_noise_db"]) for b in m["noise"]["bands"]] for m in good])
    bands=good[0]["noise"]["bands"]
    fig,ax=plt.subplots(figsize=(13,9),layout="constrained")
    im=ax.imshow(margins,aspect="auto",cmap="viridis",vmin=0,vmax=45,interpolation="nearest",
                 extent=(-.5,margins.shape[1]-.5,len(good)+.5,.5))
    ax.set_xticks(np.arange(len(bands)),[f'{b["band_hz"][0]}–{b["band_hz"][1]}' for b in bands],rotation=45,ha="right")
    ax.set(title="Worst-microphone frequency-interval support; rule ≥10 dB\nChosen filter is common to all records; weak intervals remain explicit limitations",
           xlabel="Frequency interval (Hz)",ylabel="Active-manifest order (successful records)")
    for i in range(1,len(good)):
        if good[i]["geometry"]["room_table"]!=good[i-1]["geometry"]["room_table"]:ax.axhline(i+.5,color="white",lw=1)
    fig.colorbar(im,ax=ax,label="Sweep-plus-noise / pre-marker-noise power (dB)")
    fig.savefig(folder/"02_frequency_support.png",dpi=135);plt.close(fig)
    # A few materially uncertain or highest-residual examples; no per-record plot sweep.
    notable=[m for m in good if not m["can_proceed_to_hil_proof"]][:3]
    worst=max(good,key=lambda m:max(m["same_sweep_reconstruction"]["relative_residual_energy_db"]))
    if worst not in notable:notable.append(worst)
    notable=notable[:4]
    for m in notable:
        with np.load(report/"qc_arrays"/(m["run_id"]+".npz")) as z:
            fig,ax=plt.subplots(1,3,figsize=(16,5),layout="constrained")
            early,fs=sf.read(m["output"]["path"],always_2d=True)
            t=np.arange(len(early))/fs+m["time_origin"]["export_start_relative_to_core_sec"]
            for mic,c in enumerate(COLORS):
                ax[0].plot(t*1000,early[:,mic],color=c,lw=.8,label=f"MIC{mic}")
                ax[1].plot(np.arange(len(z["block_power"]))*.02,10*np.log10(z["block_power"][:,mic]+1e-30),color=c)
                ax[1].axhline(10*np.log10(m["response"]["tail_floor_used_fs2"][mic]),color=c,linestyle=":")
                ax[2].semilogx(z["frequency_hz"][1:],z["response_db"][1:,mic],color=c,lw=.7)
            ax[0].set(xlim=(70,145),xlabel="Common core time (ms)",ylabel="Recorded FS / drive FS",title="Early response, shared axis")
            ax[0].legend(fontsize=7)
            ax[1].axvspan(m["response"]["common_taper_start_sample_in_core"]/16000,m["response"]["common_crop_end_sample_in_core"]/16000,color="grey",alpha=.2)
            ax[1].set(xlabel="Common core time (s)",ylabel="Mean response power (dB)",title="Decay and conservative floors")
            ax[2].set(xlim=(60,7900),ylim=(-110,15),xlabel="Frequency (Hz)",ylabel="Transfer magnitude (dB)",title="Canonical response spectrum")
            for a in ax:a.grid(alpha=.2)
            fig.suptitle(m["run_id"]+"\n"+", ".join(m["limitations"]),fontsize=10)
            fig.savefig(folder/("notable_"+m["run_id"]+".png"),dpi=120);plt.close(fig)
    save(report/"PLOT_RESULTS.json",{"status":"COMPLETE","count":2+len(notable),"notable_ids":[m["run_id"] for m in notable],"elapsed_sec":time.monotonic()-start})
    print(f'{2+len(notable)} compact plots written.',flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--report",required=True);render(p.parse_args().report)
