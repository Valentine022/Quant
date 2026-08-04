from __future__ import annotations

import base64
import io
import re
import zipfile
from html import escape
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st


# Hard-coded upload location shown in the app and exported report.
# Replace this URL once with your real SharePoint/network web location.
UPLOAD_LOCATION_URL = "https://drive.google.com/drive/folders/1Q1esl-zOp91ddqjxvqj0CAehQ2wXOKTb?usp=sharing"
UPLOAD_LOCATION_LABEL = "Upload your reports to EVO Shared Data - 96 Well Plate"

# Access control: authorised Google accounts only.
ALLOWED_DOMAIN = "evoralis.com"
ALLOWED_EMAILS = {
    "daniel.kaute@evoralis.com",
    "mariana.rangel@evoralis.com",
    "josephin.holstein@evoralis.com",
    "tom.ogden@evoralis.com",
    "devanshi.singh@evoralis.com",
    "simona.pilotto@evoralis.com",
    "elizabeth.nganga@evoralis.com",
    "marcus.bage@evoralis.com",
    "adam.roberts@evoralis.com",
    "david.miranda@evoralis.com",
    "dylan.george@evoralis.com",
    "michaela.buerdsell@evoralis.com",
    "asha.webb@evoralis.com",
    "valentine.patterson@evoralis.com",
}


def get_user_value(name: str, default=None):
    """Read an OIDC claim from ``st.user`` safely."""
    try:
        value = getattr(st.user, name)
        if value is not None:
            return value
    except Exception:
        pass

    try:
        return st.user.get(name, default)
    except Exception:
        return default


def claim_is_true(value) -> bool:
    """Convert a string or boolean OIDC claim safely."""
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


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


def get_logo_data_uri() -> str | None:
    """Return the first available Evoralis logo as an embedded PNG data URI."""
    app_directory = Path(__file__).resolve().parent
    possible_logos = [
        app_directory / "EvoralisLogo.png",
        app_directory / "cropped-cropped-0_Evoralis_logo_for-emails_final_v2.png",
    ]
    for logo_path in possible_logos:
        if logo_path.exists():
            encoded_logo = base64.b64encode(logo_path.read_bytes()).decode("ascii")
            return f"data:image/png;base64,{encoded_logo}"
    return None


logo_html = get_logo_html()
logo_data_uri = get_logo_data_uri()


st.set_page_config(
    page_title="Peak Comparison",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------
# Authentication
# --------------------------------------------------

if not st.user.is_logged_in:
    st.markdown(
        """
        <style>
          .stApp { background: #e8f7f5; }
          header[data-testid="stHeader"],
          div[data-testid="stToolbar"] { display: none; }
          .block-container { max-width: 900px; padding-top: 2rem; }
          .login-card {
            display: flex; align-items: center; gap: 1.4rem;
            background: white; border: 1px solid #b9dfd8;
            border-radius: 18px; padding: 1.4rem 1.6rem; margin-bottom: 1.2rem;
          }
          .login-card h1 { margin: 0; }
          .login-card p { margin: .4rem 0 0; color: #555; }
          .evoralis-logo { height: 80px; width: auto; max-width: 220px; object-fit: contain; }
          .evoralis-wordmark {
            min-width: 190px; height: 72px; display: flex; align-items: center;
            justify-content: center; border-radius: 12px; background: #f0e8f7;
            border: 2px solid #9370DB; color: #7651c6; font-size: 1.35rem;
            font-weight: 850; letter-spacing: .12em;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="login-card">
          {logo_html}
          <div>
            <h1>HPLC Peak Comparison</h1>
            <p>This private application is available to authorised users.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info("Sign in with Google to continue.")
    if st.button(
        "Sign in with Google",
        key="google_login_button",
        type="primary",
        use_container_width=True,
    ):
        st.login()
    st.stop()

email = str(get_user_value("email", "") or "").strip().lower()
email_verified = claim_is_true(get_user_value("email_verified", False))
allowed_emails = {address.strip().lower() for address in ALLOWED_EMAILS if address.strip()}
is_authorised = email_verified and (
    email.endswith(f"@{ALLOWED_DOMAIN}") or email in allowed_emails
)

if not is_authorised:
    st.error("Access denied. Your Google account is not authorised to use this application.")
    if email:
        st.write(f"Signed-in email: **{email}**")
    if st.button("Sign out", key="unauthorised_logout_button", use_container_width=True):
        st.logout()
    st.stop()


# --------------------------------------------------
# Styling
# --------------------------------------------------

st.markdown(
    """
    <style>
      :root {
        --ev-bg: #e8f7f5;
        --ev-panel: #f9fffe;
        --ev-card: #ffffff;
        --ev-border: #b9dfd8;
        --ev-text: #1c2434;
        --ev-muted: #667085;
        --ev-purple: #9370DB;
        --ev-purple-dark: #9370DB;
        --ev-purple-soft: #f0e8f7;
        --ev-good: #18794e;
        --ev-warn: #9a6700;
        --ev-bad: #b42318;
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
        max-width: 1180px;
        padding-top: 1.8rem;
        padding-bottom: 3rem;
      }

      .hero {
        display: flex;
        align-items: center;
        gap: 1rem;
        background: #ffffff;
        border: 1px solid var(--ev-border);
        border-radius: 16px;
        padding: 1.25rem 1.55rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
      }

      .hero-text {
        flex: 1;
      }

      .hero h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
      }

      .hero p {
        margin: 0.35rem 0 0;
        font-size: 1.05rem;
        color: #555;
      }

      .evoralis-logo {
        height: 66px;
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
        background: #f1f3f6;
        border-right: 1px solid #d9dee7;
      }

      section[data-testid="stSidebar"] > div {
        padding-top: 1.5rem;
      }

      section[data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
      }

      section[data-testid="stSidebar"] h1,
      section[data-testid="stSidebar"] h2,
      section[data-testid="stSidebar"] h3 {
        color: var(--ev-text);
      }

      div[data-testid="stSelectbox"] > label,
      div[data-testid="stNumberInput"] > label,
      div[data-testid="stTextInput"] > label,
      div[data-testid="stFileUploader"] > label {
        color: var(--ev-text) !important;
        font-size: 1rem;
        font-weight: 650;
      }

      div[data-baseweb="select"] > div,
      div[data-testid="stTextInput"] input,
      div[data-testid="stNumberInput"] input {
        border-color: #d8dde6 !important;
        border-radius: 8px !important;
        background: #ffffff !important;
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
        background: #ff4b4b;
        border-color: #ff4b4b;
        color: white;
      }

      .stButton > button[kind="primary"]:hover {
        background: #e83f3f;
        border-color: #e83f3f;
      }

      h2, h3 {
        color: var(--ev-text);
      }

      html {
        scroll-behavior: smooth;
      }

      .topnav { display: none; }

      .section-anchor {
        position: relative;
        top: -96px;
        visibility: hidden;
      }

      .purple-section-header {
        margin: 1.4rem 0 0.75rem;
        padding: 0;
        border: 0;
        background: transparent;
        color: var(--ev-text);
        font-size: 1.55rem;
        font-weight: 750;
        line-height: 1.2;
      }

      .preview-nav {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        padding: 12px 14px;
        margin: 0.7rem 0 1rem;
        background: var(--ev-purple-soft);
        border-top: 1px solid #d7c8e9;
        border-bottom: 1px solid #d7c8e9;
      }

      .preview-nav a {
        display: inline-block;
        padding: 8px 13px;
        border-radius: 999px;
        background: var(--ev-purple);
        color: white !important;
        text-decoration: none !important;
        font-weight: 700;
      }



      .combined-report-header {
        display: flex;
        align-items: center;
        gap: 30px;
        padding: 28px 20px 26px;
        margin: 0.8rem 0 1.4rem;
        border-top: 1px solid #d7c8e9;
        border-bottom: 1px solid #d7c8e9;
        background: transparent;
      }

      .combined-report-header .report-logo-wrap {
        width: 125px;
        flex: 0 0 125px;
        display: flex;
        justify-content: center;
        align-items: center;
      }

      .combined-report-header .report-logo-wrap img {
        width: 100%;
        height: auto;
        max-height: 96px;
        object-fit: contain;
      }

      .combined-report-header .report-copy {
        flex: 1;
        min-width: 0;
      }

      .combined-report-header h1 {
        margin: 0 0 12px;
        color: var(--ev-text);
        font-size: clamp(2rem, 4vw, 3.3rem);
        line-height: 1.05;
        font-weight: 800;
        letter-spacing: -0.02em;
      }

      .combined-report-header p {
        margin: 7px 0;
        color: #66738f;
        font-size: 1.22rem;
        line-height: 1.25;
      }

      .combined-report-header p strong {
        color: #66738f;
      }

      @media (max-width: 700px) {
        .combined-report-header {
          align-items: flex-start;
          gap: 18px;
          padding-left: 0;
          padding-right: 0;
        }
        .combined-report-header .report-logo-wrap {
          width: 86px;
          flex-basis: 86px;
        }
        .combined-report-header h1 {
          font-size: 2rem;
        }
        .combined-report-header p {
          font-size: 1rem;
        }
      }

      .upload-guide {
        margin: 0.15rem 0 0.8rem;
        color: var(--ev-muted);
      }

      .upload-guide a {
        color: #0b66c3;
        font-weight: 650;
      }

      .result-panel {
        background: white;
        border: 1px solid var(--ev-border);
        border-radius: 14px;
        padding: 0.9rem;
        margin-bottom: 1rem;
      }

      /* Keep the sidebar visible and remove its collapse control. */
      section[data-testid="stSidebar"] {
        min-width: 21rem !important;
        width: 21rem !important;
        transform: none !important;
      }

      button[data-testid="stSidebarCollapseButton"],
      button[data-testid="collapsedControl"] {
        display: none !important;
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
          Upload a peak report, generate the comparison, and download a report.
          Upload the finished report to the shared location.
        </p>
      </div>
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
                facecolor = plt.cm.RdYlGn(normalized)
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
    cmap=plt.cm.RdYlGn,
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


def figure_to_png_bytes(figure) -> bytes:
    """Render a Matplotlib figure to PNG bytes."""
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=220, bbox_inches="tight")
    buffer.seek(0)
    return buffer.getvalue()


def build_html_report(
    *,
    report_title: str,
    plate_name: str,
    analyst_name: str,
    upload_location_url: str,
    logo_uri: str | None,
    target_rt: float,
    tolerance: float,
    plate_metric: str,
    results_table: pd.DataFrame,
    plate_png: bytes,
    peak_area_png: bytes | None,
    peak_area_html: str | None,
) -> str:
    """Build a self-contained HTML report with images embedded as data URIs."""
    report_date = datetime.now().strftime("%Y-%m-%d")
    analyst_display = analyst_name.strip() or "Not specified"
    safe_upload_url = upload_location_url.replace('"', '%22')
    if logo_uri:
        report_logo = f'<img class="report-logo" src="{logo_uri}" alt="Evoralis">'
    else:
        report_logo = '<div class="report-wordmark">EVORALIS</div>'
    table_html = results_table.to_html(
        index=False,
        border=0,
        na_rep="—",
        classes="results-table",
        float_format=lambda value: f"{value:,.3f}",
    )

    plate_data_uri = "data:image/png;base64," + base64.b64encode(plate_png).decode("ascii")
    peak_area_section = ""
    if peak_area_html:
        peak_area_section = (
            '<section class="card" id="peak-area"><h2 class="section-bar">Peak area</h2>'
            '<p class="chart-help">Hover for sample details. Drag to zoom, double-click to reset, or use the toolbar.</p>'
            f'<div class="interactive-chart">{peak_area_html}</div></section>'
        )
    elif peak_area_png is not None:
        peak_area_data_uri = (
            "data:image/png;base64," + base64.b64encode(peak_area_png).decode("ascii")
        )
        peak_area_section = (
            '<section class="card" id="peak-area"><h2 class="section-bar">Peak area</h2>'
            f'<img src="{peak_area_data_uri}" alt="Peak area plot"></section>'
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{report_title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 0; background: #e8f7f5; color: #1c2434; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px; }}
    .card {{ background: white; border: 1px solid #b9dfd8; border-radius: 14px; padding: 24px; margin-bottom: 22px; scroll-margin-top: 90px; }}
    h1, h2 {{ margin-top: 0; }}
    .report-masthead {{ display: flex; align-items: center; gap: 22px; background: white; border: 1px solid #b9dfd8; border-radius: 16px; padding: 20px 24px; margin-bottom: 14px; }}
    .report-masthead-logo {{ width: 105px; flex: 0 0 105px; display: flex; align-items: center; justify-content: center; }}
    .report-masthead-logo .report-logo {{ max-width: 100px; max-height: 74px; }}
    .report-masthead-copy {{ flex: 1; min-width: 0; }}
    .report-masthead-copy h1 {{ margin: 0 0 8px; font-size: 2rem; line-height: 1.1; }}
    .report-masthead-copy p {{ margin: 0; color: #667085; font-size: 1rem; }}
    .report-masthead-copy a {{ color: #0b66c3; font-weight: 700; }}
    .report-nav {{ position: sticky; top: 0; z-index: 20; display: flex; align-items: center; gap: 9px; flex-wrap: wrap; padding: 12px 14px; margin-bottom: 24px; background: #f0e8f7; border: 1px solid #d7c8e9; border-radius: 14px; }}
    .report-nav a {{ display: inline-block; padding: 9px 15px; border-radius: 999px; background: #9370DB; color: white; text-decoration: none; font-weight: 700; }}
    .report-nav a:hover {{ background: #7651c6; }}
    .combined-header {{ display: flex; align-items: center; gap: 30px; padding: 32px 4px 30px; margin-bottom: 24px; border-top: 1px solid #d7c8e9; border-bottom: 1px solid #d7c8e9; }}
    .combined-logo {{ width: 130px; flex: 0 0 130px; display: flex; align-items: center; justify-content: center; }}
    .combined-logo .report-logo {{ max-width: 125px; max-height: 100px; }}
    .combined-copy {{ flex: 1; min-width: 0; }}
    .combined-copy h1 {{ margin: 0 0 14px; font-size: 3.1rem; line-height: 1.05; letter-spacing: -0.02em; }}
    .combined-copy p {{ margin: 7px 0; color: #66738f; font-size: 1.2rem; }}
    .combined-copy a {{ color: #0b66c3; font-weight: 700; }}
    @media (max-width: 700px) {{
      .report-masthead {{ align-items: flex-start; gap: 14px; padding: 16px; }}
      .report-masthead-logo {{ width: 72px; flex-basis: 72px; }}
      .report-masthead-copy h1 {{ font-size: 1.55rem; }}
      .report-nav {{ position: static; }}
      .combined-header {{ align-items: flex-start; gap: 18px; }}
      .combined-logo {{ width: 88px; flex-basis: 88px; }}
      .combined-copy h1 {{ font-size: 2rem; }}
    }}
    .report-header {{ display: flex; align-items: center; gap: 22px; flex-wrap: wrap; }}
    .report-logo {{ width: auto; max-width: 230px; max-height: 86px; border-radius: 0; }}
    .report-wordmark {{ padding: 18px 24px; border: 2px solid #9370DB; color: #7651c6; font-weight: 850; letter-spacing: .12em; border-radius: 12px; }}
    .report-heading {{ flex: 1; min-width: 260px; }}
    .upload-link {{ display: inline-block; margin-top: 8px; padding: 9px 14px; border-radius: 999px; background: #9370DB; color: white; text-decoration: none; font-weight: 700; }}
    .section-bar {{ margin: -24px -24px 20px; padding: 13px 20px; border-radius: 13px 13px 0 0; background: #9370DB; color: white; }}
    .meta {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 20px; }}
    .meta div {{ background: #f0e8f7; border-radius: 10px; padding: 12px; }}
    img {{ display: block; width: 100%; height: auto; border-radius: 10px; }}
    .results-table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
    .results-table th, .results-table td {{ border-bottom: 1px solid #dce7e5; padding: 9px; text-align: left; }}
    .results-table th {{ background: #9370DB; color: white; }}
    .chart-help {{ margin: 0 0 12px; color: #667085; }}
    .interactive-chart {{ width: 100%; min-height: 480px; }}
    .interactive-chart .plotly-graph-div {{ width: 100% !important; }}
  </style>
</head>
<body>
<main>
  <header class="report-masthead" id="report-top">
    <div class="report-masthead-logo">{report_logo}</div>
    <div class="report-masthead-copy">
      <h1>HPLC Peak Comparison</h1>
      <p>Peak comparison and 96-well plate report. <a href="{safe_upload_url}" target="_blank" rel="noopener noreferrer">{UPLOAD_LOCATION_LABEL}</a></p>
    </div>
  </header>
  <nav class="report-nav" aria-label="Report sections">
    <a href="#input-data">Input data</a>
    <a href="#plate-view">96-Well plate</a>
    <a href="#results-table">Results</a>
    <a href="#peak-area">Peak area</a>
    <a href="#report-top">Top</a>
  </nav>
  <section class="combined-header" id="input-data">
    <div class="combined-logo">{report_logo}</div>
    <div class="combined-copy">
      <h1>{escape(plate_name)} &ndash; Combined report</h1>
      <p><strong>Prepared by:</strong> {escape(analyst_display)}</p>
      <p><strong>Samples:</strong> {len(results_table)}</p>
      <p><strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
      <p><a href="{safe_upload_url}" target="_blank" rel="noopener noreferrer">{UPLOAD_LOCATION_LABEL}</a></p>
    </div>
  </section>
  <section class="card" id="plate-view">
    <h2 class="section-bar">96-well plate</h2>
    <img src="{plate_data_uri}" alt="96-well plate plot">
  </section>
  <section class="card" id="results-table">
    <h2 class="section-bar">Results table</h2>
    {table_html}
  </section>
  {peak_area_section}
</main>
</body>
</html>"""


def make_html_export_zip(
    *,
    report_html: str,
    csv_bytes: bytes,
    plate_png: bytes,
    peak_area_png: bytes | None,
    export_name: str,
) -> bytes:
    """Package the HTML report, results CSV, and plot images into one ZIP."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("report.html", report_html.encode("utf-8"))
        archive.writestr(f"{export_name}_results.csv", csv_bytes)
        archive.writestr("images/plate.png", plate_png)
        if peak_area_png is not None:
            archive.writestr("images/peak_area.png", peak_area_png)
    buffer.seek(0)
    return buffer.getvalue()


# --------------------------------------------------
# Sidebar controls
# --------------------------------------------------

with st.sidebar:
    st.success(f"Signed in as {email}")
    if st.button(
        "Sign out",
        key="authorised_logout_button",
        use_container_width=True,
    ):
        st.logout()
    st.divider()

    st.markdown('<div id="settings" class="section-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="purple-section-header">Report settings</div>',
        unsafe_allow_html=True,
    )

    plate_name = st.text_input(
        "Sample / plate name",
        value="HPLC Peak Comparison",
        help="Used as the report heading and the 96-well plate plot title.",
    )

    signed_in_name = str(get_user_value("name", "") or "").strip()
    default_analyst = signed_in_name or email.split("@", 1)[0].replace(".", " ").title()
    analyst_name = st.text_input(
        "User / analyst name",
        value=default_analyst,
        help="Added to the exported HTML report.",
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
safe_upload_url = UPLOAD_LOCATION_URL.replace('"', '%22')
st.markdown(
    f'<div class="upload-guide">Upload the source peak report below. '
    f'Finished reports should be stored in '
    f'<a href="{safe_upload_url}" target="_blank" rel="noopener noreferrer">the shared upload location</a>.</div>',
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
        "analyst_name": analyst_name.strip(),
        "upload_location_url": UPLOAD_LOCATION_URL,
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

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    analyst_display = results["analyst_name"] or "Not specified"
    sample_count = len(comparison)
    st.markdown('<div id="input-data" class="section-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <section class="combined-report-header">
          <div class="report-logo-wrap">{logo_html}</div>
          <div class="report-copy">
            <h1>{escape(results["plate_name"])} &ndash; Combined report</h1>
            <p><strong>Prepared by:</strong> {escape(analyst_display)}</p>
            <p><strong>Samples:</strong> {sample_count}</p>
            <p><strong>Generated:</strong> {generated_at}</p>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
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
    plate_png = figure_to_png_bytes(plate_figure)
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
    peak_area_png = None
    peak_area_html = None

    if plot_data.empty:
        st.warning("No matched peak-area values are available to plot.")
    else:
        plot_data["Sample order"] = range(1, len(plot_data) + 1)

        peak_area_plot = px.scatter(
            plot_data,
            x="Sample order",
            y="Area (mAU·s)",
            hover_data={
                "Well": True,
                "Sample name": True,
                "Sample order": True,
                "Area (mAU·s)": ":,.3f",
            },
            title=(
                f"{results['plate_name']} — Peak area near "
                f"{results['target_rt']:.3f} min"
            ),
        )
        peak_area_plot.update_traces(marker={"size": 11})
        peak_area_plot.update_layout(
            xaxis_title="Sample order",
            yaxis_title="Area (mAU·s)",
            hovermode="closest",
            margin={"l": 60, "r": 30, "t": 70, "b": 55},
        )
        st.plotly_chart(
            peak_area_plot,
            use_container_width=True,
            config={"displaylogo": False, "responsive": True},
        )

        # Self-contained Plotly fragment for the downloaded HTML report.
        # include_plotlyjs=True embeds the JavaScript, so the chart works offline.
        peak_area_html = pio.to_html(
            peak_area_plot,
            include_plotlyjs=True,
            full_html=False,
            config={"displaylogo": False, "responsive": True},
            default_width="100%",
            default_height="520px",
        )

        # Keep a PNG fallback in the ZIP package.
        peak_area_figure, peak_area_axis = plt.subplots(figsize=(11, 5.5))
        peak_area_axis.scatter(
            plot_data["Sample order"],
            plot_data["Area (mAU·s)"],
            s=90,
        )
        peak_area_axis.set_xlabel("Sample order")
        peak_area_axis.set_ylabel("Area (mAU·s)")
        peak_area_axis.set_title(
            f"{results['plate_name']} — Peak area near {results['target_rt']:.3f} min"
        )
        peak_area_axis.grid(True, alpha=0.25)
        peak_area_figure.tight_layout()
        peak_area_png = figure_to_png_bytes(peak_area_figure)
        plt.close(peak_area_figure)

        st.caption("Each dot represents one sample and its matched peak area.")

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

    export_date = datetime.now().strftime("%Y-%m-%d")

    def filename_part(value: str, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
        return cleaned.strip("._-") or fallback

    sample_filename = filename_part(results["plate_name"], "sample")
    user_filename = filename_part(results["analyst_name"], "user")
    export_name = f"{export_date}_{sample_filename}_{user_filename}"

    st.markdown('<div id="download-results" class="section-anchor"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="purple-section-header">Download</div>',
        unsafe_allow_html=True,
    )

    csv_bytes = make_export_table(basic_table)
    report_html = build_html_report(
        report_title=results["title"],
        plate_name=results["plate_name"],
        analyst_name=results["analyst_name"],
        upload_location_url=results["upload_location_url"],
        logo_uri=logo_data_uri,
        target_rt=results["target_rt"],
        tolerance=results["tolerance"],
        plate_metric=plate_metric,
        results_table=basic_table,
        plate_png=plate_png,
        peak_area_png=peak_area_png,
        peak_area_html=peak_area_html,
    )
    html_bytes = report_html.encode("utf-8")
    zip_bytes = make_html_export_zip(
        report_html=report_html,
        csv_bytes=csv_bytes,
        plate_png=plate_png,
        peak_area_png=peak_area_png,
        export_name=export_name,
    )

    st.download_button(
        "Download HTML report",
        data=html_bytes,
        file_name=f"{export_name}.html",
        mime="text/html",
        use_container_width=True,
    )

    st.download_button(
        "Download HTML report folder (ZIP)",
        data=zip_bytes,
        file_name=f"{export_name}_report_folder.zip",
        mime="application/zip",
        use_container_width=True,
    )

    st.download_button(
        "Download results CSV",
        data=csv_bytes,
        file_name=f"{export_name}_results.csv",
        mime="text/csv",
        use_container_width=True,
    )
