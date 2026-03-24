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
STEAM_ITEM_IMAGE_BASE_URL = f"{STEAM_CDN_BASE_URL}/apps/dota2/images/dota_react/items"
ROLE_OPTIONS = ["All", "Carry", "Support", "Mid", "Offlane", "Disabler", "Durable"]
REQUEST_TIMEOUT = 30
DEFAULT_MIN_GAMES_THRESHOLD = 50
DATA_DIR = Path(__file__).parent / "data"
DOTABUFF_DATASET_PATH = DATA_DIR / "dotabuff_worst_versus.json"
SYNERGY_CONFIG_PATH = DATA_DIR / "synergy_map.json"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

ENEMY_ARCHETYPES = {
    "wide_spell_damage": {
        "Dark Seer",
        "Death Prophet",
        "Disruptor",
        "Enigma",
        "Invoker",
        "Jakiro",
        "Leshrac",
        "Lina",
        "Phoenix",
        "Puck",
        "Sand King",
        "Skywrath Mage",
        "Storm Spirit",
        "Techies",
        "Venomancer",
        "Zeus",
    },
    "targeted_magic_damage": {
        "Ancient Apparition",
        "Crystal Maiden",
        "Death Prophet",
        "Invoker",
        "Lina",
        "Lion",
        "Necrophos",
        "Nyx Assassin",
        "Ogre Magi",
        "Oracle",
        "Pugna",
        "Skywrath Mage",
        "Tinker",
        "Zeus",
    },
    "jump_burst": {
        "Axe",
        "Batrider",
        "Clockwerk",
        "Legion Commander",
        "Mars",
        "Night Stalker",
        "Nyx Assassin",
        "Primal Beast",
        "Puck",
        "Riki",
        "Slardar",
        "Spirit Breaker",
        "Storm Spirit",
        "Tiny",
        "Tusk",
        "Void Spirit",
    },
    "super_regen": {
        "Alchemist",
        "Bristleback",
        "Dragon Knight",
        "Huskar",
        "Morphling",
        "Necrophos",
        "Timbersaw",
    },
    "physical_right_click": {
        "Clinkz",
        "Drow Ranger",
        "Juggernaut",
        "Luna",
        "Medusa",
        "Monkey King",
        "Muerta",
        "Phantom Assassin",
        "Shadow Fiend",
        "Sniper",
        "Templar Assassin",
        "Terrorblade",
        "Troll Warlord",
        "Ursa",
    },
    "kitable_buffs": {
        "Abaddon",
        "Juggernaut",
        "Lifestealer",
        "Necrophos",
        "Night Stalker",
        "Troll Warlord",
        "Ursa",
    },
    "roots_and_leashes": {
        "Crystal Maiden",
        "Dark Willow",
        "Naga Siren",
        "Nature's Prophet",
        "Puck",
        "Slark",
        "Treant Protector",
        "Underlord",
    },
    "single_target_spells": {
        "Bane",
        "Batrider",
        "Beastmaster",
        "Doom",
        "Legion Commander",
        "Lion",
        "Oracle",
        "Pudge",
        "Shadow Shaman",
        "Spirit Breaker",
        "Vengeful Spirit",
    },
    "illusions_summons": {
        "Beastmaster",
        "Broodmother",
        "Chaos Knight",
        "Chen",
        "Lycan",
        "Naga Siren",
        "Phantom Lancer",
        "Terrorblade",
        "Visage",
    },
    "escape_heroes": {
        "Anti-Mage",
        "Ember Spirit",
        "Morphling",
        "Pangolier",
        "Puck",
        "Queen of Pain",
        "Riki",
        "Storm Spirit",
        "Void Spirit",
        "Weaver",
    },
    "passive_reliant": {
        "Bristleback",
        "Dragon Knight",
        "Huskar",
        "Necrophos",
        "Phantom Assassin",
        "Spectre",
        "Timbersaw",
        "Treant Protector",
        "Viper",
    },
    "hard_disable": {
        "Axe",
        "Bane",
        "Beastmaster",
        "Batrider",
        "Disruptor",
        "Enigma",
        "Invoker",
        "Legion Commander",
        "Lion",
        "Mars",
        "Sand King",
        "Shadow Shaman",
        "Tiny",
    },
}

ALLY_ARCHETYPES = {
    "big_teamfight": {
        "Dark Seer",
        "Earthshaker",
        "Enigma",
        "Faceless Void",
        "Magnus",
        "Mars",
        "Phoenix",
        "Tidehunter",
    },
    "save_sensitive_cores": {
        "Drow Ranger",
        "Luna",
        "Shadow Fiend",
        "Sniper",
        "Terrorblade",
    },
    "frontline_cores": {
        "Bristleback",
        "Centaur Warrunner",
        "Dragon Knight",
        "Mars",
        "Primal Beast",
        "Tidehunter",
        "Underlord",
    },
    "pickoff_allies": {
        "Batrider",
        "Beastmaster",
        "Doom",
        "Legion Commander",
        "Shadow Shaman",
        "Spirit Breaker",
    },
}

COUNTER_ARCHETYPES = {
    "blink_initiators": {
        "Axe",
        "Centaur Warrunner",
        "Earthshaker",
        "Enigma",
        "Legion Commander",
        "Magnus",
        "Mars",
        "Sand King",
        "Tidehunter",
        "Tiny",
    },
    "magic_burst_cores": {
        "Invoker",
        "Leshrac",
        "Lina",
        "Puck",
        "Pugna",
        "Queen of Pain",
        "Shadow Fiend",
        "Skywrath Mage",
        "Storm Spirit",
        "Tinker",
        "Zeus",
    },
    "right_click_ranged": {
        "Clinkz",
        "Drow Ranger",
        "Lina",
        "Luna",
        "Muerta",
        "Shadow Fiend",
        "Sniper",
        "Templar Assassin",
        "Terrorblade",
    },
    "silence_or_pickoff": {
        "Death Prophet",
        "Night Stalker",
        "Puck",
        "Queen of Pain",
        "Riki",
        "Silencer",
        "Skywrath Mage",
        "Storm Spirit",
        "Void Spirit",
    },
    "illusion_clear": {
        "Axe",
        "Ember Spirit",
        "Leshrac",
        "Lina",
        "Medusa",
        "Sven",
        "Tidehunter",
    },
    "aura_builders": {
        "Abaddon",
        "Dark Seer",
        "Omniknight",
        "Treant Protector",
        "Underlord",
        "Visage",
    },
}

INVOKER_DRAFT_SIGNALS = {
    "low_mana_pool": {
        "Anti-Mage",
        "Clinkz",
        "Crystal Maiden",
        "Drow Ranger",
        "Hoodwink",
        "Muerta",
        "Phantom Assassin",
        "Riki",
        "Shadow Fiend",
        "Sniper",
        "Templar Assassin",
        "Weaver",
    },
    "low_armor": {
        "Ancient Apparition",
        "Clinkz",
        "Crystal Maiden",
        "Dark Willow",
        "Drow Ranger",
        "Grimstroke",
        "Hoodwink",
        "Muerta",
        "Nature's Prophet",
        "Shadow Fiend",
        "Silencer",
        "Skywrath Mage",
        "Sniper",
        "Tinker",
        "Vengeful Spirit",
        "Warlock",
        "Witch Doctor",
        "Zeus",
    },
    "slow_cores": {
        "Drow Ranger",
        "Luna",
        "Medusa",
        "Shadow Fiend",
        "Sniper",
        "Spectre",
        "Terrorblade",
    },
    "bkb_punishable": {
        "Juggernaut",
        "Lifestealer",
        "Luna",
        "Phantom Assassin",
        "Shadow Fiend",
        "Sniper",
        "Templar Assassin",
        "Terrorblade",
        "Ursa",
    },
    "silence_threats": {
        "Death Prophet",
        "Drow Ranger",
        "Night Stalker",
        "Puck",
        "Silencer",
        "Skywrath Mage",
        "Storm Spirit",
    },
    "blink_initiators": {
        "Axe",
        "Centaur Warrunner",
        "Earthshaker",
        "Enigma",
        "Legion Commander",
        "Magnus",
        "Mars",
        "Sand King",
        "Tidehunter",
        "Tiny",
    },
    "physical_burst": {
        "Clinkz",
        "Drow Ranger",
        "Juggernaut",
        "Muerta",
        "Phantom Assassin",
        "Shadow Fiend",
        "Sniper",
        "Templar Assassin",
        "Ursa",
    },
    "deathball": {
        "Chen",
        "Death Prophet",
        "Dragon Knight",
        "Leshrac",
        "Luna",
        "Lycan",
        "Shadow Shaman",
        "Visage",
    },
    "pickoff": {
        "Batrider",
        "Clockwerk",
        "Legion Commander",
        "Nyx Assassin",
        "Puck",
        "Queen of Pain",
        "Riki",
        "Spirit Breaker",
        "Storm Spirit",
        "Void Spirit",
    },
}

INVOKER_ITEM_REMINDERS = {
    "Phantom Assassin": {
        "item": "Ghost Scepter",
        "timing": "Target by 3rd item",
        "reason": "PA can skip your combo window if she gets on top of you before you have a defensive reset.",
    },
    "Storm Spirit": {
        "item": "Orchid Malevolence",
        "timing": "Rush after boots if lane is even",
        "reason": "Silence converts catches into kills before Storm reaches comfortable mana scaling.",
    },
    "Queen of Pain": {
        "item": "Orchid Malevolence",
        "timing": "Early-mid game timing",
        "reason": "Punishes blink-dependent escapes and forces a defensive item response.",
    },
    "Puck": {
        "item": "Scythe of Vyse",
        "timing": "Core late-mid timing",
        "reason": "Reliable instant control matters more than more raw spell damage into phase shift and mobility.",
    },
    "Spirit Breaker": {
        "item": "Eul's Scepter of Divinity",
        "timing": "Before his repeated charge timings",
        "reason": "Lets you dodge charge setups and create a clean Tornado or disengage window.",
    },
    "Legion Commander": {
        "item": "Linken's Sphere",
        "timing": "Before Duel becomes fight-defining",
        "reason": "You need a reliable answer once LC can blink-duel through positioning mistakes.",
    },
    "Doom": {
        "item": "Linken's Sphere",
        "timing": "Mid game priority",
        "reason": "Stops the one spell that removes your entire hero from the fight.",
    },
    "Clockwerk": {
        "item": "Force Staff",
        "timing": "Early utility pickup",
        "reason": "Solves cogs and lets you maintain casting distance during chaotic skirmishes.",
    },
    "Nyx Assassin": {
        "item": "Black King Bar",
        "timing": "Before high-risk outer map fights",
        "reason": "Invoker hates chain setup from Vendetta catches and mana burn into follow-up disable.",
    },
    "Anti-Mage": {
        "item": "Scythe of Vyse",
        "timing": "As soon as you need hard catch",
        "reason": "You need instant control because long spell chains are unreliable once AM gets manta or blink space.",
    },
    "Huskar": {
        "item": "Spirit Vessel",
        "timing": "One of your first major pickups",
        "reason": "Without heal reduction, your spell damage often fails to convert into a kill.",
    },
    "Morphling": {
        "item": "Spirit Vessel",
        "timing": "Early-mid game",
        "reason": "Forces Morphling to respect burst windows instead of freely attribute-shifting through them.",
    },
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


def get_item_image_url(item_slug: str) -> str:
    """Return the Steam CDN URL for an item icon."""
    return f"{STEAM_ITEM_IMAGE_BASE_URL}/{item_slug}.png"


@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_synergy_config() -> dict:
    """Load local synergy presets and role weights."""
    if not SYNERGY_CONFIG_PATH.exists():
        return {"ally_synergy_map": {}, "role_synergy_weights": {}}

    with SYNERGY_CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        payload = json.load(config_file)
    if not isinstance(payload, dict):
        raise ValueError("Synergy config must be a JSON object.")
    payload.setdefault("ally_synergy_map", {})
    payload.setdefault("role_synergy_weights", {})
    return payload


def count_matching_heroes(hero_names: Iterable[str], hero_pool: set[str]) -> int:
    """Count how many selected heroes belong to a named archetype pool."""
    return sum(1 for hero_name in hero_names if hero_name in hero_pool)


def add_item_suggestion(
    suggestion_map: dict[str, dict],
    *,
    item_name: str,
    item_slug: str,
    score: float,
    reason: str,
    tags: Iterable[str],
    category: str,
) -> None:
    """Accumulate weighted item suggestions from multiple independent rules."""
    if score <= 0:
        return

    entry = suggestion_map.setdefault(
        item_name,
        {
            "item_name": item_name,
            "item_slug": item_slug,
            "score": 0.0,
            "reasons": [],
            "tags": set(),
            "category_scores": {},
        },
    )
    entry["score"] += score
    entry["reasons"].append(reason)
    entry["tags"].update(tags)
    entry["category_scores"][category] = entry["category_scores"].get(category, 0.0) + score


def build_item_suggestions(
    selected_enemy_names: Iterable[str],
    ally_hero_names: Iterable[str] | None,
    selected_role: str,
    counter_hero_name: str | None = None,
    hero_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build situational item suggestions from enemy threats and ally synergy context."""
    enemy_names = list(selected_enemy_names)
    ally_names = list(ally_hero_names or [])
    suggestion_map: dict[str, dict] = {}

    wide_spell_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["wide_spell_damage"])
    targeted_magic_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["targeted_magic_damage"])
    jump_burst_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["jump_burst"])
    regen_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["super_regen"])
    physical_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["physical_right_click"])
    kite_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["kitable_buffs"])
    root_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["roots_and_leashes"])
    single_target_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["single_target_spells"])
    illusions_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["illusions_summons"])
    escape_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["escape_heroes"])
    passive_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["passive_reliant"])
    disable_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["hard_disable"])

    big_teamfight_allies = count_matching_heroes(ally_names, ALLY_ARCHETYPES["big_teamfight"])
    save_sensitive_allies = count_matching_heroes(ally_names, ALLY_ARCHETYPES["save_sensitive_cores"])
    frontline_allies = count_matching_heroes(ally_names, ALLY_ARCHETYPES["frontline_cores"])
    pickoff_allies = count_matching_heroes(ally_names, ALLY_ARCHETYPES["pickoff_allies"])

    counter_roles: set[str] = set()
    if counter_hero_name and hero_df is not None and not hero_df.empty:
        counter_row = hero_df[hero_df["localized_name"] == counter_hero_name]
        if not counter_row.empty:
            counter_roles = set(counter_row.iloc[0].get("roles", []) or [])

    support_like = (
        "Support" in counter_roles
        or "Disabler" in counter_roles
        or (not counter_roles and selected_role in {"Support", "Disabler"})
    )
    core_like = (
        bool(counter_roles.intersection({"Carry", "Escape", "Durable", "Initiator", "Nuker"}))
        or (not counter_roles and selected_role in {"Carry", "Mid", "Offlane"})
    )
    frontline_like = bool(counter_roles.intersection({"Durable", "Initiator"}))
    catch_like = bool(counter_roles.intersection({"Disabler", "Escape", "Nuker"}))
    right_click_like = bool(counter_roles.intersection({"Carry", "Escape"}))
    blink_initiator_like = bool(counter_hero_name and counter_hero_name in COUNTER_ARCHETYPES["blink_initiators"])
    magic_burst_like = bool(counter_hero_name and counter_hero_name in COUNTER_ARCHETYPES["magic_burst_cores"])
    ranged_damage_like = bool(counter_hero_name and counter_hero_name in COUNTER_ARCHETYPES["right_click_ranged"])
    pickoff_like = bool(counter_hero_name and counter_hero_name in COUNTER_ARCHETYPES["silence_or_pickoff"])
    illusion_clear_like = bool(counter_hero_name and counter_hero_name in COUNTER_ARCHETYPES["illusion_clear"])
    aura_builder_like = bool(counter_hero_name and counter_hero_name in COUNTER_ARCHETYPES["aura_builders"])

    add_item_suggestion(
        suggestion_map,
        item_name="Pipe of Insight",
        item_slug="pipe",
        score=wide_spell_count * 2.7 + big_teamfight_allies * 0.8,
        reason="Enemy lineup has strong teamfight spell damage; aura mitigation gets higher value.",
        tags=["Enemy Damage", "Aura"],
        category="Defensive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Eternal Shroud",
        item_slug="eternal_shroud",
        score=targeted_magic_count * 2.3
        + (1.0 if frontline_allies and core_like else 0.0)
        + (0.8 if frontline_like else 0.0),
        reason="Enemy lineup can focus a single core with repeated magic damage.",
        tags=["Survivability", "Magic"],
        category="Defensive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Glimmer Cape",
        item_slug="glimmer_cape",
        score=(jump_burst_count * 1.8 + targeted_magic_count * 1.0 + save_sensitive_allies * 1.2)
        if support_like or selected_role == "All"
        else 0.0,
        reason="Enemy jump plus burst makes fast save/invis usage much more valuable.",
        tags=["Save", "Support"],
        category="Utility",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Spirit Vessel",
        item_slug="spirit_vessel",
        score=regen_count * 3.2,
        reason="Enemy lineup includes heavy regen or sustain cores that need healing reduction.",
        tags=["Healing Reduction", "Counter"],
        category="Aggressive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Aeon Disk",
        item_slug="aeon_disk",
        score=jump_burst_count * 1.9
        + single_target_count * 1.4
        + disable_count * 0.9
        + (0.9 if support_like else 0.0),
        reason="Enemy lineup can delete one hero on contact; emergency dispel/passive save is high value.",
        tags=["Save", "Burst"],
        category="Defensive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Ghost Scepter",
        item_slug="ghost",
        score=max(physical_count * 2.0 - targeted_magic_count * 1.2, 0.0) + (0.7 if support_like else 0.0),
        reason="Enemy damage profile leans heavily into right-clicks over direct magic punish.",
        tags=["Defense", "Physical"],
        category="Defensive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Eul's Scepter of Divinity",
        item_slug="cyclone",
        score=kite_count * 2.0 + escape_count * 0.8,
        reason="Enemy heroes rely on short-lived buffs or timing windows that are easier to kite or reset.",
        tags=["Utility", "Dispel"],
        category="Utility",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Hurricane Pike",
        item_slug="hurricane_pike",
        score=(root_count * 2.2 + jump_burst_count * 0.7 + (0.9 if right_click_like else 0.0))
        if core_like or selected_role == "All"
        else 0.0,
        reason="Enemy lineup has roots, leashes, or gap-close pressure that force reposition tools.",
        tags=["Mobility", "Core"],
        category="Utility",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Lotus Orb",
        item_slug="lotus_orb",
        score=single_target_count * 2.2
        + disable_count * 0.8
        + save_sensitive_allies * 0.9
        + (0.8 if frontline_like else 0.0),
        reason="Enemy lineup relies on targeted control or dispellable single-target spells.",
        tags=["Reflect", "Dispel"],
        category="Defensive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Linken's Sphere",
        item_slug="sphere",
        score=(single_target_count * 1.9 + jump_burst_count * 0.8) if core_like or selected_role == "All" else 0.0,
        reason="Enemy draft has multiple high-value single-target initiations worth blocking.",
        tags=["Defense", "Spell Block"],
        category="Defensive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Black King Bar",
        item_slug="black_king_bar",
        score=(disable_count * 2.0 + targeted_magic_count * 0.7 + jump_burst_count * 0.6)
        + (0.8 if right_click_like or frontline_like else 0.0)
        if core_like or selected_role == "All"
        else 0.0,
        reason="Enemy draft can lock down a core through repeated disables and magic burst.",
        tags=["Core", "Immunity"],
        category="Defensive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Crimson Guard",
        item_slug="crimson_guard",
        score=illusions_count * 2.6 + physical_count * 0.7,
        reason="Enemy lineup has summons, illusions, or sustained physical chip damage.",
        tags=["Aura", "Physical"],
        category="Defensive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Orchid Malevolence",
        item_slug="orchid",
        score=(escape_count * 2.1 + pickoff_allies * 0.9 + (0.7 if catch_like else 0.0))
        if core_like or selected_role == "All"
        else 0.0,
        reason="Enemy lineup has mobile targets that become much easier to punish with silence.",
        tags=["Catch", "Silence"],
        category="Aggressive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Heaven's Halberd",
        item_slug="heavens_halberd",
        score=physical_count * 2.0 + frontline_allies * 0.6,
        reason="Enemy draft leans on right-click cores that can be disrupted with disarm.",
        tags=["Counter", "Physical"],
        category="Defensive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Silver Edge",
        item_slug="silver_edge",
        score=(passive_count * 2.8) if core_like or selected_role == "All" else 0.0,
        reason="Enemy lineup includes passive-heavy cores that lose a lot of value when broken.",
        tags=["Break", "Core"],
        category="Aggressive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Force Staff",
        item_slug="force_staff",
        score=(root_count * 1.8 + jump_burst_count * 1.0 + save_sensitive_allies * 0.9)
        + (0.7 if support_like else 0.0)
        if support_like or selected_role == "All"
        else 0.0,
        reason="Enemy draft threatens catches and roots that are solved by instant repositioning.",
        tags=["Save", "Mobility"],
        category="Utility",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Solar Crest",
        item_slug="solar_crest",
        score=(save_sensitive_allies * 1.8 + frontline_allies * 1.2 + physical_count * 0.5)
        if support_like or selected_role == "All"
        else 0.0,
        reason="Your ally lineup benefits from extra sustain, armor, and commit support in fights.",
        tags=["Synergy", "Buff"],
        category="Synergy",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Refresher Orb",
        item_slug="refresher",
        score=(big_teamfight_allies * 1.8 + wide_spell_count * 0.5 + (0.6 if frontline_like else 0.0))
        if core_like or selected_role == "All"
        else 0.0,
        reason="Your ally lineup has layered teamfight ultimates, making second-round spell value much higher.",
        tags=["Synergy", "Teamfight"],
        category="Synergy",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Blink Dagger",
        item_slug="blink",
        score=(jump_burst_count * 0.9 + pickoff_allies * 1.1 + big_teamfight_allies * 1.0)
        if blink_initiator_like
        else 0.0,
        reason="This counter hero converts extra reach into faster initiations and cleaner teamfight catches.",
        tags=["Initiation", "Tempo"],
        category="Aggressive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Shiva's Guard",
        item_slug="shivas_guard",
        score=(physical_count * 1.0 + regen_count * 1.5 + illusions_count * 0.8)
        if frontline_like or aura_builder_like
        else 0.0,
        reason="Armor, healing reduction, and teamfight slow all scale well into this matchup.",
        tags=["Armor", "Teamfight"],
        category="Defensive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Scythe of Vyse",
        item_slug="sheepstick",
        score=(escape_count * 1.8 + pickoff_allies * 1.0 + catch_like * 0.8)
        if magic_burst_like or pickoff_like or selected_role == "All"
        else 0.0,
        reason="Enemy escape heroes are easier to convert into kills with hard instant control.",
        tags=["Catch", "Disable"],
        category="Aggressive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Gleipnir",
        item_slug="gleipnir",
        score=(escape_count * 1.4 + illusions_count * 1.1 + big_teamfight_allies * 0.9)
        if ranged_damage_like or magic_burst_like or selected_role == "All"
        else 0.0,
        reason="This lineup rewards extra catch plus wave and illusion control from range.",
        tags=["Catch", "Waveclear"],
        category="Aggressive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Mjollnir",
        item_slug="mjollnir",
        score=(illusions_count * 1.8 + physical_count * 0.8)
        if ranged_damage_like or illusion_clear_like or right_click_like
        else 0.0,
        reason="Extra chain lightning punishes illusion-heavy drafts and accelerates damage output.",
        tags=["Damage", "Waveclear"],
        category="Aggressive",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Assault Cuirass",
        item_slug="assault",
        score=(physical_count * 1.2 + frontline_allies * 1.0 + (0.7 if right_click_like else 0.0))
        if frontline_like or ranged_damage_like or selected_role == "All"
        else 0.0,
        reason="Your lineup benefits from armor swing and objective pressure in longer fights.",
        tags=["Armor", "Push"],
        category="Synergy",
    )
    add_item_suggestion(
        suggestion_map,
        item_name="Aghanim's Scepter",
        item_slug="ultimate_scepter",
        score=(big_teamfight_allies * 1.0 + (0.8 if magic_burst_like else 0.0) + (0.7 if catch_like else 0.0))
        if counter_hero_name
        else 0.0,
        reason="This counter hero often scales through spell upgrades when the game calls for more reach or combo value.",
        tags=["Upgrade", "Scaling"],
        category="Synergy",
    )

    if not suggestion_map:
        return pd.DataFrame(columns=["item_name", "image_url", "score", "reason", "tags", "category"])

    suggestion_rows: list[dict] = []
    for entry in suggestion_map.values():
        suggestion_rows.append(
            {
                "item_name": entry["item_name"],
                "image_url": get_item_image_url(entry["item_slug"]),
                "score": round(entry["score"], 2),
                "reason": entry["reasons"][0],
                "tags": ", ".join(sorted(entry["tags"])),
                "category": max(entry["category_scores"], key=entry["category_scores"].get),
            }
        )

    suggestions_df = pd.DataFrame(suggestion_rows).sort_values(
        ["score", "item_name"], ascending=[False, True]
    )
    return suggestions_df.head(6).reset_index(drop=True)


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
    columns = st.columns(len(top_results))
    for column, (_, hero_row) in zip(columns, top_results.iterrows()):
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
        hero_name = str(hero_row["localized_name"])
        focused_counter = st.session_state.get("focused_counter_hero", "")
        selected_class = " selected" if focused_counter == hero_name else ""
        card_html = (
            f'<div class="counter-card-shell"><div class="counter-card{selected_class}">'
            '<div class="counter-card-topline">'
            f'<span class="counter-card-pill primary">Hybrid {hero_row["hybrid_score"]:.2f}</span>'
            f"{synergy_badge}"
            "</div>"
            f'<img src="{hero_row["image_url"]}" alt="{hero_name}" class="counter-card-image" />'
            f'<div class="counter-card-name">{hero_name}</div>'
            f'<div class="counter-card-meta">Win Rate: {win_rate_text}</div>'
            f'<div class="counter-card-meta">Matches: {games_text}</div>'
            "</div></div>"
        )
        with column:
            st.markdown(card_html, unsafe_allow_html=True)
            if st.button(hero_name, key=f"focus_counter_{hero_name}", use_container_width=True):
                st.session_state["focused_counter_hero"] = hero_name
                st.rerun()


def render_item_suggestions(item_df: pd.DataFrame) -> None:
    """Render situational item suggestions as compact cards."""
    if item_df.empty:
        return

    st.subheader("Situational Item Suggestions")
    cards: list[str] = []
    for _, item_row in item_df.iterrows():
        tag_html = "".join(
            f'<span class="item-card-tag">{tag.strip()}</span>'
            for tag in str(item_row["tags"]).split(",")
            if tag.strip()
        )
        cards.append(
            '<div class="item-card">'
            '<div class="item-card-topline">'
            f'<span class="item-card-score">Priority {item_row["score"]:.1f}</span>'
            f'<div class="item-card-tags">{tag_html}</div>'
            "</div>"
            '<div class="item-card-body">'
            f'<img src="{item_row["image_url"]}" alt="{item_row["item_name"]}" class="item-card-image" />'
            '<div class="item-card-copy">'
            f'<div class="item-card-name">{item_row["item_name"]}</div>'
            f'<div class="item-card-category">{item_row["category"]}</div>'
            f'<div class="item-card-reason">{item_row["reason"]}</div>'
            "</div>"
            "</div>"
            "</div>"
        )
    st.markdown(f'<div class="item-cards-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def inject_app_theme() -> None:
    """Inject the app-wide visual theme."""
    st.markdown(
        """
        <style>
        :root {
            --st-bg: var(--background-color, #f4f1e8);
            --st-panel: var(--secondary-background-color, rgba(255, 255, 255, 0.76));
            --st-text: var(--text-color, #232a36);
            --bg-main: color-mix(in srgb, var(--st-bg) 92%, #0f141b 8%);
            --bg-panel: color-mix(in srgb, var(--st-panel) 82%, transparent);
            --bg-panel-strong: color-mix(in srgb, var(--st-panel) 92%, var(--st-bg) 8%);
            --bg-select: color-mix(in srgb, var(--st-panel) 88%, var(--st-bg) 12%);
            --border-soft: color-mix(in srgb, var(--st-text) 14%, transparent);
            --text-main: var(--st-text);
            --text-muted: color-mix(in srgb, var(--st-text) 62%, var(--st-bg) 38%);
            --accent-gold: #cf8b17;
            --accent-teal: #0f8b8d;
            --shadow-soft: 0 18px 40px rgba(31, 38, 49, 0.08);
            --sidebar-border: color-mix(in srgb, var(--st-text) 10%, transparent);
            --app-bg:
                radial-gradient(circle at top left, rgba(207, 139, 23, 0.14), transparent 28%),
                radial-gradient(circle at top right, rgba(15, 139, 141, 0.12), transparent 24%),
                linear-gradient(
                    180deg,
                    color-mix(in srgb, var(--st-bg) 92%, white 8%) 0%,
                    color-mix(in srgb, var(--st-bg) 94%, black 6%) 100%
                );
            --sidebar-bg: linear-gradient(
                180deg,
                color-mix(in srgb, var(--st-panel) 94%, var(--st-bg) 6%),
                color-mix(in srgb, var(--st-panel) 84%, var(--st-bg) 16%)
            );
            --card-bg: linear-gradient(
                180deg,
                color-mix(in srgb, var(--st-panel) 94%, white 6%),
                color-mix(in srgb, var(--st-panel) 88%, var(--st-bg) 12%)
            );
            --feature-panel-bg: linear-gradient(
                180deg,
                color-mix(in srgb, var(--st-panel) 72%, #11161d 28%) 0%,
                color-mix(in srgb, var(--st-panel) 76%, #0c1118 24%) 100%
            );
            --feature-panel-title: color-mix(in srgb, var(--st-text) 92%, white 8%);
            --feature-panel-subtle: color-mix(in srgb, var(--st-text) 56%, var(--st-bg) 44%);
            --feature-panel-gold-border: rgba(255, 184, 0, 0.18);
            --feature-panel-teal-border: rgba(64, 236, 217, 0.18);
            --feature-panel-inset: inset 0 1px 0 rgba(255,255,255,0.03);
            --pill-primary-bg: color-mix(in srgb, var(--accent-gold) 18%, transparent);
            --pill-primary-text: color-mix(in srgb, var(--accent-gold) 72%, var(--st-text) 28%);
            --pill-teal-bg: color-mix(in srgb, var(--accent-teal) 16%, transparent);
            --pill-teal-text: color-mix(in srgb, var(--accent-teal) 72%, var(--st-text) 28%);
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
            border-right: 1px solid var(--sidebar-border);
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
            grid-template-columns: repeat(5, minmax(0, 1fr));
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
            transition: transform 120ms ease, border-color 120ms ease, box-shadow 120ms ease;
        }
        .counter-card-shell {
            position: relative;
        }
        div[data-testid="column"]:has(.counter-card-shell) {
            position: relative;
        }
        div[data-testid="column"]:has(.counter-card-shell) > div:has(div[data-testid="stButton"]) {
            position: absolute;
            inset: 0;
            z-index: 5;
        }
        div[data-testid="column"]:has(.counter-card-shell) div[data-testid="stButton"] {
            width: 100%;
            height: 100%;
        }
        div[data-testid="column"]:has(.counter-card-shell) div[data-testid="stButton"] button {
            width: 100%;
            height: 100%;
            opacity: 0;
            border: none;
            background: transparent;
            cursor: pointer;
            border-radius: 16px;
            padding: 0;
            margin: 0;
            min-height: 0;
            display: block;
        }
        div[data-testid="column"]:has(.counter-card-shell):hover .counter-card {
            transform: translateY(-2px);
            border-color: rgba(207, 139, 23, 0.28);
            box-shadow: 0 16px 30px rgba(0, 0, 0, 0.12);
        }
        .counter-card.selected {
            border-color: rgba(207, 139, 23, 0.42);
            box-shadow: 0 0 0 1px rgba(207, 139, 23, 0.18), var(--shadow-soft);
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
            background: var(--pill-primary-bg);
            color: var(--pill-primary-text);
        }
        .counter-card-pill.synergy {
            background: var(--pill-teal-bg);
            color: var(--pill-teal-text);
        }
        .counter-card-image {
            width: 100%;
            aspect-ratio: 16 / 9;
            border-radius: 12px;
            object-fit: cover;
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
        .item-cards-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.9rem;
            margin-bottom: 1rem;
        }
        .item-card {
            background: var(--card-bg);
            border: 1px solid var(--border-soft);
            border-radius: 16px;
            padding: 0.8rem 0.9rem;
            box-shadow: var(--shadow-soft);
        }
        .item-card-topline {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.6rem;
            margin-bottom: 0.65rem;
        }
        .item-card-score {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.24rem 0.54rem;
            font-size: 0.7rem;
            font-weight: 800;
            letter-spacing: 0.01em;
            background: var(--pill-primary-bg);
            color: var(--pill-primary-text);
        }
        .item-card-tags {
            display: flex;
            flex-wrap: wrap;
            justify-content: flex-end;
            gap: 0.35rem;
        }
        .item-card-tag {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.2rem 0.48rem;
            font-size: 0.66rem;
            font-weight: 700;
            background: var(--pill-teal-bg);
            color: var(--pill-teal-text);
        }
        .item-card-body {
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
        }
        .item-card-image {
            width: 56px;
            height: 56px;
            border-radius: 12px;
            object-fit: cover;
            flex-shrink: 0;
        }
        .item-card-copy {
            min-width: 0;
        }
        .item-card-name {
            color: var(--text-main);
            font-size: 0.96rem;
            font-weight: 800;
            margin-bottom: 0.25rem;
            line-height: 1.2;
        }
        .item-card-category {
            color: var(--accent-gold);
            font-size: 0.72rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.28rem;
        }
        .item-card-reason {
            color: var(--text-muted);
            font-size: 0.8rem;
            line-height: 1.45;
        }
        h1, h2, h3 {
            color: var(--text-main);
            letter-spacing: -0.03em;
        }
        div[data-testid="stCaptionContainer"] {
            color: var(--text-muted);
        }
        .enemy-draft-shell {
            background: var(--feature-panel-bg);
            border: 1px solid var(--feature-panel-gold-border);
            border-radius: 18px;
            padding: 1rem 1.1rem 1.2rem;
            margin: 0.8rem 0 1.2rem;
            box-shadow: var(--feature-panel-inset);
        }
        .enemy-draft-title {
            color: var(--feature-panel-title);
            font-size: 1.55rem;
            font-weight: 800;
            letter-spacing: 0.01em;
            margin: 0;
        }
        .enemy-draft-subtitle {
            color: var(--feature-panel-subtle);
            font-size: 0.86rem;
            margin-top: 0.2rem;
        }
        .hero-selection-shell {
            background: var(--feature-panel-bg);
            border: 1px solid var(--feature-panel-teal-border);
            border-radius: 18px;
            padding: 1rem 1.1rem 1.2rem;
            margin: 0.8rem 0 1.2rem;
            box-shadow: var(--feature-panel-inset);
        }
        .panel-heading {
            color: var(--feature-panel-title);
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
            color: var(--feature-panel-subtle);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.35rem;
        }
        @media (max-width: 1200px) {
            .enemy-heroes-grid,
            .counter-cards-grid,
            .item-cards-grid {
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
            .counter-cards-grid,
            .item-cards-grid {
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
            .counter-cards-grid,
            .item-cards-grid {
                grid-template-columns: minmax(0, 1fr);
            }
            .enemy-hero-card,
            .counter-card,
            .item-card {
                padding: 0.5rem;
            }
            .enemy-hero-name,
            .counter-card-name {
                font-size: 0.84rem;
            }
            .counter-card-meta {
                font-size: 0.72rem;
            }
            .item-card-topline {
                flex-direction: column;
                align-items: flex-start;
            }
            .item-card-tags {
                justify-content: flex-start;
            }
            .item-card-image {
                width: 48px;
                height: 48px;
            }
            .item-card-reason {
                font-size: 0.76rem;
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
    show_invoker_assistant: bool,
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
            <div class="summary-card">
                <div class="summary-label">Invoker Assistant</div>
                <div class="summary-value">{'On' if show_invoker_assistant else 'Off'}</div>
                <div class="summary-subtle">Draft reading, spell focus, and timing reminders</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_ally_synergy_scores(hero_df: pd.DataFrame, ally_hero_names: Iterable[str] | None) -> dict[str, float]:
    """Return combined synergy scores using explicit combos plus role-based inference."""
    if not ally_hero_names:
        return {}

    synergy_config = load_synergy_config()
    ally_synergy_map = synergy_config.get("ally_synergy_map", {})
    role_synergy_weights = synergy_config.get("role_synergy_weights", {})
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
                role_weights = role_synergy_weights.get(ally_role, {})
                for candidate_role in candidate_roles:
                    inferred_score += role_weights.get(candidate_role, 0.0)

            # Keep inferred synergy broad but weaker than hand-tuned combos.
            if inferred_score > 0:
                combined_scores[candidate_name] = combined_scores.get(candidate_name, 0.0) + min(
                    inferred_score, 3.5
                )

        for synergy_hero, score in ally_synergy_map.get(hero_name, {}).items():
            combined_scores[synergy_hero] = combined_scores.get(synergy_hero, 0.0) + score

    return combined_scores


def add_weighted_invoker_item(
    suggestion_map: dict[str, dict[str, object]],
    *,
    item_name: str,
    score: float,
    timing: str,
    reason: str,
    triggers: Iterable[str],
) -> None:
    """Accumulate weighted Invoker item priorities."""
    if score <= 0:
        return

    entry = suggestion_map.setdefault(
        item_name,
        {
            "item_name": item_name,
            "score": 0.0,
            "timing": timing,
            "reasons": [],
            "triggers": set(),
        },
    )
    entry["score"] += score
    entry["reasons"].append(reason)
    entry["triggers"].update(triggers)


def build_invoker_skill_build(
    route_title: str,
    *,
    regen_count: int,
    low_mana_count: int,
    low_armor_count: int,
    silence_count: int,
    jump_burst_count: int,
    deathball_count: int,
) -> list[dict[str, str]]:
    """Return level-by-level orb priority guidance for Invoker."""
    skill_rows = [
        {"level": "1", "orb": "", "why": ""},
        {"level": "2", "orb": "", "why": ""},
        {"level": "3", "orb": "", "why": ""},
        {"level": "4", "orb": "", "why": ""},
        {"level": "5", "orb": "", "why": ""},
        {"level": "6", "orb": "Invoke", "why": "First real combo window opens here."},
        {"level": "7", "orb": "", "why": ""},
        {"level": "8", "orb": "", "why": ""},
        {"level": "9", "orb": "", "why": ""},
        {"level": "10", "orb": "Talent", "why": "Take the talent that supports your route and lane state."},
        {"level": "11", "orb": "", "why": ""},
        {"level": "12", "orb": "", "why": ""},
        {"level": "13", "orb": "", "why": ""},
        {"level": "14", "orb": "", "why": ""},
        {"level": "15", "orb": "Talent", "why": "Choose the talent that matches whether fights are about burst conversion or safer spell uptime."},
        {"level": "16", "orb": "", "why": ""},
        {"level": "17", "orb": "", "why": ""},
        {"level": "18", "orb": "", "why": ""},
    ]

    if route_title == "Quas-Wex":
        default_orbs = ["Quas", "Wex", "Wex", "Quas", "Wex", "Quas"]
        fallback_notes = [
            "Lane sustain and last-hit security.",
            "Unlock movement and harassment.",
            "Accelerate EMP and skirmish tempo.",
            "Extra survivability for trades.",
            "Reach stronger Tornado-EMP pacing.",
            "Stabilize before mid-game rotations.",
        ]
        level8_default = ("Quas", "A third Quas point gives better trading margin once fights become longer.")
        level9_default = ("Wex", "This sharpens your main tempo route before mid-game skirmishes fully open.")
        late_defaults = {
            "11": ("Wex", "Mid-game fights still reward catch, tempo, and cleaner EMP connections."),
            "12": ("Quas", "Extra Quas makes repeated spell cycles safer when fights start extending."),
            "13": ("Wex", "Keep your main control route ahead of enemy mobility and BKB timings."),
            "14": ("Quas", "This is the defensive stabilizer point if enemies are reaching you too easily."),
            "16": ("Wex", "By now your identity should fully support control-heavy mid-game fights."),
            "17": ("Quas", "More survivability lets you get a second spell cycle instead of dying after first contact."),
            "18": ("Wex", "Cap the route that most directly affects tempo and catch reliability."),
        }
    else:
        default_orbs = ["Exort", "Quas", "Exort", "Quas", "Exort", "Wex"]
        fallback_notes = [
            "Open with stronger lane pressure and denies.",
            "Add sustain so lane damage sticks less on you.",
            "Forge Spirit and Sun Strike scaling improve.",
            "Quas keeps the lane playable while greedier levels come in.",
            "Hit your real damage spike earlier.",
            "One Wex point improves spell access and positioning.",
        ]
        level8_default = ("Wex", "A first meaningful Wex point improves reach and makes spell sequencing less clunky.")
        level9_default = ("Exort", "This keeps your damage route ahead of enemy defensive item timings.")
        late_defaults = {
            "11": ("Exort", "Push your damage breakpoint before enemy cores become too tanky for partial combos."),
            "12": ("Quas", "A stabilizing Quas point keeps you from becoming too punishable while scaling."),
            "13": ("Exort", "This is where Forge Spirit, Sun Strike, and Meteor conversions start to matter more."),
            "14": ("Wex", "You need enough mobility and cast fluidity to actually deliver your damage spells."),
            "16": ("Exort", "Continue into the high-damage route if you are still killing targets through control."),
            "17": ("Quas", "Take extra safety once enemy jump and BKB timings compress your casting window."),
            "18": ("Exort", "Finish the level 18 segment by maximizing your main scaling vector."),
        }

    editable_levels = ["1", "2", "3", "4", "5", "7"]
    editable_rows = [row for row in skill_rows if row["level"] in editable_levels]
    for row, orb, note in zip(editable_rows, default_orbs, fallback_notes):
        if row["orb"]:
            row["why"] = note
            continue
        row["orb"] = orb
        row["why"] = note

    if regen_count >= 1:
        for row in skill_rows:
            if row["level"] == "4":
                row["orb"] = "Quas"
                row["why"] = "Enemy sustain cores make lane attrition matter more; stabilize and prepare for Vessel value."
            if row["level"] == "5" and route_title == "Quas-Exort":
                row["orb"] = "Quas"
                row["why"] = "A second Quas point keeps trades efficient before raw damage alone can finish regen heroes."
    if low_mana_count >= 2:
        for row in skill_rows:
            if row["level"] == "4":
                row["orb"] = "Wex"
                row["why"] = "Punish mana-fragile heroes immediately with faster EMP timing."
            if row["level"] == "5" and route_title == "Quas-Wex":
                row["orb"] = "Wex"
                row["why"] = "Double down on movement and mana pressure before enemy heroes can itemize out."
    if low_armor_count >= 2 and route_title == "Quas-Exort":
        for row in skill_rows:
            if row["level"] == "7":
                row["orb"] = "Exort"
                row["why"] = "Multiple low-armor targets mean Forge Spirit and right-click follow-up scale immediately."
    if silence_count >= 2 or jump_burst_count >= 2:
        for row in skill_rows:
            if row["level"] == "8":
                row["orb"] = "Quas"
                row["why"] = "You need more forgiveness against repeated jump or silence pressure."
    if deathball_count >= 2:
        for row in skill_rows:
            if row["level"] == "9":
                row["orb"] = "Wex" if route_title == "Quas-Wex" else "Exort"
                row["why"] = "Their grouped timing means you should sharpen your main fight spell before outer towers fall."

    if route_title == "Quas-Wex" and low_mana_count >= 2:
        late_defaults["11"] = ("Wex", "Enemy mana pools still justify harder commitment into EMP tempo.")
        late_defaults["12"] = ("Wex", "A further Wex point keeps the mana-burn timing oppressive into mid game.")
    if route_title == "Quas-Exort" and low_armor_count >= 2:
        late_defaults["11"] = ("Exort", "Low-armor cores are still punishable, so greedier damage remains correct.")
        late_defaults["13"] = ("Exort", "Another Exort point keeps Forge Spirit and spell burst ahead of their armor items.")
    if regen_count >= 1:
        late_defaults["12"] = ("Quas", "Regen matchups still demand durable trading until Vessel or similar anti-heal is online.")
    if silence_count >= 2 or jump_burst_count >= 2:
        late_defaults["14"] = ("Quas", "You need a larger error margin because one jump or silence can otherwise end your fight.")
        late_defaults["17"] = ("Quas", "Late mid-game still requires survivability over greed if enemy catch stays reliable.")
    if deathball_count >= 2:
        deathball_orb = "Wex" if route_title == "Quas-Wex" else "Exort"
        late_defaults["16"] = (
            deathball_orb,
            "Their grouped timing means your main teamfight orb should peak before the biggest five-man fights.",
        )
        late_defaults["18"] = (
            deathball_orb,
            "Stay committed to the orb that most improves large fight execution against grouped enemies.",
        )

    for row in skill_rows:
        if row["level"] == "8" and not row["orb"]:
            row["orb"], row["why"] = level8_default
        if row["level"] == "9" and not row["orb"]:
            row["orb"], row["why"] = level9_default
        if row["level"] in late_defaults and not row["orb"]:
            row["orb"], row["why"] = late_defaults[row["level"]]

    return skill_rows


def build_invoker_item_priority(
    enemy_names: Iterable[str],
    *,
    regen_count: int,
    silence_count: int,
    blink_count: int,
    physical_burst_count: int,
    jump_burst_count: int,
    targeted_count: int,
    escape_count: int,
    big_teamfight_allies: int,
    pickoff_allies: int,
    save_sensitive_allies: int,
    frontline_allies: int,
) -> list[dict[str, object]]:
    """Return weighted item priorities for Invoker."""
    suggestion_map: dict[str, dict[str, object]] = {}
    enemy_list = list(enemy_names)

    add_weighted_invoker_item(
        suggestion_map,
        item_name="Eul's Scepter of Divinity",
        score=(silence_count * 2.6) + (blink_count * 0.7) + (pickoff_allies * 0.4),
        timing="Early-mid game",
        reason="Silence-heavy drafts punish greedy casting windows, so self-dispel and setup both gain value.",
        triggers=["Silence", "Setup"],
    )
    add_weighted_invoker_item(
        suggestion_map,
        item_name="Black King Bar",
        score=(silence_count * 2.2) + (jump_burst_count * 1.3) + (save_sensitive_allies * 0.5),
        timing="Before full 5v5 fights",
        reason="You need one clean spell cycle when enemy initiation or silence can otherwise remove you from the fight.",
        triggers=["Silence", "Jump"],
    )
    add_weighted_invoker_item(
        suggestion_map,
        item_name="Spirit Vessel",
        score=(regen_count * 3.0) + (pickoff_allies * 0.6),
        timing="First major item",
        reason="Regen heroes break your normal damage thresholds unless healing reduction arrives early.",
        triggers=["Regen"],
    )
    add_weighted_invoker_item(
        suggestion_map,
        item_name="Ghost Scepter",
        score=(physical_burst_count * 2.8) + (jump_burst_count * 0.9) + (save_sensitive_allies * 0.4),
        timing="Before PA/TA style timings",
        reason="Early physical burst drafts force a cheap defensive bridge before you can finish greedier items.",
        triggers=["Physical Burst"],
    )
    add_weighted_invoker_item(
        suggestion_map,
        item_name="Urn of Shadows",
        score=(blink_count * 1.7) + (regen_count * 0.8) + (pickoff_allies * 0.8),
        timing="Very early skirmish item",
        reason="Blink initiators hate taking persistent damage because it delays or cancels their clean entry windows.",
        triggers=["Blink", "Tempo"],
    )
    add_weighted_invoker_item(
        suggestion_map,
        item_name="Scythe of Vyse",
        score=(escape_count * 2.3) + (blink_count * 0.5) + (pickoff_allies * 0.7),
        timing="Core control timing",
        reason="Mobile cores eventually require instant disable rather than longer setup chains.",
        triggers=["Escape", "Control"],
    )
    add_weighted_invoker_item(
        suggestion_map,
        item_name="Linken's Sphere",
        score=(targeted_count * 2.1) + (save_sensitive_allies * 0.5),
        timing="Mid game protection",
        reason="Single-target catch forces you into defensive itemization once positioning alone stops being enough.",
        triggers=["Targeted Catch"],
    )
    add_weighted_invoker_item(
        suggestion_map,
        item_name="Blink Dagger",
        score=(big_teamfight_allies * 1.4) + (frontline_allies * 0.5),
        timing="Mid-game setup timing",
        reason="Teamfight-heavy ally drafts reward sharper positioning for Tornado, Ice Wall, and follow-up spell layering.",
        triggers=["Ally Teamfight", "Positioning"],
    )
    add_weighted_invoker_item(
        suggestion_map,
        item_name="Aghanim's Scepter",
        score=(big_teamfight_allies * 1.3) + (frontline_allies * 0.4),
        timing="After your first core utility item",
        reason="When allies already start fights well, extra spell reach and teamfight conversion become easier to realize.",
        triggers=["Ally Teamfight", "Scaling"],
    )

    for enemy_name in enemy_list:
        reminder = INVOKER_ITEM_REMINDERS.get(enemy_name)
        if not reminder:
            continue
        add_weighted_invoker_item(
            suggestion_map,
            item_name=str(reminder["item"]),
            score=2.4,
            timing=str(reminder["timing"]),
            reason=f"{enemy_name} specifically changes the matchup and creates a dedicated response tax.",
            triggers=[enemy_name],
        )

    item_rows = []
    for entry in suggestion_map.values():
        item_rows.append(
            {
                "item_name": str(entry["item_name"]),
                "score": round(float(entry["score"]), 1),
                "timing": str(entry["timing"]),
                "reason": str(entry["reasons"][0]),
                "triggers": ", ".join(sorted(str(trigger) for trigger in entry["triggers"])),
            }
        )

    return sorted(item_rows, key=lambda row: (-float(row["score"]), str(row["item_name"])))[:6]


def build_invoker_combo_plan(
    *,
    deathball_count: int,
    pickoff_count: int,
    low_mana_count: int,
    low_armor_count: int,
    escape_count: int,
    regen_count: int,
    big_teamfight_allies: int,
    pickoff_allies: int,
    frontline_allies: int,
) -> list[dict[str, str]]:
    """Return game-phase combo recommendations for Invoker."""
    early_combo = {
        "phase": "Early",
        "combo": "Cold Snap + Forge Spirit" if low_armor_count >= 1 else "Tornado + EMP",
        "why": (
            "Lane and small skirmishes are about forcing inefficient trades on low-armor targets."
            if low_armor_count >= 1
            else "Mana burn and reset pressure matter more before larger items appear."
        ),
    }
    if pickoff_count >= 2:
        early_combo = {
            "phase": "Early",
            "combo": "Cold Snap + Alacrity + Urn/Spirit Vessel",
            "why": "Against pickoff lineups, punishing isolated heroes before they reset is worth more than slower teamfight combos.",
        }
    if pickoff_allies >= 1:
        early_combo = {
            "phase": "Early",
            "combo": "Cold Snap + Sun Strike + ally follow-up",
            "why": "Your allied pickoff heroes make fast single-target conversions more reliable than generic poke trades.",
        }

    mid_combo = {
        "phase": "Mid",
        "combo": "Tornado + EMP + Chaos Meteor",
        "why": "Grouped fights and objective pressure reward large area denial and mana collapse.",
    }
    if big_teamfight_allies >= 1:
        mid_combo = {
            "phase": "Mid",
            "combo": "Ally setup + Tornado + Chaos Meteor + Deafening Blast",
            "why": "Reliable allied teamfight setup means you can play for cleaner layered spell damage instead of forcing every opener yourself.",
        }
    if deathball_count < 2 and pickoff_count >= 2:
        mid_combo = {
            "phase": "Mid",
            "combo": "Tornado + Cold Snap + Sun Strike",
            "why": "Split map games reward fast single-target conversion more than committing every spell into one area.",
        }

    late_combo = {
        "phase": "Late",
        "combo": "Tornado + Chaos Meteor + Deafening Blast",
        "why": "This remains the most reliable full-spell-cycle fight closer once BKBs and positioning tighten windows.",
    }
    if regen_count >= 1:
        late_combo["why"] += " Add Spirit Vessel before the chain if sustain cores are surviving your first pass."
    if escape_count >= 2:
        late_combo = {
            "phase": "Late",
            "combo": "Hex/disable + Ice Wall + Chaos Meteor + Deafening Blast",
            "why": "Mobile cores are harder to keep inside classic Tornado setups, so instant catch becomes the real fight starter.",
        }
    if frontline_allies >= 1 and escape_count < 2:
        late_combo = {
            "phase": "Late",
            "combo": "Frontline ally commit + Tornado + Chaos Meteor + Deafening Blast",
            "why": "A real frontline gives you time to hold positioning and deliver a full second-wave spell cycle.",
        }

    return [early_combo, mid_combo, late_combo]


def build_invoker_assistant_data(
    selected_enemy_names: Iterable[str],
    ally_hero_names: Iterable[str] | None = None,
) -> dict[str, object]:
    """Produce Invoker-specific coaching notes from the current draft."""
    enemy_names = list(selected_enemy_names)
    ally_names = list(ally_hero_names or [])

    low_mana_count = count_matching_heroes(enemy_names, INVOKER_DRAFT_SIGNALS["low_mana_pool"])
    low_armor_count = count_matching_heroes(enemy_names, INVOKER_DRAFT_SIGNALS["low_armor"])
    slow_core_count = count_matching_heroes(enemy_names, INVOKER_DRAFT_SIGNALS["slow_cores"])
    bkb_punishable_count = count_matching_heroes(enemy_names, INVOKER_DRAFT_SIGNALS["bkb_punishable"])
    silence_count = count_matching_heroes(enemy_names, INVOKER_DRAFT_SIGNALS["silence_threats"])
    blink_count = count_matching_heroes(enemy_names, INVOKER_DRAFT_SIGNALS["blink_initiators"])
    physical_burst_count = count_matching_heroes(enemy_names, INVOKER_DRAFT_SIGNALS["physical_burst"])
    deathball_count = count_matching_heroes(enemy_names, INVOKER_DRAFT_SIGNALS["deathball"])
    pickoff_count = count_matching_heroes(enemy_names, INVOKER_DRAFT_SIGNALS["pickoff"])
    escape_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["escape_heroes"])
    jump_burst_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["jump_burst"])
    regen_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["super_regen"])
    illusion_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["illusions_summons"])
    disable_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["hard_disable"])
    targeted_count = count_matching_heroes(enemy_names, ENEMY_ARCHETYPES["single_target_spells"])
    big_teamfight_allies = count_matching_heroes(ally_names, ALLY_ARCHETYPES["big_teamfight"])
    pickoff_allies = count_matching_heroes(ally_names, ALLY_ARCHETYPES["pickoff_allies"])
    save_sensitive_allies = count_matching_heroes(ally_names, ALLY_ARCHETYPES["save_sensitive_cores"])
    frontline_allies = count_matching_heroes(ally_names, ALLY_ARCHETYPES["frontline_cores"])

    draft_pressure_points: list[str] = []
    if low_mana_count >= 2:
        draft_pressure_points.append(
            "Several enemy heroes have fragile mana pools, so Tornado plus EMP can win fights before damage spells even start."
        )
    if low_armor_count >= 2:
        draft_pressure_points.append(
            "The draft has multiple low-armor targets, which makes Forge Spirit pressure, Cold Snap trades, and physical follow-up scale well."
        )
    if escape_count <= 1:
        draft_pressure_points.append(
            "Enemy mobility is limited, so long spell chains are easier to convert into full kills instead of partial poke."
        )
    if slow_core_count >= 2:
        draft_pressure_points.append(
            "Their cores are relatively static in fights, which improves Ice Wall control and Chaos Meteor consistency."
        )
    if bkb_punishable_count >= 2:
        draft_pressure_points.append(
            "They depend on timing-based BKB cores, so forcing awkward BKB usage and re-engaging with cooldowns is a strong plan."
        )
    if silence_count >= 2:
        draft_pressure_points.append(
            "Multiple silence sources mean you cannot plan fights as a full greedy spell cycle without a defensive bridge item."
        )
    if big_teamfight_allies >= 1:
        draft_pressure_points.append(
            "Your own draft already supplies strong teamfight setup, so Invoker gains extra value from layered AoE spell conversion."
        )
    if pickoff_allies >= 1:
        draft_pressure_points.append(
            "Your allies can start pickoffs for you, so single-target conversion spells and catch items get better than usual."
        )
    if not draft_pressure_points:
        draft_pressure_points.append(
            "This draft is more balanced than exploitable, so Invoker should play around execution windows rather than one obvious structural weakness."
        )

    quas_wex_score = (
        (low_mana_count * 2.4)
        + (escape_count * 1.6)
        + (jump_burst_count * 1.1)
        + (pickoff_allies * 0.8)
        + (disable_count * 0.4)
    )
    quas_exort_score = (
        (low_armor_count * 2.1)
        + (slow_core_count * 1.7)
        + (big_teamfight_allies * 1.0)
        + (illusion_count * 0.6)
        + (max(1 - escape_count, 0) * 1.4)
    )

    if quas_wex_score >= quas_exort_score:
        route_title = "Quas-Wex"
        route_reason = (
            "This game rewards tempo, mana burn, and repeated control more than pure greed. "
            "You should pressure skirmishes early, rotate faster, and make EMP-centered fights awkward for mobile or mana-hungry heroes."
        )
        route_plan = "Prioritize lane stability into early movement, look for Tornado-EMP windows, and force resources before enemy cores reach clean item timings."
    else:
        route_title = "Quas-Exort"
        route_reason = (
            "This game gives you enough time and enough vulnerable targets to scale for damage. "
            "You should lean into stronger lane threat, Forge Spirit chip, and heavier spell conversion once key targets are controlled."
        )
        route_plan = "Use lane pressure and farming efficiency to reach damage timings, then play around Sun Strike, Cold Snap, and Meteor/Blast kill windows."

    if big_teamfight_allies >= 1 and route_title == "Quas-Exort":
        route_plan += " Since your allies already provide setup, you can hold spells longer and commit for layered AoE instead of rushed openers."
    if pickoff_allies >= 1 and route_title == "Quas-Wex":
        route_plan += " Ally catch means your rotations should convert into faster isolated kills rather than only mana-burn poke."
    if frontline_allies >= 1:
        route_plan += " A real frontline lets you position more greedily for a second spell cycle."
    if save_sensitive_allies >= 1:
        route_plan += " Keep enough defensive flexibility to peel or reset fights when your vulnerable backliners are being hunted."

    skill_rows = build_invoker_skill_build(
        route_title,
        regen_count=regen_count,
        low_mana_count=low_mana_count,
        low_armor_count=low_armor_count,
        silence_count=silence_count,
        jump_burst_count=jump_burst_count,
        deathball_count=deathball_count,
    )
    item_rows = build_invoker_item_priority(
        enemy_names,
        regen_count=regen_count,
        silence_count=silence_count,
        blink_count=blink_count,
        physical_burst_count=physical_burst_count,
        jump_burst_count=jump_burst_count,
        targeted_count=targeted_count,
        escape_count=escape_count,
        big_teamfight_allies=big_teamfight_allies,
        pickoff_allies=pickoff_allies,
        save_sensitive_allies=save_sensitive_allies,
        frontline_allies=frontline_allies,
    )
    combo_rows = build_invoker_combo_plan(
        deathball_count=deathball_count,
        pickoff_count=pickoff_count,
        low_mana_count=low_mana_count,
        low_armor_count=low_armor_count,
        escape_count=escape_count,
        regen_count=regen_count,
        big_teamfight_allies=big_teamfight_allies,
        pickoff_allies=pickoff_allies,
        frontline_allies=frontline_allies,
    )

    spell_notes: list[str] = []
    if deathball_count >= 2:
        spell_notes.append("`Tornado + EMP + Chaos Meteor` should be your default grouped-fight shell into deathball timings.")
    if pickoff_count >= 2:
        spell_notes.append("`Cold Snap` plus single-target follow-up matters more because the map will present isolated catches.")
    if low_mana_count >= 2:
        spell_notes.append("`EMP` is a first-class spell here because draining mana removes both damage and escape options.")
    if silence_count >= 2:
        spell_notes.append("`Ghost Walk` discipline matters more than usual because your fights can collapse if you are silenced before the first cast.")
    if slow_core_count >= 2 or jump_burst_count >= 1:
        spell_notes.append("`Ice Wall` is a high-value follow-up because static or diving heroes struggle once they commit through it.")
    if low_armor_count >= 2:
        spell_notes.append("`Forge Spirit` deserves more attention because armor reduction improves both lane and mid-game conversions.")
    if big_teamfight_allies >= 1:
        spell_notes.append("`Chaos Meteor` and `Deafening Blast` gain value when your allies already provide reliable setup.")
    if pickoff_allies >= 1:
        spell_notes.append("`Cold Snap` and `Sun Strike` rise in value because allied catch makes single-target execution more consistent.")
    if frontline_allies >= 1:
        spell_notes.append("`Chaos Meteor` becomes easier to maximize because your frontline buys more cast time and positional discipline.")
    if save_sensitive_allies >= 1:
        spell_notes.append("`Tornado` has extra defensive value because it can interrupt dives onto fragile allied cores.")
    if escape_count <= 1 and low_armor_count >= 1:
        spell_notes.append("`Cold Snap` is strong in skirmishes because enemies cannot easily disengage from repeated mini-stuns.")
    if not spell_notes:
        spell_notes.append("`Tornado`, `EMP`, and `Cold Snap` remain the safest default trio until the game reveals clearer priorities.")

    return {
        "pressure_points": draft_pressure_points[:4],
        "route_title": route_title,
        "route_reason": route_reason,
        "route_plan": route_plan,
        "synergy_summary": [
            note
            for note in [
                "Ally teamfight setup pushes Invoker toward bigger AoE follow-up windows." if big_teamfight_allies >= 1 else "",
                "Ally pickoff tools make single-target conversions and catch itemization stronger." if pickoff_allies >= 1 else "",
                "Frontline allies give you safer casting distance and more second-cycle value." if frontline_allies >= 1 else "",
                "Save-sensitive allied cores increase the value of defensive Tornado usage and flexible positioning." if save_sensitive_allies >= 1 else "",
            ]
            if note
        ][:4],
        "skill_rows": skill_rows,
        "item_rows": item_rows,
        "combo_rows": combo_rows,
        "spell_notes": spell_notes[:4],
    }


def render_invoker_assistant(
    selected_enemy_names: Iterable[str],
    ally_hero_names: Iterable[str] | None = None,
) -> None:
    """Render the Invoker coaching panel."""
    assistant_data = build_invoker_assistant_data(selected_enemy_names, ally_hero_names)

    st.subheader("Invoker Assistant")
    st.caption("Draft-aware coaching for Invoker: lane direction, key punish windows, and spell priorities.")

    draft_col, route_col = st.columns(2)
    with draft_col:
        st.markdown("**Draft Analysis**")
        for note in assistant_data["pressure_points"]:
            st.markdown(f"- {note}")
    with route_col:
        st.markdown(f"**Early Route: {assistant_data['route_title']}**")
        st.write(str(assistant_data["route_reason"]))
        st.caption(str(assistant_data["route_plan"]))
        if assistant_data.get("synergy_summary"):
            st.markdown("**Ally Synergy Impact**")
            for note in assistant_data["synergy_summary"]:
                st.markdown(f"- {note}")

    skill_df = pd.DataFrame(assistant_data["skill_rows"]).rename(
        columns={"level": "Level", "orb": "Orb Priority", "why": "Reason"}
    )
    st.markdown("**Dynamic Skill Build**")
    st.dataframe(skill_df, use_container_width=True, hide_index=True)

    item_col, spell_col = st.columns(2)
    with item_col:
        st.markdown("**Counter Item Priorities**")
        item_df = pd.DataFrame(assistant_data["item_rows"]).rename(
            columns={
                "item_name": "Item",
                "score": "Weight",
                "timing": "Timing",
                "reason": "Reason",
                "triggers": "Triggers",
            }
        )
        st.dataframe(item_df, use_container_width=True, hide_index=True)
    with spell_col:
        st.markdown("**Combo Priority**")
        for note in assistant_data["spell_notes"]:
            st.markdown(f"- {note}")

    st.markdown("**Combo Suggestions By Phase**")
    combo_cols = st.columns(len(assistant_data["combo_rows"]))
    for column, combo_row in zip(combo_cols, assistant_data["combo_rows"]):
        with column:
            st.markdown(f"**{combo_row['phase']}**")
            st.code(str(combo_row["combo"]), language="text")
            st.caption(str(combo_row["why"]))


def render_sidebar(hero_df: pd.DataFrame) -> tuple[list[str], str, int, bool, list[str], bool]:
    """Render sidebar controls and return current selections."""
    hero_names = hero_df["localized_name"].sort_values().tolist()

    st.sidebar.header("Filters")
    selected_heroes = st.sidebar.multiselect(
        "Enemy heroes",
        options=hero_names,
        max_selections=5,
        help="Select up to 5 enemy heroes.",
        key="selected_enemy_heroes",
    )
    selected_role = st.sidebar.selectbox("Role filter", ROLE_OPTIONS)
    show_synergy = st.sidebar.checkbox(
        "Show Synergy",
        value=False,
        help="Boost counter picks that also work especially well with selected ally heroes.",
        key="show_synergy_enabled",
    )
    ally_hero_names: list[str] = []
    if show_synergy:
        ally_hero_names = st.sidebar.multiselect(
            "Ally heroes",
            options=hero_names,
            max_selections=5,
            help="For example, add Faceless Void to prioritize Chronosphere follow-up heroes.",
            key="selected_ally_heroes",
        )
    min_games_threshold = st.sidebar.slider(
        "Minimum matches threshold",
        min_value=20,
        max_value=100,
        value=DEFAULT_MIN_GAMES_THRESHOLD,
        step=5,
        help="Only show counter picks with at least this many matches.",
    )
    show_invoker_assistant = st.sidebar.checkbox(
        "Invoker Assistant Mode",
        value=False,
        help="Adds draft analysis, Quas-Wex vs Quas-Exort guidance, item timing reminders, and spell priorities for Invoker.",
        key="show_invoker_assistant",
    )
    return (
        selected_heroes,
        selected_role,
        min_games_threshold,
        show_synergy,
        ally_hero_names,
        show_invoker_assistant,
    )


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

    if enemy_name_set:
        merged_df = merged_df[~merged_df["localized_name"].isin(enemy_name_set)]

    if selected_role != "All":
        merged_df = merged_df[merged_df["roles"].apply(lambda roles: matches_role_filter(roles, selected_role))]

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
        show_invoker_assistant,
    ) = render_sidebar(hero_df)
    effective_ally_hero_names = [hero_name for hero_name in ally_hero_names if hero_name not in selected_hero_names]
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
        effective_ally_hero_names,
        show_invoker_assistant,
    )
    if show_synergy and effective_ally_hero_names:
        st.caption(f"Synergy mode: enabled for ally heroes {', '.join(effective_ally_hero_names)}")
        st.caption("Synergy model: explicit combo presets + role-based fallback for every hero")
    if show_synergy and set(ally_hero_names).intersection(selected_hero_names):
        overlapping_heroes = sorted(set(ally_hero_names).intersection(selected_hero_names))
        st.caption(
            f"Ignoring overlapping ally/enemy heroes for synergy: {', '.join(overlapping_heroes)}"
        )

    if not selected_enemy_ids:
        st.info("Select at least one enemy hero from the sidebar to continue.")
        return

    st.subheader("Selected Enemies")
    render_selected_hero_grid(selected_hero_names, hero_df)
    if show_invoker_assistant:
        render_invoker_assistant(selected_hero_names, effective_ally_hero_names)

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
            ally_hero_names=effective_ally_hero_names,
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
            ally_hero_names=effective_ally_hero_names,
            show_synergy=show_synergy,
        )

    if results_df.empty:
        st.warning(
            "Not enough data was found for the selected role. Try a different role, enemy combination, "
            "or a lower match threshold."
        )
        return

    if show_synergy and effective_ally_hero_names:
        st.caption("Synergy weighting: ally combo heroes receive an additional score bonus")
    top_counter_names = results_df["localized_name"].head(5).tolist()
    focused_counter_hero = st.session_state.get("focused_counter_hero", "")
    if focused_counter_hero not in top_counter_names:
        focused_counter_hero = top_counter_names[0] if top_counter_names else ""
        st.session_state["focused_counter_hero"] = focused_counter_hero

    st.caption("Click a top counter pick to see item suggestions tailored for that hero.")
    render_counter_cards(results_df)
    focused_counter_hero = st.session_state.get("focused_counter_hero", focused_counter_hero)
    item_suggestions_df = build_item_suggestions(
        selected_hero_names,
        effective_ally_hero_names,
        selected_role,
        counter_hero_name=focused_counter_hero,
        hero_df=hero_df,
    )
    if focused_counter_hero:
        st.caption(f"Item suggestions are currently tailored for: {focused_counter_hero}")
    render_item_suggestions(item_suggestions_df)

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
