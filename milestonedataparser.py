# milestonedataparser.py
import os
import re
import json
from colorama import Fore, Style
from utils import debug_log, epoch_to_gmt

class MilestoneDataParser:
    def __init__(self, folder="TextAsset", translations=None):
        self.folder = folder
        self.translations = translations or {}
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
            if schedule and isinstance(schedule, list) and "Time_ActiveBetweenAny" in schedule[0]:
                try:
                    start_epoch, end_epoch = schedule[0]["Time_ActiveBetweenAny"][0]
                except Exception:
                    start_epoch = end_epoch = None

            rewards = event.get("CrewLeaderboardRewardDefinitions", {}).get("SeasonalRewardCars", {}).get(title, {})
            pc_car = rewards.get("PrestigeCupCar")
            ms_car = rewards.get("secondaryPrizeCarDBid")

            pc_trans = self.translations.get(pc_car, pc_car) if pc_car else "None"
            ms_trans = self.translations.get(ms_car, ms_car) if ms_car else "None"

            console_lines.append(f"{Fore.CYAN}Milestone Season {title}:{Style.RESET_ALL}")
            file_lines.append(f"Milestone Season {title}:")
            if start_epoch and end_epoch:
                console_lines.append(epoch_to_gmt(start_epoch))
                console_lines.append(epoch_to_gmt(end_epoch))
                file_lines.append(epoch_to_gmt(start_epoch))
                file_lines.append(epoch_to_gmt(end_epoch))
            console_lines.append(f"PC : {pc_trans}")
            console_lines.append(f"MS : {ms_trans}")
            console_lines.append("")
            file_lines.append(f"PC : {pc_trans}")
            file_lines.append(f"MS : {ms_trans}")
            file_lines.append("")

        console_text = "\n".join(console_lines)
        print(console_text)

        file_text = "\n".join(file_lines)
        with open(os.path.join(self.folder, self.output_file), "w", encoding="utf-8") as f:
            f.write(file_text)
        debug_log(f"Milestone output written to {self.output_file}", "success")

        return file_text