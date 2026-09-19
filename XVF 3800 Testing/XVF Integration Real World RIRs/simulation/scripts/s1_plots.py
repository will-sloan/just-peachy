"""Render S1 diagnostics from saved analysis arrays; never reads original captures."""
import argparse
import time
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import signal
from s0_common import read, save, now

COLORS = ["#1672b8", "#e47c20", "#249759", "#a052a4"]

def render(report):
    report = Path(report)
    start = time.monotonic()
    cfg = read(report / "extraction_config.json")
    selected = read(report / "selected_pilot_manifest.json")["recordings"]
    folder = report / "plots"
    folder.mkdir(exist_ok=True)
    rows = []
    for row in selected:
        m = read(report / "records" / row["run_id"] / "metrics.json")
        x = m["response_metrics"]
        timing = m["timing"]
        with np.load(m["plot_data_path"]) as z:
            fig, ax = plt.subplots(3, 2, figsize=(15, 12), layout="constrained")
            fig.suptitle(f'{row["pilot_order"]:02d}  {row["room_table"]} | {row["speaker_angle_deg_effective"]:+g}° | '
                         f'{row["source_distance_m_effective"]:g} m\n{m["run_id"]}\n'
                         f'{m["status"]} • selected clock {timing["selected_ppm"]:.2f} ppm • provisional only', fontsize=12)
            for mic, color in enumerate(COLORS):
                for fit in [v for v in timing["fits"] if v["mic"] == mic]:
                    ax[0, 0].plot([2, 16, 16.2], fit["residual_samples"], ".-", color=color, alpha=.65)
                ax[0, 0].plot([], [], color=color, label=f"MIC{mic}")
            ax[0, 0].set(title="Marker fit residuals: 3 frequency bands per microphone",
                         xlabel="Source marker time (s)", ylabel="Residual (samples at 16 kHz)")
            ax[0, 0].legend(ncol=4, fontsize=8)
            sensitivity = sorted(timing["clock_sensitivity"], key=lambda v: v["ppm"])
            ax[0, 1].plot([v["ppm"] for v in sensitivity], [v["concentration"] for v in sensitivity], "o-", color="#28374e")
            ax[0, 1].axvspan(*timing["working_interval_ppm"], color="#6f89a4", alpha=.2)
            ax[0, 1].axvline(timing["selected_ppm"], color="#bd493c", linestyle="--", label="Selected")
            ax[0, 1].set(title=f'Marker {timing["marker_regression_ppm"]:.2f} ± {timing["working_half_width_ppm"]:.2f} ppm; working interval only',
                         xlabel="Shared reference clock (ppm)", ylabel="Early energy concentration (fraction)")
            ax[0, 1].legend(fontsize=8)
            t = np.arange(len(z["core"])) / 16000
            earliest = min(a["first_significant_energy_sec"] for a in x["arrivals"])
            for mic, color in enumerate(COLORS):
                ax[1, 0].plot(t * 1000, z["core"][:, mic], color=color, lw=.8)
                ax[1, 1].semilogx(z["frequency_hz"][1:], z["response_db"][1:, mic], color=color, alpha=.45, lw=.7)
                ax[1, 1].semilogx(z["frequency_hz"][1:], z["candidate_db"][1:, mic], color=color, lw=.7)
                ax[2, 0].plot(np.arange(len(z["block_power"])) * .02, 10 * np.log10(z["block_power"][:, mic] + 1e-30), color=color)
                ax[2, 0].axhline(10 * np.log10(x["tail_floor_used_fs2"][mic]), color=color, linestyle=":", alpha=.75)
                ax[2, 1].semilogx(z["noise_frequency_hz"][1:], z["noise_psd_db"][1:, mic], color=color, linestyle=":")
                ax[2, 1].semilogx(z["residual_frequency_hz"][1:], z["observed_psd_db"][1:, mic], color=color, alpha=.35)
                ax[2, 1].semilogx(z["residual_frequency_hz"][1:], z["residual_psd_db"][1:, mic], color=color)
            ax[1, 0].set(xlim=((earliest-.008)*1000, (earliest+.025)*1000),
                         title="Early response, one common time axis", xlabel="Time from full-core origin (ms)",
                         ylabel="Response amplitude (recorded FS / drive FS)")
            ax[1, 1].set(xlim=(80, 7900), ylim=(-100, 15), title="Response magnitude: faint = core; solid = candidate",
                         xlabel="Frequency (Hz)", ylabel="Magnitude (dB, recorded FS / drive FS)")
            ax[2, 0].axvspan(x["common_taper_start_sample"]/16000, x["common_crop_end_sample"]/16000, alpha=.2, color="grey")
            ax[2, 0].set(xlim=(0, 2.8), title="20 ms response energy; dotted = conservative floor; grey = taper",
                         xlabel="Time from full-core origin (s)", ylabel="Mean response power (dB)")
            ax[2, 1].set(xlim=(80,7900), title="PSD: faint = sweep; solid = residual; dotted = pre-noise",
                         xlabel="Frequency (Hz)", ylabel="PSD (dB FS²/Hz)")
            for a in ax.flat: a.grid(True, alpha=.2)
            fig.savefig(folder / f'{row["pilot_order"]:02d}_{row["run_id"]}.png', dpi=130)
            plt.close(fig)
        lo, hi = x["supported_candidate_band_hz"]
        b = signal.firwin(cfg["candidate_fir_taps"], [lo, hi], pass_zero=False, fs=16000, window=("kaiser", 8.6))
        f, h = signal.freqz(b, worN=131072, fs=16000)
        ix = (f >= lo) & (f <= hi) & (abs(20*np.log10(abs(h)+1e-30)) <= .1)
        flat = [float(f[ix][0]), float(f[ix][-1])]
        rows.append({"pilot_order":row["pilot_order"], "run_id":row["run_id"], "filter_cutoffs_hz":[lo, hi],
                     "filter_only_flat_within_0_1_db_hz":flat, "timing":timing, "response":x,
                     "worst_residual_db":max(m["reconstruction"]["relative_residual_energy_db"])})
        print(f'Plot {len(rows)}/12: {row["run_id"]}', flush=True)
        save(report / "plot_status.json", {"updated_utc":now(), "complete":len(rows), "total":12})
    fig, ax = plt.subplots(2, 2, figsize=(13, 9), layout="constrained")
    numbers = np.arange(1, 13)
    colors = ["#218255" if r["timing"]["selected_ppm"] else "#d29128" for r in rows]
    ax[0, 0].errorbar(numbers, [r["timing"]["marker_regression_ppm"] for r in rows],
                      yerr=[r["timing"]["working_half_width_ppm"] for r in rows], fmt="o", color="#263a54", capsize=3)
    ax[0, 0].scatter(numbers, [r["timing"]["selected_ppm"] for r in rows], c=colors, marker="x", s=70, label="Selected clock")
    ax[0, 0].axhline(0, color="grey", lw=.6)
    ax[0, 0].set(title="Marker drift ± working interval; crosses = selected", ylabel="Shared reference clock (ppm)")
    ax[0, 0].legend(fontsize=8)
    ax[0, 1].bar(numbers, [100*r["timing"]["sweep_concentration_improvement_fraction"] for r in rows], color=colors)
    ax[0, 1].axhline(3, color="#a9403c", linestyle="--", label="Prewritten 3% gate")
    ax[0, 1].set(title="Sweep concentration change at marker clock", ylabel="Change versus zero clock (%)")
    ax[0, 1].legend(fontsize=8)
    ax[1, 0].bar(numbers, [r["response"]["candidate_duration_sec"] for r in rows], color=colors)
    ax[1, 0].set(title="Common cropped candidate duration", ylabel="Duration (s)")
    ax[1, 1].bar(numbers, [r["worst_residual_db"] for r in rows], color=colors)
    ax[1, 1].set(title="Worst-channel same-sweep residual; descriptive only", ylabel="Residual / observed energy (dB)")
    for a in ax.flat:
        a.set_xticks(numbers)
        a.set_xlabel("Pilot order (see manifest)")
        a.grid(axis="y", alpha=.2)
    fig.suptitle("S1: 12 provisional responses • 4 clock-supported / 8 timing-review\n"
                 "Green = provisional clock correction; amber = zero clock pending review. None is simulation-ready.", fontsize=13)
    fig.savefig(folder / "00_pilot_overview.png", dpi=145)
    plt.close(fig)
    save(report / "plot_results.json", {"status":"COMPLETE", "elapsed_sec":time.monotonic()-start,
         "plot_count":13, "filter_characterization":[{k:v for k,v in r.items() if k not in ("timing","response")} for r in rows],
         "visual_inspection":"See visual_qa.json; this script does not assert human/model visual inspection."})

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--report", required=True)
    render(p.parse_args().report)
