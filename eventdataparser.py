# eventdataparser.py
import os
import re
import json
from colorama import Fore, Style
from utils import (
    debug_log, epoch_to_gmt, translate_model_name_with_suffix,
    is_match, translate_event_name
)

class EventDataParser:
    def __init__(self, folder="TextAsset", translations=None, shop_data=None, debug=False):
        self.folder = folder
        self.translations = translations or {}
        self.shop_data = shop_data or {}
        self.debug = debug
        self.output_file = "event_output.txt"

    def _collect_milestone_rewards(self, event, title):
        rewards_out = []
        top = event.get("EventMilestoneRewards")
        if isinstance(top, list):
            rewards_out.extend([r for r in top if isinstance(r, dict)])
        elif isinstance(top, dict):
            maybe = top.get(title)
            if isinstance(maybe, dict):
                rl = maybe.get("RewardLevels") or maybe.get("rewards") or []
                if isinstance(rl, list):
                    for item in rl:
                        if isinstance(item, dict):
                            if "rewards" in item and isinstance(item["rewards"], list):
                                rewards_out.extend([r for r in item["rewards"] if isinstance(r, dict)])
                            else:
                                rewards_out.append(item)
                elif isinstance(rl, dict):
                    rewards_out.append(rl)
            rl2 = top.get("RewardLevels")
            if isinstance(rl2, list):
                for item in rl2:
                    if isinstance(item, dict):
                        if "rewards" in item and isinstance(item["rewards"], list):
                            rewards_out.extend([r for r in item["rewards"] if isinstance(r, dict)])
                        else:
                            rewards_out.append(item)
        if not rewards_out:
            def find_rewardlevels(obj):
                found = []
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k == "RewardLevels" and isinstance(v, list):
                            found.append(v)
                        else:
                            found.extend(find_rewardlevels(v))
                elif isinstance(obj, list):
                    for item in obj:
                        found.extend(find_rewardlevels(item))
                return found
            for rl in find_rewardlevels(event):
                for item in rl:
                    if isinstance(item, dict):
                        if "rewards" in item and isinstance(item["rewards"], list):
                            rewards_out.extend([r for r in item["rewards"] if isinstance(r, dict)])
                        else:
                            rewards_out.append(item)
        rewards_out = [r for r in rewards_out if isinstance(r, dict)]
        return rewards_out

    def process(self):
        events_data = []  # List to store event data for sorting
        files = sorted([f for f in os.listdir(self.folder) if os.path.isfile(os.path.join(self.folder, f)) and f.lower().endswith(".txt")])
        sd_files = [f for f in files if "_sd" in f.lower() or f.lower().endswith("_bs.txt")]
        for filename in files:
            if "_sd" in filename.lower() or "smp_showdown_" in filename.lower():
                if self.debug:
                    debug_log(f"Skipping {filename} (Showdown variant)", "debug")
                continue
            if "tournament_" in filename.lower():
                if self.debug:
                    debug_log(f"Skipping {filename} (Tournament variant)", "debug")
                continue                
            if filename.lower().endswith("_bs.txt"):
                if self.debug:
                    debug_log(f"Skipping {filename} (Bespoke Showdown variant)", "debug")
                continue            

            path = os.path.join(self.folder, filename)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    content = fh.read()
            except Exception as e:
                debug_log(f"Failed to read {filename}: {e}", "error")
                continue

            if not re.search(r'^\s*\{\s*".+?"\s*:\s*{', content):
                debug_log(f"Skipping {filename} (not event format)", "warn")
                continue

            try:
                data = json.loads(content)
            except Exception as e:
                debug_log(f"Failed to parse JSON {filename}: {e}", "error")
                continue

            title = list(data.keys())[0]
            if re.fullmatch(r"\d+", title):
                if self.debug:
                    debug_log(f"Skipping {filename} (milestone file detected)", "debug")
                continue

            event = data[title]
            debug_log(f"Processing {title}", "info")

            console_lines = []
            file_lines = []

            schedule = event.get("EventSchedule", {}).get("ScheduleList", [])
            start_epoch = end_epoch = None
            if schedule and isinstance(schedule, list) and "Time_ActiveBetweenAny" in schedule[0]:
                try:
                    start_epoch, end_epoch = schedule[0]["Time_ActiveBetweenAny"][0]
                except Exception:
                    pass

            sd_prizes = {}
            sd_event_name = None
            norm_year = title.split("_")[-1] if "_" in title and title.split("_")[-1].isdigit() else ""
            norm_title = re.sub(r'[_ ]', '', title.lower())
            if norm_year:
                norm_title = norm_title.replace(norm_year.lower(), "")

            matching_sd_file = None
            for sd_file in sd_files:
                norm_sd = re.sub(r'[_ ](sd|bs)[0-9]*\.txt$|_?[0-9]{4}\.txt$', '', sd_file, flags=re.IGNORECASE)
                norm_sd = re.sub(r'[_ ]', '', norm_sd.lower())
                if norm_sd == norm_title:
                    matching_sd_file = sd_file
                    break

            if matching_sd_file:
                sd_path = os.path.join(self.folder, matching_sd_file)
                try:
                    with open(sd_path, "r", encoding="utf-8") as fh:
                        sd_content = fh.read()
                    sd_data = json.loads(sd_content)
                    sd_title = list(sd_data.keys())[0]
                    sd_event = sd_data[sd_title]
                    sd_event_name = translate_event_name(sd_title, self.translations)
                    brackets = sd_event.get("ShowdownMilestoneRewards", {}).get("RewardContainers", {}).get(sd_title, {}).get("brackets", [])
                    for bracket in brackets:
                        threshold = bracket.get("threshold")
                        for rew in bracket.get("rewards", []):
                            reward = rew.get("reward", {})
                            if reward.get("rewardType") == 11:
                                name = reward.get("name")
                                if name:
                                    sd_prizes[name] = threshold
                    if sd_prizes:
                        debug_log(f"Extracted SD prizes from {matching_sd_file}: {sd_prizes}", "info")
                except Exception as e:
                    debug_log(f"Failed to process SD file {matching_sd_file}: {e}", "error")

            lockins = event.get("LockinNamespaces", {}).get("Namespaces", {}).get(title, {}).get("LockinSlotsList", [])
            slot_models = {}
            for entry in lockins:
                slot_ids = entry.get("SlotIds", [])
                restrictions = entry.get("Restrictions", [])
                models = [r.get("Model") for r in restrictions if r.get("RestrictionType") == "CarModel" and r.get("Model")]
                seen = []
                for m in models:
                    if m not in seen:
                        seen.append(m)
                for sid in slot_ids:
                    slot_label = sid.strip().strip("{}")
                    slot_models.setdefault(slot_label, []).extend(seen)

            for k in list(slot_models.keys()):
                seen = []
                for m in slot_models[k]:
                    if m not in seen:
                        seen.append(m)
                slot_models[k] = tuple(seen)

            combined = {}
            for slot_label, models in slot_models.items():
                combined.setdefault(models, []).append(slot_label)

            reward_entries = self._collect_milestone_rewards(event, title)

            wins_by_rewardname = {}
            prize_type = prize_value = None
            for r in reward_entries:
                if not isinstance(r, dict):
                    continue
                info = r.get("RewardInfo") or {}
                wins = r.get("WinsRequired")
                if isinstance(info, dict):
                    rt = info.get("rewardType")
                    name = info.get("name")
                    if rt == 11 and name:
                        try:
                            w = int(wins) if wins is not None else None
                        except Exception:
                            w = wins
                        if name and (name not in wins_by_rewardname or (w is not None and w > (wins_by_rewardname.get(name) or 0))):
                            wins_by_rewardname[name] = w
                    elif rt == 44 and name:
                        prize_type = "Sticker"
                        prize_value = name

            special_prize = None
            special_ladder = event.get("SpecialLadderEvents", {}).get("LadderEvents", {}).get("RaceEventGroups", [])
            if isinstance(special_ladder, list):
                for group in special_ladder:
                    car_prize = group.get("CarPrizeForCompletionDetails")
                    if car_prize:
                        if isinstance(car_prize, dict):
                            special_prize = car_prize.get("Car") or next(iter(car_prize.values()), None)
                        else:
                            special_prize = car_prize
                        break

            shop_map = {}
            if self.shop_data:
                promos = self.shop_data.get("ShopTimeGatedEvents", {}).get("GENERATED_TimeGatedCarPromotions", {})
                for car_name, entries in promos.items():
                    if not isinstance(entries, list):
                        continue
                    matching_entries = [
                        entry for entry in entries
                        if title in (entry.get("ScheduleIDList") or [])
                    ]
                    if matching_entries:
                        shop_map[car_name] = matching_entries

            gold_rewards = []
            for gacha in event.get("GachaEventsCalendar", {}).get("GachaEvents", []):
                for alt in gacha.get("GachaWeightAlterations", []):
                    if alt.get("RewardType") == 11:
                        rn = alt.get("RewardName")
                        mach = alt.get("AffectedGachaMachine", "")
                        if rn and re.search(r"_GOLD_[A-Z]$", mach, re.IGNORECASE):
                            gold_rewards.append(rn)
            gold_rewards = list(dict.fromkeys(gold_rewards))

            pretty_title = translate_event_name(title, self.translations)
            if pretty_title != title:
                console_lines.append(f"{Fore.CYAN}{pretty_title}{Style.RESET_ALL} ({title})")
                file_lines.append(f"{pretty_title} ({title})")
            else:
                console_lines.append(f"{Fore.CYAN}{title}{Style.RESET_ALL}")
                file_lines.append(title)
            if start_epoch and end_epoch:
                console_lines.append(epoch_to_gmt(start_epoch))
                console_lines.append(epoch_to_gmt(end_epoch))
                file_lines.append(epoch_to_gmt(start_epoch))
                file_lines.append(epoch_to_gmt(end_epoch))
            console_lines.append("")
            file_lines.append("")

            def slot_sort_key(slots):
                nums = []
                for s in slots:
                    m = re.search(r'(\d+)', s)
                    if m:
                        nums.append(int(m.group(1)))
                return min(nums) if nums else float("inf")

            sorted_items = sorted(combined.items(), key=lambda kv: slot_sort_key(kv[1]))

            for models_tuple, slots in sorted_items:
                nums = []
                others = []
                for s in slots:
                    m = re.search(r'(\d+)', s)
                    if m:
                        nums.append(m.group(1))
                    else:
                        others.append(re.sub(r'\W+', '', s))
                if nums:
                    label = "Slot " + " / ".join(nums)
                elif others:
                    label = "Slot " + " / ".join(others)
                else:
                    label = "Slot ?"
                console_lines.append(f"{Fore.GREEN}{label}{Style.RESET_ALL}")
                file_lines.append(label)

                for model_raw in models_tuple:
                    translated_variants = translate_model_name_with_suffix(model_raw, self.translations, debug_mode=self.debug)
                    for pretty, suffix_color, raw_id in translated_variants:
                        console_display = pretty + (f" {suffix_color}" if suffix_color else "")
                        file_display = pretty
                        annotations = []

                        for reward_name, wins_required in wins_by_rewardname.items():
                            if is_match(reward_name, model_raw) or is_match(model_raw, reward_name):
                                annotations.append(f"Winnable Race {wins_required}")
                                break

                        if any(is_match(gr, raw_id) or is_match(raw_id, gr) for gr in gold_rewards):
                            gk_text = f"{Fore.YELLOW}Pullable GK{Style.RESET_ALL}" if suffix_color else "Pullable GK"
                            annotations.append(gk_text)

                        shop_annotations = []
                        for shop_key, entries in shop_map.items():
                            if not isinstance(entries, list):
                                entries = [entries]
                            check_keys = [raw_id]
                            if raw_id != model_raw:
                                check_keys.append(model_raw)
                            for entry in entries:
                                if any(is_match(shop_key, ck) or is_match(ck, shop_key) for ck in check_keys):
                                    qty = entry.get("quantity", 0)
                                    shop_text = "0 Gold Coins" if qty == 0 else f"{qty} Gold Coins"
                                    colored = f"{Fore.YELLOW}{shop_text}{Style.RESET_ALL}"
                                    shop_annotations.append(colored)

                        if shop_annotations:
                            seen = set()
                            unique = []
                            for ann in shop_annotations:
                                plain = re.sub(r'\x1b\[[0-9;]*m', '', ann)
                                if plain not in seen:
                                    seen.add(plain)
                                    unique.append(ann)
                            annotations.extend(unique)

                        for sd_name, thresh in sd_prizes.items():
                            if is_match(sd_name, model_raw) or is_match(model_raw, sd_name):
                                sd_text = f"{sd_event_name} {thresh} SD Prize Car"
                                console_sd_text = f"{Fore.BLUE}{sd_text}{Style.RESET_ALL}"
                                annotations.append(console_sd_text)
                                break

                        # REMOVED: No more "CRDB: ..." annotation on regular cars

                        bullet_console = "- "
                        bullet_file = "- "

                        if annotations:
                            console_lines.append(f"{bullet_console}{console_display} - {' / '.join(annotations)}")
                            plain_annotations = [re.sub(r'\x1b\[[0-9;]*m', '', a) for a in annotations]
                            file_lines.append(f"{bullet_file}{file_display} - {' / '.join(plain_annotations)}")
                        else:
                            console_lines.append(f"{bullet_console}{console_display}")
                            file_lines.append(f"{bullet_file}{file_display}")
                console_lines.append("")
                file_lines.append("")

            # Prize handling – dash bullet + optional debug CRDB in parentheses
            prize_console_prefix = f"{Fore.MAGENTA}- Prize Car : "
            prize_file_prefix = "- Prize Car : "
            sticker_console_prefix = f"{Fore.MAGENTA}- Prize Sticker : "
            sticker_file_prefix = "- Prize Sticker : "

            if special_prize:
                translated = self.translations.get(special_prize, special_prize)
                raw_key = special_prize
                is_sticker = False
            elif prize_type == "Car":
                translated = self.translations.get(prize_value, prize_value)
                raw_key = prize_value
                is_sticker = False
            elif prize_type == "Sticker":
                translated = self.translations.get(prize_value, prize_value)
                raw_key = prize_value
                is_sticker = True
            else:
                if reward_entries:
                    max_win = -1
                    max_info = None
                    for r in reward_entries:
                        if not isinstance(r, dict):
                            continue
                        w = r.get("WinsRequired")
                        info = r.get("RewardInfo", {}) or {}
                        if isinstance(w, int) and w > max_win:
                            max_win = w
                            max_info = info
                    if max_info and max_info.get("rewardType") == 11 and max_info.get("name"):
                        raw_key = max_info.get("name")
                        translated = self.translations.get(raw_key, raw_key)
                        is_sticker = False
                    else:
                        translated = None
                        raw_key = None
                else:
                    translated = None
                    raw_key = None
                is_sticker = False

            if translated is not None:
                if is_sticker:
                    console_base = f"{sticker_console_prefix}{translated}"
                    file_base = f"{sticker_file_prefix}{translated}"
                else:
                    console_base = f"{prize_console_prefix}{translated}"
                    file_base = f"{prize_file_prefix}{translated}"

                if self.debug and raw_key and raw_key != translated:
                    console_base += f" ({raw_key})"
                    file_base += f" ({raw_key})"

                console_lines.append(f"{console_base}{Style.RESET_ALL}")
                file_lines.append(file_base)

            console_lines.append("")
            file_lines.append("")

            events_data.append({
                "start_epoch": start_epoch if start_epoch else float("inf"),
                "console_lines": console_lines,
                "file_lines": file_lines
            })

        events_data.sort(key=lambda x: x["start_epoch"])

        console_lines = []
        file_lines = []
        for event in events_data:
            console_lines.extend(event["console_lines"])
            file_lines.extend(event["file_lines"])

        console_text = "\n".join(console_lines)
        print(console_text)

        file_text = "\n".join(file_lines)
        with open(os.path.join(self.folder, self.output_file), "w", encoding="utf-8") as f:
            f.write(file_text)
        debug_log(f"Event output written to {self.output_file}", "success")

        return file_text