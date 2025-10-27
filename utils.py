# utils.py
import os
import re
import json
import traceback
from datetime import datetime, timezone
from colorama import Fore, Style, init

init(autoreset=True)

# Toggle debug output here
DEBUG = True

def debug_log(msg, level="info", force=False):
    """Colored debug logging used across modules."""
    if not DEBUG and not force:
        return
    colors = {
        "info": Fore.CYAN,
        "warn": Fore.YELLOW,
        "success": Fore.GREEN,
        "error": Fore.RED,
        "debug": Fore.MAGENTA,
    }
    color = colors.get(level, Fore.WHITE)
    print(f"{color}[{level.upper()}]{Style.RESET_ALL} {msg}")

def epoch_to_gmt(epoch):
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
    except Exception:
        return str(epoch)

def format_time(epoch, for_file=False):
    """Format epoch time to UTC string, optionally for file output with Discord timestamp."""
    try:
        dt = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
        if for_file:
            return f"<t:{int(epoch)}:f>"
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(epoch)

def colorize_star_for_console(star_value: str) -> str:
    """Color 'P*' magenta, 'G*' yellow for console output."""
    if not star_value:
        return "?"
    parts = str(star_value).split("_")
    colored = []
    for p in parts:
        if "P" in p:
            colored.append(f"{Fore.MAGENTA}{p}{Style.RESET_ALL}")
        elif "G" in p:
            colored.append(f"{Fore.YELLOW}{p}{Style.RESET_ALL}")
        else:
            colored.append(p)
    return "_".join(colored)

# ---------------- Translation loader ----------------
def find_translation_file(folder="MonoBehaviour"):
    if not os.path.exists(folder):
        debug_log(f"Translation folder {folder} not found.", "warn", force=True)
        return None
    try:
        candidates = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and re.search(r"translationdataasset", f, re.IGNORECASE)]
        return os.path.join(folder, sorted(candidates)[0]) if candidates else None
    except Exception as e:
        debug_log(f"Error accessing translation folder {folder}: {e}", "error", force=True)
        if "-debug" in sys.argv:
            debug_log(f"Stack trace: {traceback.format_exc()}", "debug", force=True)
        return None

def build_translation_lookup(translation_path):
    """Return mapping code -> pretty name extracted from TranslationDataAsset.json"""
    if not translation_path or not os.path.exists(translation_path):
        debug_log("TranslationDataAsset.json not found. Car names will be untranslated.", "warn")
        return {}

    try:
        with open(translation_path, "r", encoding="utf-8") as fh:
            translations = json.load(fh)
    except UnicodeDecodeError:
        try:
            with open(translation_path, "r", encoding="utf-8-sig") as fh:
                translations = json.load(fh)
        except Exception as e:
            debug_log(f"Failed to load translation file {translation_path}: {e}", "error", force=True)
            if "-debug" in sys.argv:
                debug_log(f"Stack trace: {traceback.format_exc()}", "debug", force=True)
            return {}
    except Exception as e:
        debug_log(f"Failed to load translation file {translation_path}: {e}", "error", force=True)
        if "-debug" in sys.argv:
            debug_log(f"Stack trace: {traceback.format_exc()}", "debug", force=True)
        return {}

    from_keys = translations.get("TranslationsFrom", [])
    to_values = translations.get("TranslationsTo", [])
    mapping = {}

    for k, v in zip(from_keys, to_values):
        if k.startswith("TEXT_CAR_") and k.endswith("_LONG"):
            code = k[len("TEXT_CAR_"):-len("_LONG")]
            mapping[code] = v
        else:
            mapping[k] = v

    file_date = datetime.fromtimestamp(os.path.getmtime(translation_path)).strftime("%Y/%m/%d")
    filename = os.path.basename(translation_path)
    debug_log(f"Translation lookup built with {len(mapping)} entries from {filename} (File Date - {file_date})", "success")
    return mapping

# ---------------- Collection loader ----------------
def find_collection_file(folder="MetaData"):
    if not os.path.exists(folder):
        debug_log(f"Collection folder {folder} not found.", "warn", force=True)
        return None
    try:
        candidates = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and re.search(r"collectionslots", f, re.IGNORECASE)]
        return os.path.join(folder, sorted(candidates)[0]) if candidates else None
    except Exception as e:
        debug_log(f"Error accessing collection folder {folder}: {e}", "error", force=True)
        if "-debug" in sys.argv:
            debug_log(f"Stack trace: {traceback.format_exc()}", "debug", force=True)
        return None

def build_collection_lookup(collection_path):
    """Build lookup for collection slot names from CollectionSlots.meta."""
    if not collection_path or not os.path.exists(collection_path):
        debug_log("CollectionSlots.meta not found. Slot names will default to 'Unknown'.", "warn")
        return {}

    try:
        with open(collection_path, "r", encoding="utf-8") as fh:
            collection_slots = json.load(fh)
    except UnicodeDecodeError:
        try:
            with open(collection_path, "r", encoding="utf-8-sig") as fh:
                collection_slots = json.load(fh)
        except Exception as e:
            debug_log(f"Failed to load collection file {collection_path}: {e}", "error", force=True)
            if "-debug" in sys.argv:
                debug_log(f"Stack trace: {traceback.format_exc()}", "debug", force=True)
            return {}
    except Exception as e:
        debug_log(f"Failed to load collection file {collection_path}: {e}", "error", force=True)
        if "-debug" in sys.argv:
            debug_log(f"Stack trace: {traceback.format_exc()}", "debug", force=True)
        return {}

    lookup = {}
    for key, slot in collection_slots.get("CollectionSlots", {}).items():
        for milestone in slot.get("milestones", []):
            names = milestone.get("names")
            if names:
                lookup[key] = names

    file_date = datetime.fromtimestamp(os.path.getmtime(collection_path)).strftime("%Y/%m/%d")
    filename = os.path.basename(collection_path)
    debug_log(f"Collection lookup built with {len(lookup)} entries from {filename} (File Date - {file_date})", "success")
    return lookup

# ---------------- Shop loader ----------------
def load_shop_time_gated_events(folder="MetaData"):
    """Load ShopTimeGatedEvents.meta for car promotions, with fallback for different file names."""
    if not os.path.exists(folder):
        debug_log(f"Shop folder {folder} not found.", "warn", force=True)
        return None, None
    try:
        candidates = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and re.search(r"shoptimegatedevents", f, re.IGNORECASE)]
        if not candidates:
            return None, None

        for fname in sorted(candidates):
            path = os.path.join(folder, fname)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                file_date = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y/%m/%d")
                debug_log(f"Loaded {fname} (File Date - {file_date})", "success")
                promos = data.get("ShopTimeGatedEvents", {}).get("GENERATED_TimeGatedCarPromotions", {})
                return {"ShopTimeGatedEvents": {"GENERATED_TimeGatedCarPromotions": promos}}, file_date
            except Exception as e:
                debug_log(f"Failed to load {fname}: {e}", "warn")
                if "-debug" in sys.argv:
                    debug_log(f"Stack trace: {traceback.format_exc()}", "debug", force=True)
                continue
    except Exception as e:
        debug_log(f"Error accessing shop folder {folder}: {e}", "error", force=True)
        if "-debug" in sys.argv:
            debug_log(f"Stack trace: {traceback.format_exc()}", "debug", force=True)
        return None, None

    return None, None

# ---------------- Matching utilities ----------------
def _normalize(s: str) -> str:
    """Normalize a DBID-like string for fuzzy matching."""
    if s is None:
        return ""
    return re.sub(r'[^a-z0-9]', '', s.lower())

def pattern_to_regex(pat: str) -> str:
    """Convert a wildcard pattern (with *) to a regex (normalized)"""
    esc = re.escape(pat)
    esc = esc.replace(r'\*', '.*')
    return '^' + esc + '$'

def is_match(pattern: str, key: str) -> bool:
    """
    Robust matching between two DBIDs.
    - If pattern contains '*', treat as wildcard.
    - Otherwise accept exact normalized equality or containment either way.
    """
    if not pattern or not key:
        return False

    if pattern == key:
        return True
    n_pat = _normalize(pattern)
    n_key = _normalize(key)

    if '*' in pattern:
        norm_pat = re.escape(n_pat).replace(r'\.\*', '.*')
        try:
            return re.fullmatch(norm_pat, n_key) is not None
        except re.error:
            return n_pat.replace('.*', '') in n_key

    if n_pat == n_key or n_pat in n_key or n_key in n_pat:
        return True

    return False

def translate_event_name(event_key: str, translations: dict):
    """
    Returns pretty event title if available, else fallback.
    Looks for TEXT_<EVENT>_TITLE or TEXT_<EVENT>_TITLE_SHORT.
    """
    if not event_key or not translations:
        return event_key

    lookup_keys = [
        f"TEXT_{event_key}_TITLE",
        f"TEXT_{event_key}_TITLE_SHORT",
    ]
    for lk in lookup_keys:
        if lk in translations:
            return translations[lk]
    return event_key

# ---------------- Translation helper ----------------
def translate_model_name_with_suffix(model, translations, debug_mode=False):
    """
    Clean translator with wildcard expansion:
      • If model contains '*', return all matching variants joined with '/'
      • Otherwise, return single translated entry
      • Keeps PS/GS coloring
      • Debug mode appends raw DBIDs
    """
    if not model:
        return []

    def colored_suffix_for(name):
        if re.search(r"(RewardRecycled|Gold)", name, re.IGNORECASE):
            return "(GS)", f"{Fore.YELLOW}(GS){Style.RESET_ALL}"
        if re.search(r"Reward", name, re.IGNORECASE):
            return "(PS)", f"{Fore.MAGENTA}(PS){Style.RESET_ALL}"
        return "(PS)", f"{Fore.MAGENTA}(PS){Style.RESET_ALL}"

    results = []
    keys = list(translations.keys())

    if "*" in model:
        prefix, _, suffix = model.partition("*")
        candidates = [k for k in keys if k.startswith(prefix) and (not suffix or k.endswith(suffix))]

        if not candidates:
            candidates = [model]

        variants = []
        for k in candidates:
            pretty = translations.get(k, k.replace("_", " "))
            _, color_suffix = colored_suffix_for(k)
            display = pretty
            if debug_mode:
                display = f"{display} ({k})"
            variants.append(f"{display} {color_suffix}")
        combined_display = " / ".join(variants)
        results.append((combined_display, "", model))
        return results

    if model in translations:
        chosen_key = model
    else:
        starts = [k for k in keys if k.startswith(model)]
        contains = [k for k in keys if model in k]
        chosen_key = starts[0] if starts else (contains[0] if contains else model)

    pretty = translations.get(chosen_key, model.replace("_", " "))
    _, color_suffix = colored_suffix_for(chosen_key)
    display = pretty
    if debug_mode:
        display = f"{display} ({model})"

    results.append((display, color_suffix, chosen_key))
    return results

# ---------------- Tournament utilities ----------------
def format_cooldown_time(seconds):
    minutes = seconds // 60
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m"

def format_restriction(restriction):
    """Pretty print a restriction dict. Assumes a non-empty restriction object."""
    rtype = restriction.get("RestrictionType", "Unknown")
    readable = re.sub(r"(?<=[a-z])([A-Z])", r" \1", rtype)
    readable = readable.replace("EPRange", "EP Range").replace("PPRange", "PP Range")
    readable = readable.replace("No ", "No ")

    if rtype in ("EPRange", "PPRange"):
        min_val = restriction.get("MinEP") or restriction.get("MinPP")
        max_val = restriction.get("MaxEP") or restriction.get("MaxPP")
        if min_val is not None and max_val is not None:
            readable += f" {min_val} - {max_val}"
    return readable

def format_distance(race_event):
    if race_event.get("ECBRaceType") == "QuickestTime100Race":
        return "0-100 Sprint"
    return "1/2 Mile" if race_event.get("IsHalfMile", False) else "1/4 Mile"