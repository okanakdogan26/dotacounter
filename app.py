from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = "https://api.opendota.com/api"
STEAM_CDN_BASE_URL = "https://cdn.cloudflare.steamstatic.com"
STEAM_HERO_IMAGE_BASE_URL = f"{STEAM_CDN_BASE_URL}/apps/dota2/images/dota_react/heroes"
ROLE_OPTIONS = ["All", "Carry", "Support", "Mid", "Offlane", "Disabler", "Durable"]
REQUEST_TIMEOUT = 30
DEFAULT_MIN_GAMES_THRESHOLD = 50
DATA_DIR = Path(__file__).parent / "data"
DOTABUFF_DATASET_PATH = DATA_DIR / "dotabuff_worst_versus.json"
ALLY_SYNERGY_MAP = {
    "Faceless Void": {
        "Dark Seer": 8.5,
        "Jakiro": 8.0,
        "Invoker": 7.8,
        "Phoenix": 7.6,
        "Shadow Fiend": 7.4,
        "Snapfire": 7.0,
        "Skywrath Mage": 6.6,
        "Witch Doctor": 6.5,
        "Ancient Apparition": 6.3,
        "Lina": 6.1,
        "Disruptor": 5.9,
        "Leshrac": 5.7,
        "Death Prophet": 5.5,
        "Ringmaster": 5.2,
    },
    "Magnus": {
        "Dark Seer": 7.8,
        "Phoenix": 7.4,
        "Jakiro": 6.8,
        "Shadow Fiend": 6.7,
        "Earthshaker": 6.5,
        "Invoker": 6.3,
        "Lina": 6.1,
        "Snapfire": 5.9,
        "Leshrac": 5.6,
        "Disruptor": 5.3,
    },
    "Enigma": {
        "Phoenix": 7.6,
        "Jakiro": 7.2,
        "Snapfire": 6.8,
        "Invoker": 6.7,
        "Shadow Fiend": 6.4,
        "Lina": 6.2,
        "Leshrac": 5.8,
        "Disruptor": 5.6,
        "Ringmaster": 5.4,
        "Death Prophet": 5.2,
    },
    "Mars": {
        "Phoenix": 8.2,
        "Snapfire": 7.8,
        "Invoker": 7.0,
        "Jakiro": 6.6,
        "Skywrath Mage": 6.3,
        "Dark Seer": 6.2,
        "Lina": 5.9,
        "Leshrac": 5.8,
        "Shadow Demon": 5.6,
        "Disruptor": 5.4,
        "Ringmaster": 5.2,
    },
}
ROLE_SYNERGY_WEIGHTS = {
    "Carry": {"Support": 1.2, "Disabler": 1.0, "Initiator": 0.8, "Durable": 0.4},
    "Support": {"Carry": 1.2, "Initiator": 0.9, "Durable": 0.5, "Pusher": 0.4},
    "Disabler": {"Nuker": 1.4, "Carry": 1.0, "Support": 0.5, "Pusher": 0.3},
    "Initiator": {"Nuker": 1.6, "Disabler": 1.1, "Carry": 0.8, "Support": 0.4},
    "Nuker": {"Disabler": 0.9, "Initiator": 0.8, "Carry": 0.4},
    "Durable": {"Nuker": 0.8, "Disabler": 0.8, "Support": 0.4},
    "Escape": {"Support": 0.6, "Disabler": 0.5},
    "Pusher": {"Durable": 0.6, "Support": 0.5, "Initiator": 0.4},
}
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def matches_role_filter(roles: list[str] | object, selected_role: str) -> bool:
    """Match UI roles against OpenDota roles and a few inferred lane heuristics."""
    normalized_roles = roles if isinstance(roles, list) else []
    role_set = set(normalized_roles)

    if selected_role == "All":
        return True
    if selected_role in {"Carry", "Support", "Disabler", "Durable"}:
        return selected_role in role_set
    if selected_role == "Mid":
        # OpenDota does not expose "Mid" directly in hero roles, so infer it from
        # common mid hero traits while excluding hard supports.
        return (
            "Support" not in role_set
            and bool(role_set.intersection({"Carry", "Nuker", "Escape", "Disabler"}))
        )
    if selected_role == "Offlane":
        # OpenDota does not expose "Offlane" directly either; durable initiators
        # and utility frontliners are the closest approximation.
        return (
            "Support" not in role_set
            and bool(role_set.intersection({"Durable", "Initiator", "Disabler"}))
        )
    return False


def get_hero_image_url(image_path: str | None, hero_name: str | None = None) -> str:
    """Convert OpenDota hero metadata into a full Steam CDN image URL."""
    normalized_image_path = image_path if isinstance(image_path, str) else ""
    normalized_hero_name = hero_name if isinstance(hero_name, str) else ""

    if not normalized_image_path:
        if normalized_hero_name:
            hero_slug = normalized_hero_name.removeprefix("npc_dota_hero_")
            return f"{STEAM_HERO_IMAGE_BASE_URL}/{hero_slug}.png"
        return ""
    if normalized_image_path.startswith("http://") or normalized_image_path.startswith("https://"):
        return normalized_image_path
    if normalized_image_path.startswith("/apps/dota2/images/dota_react/heroes/"):
        return f"{STEAM_CDN_BASE_URL}{normalized_image_path}"
    return (
        f"{STEAM_HERO_IMAGE_BASE_URL}/"
        f"{normalized_image_path.rsplit('/', 1)[-1].replace('.full.png', '.png')}"
    )


def render_selected_hero_grid(selected_hero_names: list[str], hero_df: pd.DataFrame) -> None:
    """Render selected enemy heroes as a polished compact grid."""
    selected_df = hero_df[hero_df["localized_name"].isin(selected_hero_names)].copy()
    if selected_df.empty:
        return

    selected_df["image_url"] = selected_df.apply(
        lambda row: get_hero_image_url(row["img"], row.get("name")), axis=1
    )
    card_html = "".join(
        (
            '<div class="enemy-hero-card">'
            f'<img src="{hero_row["image_url"]}" alt="{hero_row["localized_name"]}" class="enemy-hero-image" />'
            f'<div class="enemy-hero-name">{hero_row["localized_name"]}</div>'
            "</div>"
        )
        for _, hero_row in selected_df.iterrows()
    )
    st.markdown(f'<div class="enemy-heroes-grid">{card_html}</div>', unsafe_allow_html=True)


def render_counter_cards(results_df: pd.DataFrame) -> None:
    """Render top counter heroes as polished visual cards."""
    top_results = results_df.head(5)
    if top_results.empty:
        return

    st.subheader("Top Counter Picks")
    cards: list[str] = []
    for _, hero_row in top_results.iterrows():
        has_opendota_data = int(hero_row["games_played"]) > 0
        win_rate_text = (
            f"%{hero_row['win_rate']:.2f}"
            if has_opendota_data
            else "N/A (Dotabuff-only)"
        )
        games_text = str(int(hero_row["games_played"])) if has_opendota_data else "No OpenDota data"
        synergy_badge = (
            f'<span class="counter-card-pill synergy">Synergy {hero_row["synergy_score"]:.1f}</span>'
            if float(hero_row.get("synergy_score", 0.0)) > 0
            else ""
        )
        cards.append(
            '<div class="counter-card">'
            '<div class="counter-card-topline">'
            f'<span class="counter-card-pill primary">Hybrid {hero_row["hybrid_score"]:.2f}</span>'
            f"{synergy_badge}"
            "</div>"
            f'<img src="{hero_row["image_url"]}" alt="{hero_row["localized_name"]}" class="counter-card-image" />'
            f'<div class="counter-card-name">{hero_row["localized_name"]}</div>'
            f'<div class="counter-card-meta">Win Rate: {win_rate_text}</div>'
            f'<div class="counter-card-meta">Matches: {games_text}</div>'
            "</div>"
        )
    st.markdown(f'<div class="counter-cards-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def inject_app_theme() -> None:
    """Inject the app-wide visual theme."""
    st.markdown(
        """
        <style>
        :root {
            --bg-main: #f4f1e8;
            --bg-panel: rgba(255, 255, 255, 0.76);
            --bg-panel-strong: rgba(255, 255, 255, 0.9);
            --bg-select: rgba(255,255,255,0.82);
            --border-soft: rgba(44, 56, 72, 0.12);
            --text-main: #232a36;
            --text-muted: #6f7888;
            --accent-gold: #cf8b17;
            --accent-teal: #0f8b8d;
            --shadow-soft: 0 18px 40px rgba(31, 38, 49, 0.08);
            --app-bg:
                radial-gradient(circle at top left, rgba(207, 139, 23, 0.14), transparent 28%),
                radial-gradient(circle at top right, rgba(15, 139, 141, 0.12), transparent 24%),
                linear-gradient(180deg, #f6f2e9 0%, #ede8dc 100%);
            --sidebar-bg: linear-gradient(180deg, rgba(251, 249, 244, 0.96), rgba(240, 236, 226, 0.96));
            --card-bg: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(250,247,241,0.9));
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --bg-main: #0f141b;
                --bg-panel: rgba(22, 29, 39, 0.82);
                --bg-panel-strong: rgba(26, 34, 46, 0.94);
                --bg-select: rgba(24, 31, 42, 0.92);
                --border-soft: rgba(171, 185, 204, 0.14);
                --text-main: #edf2f7;
                --text-muted: #9aa7bb;
                --shadow-soft: 0 18px 40px rgba(0, 0, 0, 0.26);
                --app-bg:
                    radial-gradient(circle at top left, rgba(207, 139, 23, 0.12), transparent 28%),
                    radial-gradient(circle at top right, rgba(15, 139, 141, 0.12), transparent 24%),
                    linear-gradient(180deg, #111821 0%, #0b1118 100%);
                --sidebar-bg: linear-gradient(180deg, rgba(16, 22, 31, 0.98), rgba(12, 18, 26, 0.98));
                --card-bg: linear-gradient(180deg, rgba(26,34,46,0.94), rgba(18,24,33,0.92));
            }
        }
        html[data-theme="dark"],
        body[data-theme="dark"],
        [data-theme="dark"] {
            --bg-main: #0f141b;
            --bg-panel: rgba(22, 29, 39, 0.82);
            --bg-panel-strong: rgba(26, 34, 46, 0.94);
            --bg-select: rgba(24, 31, 42, 0.92);
            --border-soft: rgba(171, 185, 204, 0.14);
            --text-main: #edf2f7;
            --text-muted: #9aa7bb;
            --shadow-soft: 0 18px 40px rgba(0, 0, 0, 0.26);
            --app-bg:
                radial-gradient(circle at top left, rgba(207, 139, 23, 0.12), transparent 28%),
                radial-gradient(circle at top right, rgba(15, 139, 141, 0.12), transparent 24%),
                linear-gradient(180deg, #111821 0%, #0b1118 100%);
            --sidebar-bg: linear-gradient(180deg, rgba(16, 22, 31, 0.98), rgba(12, 18, 26, 0.98));
            --card-bg: linear-gradient(180deg, rgba(26,34,46,0.94), rgba(18,24,33,0.92));
        }
        .stApp {
            background: var(--app-bg);
            color: var(--text-main);
        }
        .block-container {
            padding-top: 2.2rem;
            padding-bottom: 3rem;
            max-width: 1400px;
        }
        [data-testid="stSidebar"] {
            background: var(--sidebar-bg);
            border-right: 1px solid rgba(44, 56, 72, 0.08);
        }
        div[data-baseweb="select"] > div {
            background: var(--bg-select);
            border: 1px solid var(--border-soft);
            border-radius: 16px;
            box-shadow: none;
        }
        div[data-baseweb="tag"] {
            background: linear-gradient(135deg, #c75b4b, #dd7d5d);
            border-radius: 999px;
        }
        div[data-baseweb="tag"] span {
            color: white !important;
            font-weight: 700;
        }
        .summary-strip {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.9rem;
            margin: 1rem 0 1.4rem;
        }
        .enemy-heroes-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.8rem;
            margin-bottom: 0.8rem;
        }
        .summary-card {
            background: var(--bg-panel-strong);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border-soft);
            border-radius: 18px;
            padding: 1rem 1rem 0.95rem;
            box-shadow: var(--shadow-soft);
        }
        .summary-label {
            color: var(--text-muted);
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 0.45rem;
            font-weight: 700;
        }
        .summary-value {
            color: var(--text-main);
            font-size: 1.15rem;
            font-weight: 800;
            line-height: 1.2;
        }
        .summary-subtle {
            color: var(--text-muted);
            font-size: 0.86rem;
            margin-top: 0.25rem;
        }
        .enemy-hero-card {
            background: var(--bg-panel);
            border: 1px solid var(--border-soft);
            border-radius: 16px;
            padding: 0.55rem;
            box-shadow: var(--shadow-soft);
            text-align: center;
            margin-bottom: 0.45rem;
        }
        .enemy-hero-image {
            width: 100%;
            border-radius: 12px;
            display: block;
            margin-bottom: 0.5rem;
        }
        .enemy-hero-name {
            color: var(--text-main);
            font-weight: 800;
            font-size: 0.88rem;
            letter-spacing: -0.01em;
            line-height: 1.2;
        }
        .counter-card {
            background: var(--card-bg);
            border: 1px solid var(--border-soft);
            border-radius: 16px;
            padding: 0.55rem;
            box-shadow: var(--shadow-soft);
            margin-bottom: 0.45rem;
        }
        .counter-cards-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.8rem;
            margin-bottom: 0.8rem;
        }
        .counter-card-topline {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-bottom: 0.45rem;
        }
        .counter-card-pill {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.22rem 0.5rem;
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.01em;
        }
        .counter-card-pill.primary {
            background: rgba(207, 139, 23, 0.14);
            color: #8a5a09;
        }
        .counter-card-pill.synergy {
            background: rgba(15, 139, 141, 0.12);
            color: #0b6f70;
        }
        @media (prefers-color-scheme: dark) {
            .counter-card-pill.primary {
                background: rgba(207, 139, 23, 0.2);
                color: #ffd488;
            }
            .counter-card-pill.synergy {
                background: rgba(15, 139, 141, 0.2);
                color: #8de5e1;
            }
        }
        html[data-theme="dark"] .counter-card-pill.primary,
        body[data-theme="dark"] .counter-card-pill.primary,
        [data-theme="dark"] .counter-card-pill.primary {
            background: rgba(207, 139, 23, 0.2);
            color: #ffd488;
        }
        html[data-theme="dark"] .counter-card-pill.synergy,
        body[data-theme="dark"] .counter-card-pill.synergy,
        [data-theme="dark"] .counter-card-pill.synergy {
            background: rgba(15, 139, 141, 0.2);
            color: #8de5e1;
        }
        .counter-card-image {
            width: 100%;
            border-radius: 12px;
            display: block;
            margin-bottom: 0.45rem;
        }
        .counter-card-name {
            color: var(--text-main);
            font-size: 0.9rem;
            font-weight: 800;
            letter-spacing: -0.01em;
            margin-bottom: 0.2rem;
            line-height: 1.2;
        }
        .counter-card-meta {
            color: var(--text-muted);
            font-size: 0.76rem;
            line-height: 1.35;
        }
        h1, h2, h3 {
            color: var(--text-main);
            letter-spacing: -0.03em;
        }
        div[data-testid="stCaptionContainer"] {
            color: var(--text-muted);
        }
        .enemy-draft-shell {
            background: linear-gradient(180deg, #171c24 0%, #11161d 100%);
            border: 1px solid rgba(255, 184, 0, 0.18);
            border-radius: 18px;
            padding: 1rem 1.1rem 1.2rem;
            margin: 0.8rem 0 1.2rem;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
        }
        .enemy-draft-title {
            color: #f3f5f7;
            font-size: 1.55rem;
            font-weight: 800;
            letter-spacing: 0.01em;
            margin: 0;
        }
        .enemy-draft-subtitle {
            color: #8ea0b5;
            font-size: 0.86rem;
            margin-top: 0.2rem;
        }
        .hero-selection-shell {
            background: linear-gradient(180deg, #171c24 0%, #11161d 100%);
            border: 1px solid rgba(64, 236, 217, 0.18);
            border-radius: 18px;
            padding: 1rem 1.1rem 1.2rem;
            margin: 0.8rem 0 1.2rem;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
        }
        .panel-heading {
            color: #f3f5f7;
            font-size: 1.15rem;
            font-weight: 800;
            letter-spacing: 0.06em;
            margin-bottom: 0.8rem;
            text-transform: uppercase;
        }
        div[data-testid="stButton"] button[kind="secondary"],
        div[data-testid="stButton"] button[kind="tertiary"] {
            border-radius: 12px;
        }
        .slot-label {
            color: #8ea0b5;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.35rem;
        }
        @media (max-width: 1200px) {
            .enemy-heroes-grid,
            .counter-cards-grid {
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }
        }
        @media (max-width: 1100px) {
            .summary-strip {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 820px) {
            .block-container {
                padding-top: 1.25rem;
                padding-left: 1rem;
                padding-right: 1rem;
            }
            h1 {
                font-size: 2.2rem !important;
            }
            .summary-strip,
            .enemy-heroes-grid,
            .counter-cards-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.65rem;
            }
            .summary-card {
                padding: 0.85rem 0.85rem 0.8rem;
            }
        }
        @media (max-width: 560px) {
            .summary-strip,
            .enemy-heroes-grid,
            .counter-cards-grid {
                grid-template-columns: minmax(0, 1fr);
            }
            .enemy-hero-card,
            .counter-card {
                padding: 0.5rem;
            }
            .enemy-hero-name,
            .counter-card-name {
                font-size: 0.84rem;
            }
            .counter-card-meta {
                font-size: 0.72rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_summary_strip(
    selected_hero_names: list[str],
    selected_role: str,
    min_games_threshold: int,
    show_synergy: bool,
    ally_hero_names: list[str],
) -> None:
    """Render a compact status strip for the current filters."""
    synergy_value = ", ".join(ally_hero_names) if show_synergy and ally_hero_names else "Disabled"
    enemy_value = ", ".join(selected_hero_names) if selected_hero_names else "No enemies selected"
    st.markdown(
        f"""
        <div class="summary-strip">
            <div class="summary-card">
                <div class="summary-label">Enemy Draft</div>
                <div class="summary-value">{len(selected_hero_names)}/5 selected</div>
                <div class="summary-subtle">{enemy_value}</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">Role Focus</div>
                <div class="summary-value">{selected_role}</div>
                <div class="summary-subtle">Filtering the recommendation pool</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">Sample Threshold</div>
                <div class="summary-value">{min_games_threshold} matches</div>
                <div class="summary-subtle">Lower this if the pool becomes sparse</div>
            </div>
            <div class="summary-card">
                <div class="summary-label">Synergy Mode</div>
                <div class="summary-value">{'Active' if show_synergy and ally_hero_names else 'Off'}</div>
                <div class="summary-subtle">{synergy_value}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_ally_synergy_scores(hero_df: pd.DataFrame, ally_hero_names: Iterable[str] | None) -> dict[str, float]:
    """Return combined synergy scores using explicit combos plus role-based inference."""
    if not ally_hero_names:
        return {}

    hero_roles_lookup = hero_df.set_index("localized_name")["roles"].to_dict()
    candidate_names = hero_df["localized_name"].dropna().tolist()
    combined_scores: dict[str, float] = {}

    for hero_name in ally_hero_names:
        ally_roles = hero_roles_lookup.get(hero_name, [])

        for candidate_name in candidate_names:
            if candidate_name == hero_name:
                continue

            candidate_roles = hero_roles_lookup.get(candidate_name, [])
            inferred_score = 0.0
            for ally_role in ally_roles:
                role_weights = ROLE_SYNERGY_WEIGHTS.get(ally_role, {})
                for candidate_role in candidate_roles:
                    inferred_score += role_weights.get(candidate_role, 0.0)

            # Keep inferred synergy broad but weaker than hand-tuned combos.
            if inferred_score > 0:
                combined_scores[candidate_name] = combined_scores.get(candidate_name, 0.0) + min(
                    inferred_score, 3.5
                )

        for synergy_hero, score in ALLY_SYNERGY_MAP.get(hero_name, {}).items():
            combined_scores[synergy_hero] = combined_scores.get(synergy_hero, 0.0) + score

    return combined_scores


def render_sidebar(hero_df: pd.DataFrame) -> tuple[list[str], str, int, bool, list[str]]:
    """Render sidebar controls and return current selections."""
    hero_names = hero_df["localized_name"].sort_values().tolist()

    st.sidebar.header("Filters")
    selected_heroes = st.sidebar.multiselect(
        "Enemy heroes",
        options=hero_names,
        max_selections=5,
        help="Select up to 5 enemy heroes.",
    )
    selected_role = st.sidebar.selectbox("Role filter", ROLE_OPTIONS)
    show_synergy = st.sidebar.checkbox(
        "Show Synergy",
        value=False,
        help="Boost counter picks that also work especially well with selected ally heroes.",
    )
    ally_hero_names: list[str] = []
    if show_synergy:
        ally_options = [hero_name for hero_name in hero_names if hero_name not in selected_heroes]
        ally_hero_names = st.sidebar.multiselect(
            "Ally heroes",
            options=ally_options,
            max_selections=5,
            help="For example, add Faceless Void to prioritize Chronosphere follow-up heroes.",
        )
    min_games_threshold = st.sidebar.slider(
        "Minimum matches threshold",
        min_value=20,
        max_value=100,
        value=DEFAULT_MIN_GAMES_THRESHOLD,
        step=5,
        help="Only show counter picks with at least this many matches.",
    )
    return selected_heroes, selected_role, min_games_threshold, show_synergy, ally_hero_names


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def fetch_heroes() -> list[dict]:
    """Fetch and cache the hero catalog from OpenDota."""
    response = requests.get(f"{API_BASE_URL}/heroes", timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    heroes = response.json()
    if not isinstance(heroes, list):
        raise ValueError("OpenDota hero response is not a list.")
    return heroes


@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_counter_rows(selected_enemy_ids: tuple[int, ...], min_games_threshold: int) -> list[dict]:
    """Run the Explorer SQL query for the selected enemy heroes."""
    if not selected_enemy_ids:
        return []

    sql = build_counter_sql(selected_enemy_ids, min_games_threshold)
    response = requests.get(
        f"{API_BASE_URL}/explorer",
        params={"sql": sql},
        timeout=REQUEST_TIMEOUT,
        headers=REQUEST_HEADERS,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        raise ValueError("OpenDota explorer response does not contain a valid rows list.")
    return rows


@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_hero_matchups(hero_id: int) -> list[dict]:
    """Fetch historical hero matchup data for a single enemy hero."""
    response = requests.get(
        f"{API_BASE_URL}/heroes/{hero_id}/matchups",
        timeout=REQUEST_TIMEOUT,
        headers=REQUEST_HEADERS,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("OpenDota hero matchup response is not a list.")
    return rows


def build_counter_sql(selected_enemy_ids: Iterable[int], min_games_threshold: int) -> str:
    """Build the Explorer SQL query for counter heroes in the last 30 days."""
    enemy_ids = sorted({int(hero_id) for hero_id in selected_enemy_ids})
    if not enemy_ids:
        raise ValueError("At least one enemy hero is required.")

    cutoff = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp())
    enemy_id_csv = ", ".join(str(hero_id) for hero_id in enemy_ids)
    return f"""
    WITH enemy_matches AS (
        SELECT
            m.match_id,
            enemy_pb.team AS enemy_team,
            COUNT(DISTINCT enemy_pb.hero_id) AS matched_enemy_count
        FROM matches m
        JOIN picks_bans enemy_pb
            ON m.match_id = enemy_pb.match_id
        WHERE m.start_time >= {cutoff}
          AND enemy_pb.is_pick = TRUE
          AND enemy_pb.hero_id IN ({enemy_id_csv})
        GROUP BY m.match_id, enemy_pb.team
        HAVING COUNT(DISTINCT enemy_pb.hero_id) >= 1
    )
    SELECT
        pb.hero_id,
        COUNT(*) AS games_played,
        ROUND(AVG(em.matched_enemy_count), 2) AS avg_enemy_overlap,
        SUM(
            CASE
                WHEN (pb.team = 0 AND m.radiant_win)
                  OR (pb.team = 1 AND NOT m.radiant_win)
                THEN 1
                ELSE 0
            END
        ) AS wins,
        ROUND(
            100.0 * SUM(
                CASE
                    WHEN (pb.team = 0 AND m.radiant_win)
                      OR (pb.team = 1 AND NOT m.radiant_win)
                    THEN 1
                    ELSE 0
                END
            ) / COUNT(*),
            2
        ) AS win_rate
    FROM enemy_matches em
    JOIN matches m
        ON m.match_id = em.match_id
    JOIN picks_bans pb
        ON pb.match_id = em.match_id
    WHERE pb.is_pick = TRUE
      AND pb.team != em.enemy_team
    GROUP BY pb.hero_id
    HAVING COUNT(*) >= {int(min_games_threshold)}
    ORDER BY win_rate DESC, games_played DESC
    LIMIT 25
    """.strip()


def build_hero_dataframe(heroes: list[dict]) -> pd.DataFrame:
    """Normalize hero metadata into a DataFrame."""
    hero_df = pd.DataFrame(heroes)
    required_columns = {"id", "name", "localized_name", "roles"}
    missing_columns = required_columns.difference(hero_df.columns)
    if missing_columns:
        missing_text = ", ".join(sorted(missing_columns))
        raise ValueError(f"Hero response is missing columns: {missing_text}")

    if "img" not in hero_df.columns:
        hero_df["img"] = ""

    hero_df = hero_df.loc[:, ["id", "name", "localized_name", "roles", "img"]].copy()
    hero_df["roles"] = hero_df["roles"].apply(lambda value: value if isinstance(value, list) else [])
    hero_df["img"] = hero_df["img"].fillna("")
    return hero_df


def build_fallback_matchup_dataframe(
    selected_enemy_ids: Iterable[int],
    min_games_threshold: int,
) -> pd.DataFrame:
    """
    Build fallback counter rows from hero matchup endpoints.

    Explorer data is professional-match focused and often sparse for normal pub drafts.
    This fallback aggregates per-enemy historical matchup data so the app remains usable.
    """
    aggregated_rows: list[dict] = []

    for enemy_id in selected_enemy_ids:
        for row in fetch_hero_matchups(int(enemy_id)):
            games_played = int(row.get("games_played", 0) or 0)
            enemy_wins = int(row.get("wins", 0) or 0)
            if games_played <= 0:
                continue

            aggregated_rows.append(
                {
                    "hero_id": int(row["hero_id"]),
                    "games_played": games_played,
                    "candidate_wins": max(games_played - enemy_wins, 0),
                    "enemy_overlap": 1,
                }
            )

    if not aggregated_rows:
        return pd.DataFrame()

    fallback_df = pd.DataFrame(aggregated_rows)
    fallback_df = (
        fallback_df.groupby("hero_id", as_index=False)
        .agg(
            games_played=("games_played", "sum"),
            wins=("candidate_wins", "sum"),
            enemy_overlap=("enemy_overlap", "sum"),
        )
    )
    fallback_df = fallback_df[fallback_df["games_played"] >= int(min_games_threshold)]
    if fallback_df.empty:
        return fallback_df

    fallback_df["avg_enemy_overlap"] = fallback_df["enemy_overlap"].astype(float)
    fallback_df["win_rate"] = (100.0 * fallback_df["wins"] / fallback_df["games_played"]).round(2)
    fallback_df = fallback_df.sort_values(["win_rate", "games_played"], ascending=[False, False])
    return fallback_df.loc[:, ["hero_id", "games_played", "wins", "win_rate", "avg_enemy_overlap"]]


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_dotabuff_dataset() -> dict:
    """Load locally curated Dotabuff worst-versus data."""
    if not DOTABUFF_DATASET_PATH.exists():
        return {"updated_at": None, "heroes": {}}

    with DOTABUFF_DATASET_PATH.open("r", encoding="utf-8") as dataset_file:
        payload = json.load(dataset_file)
    if not isinstance(payload, dict):
        raise ValueError("Dotabuff dataset must be a JSON object.")
    payload.setdefault("heroes", {})
    return payload


def build_dotabuff_signal_dataframe(selected_enemy_names: Iterable[str]) -> pd.DataFrame:
    """Aggregate locally stored Dotabuff worst-versus data across selected enemy heroes."""
    dataset = load_dotabuff_dataset()
    hero_map = dataset.get("heroes", {})
    signal_rows: list[dict] = []

    for enemy_name in selected_enemy_names:
        for entry in hero_map.get(enemy_name, []):
            signal_rows.append(
                {
                    "localized_name": entry["hero"],
                    "dotabuff_disadvantage": pd.to_numeric(entry["disadvantage_pct"], errors="coerce"),
                    "dotabuff_matches": pd.to_numeric(entry["matches"], errors="coerce"),
                    "dotabuff_enemy_hits": 1,
                }
            )

    if not signal_rows:
        return pd.DataFrame()

    signal_df = pd.DataFrame(signal_rows).dropna(subset=["localized_name"])
    if signal_df.empty:
        return signal_df

    signal_df = (
        signal_df.groupby("localized_name", as_index=False)
        .agg(
            dotabuff_disadvantage=("dotabuff_disadvantage", "mean"),
            dotabuff_matches=("dotabuff_matches", "sum"),
            dotabuff_enemy_hits=("dotabuff_enemy_hits", "sum"),
        )
        .sort_values(["dotabuff_enemy_hits", "dotabuff_disadvantage"], ascending=[False, False])
    )
    return signal_df


def prepare_results_dataframe(
    rows: list[dict],
    hero_df: pd.DataFrame,
    selected_role: str,
    selected_enemy_names: Iterable[str],
    dotabuff_signal_df: pd.DataFrame | None = None,
    ally_hero_names: Iterable[str] | None = None,
    show_synergy: bool = False,
) -> pd.DataFrame:
    """Convert explorer rows into a filtered, display-ready DataFrame."""
    results_df = pd.DataFrame(rows)
    if results_df.empty:
        results_df = pd.DataFrame(columns=["hero_id", "games_played", "wins", "win_rate", "avg_enemy_overlap"])

    if "avg_enemy_overlap" not in results_df.columns:
        results_df["avg_enemy_overlap"] = 0.0

    merged_df = results_df.merge(hero_df, left_on="hero_id", right_on="id", how="left")
    merged_df["localized_name"] = merged_df["localized_name"].fillna("Unknown Hero")
    merged_df["image_url"] = merged_df.apply(
        lambda row: get_hero_image_url(row["img"], row.get("name")), axis=1
    )
    enemy_name_set = set(selected_enemy_names)

    if enemy_name_set:
        merged_df = merged_df[~merged_df["localized_name"].isin(enemy_name_set)]

    if selected_role != "All":
        merged_df = merged_df[merged_df["roles"].apply(lambda roles: matches_role_filter(roles, selected_role))]

    if merged_df.empty:
        return merged_df

    merged_df["wins"] = pd.to_numeric(merged_df["wins"], errors="coerce").fillna(0).astype(int)
    merged_df["games_played"] = pd.to_numeric(merged_df["games_played"], errors="coerce").fillna(0).astype(int)
    merged_df["win_rate"] = pd.to_numeric(merged_df["win_rate"], errors="coerce").fillna(0.0)
    merged_df["avg_enemy_overlap"] = pd.to_numeric(
        merged_df["avg_enemy_overlap"], errors="coerce"
    ).fillna(0.0)

    if dotabuff_signal_df is not None and not dotabuff_signal_df.empty:
        merged_df = merged_df.merge(dotabuff_signal_df, on="localized_name", how="left")
    else:
        merged_df["dotabuff_disadvantage"] = 0.0
        merged_df["dotabuff_matches"] = 0
        merged_df["dotabuff_enemy_hits"] = 0

    # Include heroes that exist only in the local Dotabuff dataset but were absent
    # from the OpenDota result set, so strong manual counter signals can still appear.
    if dotabuff_signal_df is not None and not dotabuff_signal_df.empty:
        existing_names = set(merged_df["localized_name"].dropna().tolist())
        dotabuff_only_df = dotabuff_signal_df[~dotabuff_signal_df["localized_name"].isin(existing_names)].copy()
        if not dotabuff_only_df.empty:
            hero_lookup_df = hero_df.loc[:, ["localized_name", "name", "img", "roles"]].copy()
            dotabuff_only_df = dotabuff_only_df.merge(hero_lookup_df, on="localized_name", how="left")
            dotabuff_only_df["image_url"] = dotabuff_only_df.apply(
                lambda row: get_hero_image_url(row.get("img"), row.get("name")), axis=1
            )
            dotabuff_only_df["games_played"] = 0
            dotabuff_only_df["wins"] = 0
            dotabuff_only_df["win_rate"] = 0.0
            dotabuff_only_df["avg_enemy_overlap"] = 0.0
            merged_df = pd.concat([merged_df, dotabuff_only_df], ignore_index=True, sort=False)

    merged_df["dotabuff_disadvantage"] = pd.to_numeric(
        merged_df["dotabuff_disadvantage"], errors="coerce"
    ).fillna(0.0)
    merged_df["dotabuff_matches"] = pd.to_numeric(
        merged_df["dotabuff_matches"], errors="coerce"
    ).fillna(0).astype(int)
    merged_df["dotabuff_enemy_hits"] = pd.to_numeric(
        merged_df["dotabuff_enemy_hits"], errors="coerce"
    ).fillna(0).astype(int)
    merged_df["roles"] = merged_df["roles"].apply(lambda roles: roles if isinstance(roles, list) else [])
    synergy_lookup = get_ally_synergy_scores(hero_df, ally_hero_names) if show_synergy else {}
    merged_df["synergy_score"] = merged_df["localized_name"].map(synergy_lookup).fillna(0.0)

    selected_enemy_count = max(len(set(selected_enemy_names)), 1)
    merged_df["sample_factor"] = (merged_df["games_played"] / (merged_df["games_played"] + 75.0)).clip(0, 1)
    merged_df["overlap_factor"] = (merged_df["avg_enemy_overlap"] / selected_enemy_count).clip(0, 1)
    merged_df["role_factor"] = merged_df["roles"].apply(
        lambda roles: 1.0 if matches_role_filter(roles, selected_role) else 0.85
    )
    merged_df["stabilized_win_rate"] = (
        (merged_df["wins"] + 25.0) / (merged_df["games_played"] + 50.0) * 100.0
    ).round(2)
    merged_df["dotabuff_only"] = (
        (merged_df["games_played"] == 0) & (merged_df["dotabuff_enemy_hits"] > 0)
    )
    merged_df["confidence_score"] = (
        merged_df["stabilized_win_rate"] * 0.55
        + merged_df["sample_factor"] * 25.0
        + merged_df["overlap_factor"] * 15.0
        + merged_df["role_factor"] * 5.0
    ).round(2)
    merged_df.loc[merged_df["dotabuff_only"], "confidence_score"] = (
        25.0
        + (merged_df.loc[merged_df["dotabuff_only"], "dotabuff_disadvantage"] * 4.0)
        + (merged_df.loc[merged_df["dotabuff_only"], "dotabuff_enemy_hits"] * 5.0)
        + ((merged_df.loc[merged_df["dotabuff_only"], "dotabuff_matches"] / 10000.0).clip(0, 4.0))
    ).round(2)
    merged_df["hybrid_score"] = (
        merged_df["confidence_score"]
        + (merged_df["dotabuff_disadvantage"] * 1.5)
        + (merged_df["dotabuff_enemy_hits"] * 3.0)
        + ((merged_df["dotabuff_matches"] / 10000.0).clip(0, 3.0))
        + merged_df["synergy_score"]
    ).round(2)
    merged_df = merged_df.sort_values(
        ["hybrid_score", "synergy_score", "confidence_score", "games_played"],
        ascending=[False, False, False, False],
    )

    return merged_df.loc[
        :,
        [
            "image_url",
            "localized_name",
            "games_played",
            "wins",
            "win_rate",
            "stabilized_win_rate",
            "avg_enemy_overlap",
            "sample_factor",
            "overlap_factor",
            "confidence_score",
            "dotabuff_disadvantage",
            "dotabuff_matches",
            "dotabuff_enemy_hits",
            "synergy_score",
            "hybrid_score",
            "roles",
        ],
    ]


def main() -> None:
    st.set_page_config(page_title="Dota 2 Counter Picker", page_icon=":crossed_swords:", layout="wide")
    inject_app_theme()
    st.title("Dota 2 Counter Picker")

    try:
        heroes = fetch_heroes()
        hero_df = build_hero_dataframe(heroes)
    except (requests.RequestException, ValueError) as exc:
        st.error(f"Failed to load hero list: {exc}")
        return

    (
        selected_hero_names,
        selected_role,
        min_games_threshold,
        show_synergy,
        ally_hero_names,
    ) = render_sidebar(hero_df)
    hero_name_to_id = hero_df.set_index("localized_name")["id"].to_dict()
    selected_enemy_ids = tuple(hero_name_to_id[name] for name in selected_hero_names)

    st.caption(
        f"Find the best hero counters against the selected enemies using OpenDota data from the last 30 days. "
        f"Current minimum sample threshold: {min_games_threshold} matches."
    )

    st.write("Choose an enemy lineup and review the best counter recommendations.")
    render_summary_strip(
        selected_hero_names,
        selected_role,
        min_games_threshold,
        show_synergy,
        ally_hero_names,
    )
    if show_synergy and ally_hero_names:
        st.caption(f"Synergy mode: enabled for ally heroes {', '.join(ally_hero_names)}")
        st.caption("Synergy model: explicit combo presets + role-based fallback for every hero")

    if not selected_enemy_ids:
        st.info("Select at least one enemy hero from the sidebar to continue.")
        return

    st.subheader("Selected Enemies")
    render_selected_hero_grid(selected_hero_names, hero_df)

    try:
        rows = fetch_counter_rows(selected_enemy_ids, min_games_threshold)
    except requests.RequestException as exc:
        st.error(f"OpenDota Explorer API request failed: {exc}")
        return
    except ValueError as exc:
        st.error(f"Failed to process Explorer data: {exc}")
        return

    dotabuff_signal_df = build_dotabuff_signal_dataframe(selected_hero_names)
    dotabuff_dataset = load_dotabuff_dataset()
    dotabuff_status = (
        f"local dataset active (updated: {dotabuff_dataset.get('updated_at', 'unknown')})"
        if not dotabuff_signal_df.empty
        else "local dataset loaded, but no entries exist for the selected heroes"
    )

    data_source_label = "OpenDota Explorer"
    if rows:
        results_df = prepare_results_dataframe(
            rows,
            hero_df,
            selected_role,
            selected_hero_names,
            dotabuff_signal_df,
            ally_hero_names=ally_hero_names,
            show_synergy=show_synergy,
        )
    else:
        try:
            fallback_rows_df = build_fallback_matchup_dataframe(selected_enemy_ids, min_games_threshold)
        except (requests.RequestException, ValueError) as exc:
            st.error(f"Failed to load OpenDota matchup data: {exc}")
            return

        if fallback_rows_df.empty:
            st.warning(
                "Not enough data was found for the selected enemies. Lower the threshold and try again."
            )
            return

        data_source_label = "OpenDota Hero Matchups"
        results_df = prepare_results_dataframe(
            fallback_rows_df.to_dict("records"),
            hero_df,
            selected_role,
            selected_hero_names,
            dotabuff_signal_df,
            ally_hero_names=ally_hero_names,
            show_synergy=show_synergy,
        )

    if results_df.empty:
        st.warning(
            "Not enough data was found for the selected role. Try a different role, enemy combination, "
            "or a lower match threshold."
        )
        return

    st.caption(f"Data source: {data_source_label}")
    st.caption(f"Dotabuff status: {dotabuff_status}")
    st.caption("Ranking logic: OpenDota confidence score + local Dotabuff worst-versus signal")
    if show_synergy and ally_hero_names:
        st.caption("Synergy weighting: ally combo heroes receive an additional score bonus")
    render_counter_cards(results_df)

    display_df = results_df.copy()
    display_df["roles"] = display_df["roles"].apply(lambda roles: ", ".join(roles))
    display_df = display_df.rename(
        columns={
            "image_url": "Image",
            "localized_name": "Hero",
            "games_played": "Games",
            "wins": "Wins",
            "win_rate": "Win Rate (%)",
            "stabilized_win_rate": "Stabilized Win Rate (%)",
            "avg_enemy_overlap": "Avg Enemy Match Count",
            "sample_factor": "Sample Factor",
            "overlap_factor": "Overlap Factor",
            "confidence_score": "Confidence Score",
            "dotabuff_disadvantage": "Dotabuff Disadvantage (%)",
            "dotabuff_matches": "Dotabuff Matches",
            "dotabuff_enemy_hits": "Dotabuff Enemy Hits",
            "synergy_score": "Synergy Score",
            "hybrid_score": "Hybrid Score",
            "roles": "Roles",
        }
    )

    st.subheader("Counter Results")
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Image": st.column_config.ImageColumn("Image", help="Hero portrait", width="medium"),
        },
    )

    chart_df = results_df.loc[:, ["localized_name", "win_rate"]].set_index("localized_name")
    st.subheader("Win Rate Chart")
    st.bar_chart(chart_df)


if __name__ == "__main__":
    main()
