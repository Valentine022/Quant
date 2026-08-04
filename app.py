from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st



def get_logo_html() -> str:
    """Load the Evoralis logo from the app folder, with a styled fallback."""
    app_directory = Path(__file__).resolve().parent
    possible_logos = [
        app_directory / "EvoralisLogo.png",
        app_directory / "cropped-cropped-0_Evoralis_logo_for-emails_final_v2.png",
    ]

    for logo_path in possible_logos:
        if logo_path.exists():
            encoded_logo = base64.b64encode(logo_path.read_bytes()).decode("ascii")
            return (
                f'<img class="evoralis-logo" '
                f'src="data:image/png;base64,{encoded_logo}" '
                f'alt="Evoralis">'
            )

    return (
        '<div class="evoralis-wordmark" aria-label="Evoralis">'
        '<span>EVORALIS</span>'
        '</div>'
    )


logo_html = get_logo_html()


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
      :root {
        --ev-bg: #e8f7f5;
        --ev-panel: #ffffff;
        --ev-border: #b9dfd8;
        --ev-text: #1c2434;
        --ev-muted: #667085;
        --ev-purple: #9370DB;
        --ev-purple-dark: #7651c6;
        --ev-purple-soft: #f0e8f7;
      }

      .stApp {
        background: var(--ev-bg);
        color: var(--ev-text);
      }

      header[data-testid="stHeader"],
      div[data-testid="stToolbar"] {
        display: none;
      }

      .block-container {
        max-width: 1200px;
        padding-top: 1rem;
      }

      .hero {
        display: flex;
        align-items: center;
        gap: 1.25rem;
        background: var(--ev-panel);
        border: 1px solid var(--ev-border);
        border-radius: 18px;
        padding: 1.2rem 1.6rem;
        margin-bottom: 1.5rem;
      }

      .hero-text {
        flex: 1;
      }

      .hero h1 {
        margin: 0;
        font-size: 2.2rem;
        font-weight: 700;
      }

      .hero p {
        margin: 0.35rem 0 0;
        font-size: 1.05rem;
        color: #555;
      }

      .evoralis-logo {
        height: 80px;
        width: auto;
        max-width: 230px;
        object-fit: contain;
        flex-shrink: 0;
      }

      .evoralis-wordmark {
        min-width: 210px;
        height: 80px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 12px;
        background: var(--ev-purple-soft);
        border: 2px solid var(--ev-purple);
        color: var(--ev-purple-dark);
        font-size: 1.55rem;
        font-weight: 850;
        letter-spacing: 0.12em;
      }

      section[data-testid="stSidebar"] {
        background: #f9fffe;
        border-right: 1px solid var(--ev-border);
      }

      section[data-testid="stSidebar"] h1,
      section[data-testid="stSidebar"] h2,
      section[data-testid="stSidebar"] h3 {
        color: var(--ev-text);
      }

      /* Purple label bars for dropdowns and key controls */
      div[data-testid="stSelectbox"] > label,
      div[data-testid="stNumberInput"] > label,
      div[data-testid="stTextInput"] > label,
      div[data-testid="stFileUploader"] > label {
        display: inline-block;
        width: 100%;
        background: var(--ev-purple);
        color: white !important;
        padding: 0.58rem 0.8rem;
        border-radius: 10px 10px 0 0;
        font-size: 1rem;
        font-weight: 750;
        margin-bottom: 0;
      }

      div[data-testid="stSelectbox"] > div,
      div[data-testid="stNumberInput"] > div,
      div[data-testid="stTextInput"] > div {
        background: white;
        border: 1px solid var(--ev-border);
        border-top: 0;
        border-radius: 0 0 10px 10px;
        padding: 0.35rem;
      }

      div[data-baseweb="select"] > div {
        border-color: var(--ev-border) !important;
        border-radius: 8px !important;
      }

      div[data-testid="stFileUploader"] {
        background: white;
        border: 1px solid var(--ev-border);
        border-radius: 12px;
        overflow: hidden;
        padding: 0;
      }

      div[data-testid="stFileUploader"] section {
        padding: 0.8rem;
      }

      div[data-testid="stDataFrame"] {
        background: white;
        border: 1px solid var(--ev-border);
        border-radius: 14px;
        overflow: hidden;
      }

      div[data-testid="stVegaLiteChart"],
      div[data-testid="stPyplotGlobalUse"] {
        background: white;
        border: 1px solid var(--ev-border);
        border-radius: 14px;
        padding: 0.7rem;
      }

      .stButton > button,
      .stDownloadButton > button {
        border-radius: 10px;
        font-weight: 700;
      }

      .stButton > button[kind="primary"] {
        background: var(--ev-purple);
        border-color: var(--ev-purple);
      }

      .stButton > button[kind="primary"]:hover {
        background: var(--ev-purple-dark);
        border-color: var(--ev-purple-dark);
      }

      h2, h3 {
        color: var(--ev-text);
      }

      html {
        scroll-behavior: smooth;
      }

      .topnav {
        position: sticky;
        top: 0;
        z-index: 999;
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin: 0 -1rem 1.35rem;
        padding: 12px 1rem;
        background: var(--ev-purple-soft);
        border-top: 1px solid #d7c8e9;
        border-bottom: 1px solid var(--ev-border);
        backdrop-filter: blur(8px);
      }

      .topnav a {
        display: inline-block;
        padding: 8px 13px;
        border-radius: 999px;
        background: var(--ev-purple);
        color: white !important;
        text-decoration: none !important;
        font-weight: 700;
        line-height: 1.2;
      }

      .topnav a:hover {
        background: var(--ev-purple-dark);
      }

      .section-anchor {
        position: relative;
        top: -82px;
        visibility: hidden;
      }

      .purple-section-header {
        margin: 1.5rem 0 0.85rem;
        padding: 0.72rem 1rem;
        border-radius: 12px;
        background: var(--ev-purple);
        color: white;
        font-size: 1.35rem;
        font-weight: 750;
        line-height: 1.2;
      }

      .result-panel {
        background: white;
        border: 1px solid var(--ev-border);
        border-radius: 14px;
        padding: 0.9rem;
        margin-bottom: 1rem;
      }

      @media (max-width: 700px) {
        .hero {
          flex-direction: column;
          align-items: flex-start;
        }

        .evoralis-logo,
        .evoralis-wordmark {
          height: 64px;
          min-width: 180px;
        }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="hero">
      {logo_html}
      <div class="hero-text">
        <h1>HPLC Peak Comparison</h1>
        <p>
          Upload a multi-sample peak table, select a target retention time,
          and compare the nearest matching peak across all samples.
        </p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <nav class="topnav" aria-label="Page sections">
      <a href="#settings">Settings</a>
      <a href="#upload">Upload</a>
      <a href="#plate-view">96-well plate</a>
      <a href="#results-table">Results</a>
      <a href="#peak-area">Peak area</a>
      <a href="#download-results">Download</a>
    </nav>
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
    plate_name: str,
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
        f"{plate_name}\n96-well plate — {value_column} near {target_rt:.3f} min",
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
    st.markdown('<div id="settings" class="section-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="purple-section-header">Comparison settings</div>',
        unsafe_allow_html=True,
    )

    plate_name = st.text_input(
        "Sample / plate name",
        value="HPLC Peak Comparison",
        help="Used as the main heading of the 96-well plate plot.",
    )

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

st.markdown('<div id="upload" class="section-anchor"></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="purple-section-header">Upload peak report</div>',
    unsafe_allow_html=True,
)

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
        "plate_name": plate_name.strip() or title or "HPLC Peak Comparison",
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

    st.markdown(
        f'<div class="purple-section-header">{results["title"]}</div>',
        unsafe_allow_html=True,
    )
    st.write(
        f"Peak nearest to **{results['target_rt']:.3f} min** "
        f"using a tolerance of **±{results['tolerance']:.3f} min**."
    )

    plate_data = assign_wells(comparison)

    st.markdown('<div id="plate-view" class="section-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="purple-section-header">96-well plate</div>',
        unsafe_allow_html=True,
    )

    plate_metric = st.selectbox(
        "96-well plot value",
        options=[
            "Area (mAU·s)",
            "Height (mAU)",
            "Area%",
            "Height%",
        ],
        index=0,
        help="Choose which matched peak measurement controls the well colours.",
    )

    plate_figure = draw_96_well_plate(
        plate_data=plate_data,
        value_column=plate_metric,
        target_rt=results["target_rt"],
        plate_name=results["plate_name"],
    )
    st.pyplot(plate_figure, use_container_width=True)
    plt.close(plate_figure)

    st.caption(
        f"Samples are assigned sequentially from A1 to A12, then B1 to B12. "
        f"Darker wells have a larger {plate_metric}. Grey wells have no accepted match."
    )

    st.markdown('<div id="results-table" class="section-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="purple-section-header">Results table</div>',
        unsafe_allow_html=True,
    )

    basic_table = plate_data[
        [
            "Well",
            "Sample name",
            "RT (min)",
            "Area (mAU·s)",
            "Area%",
            "Height (mAU)",
            "Height%",
        ]
    ].copy()

    st.dataframe(
        basic_table.style.format(
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

    st.markdown('<div id="peak-area" class="section-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="purple-section-header">Peak area</div>',
        unsafe_allow_html=True,
    )

    plot_data = basic_table.dropna(subset=["Area (mAU·s)"]).copy()

    if plot_data.empty:
        st.warning("No matched peak-area values are available to plot.")
    else:
        plot_data["Sample order"] = range(1, len(plot_data) + 1)

        st.scatter_chart(
            plot_data,
            x="Sample order",
            y="Area (mAU·s)",
            size=90,
            use_container_width=True,
        )

        st.caption(
            "Each dot represents one sample. Hover over a point to view its peak area."
        )

        label_table = plot_data[
            ["Sample order", "Well", "Sample name", "Area (mAU·s)"]
        ].copy()

        st.dataframe(
            label_table.style.format(
                {"Area (mAU·s)": "{:,.3f}"},
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

    export_name = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        results["title"].strip(),
    ).strip("._-") or "peak_comparison"

    st.markdown('<div id="download-results" class="section-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="purple-section-header">Download</div>',
        unsafe_allow_html=True,
    )

    st.download_button(
        "Download results CSV",
        data=make_export_table(basic_table),
        file_name=f"{export_name}_rt_{results['target_rt']:.3f}.csv",
        mime="text/csv",
        use_container_width=True,
    )
