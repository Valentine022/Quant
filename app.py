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

default_text = """260528 Film Comparison

Sample 1: Film 1 (old film)
#\tName\tSignal description\tRT (min)\tArea (mAU·s)\tArea%\tHeight (mAU)\tHeight%\tAmount\tConcentration\tStart time (min)\tEnd time (min)
1\t\tVWD1A,Wavelength=190 nm\t0.986\t11249.323\t14.489\t1279.262\t36.87\t\t\t0.692\t1.394
2\t\tVWD1A,Wavelength=190 nm\t1.529\t993.313\t1.279\t93.456\t2.69\t\t\t1.394\t1.744
3\t\tVWD1A,Wavelength=190 nm\t2.027\t77.896\t0.100\t2.409\t0.07\t\t\t1.744\t2.353
4\t\tVWD1A,Wavelength=190 nm\t2.586\t97.464\t0.126\t4.098\t0.12\t\t\t2.353\t3.269
5\t\tVWD1A,Wavelength=190 nm\t7.619\t450.264\t0.580\t53.751\t1.55\t\t\t7.352\t7.622
6\t\tVWD1A,Wavelength=190 nm\t7.732\t697.076\t0.898\t137.709\t3.97\t\t\t7.622\t7.737
7\t\tVWD1A,Wavelength=190 nm\t7.842\t15510.247\t19.976\t1263.822\t36.42\t\t\t7.737\t8.218
8\t\tVWD1A,Wavelength=190 nm\t8.830\t14686.187\t18.915\t317.620\t9.15\t\t\t8.218\t9.039
9\t\tVWD1A,Wavelength=190 nm\t9.282\t33880.923\t43.637\t317.560\t9.15\t\t\t9.039\t11.999

Sample 2: Film 1, 500 nM UC5
#\tName\tSignal description\tRT (min)\tArea (mAU·s)\tArea%\tHeight (mAU)\tHeight%\tAmount\tConcentration\tStart time (min)\tEnd time (min)
1\t\tVWD1A,Wavelength=190 nm\t0.985\t10994.254\t14.576\t1257.009\t35.77\t\t\t0.689\t1.391
2\t\tVWD1A,Wavelength=190 nm\t1.528\t957.727\t1.270\t89.454\t2.55\t\t\t1.391\t1.746
3\t\tVWD1A,Wavelength=190 nm\t2.581\t52.574\t0.070\t3.051\t0.09\t\t\t2.342\t3.193
4\t\tVWD1A,Wavelength=190 nm\t7.524\t1437.041\t1.905\t183.906\t5.23\t\t\t7.364\t7.622
5\t\tVWD1A,Wavelength=190 nm\t7.715\t1137.091\t1.508\t216.677\t6.17\t\t\t7.622\t7.736
6\t\tVWD1A,Wavelength=190 nm\t7.835\t12782.161\t16.946\t1144.666\t32.57\t\t\t7.736\t8.186
7\t\tVWD1A,Wavelength=190 nm\t8.834\t14053.896\t18.632\t305.839\t8.70\t\t\t8.186\t9.010
8\t\tVWD1A,Wavelength=190 nm\t9.283\t34012.743\t45.093\t313.763\t8.93\t\t\t9.010\t11.996
"""

if uploaded is not None:
    input_text = uploaded.getvalue().decode("utf-8", errors="replace")
else:
    input_text = st.text_area(
        "Paste peak report text",
        value=default_text,
        height=420,
        help=(
            "Each sample section should begin with 'Sample N: name', followed "
            "by the peak table."
        ),
    )


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

    if len(matched) >= 2:
        first = matched.iloc[0]

        st.markdown("### Change relative to the first matched sample")

        relative = matched[
            [
                "Sample",
                "Sample name",
                "Area (mAU·s)",
                "Area%",
                "Height (mAU)",
                "Height%",
            ]
        ].copy()

        for metric in [
            "Area (mAU·s)",
            "Area%",
            "Height (mAU)",
            "Height%",
        ]:
            baseline = first[metric]

            if pd.notna(baseline) and baseline != 0:
                relative[f"{metric} change (%)"] = (
                    (relative[metric] - baseline) / baseline * 100
                )
            else:
                relative[f"{metric} change (%)"] = pd.NA

        st.dataframe(
            relative.style.format(
                {
                    "Area (mAU·s)": "{:,.3f}",
                    "Area%": "{:.3f}",
                    "Height (mAU)": "{:,.3f}",
                    "Height%": "{:.3f}",
                    "Area (mAU·s) change (%)": "{:+.1f}%",
                    "Area% change (%)": "{:+.1f}%",
                    "Height (mAU) change (%)": "{:+.1f}%",
                    "Height% change (%)": "{:+.1f}%",
                },
                na_rep="—",
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### Comparison plots")

        chart_data = matched.copy()
        chart_data["Label"] = (
            chart_data["Sample"] + ": " + chart_data["Sample name"]
        )

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(chart_data["Label"], chart_data["Area (mAU·s)"])
        ax.set_ylabel("Area (mAU·s)")
        ax.set_title(
            f"Peak area near {results['target_rt']:.3f} min"
        )
        ax.tick_params(axis="x", rotation=25)
        fig.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(chart_data["Label"], chart_data["Height (mAU)"])
        ax.set_ylabel("Height (mAU)")
        ax.set_title(
            f"Peak height near {results['target_rt']:.3f} min"
        )
        ax.tick_params(axis="x", rotation=25)
        fig.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

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
