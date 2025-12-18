# milestonedataparser.py
import os
import re
import json
from colorama import Fore, Style
from utils import debug_log, epoch_to_gmt

class MilestoneDataParser:
    def __init__(self, folder="TextAsset", translations=None, debug=False):
        self.folder = folder
        self.translations = translations or {}
        self.debug = debug
        self.output_file = "milestone_output.txt"

    def process(self):
        console_lines = []
        file_lines = []
        files = sorted([f for f in os.listdir(self.folder) if os.path.isfile(os.path.join(self.folder, f)) and f.lower().endswith(".txt")])
        for filename in files:
            if not re.fullmatch(r"\d+\.txt", filename, re.IGNORECASE):
                continue

            path = os.path.join(self.folder, filename)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception as e:
                debug_log(f"Failed to load {filename}: {e}", "error")
                continue

            title = list(data.keys())[0]
            debug_log(f"Processing {title}", "info")
            event = data[title]

            schedule = event.get("EventSchedule", {}).get("ScheduleList", [])
            start_epoch = end_epoch = None
            start_str = end_str = "Unknown"
            if schedule and isinstance(schedule, list) and len(schedule) > 0 and "Time_ActiveBetweenAny" in schedule[0]:
                try:
                    start_epoch, end_epoch = schedule[0]["Time_ActiveBetweenAny"][0]
                    start_str = epoch_to_gmt(start_epoch).split(" ")[0]
                    end_str = epoch_to_gmt(end_epoch).split(" ")[0]
                except Exception:
                    pass

            rewards = event.get("CrewLeaderboardRewardDefinitions", {}).get("SeasonalRewardCars", {}).get(title, {})
            pc_car = rewards.get("PrestigeCupCar")
            ms_car = rewards.get("secondaryPrizeCarDBid")

            pc_trans = self.translations.get(pc_car, pc_car) if pc_car else "None"
            ms_trans = self.translations.get(ms_car, ms_car) if ms_car else "None"

            pc_raw = pc_car if pc_car else ""
            ms_raw = ms_car if ms_car else ""

            # Header line: *Milestone Season X*: date range
            header_text = f"Milestone Season {title}"
            date_part = f"{start_str} - {end_str}"

            console_header = f"{Fore.CYAN}*{header_text}*{Style.RESET_ALL}: {date_part}"
            file_header = f"*{header_text}*: {date_part}"

            console_lines.append(console_header)
            file_lines.append(file_header)

            console_lines.append("")  # Blank line
            file_lines.append("")

            # PC line
            pc_display = pc_trans
            if self.debug and pc_raw and pc_raw != pc_trans:
                pc_display += f" ({pc_raw})"

            console_lines.append(f"- PC : {pc_display}")
            file_lines.append(f"- PC : {pc_display}")

            # MS line
            ms_display = ms_trans
            if self.debug and ms_raw and ms_raw != ms_trans:
                ms_display += f" ({ms_raw})"

            console_lines.append(f"- MS : {ms_display}")
            file_lines.append(f"- MS : {ms_display}")

            console_lines.append("")
            file_lines.append("")

        console_text = "\n".join(console_lines)
        print(console_text)

        file_text = "\n".join(file_lines)
        with open(os.path.join(self.folder, self.output_file), "w", encoding="utf-8") as f:
            f.write(file_text)
        debug_log(f"Milestone output written to {self.output_file}", "success")

        return file_text