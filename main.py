# main.py
import os
import sys
import re
import json
import time
import traceback
from datetime import datetime
import subprocess
import importlib


# Package installation for UnityPy
required_packages = {
    "UnityPy": "UnityPy",
    "colorama": "colorama"
}

def install_if_missing(packages):
    for pip_name, import_name in packages.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            print(f"Installing missing package: {pip_name}", "info")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])

install_if_missing(required_packages)
            
from colorama import init, Fore, Style
import UnityPy  
from utils import debug_log, find_translation_file, build_translation_lookup, load_shop_time_gated_events, find_collection_file, build_collection_lookup
from eventdataparser import EventDataParser
from milestonedataparser import MilestoneDataParser
from showdownparser import ShowdownParser
from tournamentparser import TournamentParser  

init(autoreset=True)        

def unpack_all_assets(source_folder: str, destination_folder: str):
    debug_log("Extracting Resources...", "info")
    astc_count = 0
    failed_files = 0
    debug_mode = "-debug" in sys.argv

    try:
        for root, dirs, files in os.walk(source_folder):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {'__pycache__'}]
            if debug_mode and any("ASTC" in f.upper() for f in files):
                rel_path = os.path.relpath(root, source_folder)
                if rel_path == ".":
                    rel_path = "."
                debug_log(f"Scanning directory: {rel_path}", "debug")

            for file_name in files:
                if "ASTC" not in file_name:
                    continue

                astc_count += 1
                file_path = os.path.join(root, file_name)
                if debug_mode:
                    debug_log(f"Processing File: {file_name}", "debug")

                try:
                    env = UnityPy.load(file_path)
                    file_name_lower = file_name.lower()
                    extract_resources = "resources" in file_name_lower
                    extract_metadata = "metadata" in file_name_lower

                    # --- Texture2D and Sprite extraction (unchanged) ---
                    if extract_resources or not (extract_resources or extract_metadata):
                        for path, obj in env.container.items():
                            if obj.type.name in ["Texture2D", "Sprite"]:
                                try:
                                    data = obj.read()
                                    folder_name = obj.type.name
                                    filename = os.path.basename(path).upper()
                                    dest = os.path.join(destination_folder, folder_name, filename)
                                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                                    dest = os.path.splitext(dest)[0] + ".png"
                                    if debug_mode:
                                        debug_log(f"Writing {obj.type.name} to: {dest}", "debug")
                                    data.image.save(dest)
                                except Exception as e:
                                    debug_log(f"Error writing {obj.type.name} {path}: {e}", "error")

                    # --- TextAsset extraction (unchanged) ---
                    if extract_metadata or not (extract_resources or extract_metadata):
                        for path, obj in env.container.items():
                            if obj.type.name == "TextAsset":
                                try:
                                    data = obj.read()
                                    filename = os.path.basename(path).upper()
                                    dest = os.path.join(destination_folder, "TextAsset", filename)
                                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                                    dest = os.path.splitext(dest)[0] + ".txt"
                                    if debug_mode:
                                        debug_log(f"Writing TextAsset to: {dest}", "debug")
                                    with open(dest, 'w', encoding='utf-8', errors='surrogatepass') as f:
                                        f.write(str(data.m_Script))
                                except Exception as e:
                                    debug_log(f"Error writing TextAsset {path}: {e}", "error")

                    # --- MonoBehaviour extraction: ONE FILE PER BUNDLE (FIXED) ---
                    if not (extract_resources or extract_metadata):
                        all_mono = []

                        # Get clean bundle name
                        bundle_base_name = os.path.splitext(file_name)[0]  # Remove extension
                        if "." in bundle_base_name:
                            bundle_base_name = bundle_base_name.split('.')[0]  # Remove .ASTC.xxx suffix

                        is_camera_anim_bundle = bundle_base_name == "CarCameraAnimationLibrary"

                        for obj in env.objects:
                            if obj.type.name == "MonoBehaviour":
                                try:
                                    if obj.serialized_type and obj.serialized_type.nodes:
                                        tree = obj.read_typetree()
                                        m_name = tree.get("m_Name", "")
                                        # Add size for smart selection
                                        tree_str = json.dumps(tree)
                                        size = len(tree_str)
                                        all_mono.append((tree, m_name, size, obj.path_id))
                                except Exception as e:
                                    debug_log(f"Error reading MonoBehaviour {obj.path_id}: {e}", "error")

                        if all_mono:
                            if is_camera_anim_bundle:
                                # Prefer one with matching name, else largest
                                named_match = [item for item in all_mono if item[1] == bundle_base_name]
                                if named_match:
                                    selected = named_match[0][0]  # tree
                                else:
                                    selected = max(all_mono, key=lambda x: x[2])[0]  # largest by size
                                mono_to_save = [selected]

                                debug_log(f"Saved 1 MonoBehaviour (filtered main library) → {bundle_base_name}.json", "info")
                                if named_match:
                                    debug_log(f"  → Selected by name: '{bundle_base_name}'", "debug")
                                else:
                                    debug_log(f"  → Selected largest (size ~{max(all_mono, key=lambda x: x[2])[2]} chars)", "debug")
                            else:
                                # Save all for other bundles
                                mono_to_save = [item[0] for item in all_mono]
                                debug_log(f"Saved {len(mono_to_save)} MonoBehaviour(s) → {bundle_base_name}.json", "info")

                            # Write the output
                            out_path = os.path.join(destination_folder, "MonoBehaviour", f"{bundle_base_name}.json")
                            os.makedirs(os.path.dirname(out_path), exist_ok=True)

                            with open(out_path, 'w', encoding='utf-8') as f:
                                if len(mono_to_save) == 1:
                                    json.dump(mono_to_save[0], f, ensure_ascii=False, indent=4)
                                else:
                                    json.dump(mono_to_save, f, ensure_ascii=False, indent=4)

                except Exception as e:
                    failed_files += 1
                    debug_log(f"Error processing file {file_name}: {e}", "error")
                    if debug_mode:
                        debug_log(f"Stack trace: {traceback.format_exc()}", "debug")

    except FileNotFoundError as e:
        debug_log(f"Source folder {source_folder} not found: {e}", "error", force=True)
        return 0, failed_files

    return astc_count, failed_files

def main():
    start_time = time.time()
    debug_log("Starting CSR2 EventData Parser.", "info", force=True)
    folder = "."
       
    base_dir2 = os.getcwd()  # <-- wherever you run python main.py from

    cleanup_items = [
        "TextAsset",
        "MonoBehaviour",
        "Texture2D",
        "Sprite",
        "__pycache__",
        "allparser_output.txt",
         # optional: delete entire extracted folder if present
    ]

    for item in cleanup_items:
        path = os.path.join(base_dir2, item)
        if not os.path.exists(path):
            continue
        try:
            if os.path.isfile(path):
                os.remove(path)
                debug_log(f"Deleted old file: {item}", "info")
            else:
                import shutil
                shutil.rmtree(path)
                debug_log(f"Deleted old folder: {item}", "info")
        except Exception as e:
            debug_log(f"Failed to delete {item}: {e}", "warn")
    
    # Count ASTC files before extraction
    astc_count = sum(1 for root, _, files in os.walk(folder) for file_name in files if "ASTC" in file_name)
    debug_log(f"Extracting assets from ASTC files in {os.path.abspath(folder)}", "info")
    debug_log(f"Found {astc_count} ASTC file(s).", "info")
    
    # Run asset extraction
    try:
        install_if_missing(required_packages)
        extract_start_time = time.time()
        astc_count, failed_files = unpack_all_assets(folder, folder)
        extract_time = round(time.time() - extract_start_time)
        if astc_count == 0:
            debug_log("No ASTC files found in the input directory", "info")
        else:
            debug_log(f"Finished Extracting Resources from {astc_count} ASTC file(s), {failed_files} file(s) failed.", "info")
            debug_log(f"Extraction Time: {extract_time}s", "info")
    except Exception as e:
        debug_log(f"Failed to extract assets: {e}", "error", force=True)
        if "-debug" in sys.argv:
            debug_log(f"Stack trace: {traceback.format_exc()}", "debug", force=True)
    
    # Define subfolders
    meta_dir = os.path.join(folder, "metadata")
    text_dir = os.path.join(folder, "TextAsset")
    mono_dir = os.path.join(folder, "MonoBehaviour")
    
    # Initialize required_files dictionary
    required_files = {}
    
    # --- TranslationDataAsset lookup (supports old + new naming) ---
    required_files["TranslationDataAsset"] = None
    translations = {}

    if os.path.exists(mono_dir):
        possible_names = [
            "Localisation_EN.json",           # New name (current)
            "Localisation_en.json",           # Possible lowercase variant
            "Localisation.json",
            "TranslationDataAsset.json",      # Old name (legacy)
            "TranslationData.json",
        ]

        for filename in os.listdir(mono_dir):
            if filename in possible_names:
                required_files["TranslationDataAsset"] = os.path.join(mono_dir, filename)
                break

        # Optional: fallback to any file containing "localisation" or "translation"
        if not required_files["TranslationDataAsset"]:
            for filename in os.listdir(mono_dir):
                if filename.endswith(".json") and ("localisation" in filename.lower() or "translation" in filename.lower()):
                    required_files["TranslationDataAsset"] = os.path.join(mono_dir, filename)
                    debug_log(f"Found possible translation file via fuzzy match: {filename}", "info")
                    break

        if required_files["TranslationDataAsset"]:
            try:
                translations = build_translation_lookup(required_files["TranslationDataAsset"])
                if translations:
                    file_date = datetime.fromtimestamp(os.path.getmtime(required_files["TranslationDataAsset"])).strftime("%Y/%m/%d")
                    debug_log(
                        f"Translation file loaded: {os.path.basename(required_files['TranslationDataAsset'])} "
                        f"with {len(translations)} entries (File Date - {file_date})",
                        "success"
                    )
                else:
                    debug_log(f"Translation file found but lookup failed to build: {os.path.basename(required_files['TranslationDataAsset'])}", "warn")
                    translations = {}
            except Exception as e:
                debug_log(f"Error loading translation file {required_files['TranslationDataAsset']}: {e}", "error", force=True)
                translations = {}
        else:
            debug_log("No translation file found (tried Localisation_EN.json, TranslationDataAsset.json, etc.)", "warn")
    else:
        debug_log(f"MonoBehaviour folder {mono_dir} not found. Skipping translation lookup.", "warn", force=True)
    
    try:
        required_files["ShopTimeGatedEvents"] = [
            f for f in os.listdir(meta_dir)
            if os.path.isfile(os.path.join(meta_dir, f)) and re.search(r"shoptimegatedevents", f, re.IGNORECASE)
        ] if os.path.exists(meta_dir) else []
    except FileNotFoundError:
        debug_log(f"MetaData folder {meta_dir} not found. Skipping ShopTimeGatedEvents.", "warn", force=True)
        required_files["ShopTimeGatedEvents"] = []
    
    try:
        required_files["CollectionSlots"] = find_collection_file(meta_dir)
    except FileNotFoundError:
        debug_log(f"MetaData folder {meta_dir} not found. Skipping CollectionSlots.", "warn", force=True)
        required_files["CollectionSlots"] = None
    
    try:
        required_files["EventSchedule"] = [
            f for f in os.listdir(meta_dir)
            if os.path.isfile(os.path.join(meta_dir, f)) and re.search(r"eventschedule", f, re.IGNORECASE)
        ] if os.path.exists(meta_dir) else []
        if required_files["EventSchedule"]:
            try:
                event_schedule_file = os.path.join(meta_dir, required_files["EventSchedule"][0])
                file_date = datetime.fromtimestamp(os.path.getmtime(event_schedule_file)).strftime("%Y/%m/%d")
                debug_log(f"EventSchedule files found: Loaded {required_files['EventSchedule'][0]} (File Date - {file_date})", "success")
            except Exception as e:
                debug_log(f"Error accessing EventSchedule file {event_schedule_file}: {e}", "error", force=True)
        else:
            debug_log("EventSchedule file(s) not found.", "warn")
    except FileNotFoundError:
        debug_log(f"MetaData folder {meta_dir} not found. Skipping EventSchedule.", "warn", force=True)
        required_files["EventSchedule"] = []
    
    try:
        required_files["TournamentConfig"] = [
            f for f in os.listdir(text_dir)
            if os.path.isfile(os.path.join(text_dir, f)) and re.search(r"TOURNAMENT_.*\.txt", f, re.IGNORECASE)
        ] if os.path.exists(text_dir) else []
        if not required_files["TournamentConfig"]:
            debug_log("TournamentConfig file(s) not found.", "warn")
    except FileNotFoundError:
        debug_log(f"TextAsset folder {text_dir} not found. Skipping TournamentConfig.", "warn", force=True)
        required_files["TournamentConfig"] = []

    shop_data, shop_file_date = load_shop_time_gated_events(meta_dir) if required_files["ShopTimeGatedEvents"] else (None, None)
    if not shop_data:
        debug_log("No ShopTimeGatedEvents file found. Skipping shop annotations.", "warn")
    
    collection_file = required_files["CollectionSlots"]
    collections = build_collection_lookup(collection_file) if collection_file else {}
    if collection_file and not collections:
        debug_log("Failed to build collection lookup.", "warn", force=True)

    # Collect outputs from all parsers
    all_outputs = []
    debug_mode = "-debug" in sys.argv

    try:
        debug_log("Starting EventDataParser phase", "info")
        edp = EventDataParser(folder=text_dir, translations=translations, shop_data=shop_data, debug=debug_mode)
        event_output = edp.process()
        if event_output:
            all_outputs.append("=== EventDataParser Output ===\n" + event_output + "\n")
    except Exception as e:
        debug_log(f"EventDataParser failed: {e}", "error", force=True)
        if debug_mode:
            debug_log(f"Stack trace: {traceback.format_exc()}", "debug", force=True)

    try:
        debug_log("Starting MilestoneDataParser phase", "info")
        mdp = MilestoneDataParser(folder=text_dir, translations=translations, debug=debug_mode)
        milestone_output = mdp.process()
        if milestone_output:
            all_outputs.append("=== MilestoneDataParser Output ===\n" + milestone_output + "\n")
    except Exception as e:
        debug_log(f"MilestoneDataParser failed: {e}", "error", force=True)
        if debug_mode:
            debug_log(f"Stack trace: {traceback.format_exc()}", "debug", force=True)

    try:
        debug_log("Starting ShowdownParser phase", "info")
        crdb_mode = "-crdb" in sys.argv
        sp = ShowdownParser(folder=text_dir, translations=translations, shop_data=shop_data, debug=debug_mode, crdb_mode=crdb_mode)
        showdown_output = sp.process()
        if showdown_output:
            all_outputs.append("=== ShowdownParser Output ===\n" + showdown_output + "\n")
    except Exception as e:
        debug_log(f"ShowdownParser failed: {e}", "error", force=True)
        if debug_mode:
            debug_log(f"Stack trace: {traceback.format_exc()}", "debug", force=True)

    try:
        debug_log("Starting TournamentParser phase", "info")
        tp = TournamentParser(folder=text_dir, translations=translations, collections=collections, debug=debug_mode)
        tournament_output = tp.process()
        if tournament_output:
            all_outputs.append("=== TournamentParser Output ===\n" + tournament_output + "\n")
    except Exception as e:
        debug_log(f"TournamentParser failed: {e}", "error", force=True)
        if debug_mode:
            debug_log(f"Stack trace: {traceback.format_exc()}", "debug", force=True)

    # Write combined output
    if all_outputs:
        try:
            combined_output_path = os.path.join(folder, "allparser_output.txt")
            with open(combined_output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(all_outputs))
            debug_log(f"Combined output written to {combined_output_path}", "info")
        except Exception as e:
            debug_log(f"Failed to write combined output to {combined_output_path}: {e}", "error", force=True)
            if debug_mode:
                debug_log(f"Stack trace: {traceback.format_exc()}", "debug", force=True)

    total_time = round(time.time() - start_time)
    debug_log("All phases completed.", "success", force=True)
    debug_log(f"Total Processing Time: {total_time}s", "info", force=True)

if __name__ == "__main__":
    main()