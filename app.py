from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Peak Comparison",
    page_icon="📈",
    layout="wide",
)


# --------------------------------------------------
# Styling
# --------------------------------------------------

st.markdown(
    """
    <style>
      .stApp {
        background: #f4fbfa;
      }

      .block-container {
        max-width: 1300px;
        padding-top: 1.2rem;
      }

      .hero {
        background: white;
        border: 1px solid #c9e4df;
        border-radius: 18px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 8px 24px rgba(25, 80, 75, 0.06);
      }

      .hero h1 {
        margin: 0;
        font-size: 2.4rem;
      }

      .hero p {
        margin: 0.45rem 0 0;
        color: #566;
        font-size: 1.05rem;
      }

      .metric-card {
        background: white;
        border: 1px solid #c9e4df;
        border-radius: 16px;
        padding: 1rem 1.1rem;
        min-height: 145px;
      }

      .sample-name {
        font-size: 1.25rem;
        font-weight: 750;
        margin-bottom: 0.5rem;
      }

      .peak-value {
        font-size: 2.15rem;
        font-weight: 850;
        line-height: 1.05;
      }

      .peak-label {
        color: #667085;
        font-size: 0.92rem;
        margin-top: 0.25rem;
      }

      div[data-testid="stDataFrame"] {
        background: white;
        border-radius: 14px;
        overflow: hidden;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown(
    """
    <div class="hero">
      <h1>HPLC Peak Comparison</h1>
      <p>
        Paste or upload a multi-sample peak table, select a target retention time,
        and compare the nearest matching peak across all samples.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# Data model and parsing
# --------------------------------------------------

@dataclass
class ParsedSample:
    label: str
    name: str
    peaks: pd.DataFrame


EXPECTED_COLUMNS = [
    "#",
    "Name",
    "Signal description",
    "RT (min)",
    "Area (mAU·s)",
    "Area%",
    "Height (mAU)",
    "Height%",
    "Amount",
    "Concentration",
    "Start time (min)",
    "End time (min)",
]

NUMERIC_COLUMNS = [
    "#",
    "RT (min)",
    "Area (mAU·s)",
    "Area%",
    "Height (mAU)",
    "Height%",
    "Amount",
    "Concentration",
    "Start time (min)",
    "End time (min)",
]


def normalise_line(line: str) -> str:
    return line.replace("\ufeff", "").rstrip("\r\n")


def split_fields(line: str) -> list[str]:
    """
    Prefer tab-separated input. Fall back to runs of two or more spaces so that
    copied tables from reports can still be parsed.
    """
    line = normalise_line(line)

    if "\t" in line:
        return [part.strip() for part in line.split("\t")]

    return [part.strip() for part in re.split(r"\s{2,}", line.strip())]


def pad_or_trim(fields: list[str], length: int) -> list[str]:
    if len(fields) < length:
        fields = fields + [""] * (length - len(fields))
    return fields[:length]


def parse_peak_text(text: str) -> tuple[str, list[ParsedSample]]:
    lines = [normalise_line(line) for line in text.splitlines()]

    report_title = ""
    for line in lines:
        if line.strip():
            report_title = line.strip()
            break

    sample_pattern = re.compile(
        r"^\s*Sample\s+(\d+)\s*:\s*(.+?)\s*$",
        flags=re.IGNORECASE,
    )

    samples: list[ParsedSample] = []
    index = 0

    while index < len(lines):
        match = sample_pattern.match(lines[index])

        if not match:
            index += 1
            continue

        sample_number = match.group(1)
        sample_name = match.group(2).strip()
        sample_label = f"Sample {sample_number}"

        index += 1

        # Find the table header after the sample heading.
        while index < len(lines):
            candidate = lines[index].strip()
            if candidate.startswith("#") and "RT (min)" in candidate:
                break

            if sample_pattern.match(lines[index]):
                break

            index += 1

        if index >= len(lines) or not (
            lines[index].strip().startswith("#")
            and "RT (min)" in lines[index]
        ):
            continue

        header_fields = pad_or_trim(split_fields(lines[index]), len(EXPECTED_COLUMNS))
        if len(header_fields) != len(EXPECTED_COLUMNS):
            header_fields = EXPECTED_COLUMNS.copy()

        # Use the canonical names so output is consistent even when pasted headers vary.
        header_fields = EXPECTED_COLUMNS.copy()
        index += 1

        rows: list[list[str]] = []

        while index < len(lines):
            line = lines[index]

            if sample_pattern.match(line):
                break

            if not line.strip():
                index += 1
                continue

            fields = split_fields(line)

            # Peak rows begin with an integer peak number.
            if not fields or not re.fullmatch(r"\d+", fields[0].strip()):
                index += 1
                continue

            fields = pad_or_trim(fields, len(EXPECTED_COLUMNS))
            rows.append(fields)
            index += 1

        frame = pd.DataFrame(rows, columns=header_fields)

        for column in NUMERIC_COLUMNS:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

        frame["Sample"] = sample_label
        frame["Sample name"] = sample_name

        samples.append(
            ParsedSample(
                label=sample_label,
                name=sample_name,
                peaks=frame,
            )
        )

    return report_title, samples


def find_nearest_peak(
    sample: ParsedSample,
    target_rt: float,
    tolerance: float,
) -> dict:
    peaks = sample.peaks.dropna(subset=["RT (min)"]).copy()

    if peaks.empty:
        return {
            "Sample": sample.label,
            "Sample name": sample.name,
            "Matched": False,
            "Reason": "No valid retention times found",
        }

    peaks["RT difference"] = (peaks["RT (min)"] - target_rt).abs()
    nearest = peaks.sort_values(
        ["RT difference", "Area (mAU·s)"],
        ascending=[True, False],
    ).iloc[0]

    matched = float(nearest["RT difference"]) <= tolerance

    result = {
        "Sample": sample.label,
        "Sample name": sample.name,
        "Matched": matched,
        "Peak #": nearest["#"],
        "RT (min)": nearest["RT (min)"],
        "RT difference": nearest["RT difference"],
        "Area (mAU·s)": nearest["Area (mAU·s)"],
        "Area%": nearest["Area%"],
        "Height (mAU)": nearest["Height (mAU)"],
        "Height%": nearest["Height%"],
        "Start time (min)": nearest["Start time (min)"],
        "End time (min)": nearest["End time (min)"],
        "Reason": "" if matched else (
            f"Nearest peak is outside ±{tolerance:.3f} min"
        ),
    }
    return result



def assign_wells(comparison: pd.DataFrame) -> pd.DataFrame:
    """
    Assign samples sequentially across a standard 96-well plate:
    A1-A12, then B1-B12, through H12.
    """
    wells = [f"{row}{column}" for row in "ABCDEFGH" for column in range(1, 13)]
    assigned = comparison.copy()
    assigned["Well"] = wells[: len(assigned)]
    return assigned


def draw_96_well_plate(
    plate_data: pd.DataFrame,
    value_column: str,
    target_rt: float,
):
    rows = list("ABCDEFGH")
    columns = list(range(1, 13))

    values = pd.to_numeric(plate_data[value_column], errors="coerce")
    valid_values = values.dropna()

    if valid_values.empty:
        minimum = 0.0
        maximum = 1.0
    else:
        minimum = float(valid_values.min())
        maximum = float(valid_values.max())
        if maximum == minimum:
            maximum = minimum + 1.0

    fig, ax = plt.subplots(figsize=(15, 8))

    plate_lookup = plate_data.set_index("Well").to_dict("index")

    for row_index, row in enumerate(rows):
        for column_index, column in enumerate(columns):
            well = f"{row}{column}"
            x = column_index
            y = 7 - row_index

            record = plate_lookup.get(well)

            if record is None:
                face_value = 0.0
                circle = plt.Circle(
                    (x, y),
                    0.38,
                    facecolor="#f1f3f5",
                    edgecolor="#b7bec7",
                    linewidth=1.2,
                )
                ax.add_patch(circle)
                ax.text(
                    x,
                    y,
                    well,
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="#7a828c",
                )
                continue

            raw_value = record.get(value_column)
            matched = bool(record.get("Matched", False))
            numeric_value = pd.to_numeric(
                pd.Series([raw_value]),
                errors="coerce",
            ).iloc[0]

            if matched and pd.notna(numeric_value):
                normalized = (float(numeric_value) - minimum) / (maximum - minimum)
                facecolor = plt.cm.YlOrRd(0.2 + 0.8 * normalized)
            else:
                facecolor = "#d9dde3"

            circle = plt.Circle(
                (x, y),
                0.38,
                facecolor=facecolor,
                edgecolor="#545b66",
                linewidth=1.4,
            )
            ax.add_patch(circle)

            sample_name = str(record.get("Sample name", ""))
            short_name = sample_name if len(sample_name) <= 15 else sample_name[:13] + "…"

            ax.text(
                x,
                y + 0.10,
                well,
                ha="center",
                va="center",
                fontsize=8,
                fontweight="bold",
            )
            ax.text(
                x,
                y - 0.05,
                short_name,
                ha="center",
                va="center",
                fontsize=6.5,
            )

            if pd.notna(numeric_value):
                ax.text(
                    x,
                    y - 0.20,
                    f"{float(numeric_value):,.1f}",
                    ha="center",
                    va="center",
                    fontsize=6.5,
                    fontweight="bold",
                )

    ax.set_xlim(-0.7, 11.7)
    ax.set_ylim(-0.7, 7.7)
    ax.set_aspect("equal")
    ax.set_xticks(range(12))
    ax.set_xticklabels(columns, fontsize=11, fontweight="bold")
    ax.xaxis.tick_top()
    ax.set_yticks(range(8))
    ax.set_yticklabels(rows[::-1], fontsize=11, fontweight="bold")
    ax.tick_params(length=0)
    ax.set_title(
        f"96-well plate — {value_column} near {target_rt:.3f} min",
        fontsize=16,
        fontweight="bold",
        pad=22,
    )

    for spine in ax.spines.values():
        spine.set_visible(False)

    scalar_map = plt.cm.ScalarMappable(
        cmap=plt.cm.YlOrRd,
        norm=plt.Normalize(vmin=minimum, vmax=maximum),
    )
    scalar_map.set_array([])
    colorbar = fig.colorbar(
        scalar_map,
        ax=ax,
        fraction=0.025,
        pad=0.03,
    )
    colorbar.set_label(value_column)

    fig.tight_layout()
    return fig


def make_export_table(comparison: pd.DataFrame) -> bytes:
    return comparison.to_csv(index=False).encode("utf-8")


# --------------------------------------------------
# Sidebar controls
# --------------------------------------------------

with st.sidebar:
    st.header("Comparison settings")

    target_rt = st.number_input(
        "Target retention time (min)",
        min_value=0.0,
        value=7.5,
        step=0.05,
        format="%.3f",
    )

    tolerance = st.number_input(
        "Matching tolerance (± min)",
        min_value=0.001,
        value=0.35,
        step=0.05,
        format="%.3f",
        help=(
            "The nearest peak is accepted only when it falls within this "
            "distance of the target retention time."
        ),
    )

    st.caption(
        "Example: target 7.5 with tolerance 0.35 accepts peaks from "
        "7.150 to 7.850 minutes."
    )


# --------------------------------------------------
# Input
# --------------------------------------------------

uploaded = st.file_uploader(
    "Upload a TXT, TSV, or CSV export",
    type=["txt", "tsv", "csv"],
)

if uploaded is None:
    st.info("Upload a peak report file to begin.")
    st.stop()

input_text = uploaded.getvalue().decode("utf-8", errors="replace")


# --------------------------------------------------
# Analysis
# --------------------------------------------------

if st.button(
    "Compare peaks",
    type="primary",
    use_container_width=True,
):
    title, parsed_samples = parse_peak_text(input_text)

    if not parsed_samples:
        st.error(
            "No sample sections were detected. Ensure each section starts with "
            "'Sample 1: ...', 'Sample 2: ...', and so on."
        )
        st.stop()

    comparison_records = [
        find_nearest_peak(sample, target_rt, tolerance)
        for sample in parsed_samples
    ]
    comparison = pd.DataFrame(comparison_records)

    st.session_state["peak_comparison"] = {
        "title": title or "Peak Comparison",
        "target_rt": target_rt,
        "tolerance": tolerance,
        "samples": parsed_samples,
        "comparison": comparison,
    }


# --------------------------------------------------
# Results
# --------------------------------------------------

if "peak_comparison" in st.session_state:
    results = st.session_state["peak_comparison"]
    comparison = results["comparison"].copy()
    parsed_samples = results["samples"]

    st.subheader(results["title"])
    st.write(
        f"Nearest peaks to **{results['target_rt']:.3f} min** "
        f"using a tolerance of **±{results['tolerance']:.3f} min**."
    )

    matched_count = int(comparison["Matched"].fillna(False).sum())
    st.info(
        f"Matched {matched_count} of {len(comparison)} samples within the selected tolerance."
    )

    card_columns = st.columns(min(len(comparison), 4))

    for index, (_, row) in enumerate(comparison.iterrows()):
        column = card_columns[index % len(card_columns)]

        with column:
            if bool(row.get("Matched", False)):
                area_value = row.get("Area (mAU·s)")
                rt_value = row.get("RT (min)")

                st.markdown(
                    f"""
                    <div class="metric-card">
                      <div class="sample-name">{row['Sample']}: {row['Sample name']}</div>
                      <div class="peak-value">{rt_value:.3f} min</div>
                      <div class="peak-label">Matched retention time</div>
                      <div style="margin-top:0.7rem;font-size:1.2rem;font-weight:750;">
                        Area: {area_value:,.3f}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.warning(
                    f"**{row['Sample']}: {row['Sample name']}**\n\n"
                    f"{row.get('Reason', 'No matching peak')}"
                )

    st.markdown("### Peak comparison table")

    display_columns = [
        "Sample",
        "Sample name",
        "Matched",
        "Peak #",
        "RT (min)",
        "RT difference",
        "Area (mAU·s)",
        "Area%",
        "Height (mAU)",
        "Height%",
        "Start time (min)",
        "End time (min)",
    ]

    display_table = comparison.reindex(columns=display_columns).copy()

    st.dataframe(
        display_table.style.format(
            {
                "RT (min)": "{:.3f}",
                "RT difference": "{:.3f}",
                "Area (mAU·s)": "{:,.3f}",
                "Area%": "{:.3f}",
                "Height (mAU)": "{:,.3f}",
                "Height%": "{:.3f}",
                "Start time (min)": "{:.3f}",
                "End time (min)": "{:.3f}",
            },
            na_rep="—",
        ),
        use_container_width=True,
        hide_index=True,
    )

    matched = comparison[comparison["Matched"] == True].copy()

    if len(matched) >= 1:
        st.markdown("### Comparison plots")

        chart_data = matched.copy()
        chart_data["Label"] = (
            chart_data["Sample"] + ": " + chart_data["Sample name"]
        )

        x_positions = list(range(len(chart_data)))

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.scatter(
            x_positions,
            chart_data["Area (mAU·s)"],
            s=95,
        )
        ax.set_ylabel("Area (mAU·s)")
        ax.set_title(
            f"Peak area near {results['target_rt']:.3f} min"
        )
        ax.set_xticks(x_positions)
        ax.set_xticklabels(chart_data["Label"], rotation=25, ha="right")
        ax.grid(True, axis="y", alpha=0.3)

        for x, value in zip(x_positions, chart_data["Area (mAU·s)"]):
            if pd.notna(value):
                ax.annotate(
                    f"{value:,.1f}",
                    (x, value),
                    xytext=(0, 8),
                    textcoords="offset points",
                    ha="center",
                    fontsize=9,
                )

        fig.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.scatter(
            x_positions,
            chart_data["Height (mAU)"],
            s=95,
        )
        ax.set_ylabel("Height (mAU)")
        ax.set_title(
            f"Peak height near {results['target_rt']:.3f} min"
        )
        ax.set_xticks(x_positions)
        ax.set_xticklabels(chart_data["Label"], rotation=25, ha="right")
        ax.grid(True, axis="y", alpha=0.3)

        for x, value in zip(x_positions, chart_data["Height (mAU)"]):
            if pd.notna(value):
                ax.annotate(
                    f"{value:,.1f}",
                    (x, value),
                    xytext=(0, 8),
                    textcoords="offset points",
                    ha="center",
                    fontsize=9,
                )

        fig.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    st.markdown("### 96-well plate")

    plate_metric = st.selectbox(
        "Colour wells by",
        options=["Area (mAU·s)", "Height (mAU)", "Area%", "Height%"],
        index=0,
        help="The sample with the highest selected peak value is shown with the darkest colour.",
    )

    plate_data = assign_wells(comparison)

    st.caption(
        "Samples are filled sequentially from A1 to A12, then B1 to B12, through H12. "
        "Grey wells are empty or have no accepted peak match."
    )

    plate_figure = draw_96_well_plate(
        plate_data=plate_data,
        value_column=plate_metric,
        target_rt=results["target_rt"],
    )
    st.pyplot(plate_figure, use_container_width=True)
    plt.close(plate_figure)

    plate_table = plate_data[
        [
            "Well",
            "Sample",
            "Sample name",
            "Matched",
            "RT (min)",
            plate_metric,
        ]
    ].copy()

    st.dataframe(
        plate_table.style.format(
            {
                "RT (min)": "{:.3f}",
                plate_metric: "{:,.3f}",
            },
            na_rep="—",
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Peaks around the target region")

    lower_bound = results["target_rt"] - results["tolerance"]
    upper_bound = results["target_rt"] + results["tolerance"]

    nearby_tables = []
    for sample in parsed_samples:
        nearby = sample.peaks[
            sample.peaks["RT (min)"].between(
                lower_bound,
                upper_bound,
                inclusive="both",
            )
        ].copy()

        if not nearby.empty:
            nearby_tables.append(nearby)

    if nearby_tables:
        nearby_all = pd.concat(nearby_tables, ignore_index=True)

        nearby_display = nearby_all[
            [
                "Sample",
                "Sample name",
                "#",
                "RT (min)",
                "Area (mAU·s)",
                "Area%",
                "Height (mAU)",
                "Height%",
            ]
        ].sort_values(["Sample", "RT (min)"])

        st.dataframe(
            nearby_display.style.format(
                {
                    "RT (min)": "{:.3f}",
                    "Area (mAU·s)": "{:,.3f}",
                    "Area%": "{:.3f}",
                    "Height (mAU)": "{:,.3f}",
                    "Height%": "{:.3f}",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.warning("No peaks were found inside the selected target window.")

    export_name = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        results["title"].strip(),
    ).strip("._-") or "peak_comparison"

    st.download_button(
        "Download comparison CSV",
        data=make_export_table(comparison),
        file_name=f"{export_name}_rt_{results['target_rt']:.3f}.csv",
        mime="text/csv",
        use_container_width=True,
    )
