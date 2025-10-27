# tournamentparser.py
import os
import re
import json
from utils import debug_log, format_cooldown_time, format_restriction, format_distance, format_time

class TournamentParser:
    def __init__(self, folder="TextAsset", translations=None, collections=None, debug=False):
        self.folder = folder
        self.translations = translations or {}
        self.collections = collections or {}
        self.debug = debug
        self.output_file = "tournament_output.txt"

    def extract_event_schedule_time(self, config_root, season_id):
        event_schedule = config_root.get("EventSchedule", {})
        schedule_list = event_schedule.get("ScheduleList", [])

        if self.debug:
            debug_log(f"Checking EventSchedule for season {season_id}...", "debug")

        m = re.search(r"\d+", str(season_id))
        season_digits = m.group(0) if m else str(season_id)

        candidates = [
            f"TOURNAMENTS_PARTS_GACHA_{season_digits}",
            f"TOURNAMENTS_PARTS_GACHA_{season_id}",
        ]

        for entry in schedule_list:
            entry_id = entry.get("id")
            if entry_id in candidates:
                times = entry.get("Time_ActiveBetweenAny", [])
                if not times or not isinstance(times, list) or not times[0] or len(times[0]) < 2:
                    debug_log(f"No timestamps found for {entry_id}", "warn")
                    return ""
                start, end = times[0][0], times[0][1]
                if self.debug:
                    debug_log(f"Found tournament timing: start={start}, end={end}", "debug")
                return f"({format_time(start, for_file=True)} - {format_time(end, for_file=True)})"

        debug_log(f"Entry with id in {candidates} not found in ScheduleList.", "warn")
        return ""

    def extract_tournament_data(self, tournament_config):
        top_keys = list(tournament_config.keys())
        if len(top_keys) != 1:
            raise KeyError("Expected a single root key like 'TOURNAMENT_244'.")

        tournament_id = top_keys[0]
        config_root = tournament_config[tournament_id]

        events = config_root.get("TournamentConfig", {}).get("TournamentEvents", {})
        if not events:
            debug_log(f"No TournamentEvents found for {tournament_id}", "warn")
            return []

        event_id = list(events.keys())[0]
        period_details = events[event_id].get("PeriodDetails", {})
        if not period_details:
            debug_log(f"No PeriodDetails found for {tournament_id}", "warn")
            return []

        time_str = self.extract_event_schedule_time(config_root, event_id)
        header = f"Tournament Season {event_id}"
        if time_str:
            header += f" - {time_str}"
        formatted_lines = [header]

        for day, day_data in period_details.items():
            for race, race_data in day_data.items():
                slot_id = race_data.get("SlotId")
                matched_names = self.collections.get(slot_id, ["Unknown"])
                name_code = matched_names[0] if isinstance(matched_names, list) and matched_names else matched_names
                nice_name = self.translations.get(name_code, name_code)

                restrictions = race_data.get("Restrictions", [])
                if restrictions:
                    restriction_str = format_restriction(restrictions[0])
                else:
                    restriction_str = "No Restrictions"

                race_event = race_data.get("RaceEvent", {})
                distance_str = format_distance(race_event)
                cooldown_str = format_cooldown_time(race_data.get("CooldownTime", 0))

                line = (
                    f"{day.replace('Day', 'Day ')} / {race.replace('Race', 'Race ')}\n"
                    f"- {nice_name} ({restriction_str}) ({distance_str}) ({cooldown_str} Reset)"
                )
                formatted_lines.append(line)

        return formatted_lines

    def write_to_txt(self, lines):
        if not lines:
            debug_log("No data to write for tournaments.", "warn")
            return
        path = os.path.join(self.folder, self.output_file)
        with open(path, 'w', encoding='utf-8') as f:
            for line in lines:
                f.write(line + '\n')
        debug_log(f"Tournament output written to {path}", "success")

    def process(self):
        debug_log("Starting TournamentParser processing", "info")

        config_files = [f for f in os.listdir(self.folder) if os.path.isfile(os.path.join(self.folder, f)) and re.search(r'TOURNAMENT_.*\.txt', f, re.IGNORECASE) and f != 'tournament_output.txt']

        if not config_files:
            debug_log("No tournament config files found.", "error")
            return ""

        all_lines = []
        for config_file in sorted(config_files):
            try:
                debug_log(f"Processing file: {config_file}", "info")
                with open(os.path.join(self.folder, config_file), 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                lines = self.extract_tournament_data(config_data)
                all_lines.extend(lines + ["\n" + "="*50 + "\n"])
                print("\n".join(lines))
                print("="*50)
            except Exception as e:
                debug_log(f"Failed to process {config_file}: {e}", "error")
                if self.debug:
                    debug_log(f"Stack trace: {traceback.format_exc()}", "debug")

        self.write_to_txt(all_lines)
        debug_log("TournamentParser processing completed", "success")
        return "\n".join(all_lines)