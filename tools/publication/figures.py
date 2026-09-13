from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

NAVY = "#1b365d"
TEAL = "#2a9d8f"
SLATE = "#4a5568"
CORAL = "#c0564a"
GOLD = "#c9a227"


def _style(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(colors=SLATE)
    ax.xaxis.label.set_color(NAVY)
    ax.yaxis.label.set_color(NAVY)
    ax.title.set_color(NAVY)


def feasibility_opt_hit(pubs: list[dict], path: Path) -> None:
    fixtures = [f"D{i}" for i in range(1, 7)]
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.2), sharex=True)
    panels = [
        (axes[0, 0], 1, "feasible_shot_fraction", "Feasible-shot fraction, p=1"),
        (axes[0, 1], 2, "feasible_shot_fraction", "Feasible-shot fraction, p=2"),
        (axes[1, 0], 1, "optimal_hit_fraction", "Optimal-hit fraction, p=1"),
        (axes[1, 1], 2, "optimal_hit_fraction", "Optimal-hit fraction, p=2"),
    ]
    for ax, depth, field, title in panels:
        for i, fx in enumerate(fixtures):
            subset = [r for r in pubs if r["fixture"] == fx and r["p"] == depth]
            vals = [r[field] for r in subset]
            ax.scatter([i] * len(vals), vals, color=TEAL, s=28, alpha=0.85, zorder=3)
            if subset:
                ref = subset[0]["uniform_optimal_hit_probability"] if field == "optimal_hit_fraction" else subset[0]["uniform_feasibility_probability"]
                ax.hlines(ref, i - 0.35, i + 0.35, colors=CORAL, linewidth=1.2)
        ax.set_xticks(range(6), fixtures)
        ax.set_title(title)
        ax.set_ylabel("Fraction of 1,024 shots")
        _style(ax)
    fig.suptitle("Hardware sampling fractions by fixture (six clustered blocks). Coral: analytical uniform probability.", color=NAVY, fontsize=11)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def utility_panel(pubs: list[dict], path: Path) -> None:
    fixtures = [f"D{i}" for i in range(1, 7)]
    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    for i, fx in enumerate(fixtures):
        p1 = [r for r in pubs if r["fixture"] == fx and r["p"] == 1]
        opt = p1[0]["exact_optimum"]
        greedy = p1[0]["greedy_incumbent_utility"]
        bests = [r["best_feasible_utility"] for r in pubs if r["fixture"] == fx]
        ax.scatter([i] * len(bests), bests, color=TEAL, s=22, alpha=0.8, label="best feasible (blocks)" if i == 0 else None)
        ax.hlines(opt, i - 0.35, i + 0.35, colors=NAVY, linewidth=2, label="exact optimum" if i == 0 else None)
        ax.hlines(greedy, i - 0.35, i + 0.35, colors=GOLD, linewidth=2, linestyles="dashed", label="greedy incumbent" if i == 0 else None)
    ax.set_xticks(range(6), fixtures)
    ax.set_ylabel("Utility")
    ax.set_title("Best feasible hardware utility by fixture (each marker is one fixture/depth/PUB observation inside a clustered block)")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=3)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def policy_panel(pubs: list[dict], path: Path) -> None:
    policies = ["P0", "P1", "P2", "P3"]
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    x = range(len(policies))
    feas = [sum(1 for r in pubs if r["policies"][p]["selected_feasible"]) for p in policies]
    opt = [sum(1 for r in pubs if r["policies"][p]["is_optimum"] and r["policies"][p]["selected_feasible"]) for p in policies]
    improve = [sum(1 for r in pubs if r["policies"][p]["independent_strict_improvement"]) for p in policies]
    w = 0.25
    ax.bar([i - w for i in x], feas, width=w, color=NAVY, label="selected feasible")
    ax.bar(x, opt, width=w, color=TEAL, label="selected feasible optimum")
    ax.bar([i + w for i in x], improve, width=w, color=GOLD, label="strict improvement vs greedy")
    ax.set_xticks(list(x), policies)
    ax.set_ylabel("PUB count (of 72)")
    ax.set_title("Unchanged-specification hardware policy selections")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def fair_pool_panel(rows: list[dict], path: Path) -> None:
    fixtures = [f"D{i}" for i in range(1, 7)]
    subset = [r for r in rows if r.get("prefix") == 1024 and r.get("p_panel") == 1]
    fig, ax = plt.subplots(figsize=(9.6, 4.8))
    x = list(range(len(fixtures)))
    hw = []
    uni = []
    p_opt = []
    for fx in fixtures:
        row = next(r for r in subset if r["fixture"] == fx)
        hw.append(row["hardware_opt_hit"]["mean"])
        uni.append(row["uniform_opt_hit"]["mean"])
        p_opt.append(row["p_opt_uniform_single_draw"])
    ax.plot(x, hw, "o-", color=TEAL, label="hardware mean opt-hit (6 clustered blocks)")
    ax.plot(x, uni, "s--", color=NAVY, label="uniform MC mean opt-hit (32 reps)")
    ax.plot(x, p_opt, "^", color=CORAL, label="analytical uniform p_opt (single draw)")
    ax.set_xticks(x, fixtures)
    ax.set_ylabel("Optimal-hit fraction")
    ax.set_title("Prefix 1024, p=1 panel. Classical pools are reused for p=2. P(≥1 opt)=1-(1-p_opt)^m is tabulated separately.")
    ax.legend(frameon=False, fontsize=8)
    _style(ax)
    fig.tight_layout()
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def timing_panel(jobs: list[dict], path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.8))
    blocks = [r["block"] for r in jobs]
    axes[0].bar(blocks, [r["client_elapsed_seconds"] for r in jobs], color=TEAL)
    axes[0].axhline(30, color=CORAL, linestyle="--", linewidth=1)
    axes[0].set_title("Client receipt (s)")
    axes[1].bar(blocks, [r["provider_running_to_finished_s"] or 0 for r in jobs], color=NAVY)
    axes[1].set_title("Provider running→finished (s)")
    axes[2].bar(blocks, [r["charged_usage_seconds"] for r in jobs], color=GOLD)
    axes[2].set_title("Charged QPU seconds")
    for ax in axes:
        ax.set_xlabel("Block")
        _style(ax)
    fig.suptitle("Timing and usage are different quantities; receipt latency is not an organisational decision timestamp.", color=NAVY, fontsize=10)
    fig.tight_layout()
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def ghz_panel(ghz: dict, path: Path) -> None:
    rows = ghz["rows"]
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.2))
    x = range(1, len(rows) + 1)
    axes[0].plot(x, [r["hellinger_vs_sampled_aer_baseline"] for r in rows], color=TEAL, marker="o")
    axes[0].plot(x, [r["hellinger_vs_exact_ghz_baseline"] for r in rows], color=NAVY, marker="s", linestyle="--")
    axes[0].set_title("GHZ computational-basis Hellinger agreement")
    axes[0].set_xlabel("Run")
    axes[0].set_ylabel("Hellinger (bitstring distributions)")
    axes[0].legend(["sampled Aer baseline", "exact 000/111 baseline"], frameon=False)
    queues = [r["queue_wait_seconds"] for r in rows]
    axes[1].bar(x, queues, color=NAVY)
    axes[1].set_yscale("log")
    axes[1].set_title("Queue wait (s, log axis)")
    axes[1].set_xlabel("Run")
    for ax in axes:
        _style(ax)
    fig.suptitle("Hellinger here is computational-basis distribution agreement, not quantum-state fidelity or proof of entanglement. Run 20 is the long queue outlier. Log axis is labelled.", color=NAVY, fontsize=9)
    fig.tight_layout()
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)


def architecture_diagram(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10.2, 4.4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.4)
    ax.axis("off")
    boxes = [
        (0.2, 2.6, "Frozen protocol\nQPY, Powell result.x"),
        (2.7, 2.6, "SamplerV2 block\n12 PUBs × 1024"),
        (5.2, 2.6, "Raw archive\nordered shots"),
        (7.6, 2.6, "Post-collection\nanalysis (tools/)"),
        (0.2, 0.6, "Mailbox: Coordinator\nEncoder, SolverAdapter,\nValidator — local tests"),
        (2.7, 0.6, "P0–P3 policies\nfrozen functions"),
        (5.2, 0.6, "Hardware decisions\nunchanged spec"),
        (7.6, 0.6, "Replay on same\nshots (labelled)"),
    ]
    for x, y, text in boxes:
        ax.add_patch(FancyBboxPatch((x, y), 2.1, 1.4, boxstyle="round,pad=0.04", facecolor="#e8eef5", edgecolor=NAVY))
        ax.text(x + 1.05, y + 0.7, text, ha="center", va="center", color=NAVY, fontsize=8)
    ax.annotate("", xy=(2.7, 3.3), xytext=(2.3, 3.3), arrowprops=dict(arrowstyle="->", color=TEAL))
    ax.annotate("", xy=(5.2, 3.3), xytext=(4.8, 3.3), arrowprops=dict(arrowstyle="->", color=TEAL))
    ax.annotate("", xy=(7.6, 3.3), xytext=(7.3, 3.3), arrowprops=dict(arrowstyle="->", color=TEAL))
    ax.set_title("Hardware path uses runner/SamplerV2 and Coordinator persistence; full mailbox is local tests, not IBM.", color=NAVY, fontsize=9)
    fig.tight_layout()
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=180, bbox_inches="tight")
    plt.close(fig)
