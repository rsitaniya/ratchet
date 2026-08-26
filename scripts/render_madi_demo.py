"""Render the README's MaDI evidence GIF from committed evaluator receipts."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "engagements/madi_onboarding/runs/forbes"
OUTPUT = ROOT / "docs/madi-onboarding-demo.gif"
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"


def font(size: int):
    return ImageFont.truetype(FONT, size)


def receipt(name: str) -> dict:
    return json.loads((RUNS / name).read_text())


def frame(title: str, subtitle: str, accent: str, lines: list[str], note: str, color: str) -> Image.Image:
    image = Image.new("RGB", (1200, 630), color)
    draw = ImageDraw.Draw(image)
    draw.text((70, 70), title, font=font(44), fill="white")
    draw.text((70, 140), subtitle, font=font(24), fill="#9fb0c8")
    draw.text((70, 245), lines[0], font=font(32), fill=accent)
    for i, line in enumerate(lines[1:]):
        draw.text((70, 310 + i * 50), line, font=font(29), fill="white" if "regression" not in line else "#86efac")
    draw.text((70, 550), note, font=font(20), fill="#9fb0c8")
    return image


def main() -> None:
    baseline, cycle1, cycle2 = (receipt(f) for f in (
        "00_baseline.evaluate.json", "01_cycle1.evaluate.json", "02_cycle2.evaluate.json"
    ))
    metrics = [baseline["per_source"]["forbes"], cycle1["per_source"]["forbes"], cycle2["per_source"]["forbes"]]
    frames = [
        frame("Partner data onboarding", "Baseline held-out evaluation", "#7dd3fc", [
            "forbes source", f"Schema-mapping F1       {metrics[0]['schema_f1']:.2f}",
            f"Value accuracy          {metrics[0]['value_accuracy']:.2f}", "Integrated records      0 / 6",
        ], "Receipt: 00_baseline.evaluate.json", "#0b1020"),
        frame("Cycle 1: map required fields", "Signal ranked by affected records", "#fbbf24", [
            "Approved adapter change", f"Schema-mapping F1       {metrics[1]['schema_f1']:.4f}",
            f"Value accuracy          {metrics[1]['value_accuracy']:.3f}", "Integrated records      6 / 6",
            "dbpedia regression      false",
        ], "Receipts: 01_cycle1.gaps.txt + 01_cycle1.evaluate.json", "#111a2e"),
        frame("Cycle 2: complete normalization", "sales to revenue; money and country rules", "#86efac", [
            "Held-out evaluator", f"Schema-mapping F1       {metrics[2]['schema_f1']:.2f}",
            f"Value accuracy          {metrics[2]['value_accuracy']:.2f}", "Fully-correct records   6 / 6",
            "dbpedia regression      false",
        ], "Receipt: 02_cycle2.evaluate.json", "#10231e"),
    ]
    frames[0].save(OUTPUT, save_all=True, append_images=frames[1:], duration=[1900, 2100, 2200], loop=0)
    print(OUTPUT)


if __name__ == "__main__":
    main()
