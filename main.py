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
            # Only log real directories that contain ASTC files
            if debug_mode and any("ASTC" in f.upper() for f in files):
                rel_path = os.path.relpath(root, source_folder)
                if rel_path == ".":
                    rel_path = "."
                debug_log(f"Scanning directory: {rel_path}", "debug")
            for file_name in files:
                if "ASTC" not in file_name:
                    continue
                    
                astc_count += 1
                if debug_mode:
                    debug_log(f"Processing File: {file_name}", "debug")
                file_path = os.path.join(root, file_name)
                
                try:
                    env = UnityPy.load(file_path)
                    file_name_lower = file_name.lower()
                    extract_resources = "resources" in file_name_lower
                    extract_metadata = "metadata" in file_name_lower

                    if extract_resources or not (extract_resources or extract_metadata):
                        for path, obj in env.container.items():
                            if obj.type.name == "Texture2D":
                                try:
                                    data = obj.read()
                                    filename = os.path.basename(path).upper()
                                    dest = os.path.join(destination_folder, "Texture2D", filename)
                                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                                    dest, ext = os.path.splitext(dest)
                                    dest = dest + ".png"
                                    if debug_mode:
                                        debug_log(f"Writing Texture2D to: {dest}", "debug")
                                    data.image.save(dest)
                                except Exception as e:
                                    debug_log(f"Error writing Texture2D {path}: {e}", "error")

                            if obj.type.name == "Sprite":
                                try:
                                    data = obj.read()
                                    filename = os.path.basename(path).upper()
                                    dest = os.path.join(destination_folder, "Sprite", filename)
                                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                                    dest, ext = os.path.splitext(dest)
                                    dest = dest + ".png"
                                    if debug_mode:
                                        debug_log(f"Writing Sprite to: {dest}", "debug")
                                    data.image.save(dest)
                                except Exception as e:
                                    debug_log(f"Error writing Sprite {path}: {e}", "error")

                    if extract_metadata or not (extract_resources or extract_metadata):
                        for path, obj in env.container.items():
                            if obj.type.name == "TextAsset":
                                try:
                                    data = obj.read()
                                    filename = os.path.basename(path).upper()
                                    dest = os.path.join(destination_folder, "TextAsset", filename)
                                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                                    dest, ext = os.path.splitext(dest)
                                    dest = dest + ".txt"
                                    if debug_mode:
                                        debug_log(f"Writing TextAsset to: {dest}", "debug")
                                    with open(dest, 'w', encoding='utf-8', errors='surrogatepass') as f:
                                        f.write(str(data.m_Script))
                                except UnicodeEncodeError as e:
                                    debug_log(f"Unicode error writing TextAsset {path}: {e}. Retrying with replacement characters", "error")
                                    try:
                                        with open(dest, 'w', encoding='utf-8', errors='replace') as f:
                                            f.write(str(data.m_Script))
                                        if debug_mode:
                                            debug_log(f"Successfully wrote TextAsset with replacements to: {dest}", "debug")
                                    except Exception as e2:
                                        debug_log(f"Failed to write TextAsset {path} with replacements: {e2}", "error")
                                except Exception as e:
                                    debug_log(f"Error writing TextAsset {path}: {e}", "error")

                    if not (extract_resources or extract_metadata):
                        for obj in env.objects:
                            if obj.type.name == "MonoBehaviour":
                                try:
                                    if obj.serialized_type.nodes:
                                        tree = obj.read_typetree()
                                        filename = tree.get('m_Name', f"MONO_{obj.path_id}")
                                        dest = os.path.join(destination_folder, "MonoBehaviour", f"{filename}.json")
                                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                                        if debug_mode:
                                            debug_log(f"Writing MonoBehaviour to: {dest}", "debug")
                                        with open(dest, 'w', encoding='utf-8') as f:
                                            json.dump(tree, f, ensure_ascii=False, indent=4)
                                    else:
                                        debug_log(f"Skipping MonoBehaviour {obj.path_id}: no typetree nodes", "warn")
                                except Exception as e:
                                    debug_log(f"Error processing MonoBehaviour {obj.path_id}: {e}", "error")

                except Exception as e:
                    failed_files += 1
                    debug_log(f"Error processing file {file_name}: {e}", "error")

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
    
    # File checks with error handling
    required_files = {}
    try:
        required_files["TranslationDataAsset"] = find_translation_file(mono_dir)
        translations = build_translation_lookup(required_files["TranslationDataAsset"]) if required_files["TranslationDataAsset"] else {}
        if required_files["TranslationDataAsset"] and translations:
            try:
                file_date = datetime.fromtimestamp(os.path.getmtime(required_files["TranslationDataAsset"])).strftime("%Y/%m/%d")
                debug_log(f"TranslationDataAsset file found, Translation lookup built with {len(translations)} entries from {os.path.basename(required_files['TranslationDataAsset'])} (File Date - {file_date})", "success")
            except Exception as e:
                debug_log(f"Error accessing TranslationDataAsset file {required_files['TranslationDataAsset']}: {e}", "error", force=True)
        else:
            debug_log("TranslationDataAsset file(s) not found or failed to build translation lookup.", "warn")
            translations = {}
    except FileNotFoundError:
        debug_log(f"MonoBehaviour folder {mono_dir} not found. Skipping TranslationDataAsset.", "warn", force=True)
        required_files["TranslationDataAsset"] = None
        translations = {}
    
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
        mdp = MilestoneDataParser(folder=text_dir, translations=translations)
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