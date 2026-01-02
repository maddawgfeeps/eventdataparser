# showdownparser.py
import os
import re
import json
import requests
from colorama import Fore, Style
from utils import debug_log, format_time, colorize_star_for_console, translate_event_name

class ShowdownParser:
    def __init__(self, folder="TextAsset", translations=None, shop_data=None, debug=False, crdb_mode=False):
        self.folder = folder
        self.translations = translations or {}
        self.shop_data = shop_data or {}
        self.debug = debug
        self.crdb_mode = crdb_mode
        self.output_file = "sd_output.txt"
        self.wr_url = "https://raw.githubusercontent.com/Nitro4CSR/CSR2WorldRecordsDB/refs/heads/main/JessWR.json"
        self.showdown_pattern = r"SMP_SHOWDOWN_\d+_W\d+\.txt"
        self.special_bs_pattern = r".*_BS\.txt"
        self.special_sd_pattern = r".*_SD.*\.txt"
        self.missing_translations = set()
        self.missing_wr_data = set()
        self.unknown_cars = set()

    def fetch_wr_data(self):
        debug_log(f"Fetching WR data from {self.wr_url}", "info")
        try:
            r = requests.get(self.wr_url, timeout=10)
            r.raise_for_status()
            wr_data = r.json()
        except Exception as e:
            debug_log(f"Failed to fetch WR data: {e}", "error")
            return {}

        car_stats_map = {}
        ec_overwrite = 0
        ec_only_add = 0

        for entry in wr_data:
            car_id = entry.get("DB Name")
            if not car_id:
                continue

            dyno_raw = entry.get("WR-DYNO")
            best_et_raw = entry.get("WR-BEST ET")

            try:
                dyno = float(dyno_raw) if dyno_raw not in (None, "", "n.A.") else None
            except (TypeError, ValueError):
                dyno = None

            try:
                best_et = float(best_et_raw) if best_et_raw not in (None, "", "n.A.", "0.000") else None
            except (TypeError, ValueError):
                best_et = None

            # Prefer valid Best ET (>0), otherwise fall back to Dyno
            display_time = best_et if best_et is not None and best_et > 0 else dyno
            source = "ET" if best_et is not None and best_et > 0 else "Dyno"

            tier = entry.get("Un")
            star = entry.get("★")

            if car_id.endswith("_EC"):
                base_id = car_id[:-3]
                if base_id in car_stats_map:
                    ec_overwrite += 1
                else:
                    ec_only_add += 1
                car_stats_map[base_id] = (display_time, star, tier, True, source)
            elif car_id not in car_stats_map:
                car_stats_map[car_id] = (display_time, star, tier, False, source)

        debug_log(
            f"Total WR entries processed: {len(car_stats_map)} (EC overwrote {ec_overwrite}, EC-only added {ec_only_add})",
            "success"
        )
        return car_stats_map

    def parse_cars(self, car_ids, car_stats_map, filepath):
        cars = []
        for car_id in car_ids:
            if not car_id or not str(car_id).strip():
                continue

            pretty = car_id if self.crdb_mode else self.translations.get(car_id)
            wr_entry = car_stats_map.get(car_id)

            if not pretty and not wr_entry:
                self.unknown_cars.add(car_id)
                debug_log(f"New car detected (not in translations or WR): {car_id}", "warn", force=True)
                pretty = car_id
            elif not pretty:
                self.missing_translations.add(car_id)
                debug_log(f"Missing translation for car id: {car_id}", "warn", force=True)
                pretty = car_id
            elif not wr_entry:
                self.missing_wr_data.add(car_id)
                debug_log(f"No WR data for {car_id}", "info")

            if wr_entry:
                display_time, star, tier, _, source = wr_entry
            else:
                display_time, star, tier, _, source = None, None, None, None, "Dyno"

            cars.append((car_id, pretty, display_time, tier, star, source))
        return cars

    def format_output(self, title, start, end, cars, showdown_type="Default", cars_for_sale=None):
        if cars_for_sale is None:
            cars_for_sale = {}

        start_str = format_time(start, for_file=False)
        end_str = format_time(end, for_file=False)
        start_file = format_time(start, for_file=True)
        end_file = format_time(end, for_file=True)

        if showdown_type == "Championship":
            title_color = Fore.RED
        elif showdown_type == "Elite":
            title_color = Fore.MAGENTA
        elif showdown_type == "Special":
            title_color = Fore.BLUE
        else:
            title_color = Fore.WHITE

        console_lines = [f"{title_color}{title}{Style.RESET_ALL} ({start_str} - {end_str})", ""]
        file_lines = [f"{title} ({start_file} - {end_file})", ""]

        tiers_present = {c[3] for c in cars if c[3]}
        has_half_mile = any(t in ["T4", "T5"] for t in tiers_present)
        has_quarter_mile = any(t in ["T1", "T2", "T3"] for t in tiers_present)
        mark_quarter = has_half_mile and has_quarter_mile

        def sort_key(car):
            _, _, display_time, tier, _, _ = car
            tier_num = int(tier[1]) if tier and tier.startswith("T") and tier[1].isdigit() else 0
            group_priority = 1 if tier_num >= 4 else 0
            time_value = display_time if display_time is not None else 999.999
            return (-group_priority, time_value)

        sorted_cars = sorted(cars, key=sort_key)

        for car_id, pretty, display_time, tier, star, source in sorted_cars:
            tier_str = tier or "?"
            star_str = star or "?"
            star_col = colorize_star_for_console(star_str)
            time_label = "Best ET" if source == "ET" else "Dyno"
            note = " (1/4 mile Time Only)" if mark_quarter and tier in ["T1", "T2", "T3"] else ""

            sale_info_file = ""
            sale_info_console = ""
            if car_id in cars_for_sale:
                quantity = cars_for_sale[car_id]
                sale_info_file = f" - Car For Sale - {quantity} Gold Coins"
                sale_info_console = f" - Car For Sale - {Fore.YELLOW}{quantity} Gold Coins{Style.RESET_ALL}"

            # Base pretty name (translated or fallback)
            file_pretty = pretty
            console_pretty = pretty

            # Append raw car_id in debug mode if different from pretty (and not crdb_mode)
            if self.debug and not self.crdb_mode and car_id != pretty:
                debug_suffix = f" ({car_id})"
                file_pretty += debug_suffix
                console_pretty += debug_suffix

            if display_time is not None:
                file_line = f"• {file_pretty} ({time_label} - {display_time:.3f}) ({tier_str} {star_str}){sale_info_file}{note}"
                console_line = f"• {console_pretty} ({time_label} - {display_time:.3f}) ({tier_str} {star_col}){sale_info_console}{note}"
            else:
                file_line = f"• {file_pretty} ({time_label} - N/A) ({tier_str} {star_str}){sale_info_file}{note}"
                if car_id in self.unknown_cars:
                    console_line = f"• {Fore.RED}{console_pretty} ({time_label} - N/A){Style.RESET_ALL} ({tier_str} {star_col}){sale_info_console}{note}"
                elif car_id in self.missing_wr_data:
                    console_line = f"• {Fore.YELLOW}{console_pretty} ({time_label} - N/A){Style.RESET_ALL} ({tier_str} {star_col}){sale_info_console}{note}"
                else:
                    console_line = f"• {console_pretty} ({time_label} - N/A) ({tier_str} {star_col}){sale_info_console}{note}"

            file_lines.append(file_line)
            console_lines.append(console_line)

        return "\n".join(file_lines), "\n".join(console_lines)

    def derive_showdown_type_and_title(self, schedule_id: str, event_obj: dict) -> tuple[str, str]:
        season = "?"
        m = re.search(r"SMP_SHOWDOWN_(\d+)_W\d+", schedule_id or "")
        if m:
            season = m.group(1)

        showdown_type = "Default"
        for group in event_obj.get("ShowdownEventsContainer", {}).get("RaceEventGroups", []):
            pin_id = group.get("PinPositionId", "")
            if "CHMPIONSHIP_SHOWDOWN" in pin_id:
                showdown_type = "Championship"
                break
            elif "SD_ELITE_SHOWDOWN" in pin_id:
                showdown_type = "Elite"
                break

        label = "Championship Showdown" if showdown_type == "Championship" else \
                "Elite Showdown" if showdown_type == "Elite" else \
                "Showdown"

        return showdown_type, f"{label} - Season {season}"

    def parse_showdown_file(self, filepath, car_stats_map):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        event = list(data.values())[0]
        schedule = event["EventSchedule"]["ScheduleList"][0]
        start, end = schedule["Time_ActiveBetweenAny"][0]
        schedule_id = schedule["ScheduleID"]

        showdown_type, title = self.derive_showdown_type_and_title(schedule_id, event)

        cars = []
        for group in event["ShowdownEventsContainer"]["RaceEventGroups"]:
            for race in group["RaceEvents"]:
                for restriction in race.get("Restrictions", []):
                    if restriction.get("RestrictionType") == "CarModels":
                        cars.extend(self.parse_cars(restriction.get("Models", []), car_stats_map, filepath))

        cars_for_sale = {}
        if "_W2" in os.path.basename(filepath):
            sched_key = os.path.splitext(os.path.basename(filepath))[0]
            promos = self.shop_data.get("ShopTimeGatedEvents", {}).get("GENERATED_TimeGatedCarPromotions", {})
            for car_id, promo in promos.items():
                for entry in promo:
                    if sched_key in entry.get("ScheduleIDList", []):
                        cars_for_sale[car_id] = entry.get("quantity", 0)

            if not cars_for_sale:
                debug_log(
                    "W2 Showdowns are supposed to have a car for sale, please update ShopTimeGatedEvents.meta.",
                    "warn",
                    force=True
                )

        file_out, console_out = self.format_output(title, start, end, cars, showdown_type, cars_for_sale)
        return file_out, console_out

    def parse_special_event_file(self, filepath, car_stats_map):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        event = list(data.values())[0]
        schedule = event["EventSchedule"]["ScheduleList"][0]
        start, end = schedule["Time_ActiveBetweenAny"][0]
        title = translate_event_name(os.path.splitext(os.path.basename(filepath))[0], self.translations) + " - Showdown"
        showdown_type = "Special"

        cars = []
        for group in event["ShowdownEventsContainer"]["RaceEventGroups"]:
            for race in group["RaceEvents"]:
                for restriction in race.get("Restrictions", []):
                    if restriction.get("RestrictionType") == "CarModels":
                        cars.extend(self.parse_cars(restriction.get("Models", []), car_stats_map, filepath))

        file_out, console_out = self.format_output(title, start, end, cars, showdown_type)
        return file_out, console_out

    def process(self):
        debug_log("Starting ShowdownParser processing", "info")
        if self.crdb_mode:
            debug_log("CRDB mode enabled", "debug", force=True)

        car_stats_map = self.fetch_wr_data()
        file_outputs, console_outputs = [], []

        files = sorted([f for f in os.listdir(self.folder) if os.path.isfile(os.path.join(self.folder, f)) and f.lower().endswith(".txt")])
        for fname in files:
            filepath = os.path.join(self.folder, fname)
            if re.match(self.showdown_pattern, fname):
                debug_log(f"Parsing file: {fname}", "info")
                f_out, c_out = self.parse_showdown_file(filepath, car_stats_map)
                file_outputs.append(f_out)
                console_outputs.append(c_out)
            elif re.match(self.special_bs_pattern, fname) or re.match(self.special_sd_pattern, fname):
                debug_log(f"Parsing special showdown file: {fname}", "info")
                f_out, c_out = self.parse_special_event_file(filepath, car_stats_map)
                file_outputs.append(f_out)
                console_outputs.append(c_out)

        if file_outputs:
            with open(os.path.join(self.folder, self.output_file), "w", encoding="utf-8") as out:
                out.write("\n\n".join(file_outputs))
            debug_log(f"Wrote results to {self.output_file}", "success", force=True)

        output_text = "\n\n".join(console_outputs)
        if console_outputs:
            print(output_text)
        else:
            debug_log("No showdown files matched in this folder.", "warn", force=True)

        if self.missing_translations and not self.crdb_mode:
            print(f"\n{Fore.YELLOW}[SUMMARY]{Style.RESET_ALL} {len(self.missing_translations)} cars missing from TranslationDataAsset.json:")
            for car_id in sorted(self.missing_translations):
                print(f"    • {car_id}")

        if self.missing_wr_data:
            print(f"{Fore.CYAN}[SUMMARY]{Style.RESET_ALL} {len(self.missing_wr_data)} cars missing WR data:")
            for car_id in sorted(self.missing_wr_data):
                print(f"    • {car_id}")

        if self.unknown_cars:
            print(f"{Fore.RED}[SUMMARY]{Style.RESET_ALL} {len(self.unknown_cars)} brand new cars detected:")
            for car_id in sorted(self.unknown_cars):
                print(f"    • {car_id}")

        debug_log("ShowdownParser processing completed", "success")
        return output_text