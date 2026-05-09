import customtkinter as ctk
import win32gui
import win32process
import psutil
import time
import json
import os
import threading
import tkinter as tk
from tkinter import messagebox
from datetime import datetime, timedelta
from pathlib import Path


# =====================================================
# SYSTEM CONFIGURATION
# =====================================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "aura_database.json"
RETENTION_DAYS = 30
TRACK_INTERVAL_MS = 1000
AUTOSAVE_SECONDS = 30
VISUAL_REFRESH_SECONDS = 3
RANKINGS_REFRESH_SECONDS = 2
SKILLS_REFRESH_SECONDS = 3
SETTINGS_REFRESH_SECONDS = 5
PROGRESS_ANIMATION_STEPS = 8
PROGRESS_ANIMATION_MS = 24

COLORS = {
    "bg": "#080A12",
    "sidebar": "#10131D",
    "surface": "#141824",
    "surface_2": "#1B2030",
    "surface_3": "#23293A",
    "text": "#F8FAFC",
    "muted": "#9AA4B2",
    "cyan": "#00E5FF",
    "pink": "#FF2D95",
    "green": "#39FF88",
    "purple": "#8B5CF6",
    "yellow": "#FFD166",
    "red": "#FF4D6D",
    "blue": "#4DA3FF",
    "orange": "#FF9F1C",
}

CATEGORY_COLORS = {
    "Coding": COLORS["cyan"],
    "Study": COLORS["green"],
    "Creating": COLORS["pink"],
    "Music": COLORS["purple"],
    "Social": COLORS["yellow"],
    "Browsing": COLORS["blue"],
    "Gaming": COLORS["red"],
    "System": COLORS["muted"],
    "App": COLORS["muted"],
}

SKILL_COLORS = {
    "Intelligence": COLORS["cyan"],
    "Focus": COLORS["green"],
    "Creativity": COLORS["pink"],
    "Charisma": COLORS["yellow"],
    "Exploration": COLORS["blue"],
    "Reflexes": COLORS["red"],
}

# Gamification Dictionary: (Emoji, Category, Vibe Multiplier, Skill Target)
APP_CATEGORIES = {
    "code": ("💻", "Coding", 2.0, "Intelligence"),
    "code - insiders": ("💻", "Coding", 2.0, "Intelligence"),
    "cursor": ("💻", "Coding", 2.0, "Intelligence"),
    "pycharm": ("💻", "Coding", 2.0, "Intelligence"),
    "webstorm": ("💻", "Coding", 2.0, "Intelligence"),
    "devenv": ("💻", "Coding", 2.0, "Intelligence"),
    "powershell": ("⚡", "Coding", 1.5, "Intelligence"),
    "windowsterminal": ("⚡", "Coding", 1.5, "Intelligence"),
    "cmd": ("⚡", "Coding", 1.2, "Intelligence"),
    "python": ("🐍", "Coding", 2.0, "Intelligence"),
    "notepad++": ("📝", "Study", 1.0, "Focus"),
    "winword": ("📄", "Study", 1.2, "Focus"),
    "excel": ("📊", "Study", 1.2, "Focus"),
    "powerpnt": ("📽️", "Study", 1.1, "Focus"),
    "onenote": ("📒", "Study", 1.2, "Focus"),
    "obs": ("🎥", "Creating", 1.5, "Creativity"),
    "photoshop": ("🎨", "Creating", 1.5, "Creativity"),
    "illustrator": ("🎨", "Creating", 1.5, "Creativity"),
    "figma": ("🎨", "Creating", 1.5, "Creativity"),
    "spotify": ("🎧", "Music", 0.8, "Creativity"),
    "discord": ("💬", "Social", -0.4, "Charisma"),
    "slack": ("💬", "Social", 0.6, "Charisma"),
    "teams": ("💬", "Social", 0.6, "Charisma"),
    "zoom": ("🎙️", "Social", 0.6, "Charisma"),
    "chrome": ("🌐", "Browsing", 0.1, "Exploration"),
    "brave": ("🌐", "Browsing", 0.1, "Exploration"),
    "firefox": ("🌐", "Browsing", 0.1, "Exploration"),
    "msedge": ("🌐", "Browsing", 0.1, "Exploration"),
    "valorant": ("🎮", "Gaming", -1.0, "Reflexes"),
    "steam": ("🎮", "Gaming", -0.8, "Reflexes"),
    "epicgameslauncher": ("🎮", "Gaming", -0.8, "Reflexes"),
    "minecraftlauncher": ("🎮", "Gaming", -0.8, "Reflexes"),
    "system idle": ("💤", "System", 0, "Focus"),
}

APP_DISPLAY_NAMES = {
    "code": "VS Code",
    "code - insiders": "VS Code Insiders",
    "cmd": "Command Prompt",
    "msedge": "Microsoft Edge",
    "winword": "Microsoft Word",
    "powerpnt": "PowerPoint",
    "windowsterminal": "Terminal",
}


# =====================================================
# UTILITY HELPERS
# =====================================================
def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def app_name(app):
    if not app:
        return "Unknown"
    return APP_DISPLAY_NAMES.get(app, app.replace("_", " ").replace("-", " ").title())


def app_meta(app):
    return APP_CATEGORIES.get(app, ("📱", "App", 0, "Exploration"))


def format_duration(seconds, live=False):
    seconds = max(0, int(seconds or 0))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if live and hours == 0:
        return f"{minutes}m {secs}s"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return "<1m" if seconds else "0m"


def short_date(date_key):
    try:
        return datetime.strptime(date_key, "%Y-%m-%d").strftime("%d %b")
    except ValueError:
        return date_key


# =====================================================
# DATA & GAMIFICATION ENGINE
# =====================================================
class AuraEngine:
    def __init__(self):
        self.lock = threading.RLock()
        self.db = self.load_and_clean_data()
        self.today = self.date_key()
        self.db.setdefault(self.today, {})

        self.current_app = None
        self.start_time = time.time()
        self.app_started_at = self.start_time
        self.last_save_at = 0
        self.pid_cache = {}

    def date_key(self, when=None):
        when = when or datetime.now()
        return when.strftime("%Y-%m-%d")

    def recent_days(self, days=RETENTION_DAYS):
        today = datetime.now().date()
        return [
            (today - timedelta(days=offset)).strftime("%Y-%m-%d")
            for offset in range(days - 1, -1, -1)
        ]

    def normalize_app_data(self, apps):
        normalized = {}
        if not isinstance(apps, dict):
            return normalized

        for app, raw in apps.items():
            if not isinstance(app, str) or not isinstance(raw, dict):
                continue
            try:
                seconds = float(raw.get("time", 0) or 0)
                opens = int(raw.get("opens", 0) or 0)
            except (TypeError, ValueError):
                continue
            normalized[app] = {
                "time": max(0.0, seconds),
                "opens": max(0, opens),
            }
        return normalized

    def load_and_clean_data(self):
        db = {}
        if DATA_FILE.exists():
            try:
                with DATA_FILE.open("r", encoding="utf-8") as file:
                    db = json.load(file)
            except (json.JSONDecodeError, OSError):
                db = {}

        cleaned_db = {}
        cutoff_date = datetime.now().date() - timedelta(days=RETENTION_DAYS - 1)

        for date_str, apps in db.items():
            try:
                record_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                continue
            if record_date >= cutoff_date:
                cleaned_db[date_str] = self.normalize_app_data(apps)

        return cleaned_db

    def save_data(self):
        with self.lock:
            snapshot = json.loads(json.dumps(self.db))

        tmp_file = DATA_FILE.with_name(f"{DATA_FILE.name}.tmp")
        with tmp_file.open("w", encoding="utf-8") as file:
            json.dump(snapshot, file, indent=4)
        os.replace(tmp_file, DATA_FILE)

    def autosave(self):
        now = time.time()
        if now - self.last_save_at < AUTOSAVE_SECONDS:
            return
        self.last_save_at = now
        threading.Thread(target=self.save_data, daemon=True).start()

    def get_active_process(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            if pid in self.pid_cache:
                return self.pid_cache[pid]

            name = psutil.Process(pid).name().lower().replace(".exe", "")
            self.pid_cache[pid] = name
            return name
        except (psutil.Error, OSError, RuntimeError):
            return "system idle"

    def ensure_today(self, now):
        current_day = self.date_key(datetime.fromtimestamp(now))
        if current_day == self.today:
            return

        if self.current_app and self.current_app != "system idle":
            self.add_time(self.today, self.current_app, now - self.start_time)

        self.today = current_day
        self.db.setdefault(self.today, {})
        self.start_time = now
        self.app_started_at = now

    def touch_app(self, day, app, opened=False):
        if not app or app == "system idle":
            return
        day_stats = self.db.setdefault(day, {})
        day_stats.setdefault(app, {"time": 0.0, "opens": 0})
        if opened:
            day_stats[app]["opens"] += 1

    def add_time(self, day, app, seconds):
        if not app or app == "system idle" or seconds <= 0:
            return
        self.touch_app(day, app)
        self.db[day][app]["time"] += seconds

    def tick(self):
        new_app = self.get_active_process()
        now = time.time()

        with self.lock:
            self.ensure_today(now)
            elapsed = now - self.start_time

            if self.current_app is None:
                self.current_app = new_app
                self.app_started_at = now
                self.touch_app(self.today, new_app, opened=True)
            else:
                self.add_time(self.today, self.current_app, elapsed)
                if new_app != self.current_app:
                    self.current_app = new_app
                    self.app_started_at = now
                    self.touch_app(self.today, new_app, opened=True)

            self.start_time = now
            return self.get_day_stats(self.today)

    def get_day_stats(self, day):
        with self.lock:
            return {
                app: {"time": data.get("time", 0), "opens": data.get("opens", 0)}
                for app, data in self.db.get(day, {}).items()
            }

    def get_app_totals(self, days=RETENTION_DAYS):
        totals = {}
        with self.lock:
            day_keys = self.recent_days(days)
            for day in day_keys:
                for app, data in self.db.get(day, {}).items():
                    emoji, category, vibe, skill = app_meta(app)
                    if app not in totals:
                        totals[app] = {
                            "time": 0.0,
                            "opens": 0,
                            "emoji": emoji,
                            "category": category,
                            "vibe": vibe,
                            "skill": skill,
                            "score": 0.0,
                        }
                    totals[app]["time"] += data.get("time", 0)
                    totals[app]["opens"] += data.get("opens", 0)
                    totals[app]["score"] += (data.get("time", 0) / 60) * vibe
        return totals

    def get_category_totals(self, days=RETENTION_DAYS):
        categories = {}
        for data in self.get_app_totals(days).values():
            category = data["category"]
            categories.setdefault(category, {"time": 0.0, "score": 0.0, "opens": 0})
            categories[category]["time"] += data["time"]
            categories[category]["score"] += data["score"]
            categories[category]["opens"] += data["opens"]
        return categories

    def get_daily_totals(self, days=RETENTION_DAYS):
        rows = []
        with self.lock:
            for day in self.recent_days(days):
                total = sum(data.get("time", 0) for data in self.db.get(day, {}).values())
                rows.append((day, total))
        return rows

    def get_total_skills(self, days=RETENTION_DAYS):
        skills = {skill: 0.0 for skill in SKILL_COLORS}
        with self.lock:
            for day in self.recent_days(days):
                for app, data in self.db.get(day, {}).items():
                    _, _, vibe, skill = app_meta(app)
                    multiplier = max(0.25, vibe) if vibe > 0 else 0.25
                    skills.setdefault(skill, 0.0)
                    skills[skill] += data.get("time", 0) * multiplier
        return skills

    def get_streak(self, min_seconds=600):
        streak = 0
        with self.lock:
            for day in reversed(self.recent_days(RETENTION_DAYS)):
                total = sum(data.get("time", 0) for data in self.db.get(day, {}).values())
                if total >= min_seconds:
                    streak += 1
                else:
                    break
        return streak

    def get_best_day(self, days=RETENTION_DAYS):
        daily = self.get_daily_totals(days)
        if not daily:
            return None, 0
        return max(daily, key=lambda item: item[1])

    def get_summary(self, days=RETENTION_DAYS):
        apps = self.get_app_totals(days)
        total = sum(data["time"] for data in apps.values())
        opens = sum(data["opens"] for data in apps.values())
        productive = sum(data["time"] for data in apps.values() if data["vibe"] > 0)
        vibe_score = round(sum(data["score"] for data in apps.values()))
        top_app = max(apps.items(), key=lambda item: item[1]["time"]) if apps else None

        tier, tier_progress, next_label = self.get_rank_tier(productive)
        focus_ratio = (productive / total) if total else 0

        return {
            "total": total,
            "opens": opens,
            "productive": productive,
            "vibe_score": vibe_score,
            "focus_ratio": focus_ratio,
            "top_app": top_app,
            "tier": tier,
            "tier_progress": tier_progress,
            "next_label": next_label,
            "streak": self.get_streak(),
        }

    def get_rank_tier(self, productive_seconds):
        productive_hours = productive_seconds / 3600
        tiers = [
            ("Starter", 0),
            ("Bronze", 1),
            ("Silver", 5),
            ("Gold", 15),
            ("Diamond", 30),
            ("Mythic", 60),
        ]

        current = tiers[0]
        next_tier = tiers[1]
        for index, tier in enumerate(tiers):
            if productive_hours >= tier[1]:
                current = tier
                next_tier = tiers[min(index + 1, len(tiers) - 1)]

        if current == next_tier:
            return current[0], 1, "maxed"

        span = max(1, next_tier[1] - current[1])
        progress = clamp((productive_hours - current[1]) / span)
        return current[0], progress, f"{next_tier[0]} at {next_tier[1]}h"

    def prune_old_data(self):
        with self.lock:
            cleaned = self.load_and_clean_data()
            cleaned.setdefault(self.today, {})
            self.db = cleaned

    def reset_all_data(self):
        with self.lock:
            self.db = {self.today: {}}
            self.current_app = None
            self.start_time = time.time()
            self.app_started_at = self.start_time


# =====================================================
# UI COMPONENTS
# =====================================================
class StatCard(ctk.CTkFrame):
    def __init__(self, master, label, value="--", subvalue="", accent=COLORS["cyan"]):
        super().__init__(master, fg_color=COLORS["surface"], corner_radius=8)
        self.accent = accent
        self.current_value = value
        self.current_subvalue = subvalue

        self.grid_columnconfigure(0, weight=1)
        self.label = ctk.CTkLabel(self, text=label.upper(), text_color=COLORS["muted"], font=ctk.CTkFont(size=11, weight="bold"))
        self.label.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 0))

        self.value = ctk.CTkLabel(self, text=value, text_color=COLORS["text"], font=ctk.CTkFont(size=24, weight="bold"))
        self.value.grid(row=1, column=0, sticky="w", padx=14, pady=(2, 0))

        self.subvalue = ctk.CTkLabel(self, text=subvalue, text_color=accent, font=ctk.CTkFont(size=12, weight="bold"))
        self.subvalue.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 12))

    def set(self, value, subvalue="", accent=None):
        if accent:
            self.accent = accent
        if value != self.current_value:
            self.value.configure(text=value)
            self.current_value = value
        if subvalue != self.current_subvalue:
            self.subvalue.configure(text=subvalue)
            self.current_subvalue = subvalue
        self.subvalue.configure(text_color=self.accent)


class NeonProgressRow(ctk.CTkFrame):
    def __init__(self, master, name, value, progress, accent, prefix="", suffix=""):
        super().__init__(master, fg_color=COLORS["surface"], corner_radius=8)
        self.grid_columnconfigure(0, weight=1)
        self.current_progress = clamp(progress)
        self.target_progress = self.current_progress
        self.animation_after = None
        self.animation_step = 0
        self.animation_start = self.current_progress
        self.current_name = ""
        self.current_value = ""
        self.accent = accent

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        top.grid_columnconfigure(0, weight=1)

        self.name_label = ctk.CTkLabel(top, text="", text_color=COLORS["text"], font=ctk.CTkFont(weight="bold"))
        self.name_label.grid(row=0, column=0, sticky="w")
        self.value_label = ctk.CTkLabel(top, text="", text_color=accent, font=ctk.CTkFont(weight="bold"))
        self.value_label.grid(row=0, column=1, sticky="e")

        self.bar = ctk.CTkProgressBar(self, height=7, fg_color=COLORS["surface_3"], progress_color=accent)
        self.bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.bar.set(self.current_progress)
        self.update_row(name, value, progress, accent, prefix, suffix, animate=False)

    def update_row(self, name, value, progress, accent, prefix="", suffix="", animate=True):
        label_text = f"{prefix}{name}"
        value_text = f"{value}{suffix}"

        if label_text != self.current_name:
            self.name_label.configure(text=label_text)
            self.current_name = label_text
        if value_text != self.current_value:
            self.value_label.configure(text=value_text)
            self.current_value = value_text
        if accent != self.accent:
            self.accent = accent
            self.value_label.configure(text_color=accent)
            self.bar.configure(progress_color=accent)

        self.set_progress(progress, animate=animate)

    def set_progress(self, progress, animate=True):
        progress = clamp(progress)
        if self.animation_after:
            try:
                self.after_cancel(self.animation_after)
            except (ValueError, tk.TclError):
                pass
            self.animation_after = None

        if not animate or abs(progress - self.current_progress) < 0.01:
            self.current_progress = progress
            self.target_progress = progress
            self.bar.set(progress)
            return

        self.target_progress = progress
        self.animation_start = self.current_progress
        self.animation_step = 0
        self.animate_progress()

    def animate_progress(self):
        self.animation_step += 1
        ratio = self.animation_step / PROGRESS_ANIMATION_STEPS
        eased = 1 - pow(1 - ratio, 3)
        next_value = self.animation_start + (self.target_progress - self.animation_start) * eased
        self.current_progress = clamp(next_value)
        self.bar.set(self.current_progress)

        if self.animation_step < PROGRESS_ANIMATION_STEPS:
            self.animation_after = self.after(PROGRESS_ANIMATION_MS, self.animate_progress)
        else:
            self.current_progress = self.target_progress
            self.bar.set(self.target_progress)
            self.animation_after = None


def sync_progress_rows(parent, row_cache, specs, empty_label, empty_text):
    if not specs:
        for row in row_cache.values():
            row.pack_forget()
        parent.synced_row_order = []
        empty_label.configure(text=empty_text)
        if not empty_label.winfo_ismapped():
            empty_label.pack(anchor="w", pady=12)
        return

    empty_label.pack_forget()
    desired_keys = [spec["key"] for spec in specs]
    active_keys = set(desired_keys)
    order_changed = desired_keys != getattr(parent, "synced_row_order", [])

    if order_changed:
        for row in row_cache.values():
            row.pack_forget()

    for spec in specs:
        key = spec["key"]
        row_args = {name: value for name, value in spec.items() if name != "key"}

        if key not in row_cache:
            row_cache[key] = NeonProgressRow(parent, **row_args)
            animate = False
        else:
            animate = True
            row_cache[key].update_row(**row_args, animate=animate)

        if order_changed or not row_cache[key].winfo_ismapped():
            row_cache[key].pack(fill="x", pady=5)

    for key, row in row_cache.items():
        if key not in active_keys:
            row.pack_forget()

    parent.synced_row_order = desired_keys


class TrendChart(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["surface"], corner_radius=8)
        self.data = []
        self.data_signature = None
        self.canvas = tk.Canvas(self, bg=COLORS["surface"], highlightthickness=0, height=210)
        self.canvas.pack(fill="both", expand=True, padx=12, pady=12)
        self.canvas.bind("<Configure>", lambda event: self.draw())

    def set_data(self, data, force=False):
        signature = tuple((day, int(seconds // 10)) for day, seconds in data)
        if not force and signature == self.data_signature:
            return
        self.data_signature = signature
        self.data = data
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        if not self.data:
            self.canvas.create_text(width / 2, height / 2, text="No tracked data yet", fill=COLORS["muted"], font=("Segoe UI", 12, "bold"))
            return

        pad_x = 34
        pad_y = 28
        chart_w = max(1, width - pad_x * 2)
        chart_h = max(1, height - pad_y * 2)
        max_value = max(seconds for _, seconds in self.data) or 1
        bar_gap = 4
        bar_w = max(3, (chart_w - bar_gap * (len(self.data) - 1)) / len(self.data))

        self.canvas.create_line(pad_x, height - pad_y, width - pad_x, height - pad_y, fill=COLORS["surface_3"])

        for index, (date_key, seconds) in enumerate(self.data):
            x1 = pad_x + index * (bar_w + bar_gap)
            bar_h = (seconds / max_value) * chart_h
            y1 = height - pad_y - bar_h
            x2 = x1 + bar_w
            y2 = height - pad_y
            color = [COLORS["cyan"], COLORS["pink"], COLORS["green"], COLORS["purple"]][index % 4]
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")

            if index in (0, len(self.data) - 1):
                self.canvas.create_text((x1 + x2) / 2, height - 10, text=short_date(date_key), fill=COLORS["muted"], font=("Segoe UI", 8, "bold"))

        peak_day, peak_seconds = max(self.data, key=lambda item: item[1])
        self.canvas.create_text(pad_x, 14, text=f"30-day activity · peak {short_date(peak_day)} / {format_duration(peak_seconds)}", fill=COLORS["text"], anchor="w", font=("Segoe UI", 11, "bold"))


class DonutChart(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["surface"], corner_radius=8)
        self.data = {}
        self.data_signature = None
        self.canvas = tk.Canvas(self, bg=COLORS["surface"], highlightthickness=0, height=250)
        self.canvas.pack(fill="both", expand=True, padx=12, pady=12)
        self.canvas.bind("<Configure>", lambda event: self.draw())

    def set_data(self, data, force=False):
        signature = tuple(sorted((name, int(row["time"] // 10)) for name, row in data.items()))
        if not force and signature == self.data_signature:
            return
        self.data_signature = signature
        self.data = data
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        totals = {name: row["time"] for name, row in self.data.items() if row["time"] > 0}
        total_seconds = sum(totals.values())
        if not totals:
            self.canvas.create_text(width / 2, height / 2, text="Category mix loading", fill=COLORS["muted"], font=("Segoe UI", 12, "bold"))
            return

        size = min(width, height) - 58
        x1 = 24
        y1 = 34
        x2 = x1 + size
        y2 = y1 + size
        start = 90

        for category, seconds in sorted(totals.items(), key=lambda item: item[1], reverse=True):
            extent = (seconds / total_seconds) * 359.9
            color = CATEGORY_COLORS.get(category, COLORS["muted"])
            self.canvas.create_arc(x1, y1, x2, y2, start=start, extent=-extent, style="arc", outline=color, width=22)
            start -= extent

        self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2 - 8, text=format_duration(total_seconds), fill=COLORS["text"], font=("Segoe UI", 16, "bold"))
        self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2 + 14, text="tracked", fill=COLORS["muted"], font=("Segoe UI", 10, "bold"))

        legend_x = x2 + 26
        legend_y = 42
        for category, seconds in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:7]:
            color = CATEGORY_COLORS.get(category, COLORS["muted"])
            self.canvas.create_rectangle(legend_x, legend_y + 4, legend_x + 10, legend_y + 14, fill=color, outline="")
            self.canvas.create_text(legend_x + 18, legend_y + 9, text=f"{category} · {format_duration(seconds)}", fill=COLORS["text"], anchor="w", font=("Segoe UI", 10, "bold"))
            legend_y += 25


# =====================================================
# UI VIEWS (PAGES)
# =====================================================
class DashboardView(ctk.CTkFrame):
    def __init__(self, master, engine):
        super().__init__(master, fg_color="transparent")
        self.engine = engine
        self.cards = {}
        self.today_rows = {}
        self.category_rows = {}
        self.rank_progress = 0
        self.rank_animation_after = None

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(header, text="DigitalWebling Ultra", font=ctk.CTkFont(size=30, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(header, text="Live app aura, focus streaks, and 30-day glow-up stats.", text_color=COLORS["muted"]).pack(anchor="w", pady=(2, 0))

        metrics = ctk.CTkFrame(self, fg_color="transparent")
        metrics.pack(fill="x", pady=(0, 16))
        for column in range(5):
            metrics.grid_columnconfigure(column, weight=1)

        self.cards["active"] = StatCard(metrics, "Active now", accent=COLORS["cyan"])
        self.cards["session"] = StatCard(metrics, "Session", accent=COLORS["pink"])
        self.cards["today"] = StatCard(metrics, "Today", accent=COLORS["green"])
        self.cards["rank"] = StatCard(metrics, "30-day rank", accent=COLORS["yellow"])
        self.cards["streak"] = StatCard(metrics, "Streak", accent=COLORS["purple"])

        for index, card in enumerate(self.cards.values()):
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 8, 0))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")

        ctk.CTkLabel(left, text="Today Leaderboard", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 8))
        self.today_list = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.today_list.pack(fill="both", expand=True)
        self.today_empty = ctk.CTkLabel(self.today_list, text="", text_color=COLORS["muted"])

        ctk.CTkLabel(right, text="Category Pulse", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 8))
        self.category_list = ctk.CTkFrame(right, fg_color="transparent")
        self.category_list.pack(fill="x")
        self.category_empty = ctk.CTkLabel(self.category_list, text="", text_color=COLORS["muted"])

        self.rank_meter = ctk.CTkProgressBar(right, height=12, fg_color=COLORS["surface_3"], progress_color=COLORS["yellow"])
        self.rank_meter.pack(fill="x", pady=(18, 6))
        self.rank_hint = ctk.CTkLabel(right, text="", text_color=COLORS["muted"])
        self.rank_hint.pack(anchor="w")

    def update_view(self, force=False):
        current_app = self.engine.current_app or "system idle"
        emoji, category, _, _ = app_meta(current_app)
        today = self.engine.get_summary(days=1)
        month = self.engine.get_summary(days=RETENTION_DAYS)
        session = self.engine.app_started_at and (time.time() - self.engine.app_started_at)

        self.cards["active"].set(f"{emoji} {app_name(current_app)}", category, CATEGORY_COLORS.get(category, COLORS["cyan"]))
        self.cards["session"].set(format_duration(session, live=True), "current focus", COLORS["pink"])
        self.cards["today"].set(format_duration(today["total"]), f"{today['opens']} opens", COLORS["green"])
        self.cards["rank"].set(month["tier"], f"{month['vibe_score']} aura", COLORS["yellow"])
        self.cards["streak"].set(f"{month['streak']} days", "10m+ tracked", COLORS["purple"])
        self.set_rank_progress(month["tier_progress"], animate=not force)
        self.rank_hint.configure(text=f"Next rank: {month['next_label']}")

        self.load_today_apps()
        self.load_categories()

    def set_rank_progress(self, progress, animate=True):
        progress = clamp(progress)
        if self.rank_animation_after:
            try:
                self.after_cancel(self.rank_animation_after)
            except (ValueError, tk.TclError):
                pass
            self.rank_animation_after = None

        if not animate or abs(progress - self.rank_progress) < 0.01:
            self.rank_progress = progress
            self.rank_meter.set(progress)
            return

        start = self.rank_progress

        def step(frame=1):
            ratio = frame / PROGRESS_ANIMATION_STEPS
            eased = 1 - pow(1 - ratio, 3)
            self.rank_progress = start + (progress - start) * eased
            self.rank_meter.set(self.rank_progress)
            if frame < PROGRESS_ANIMATION_STEPS:
                self.rank_animation_after = self.after(PROGRESS_ANIMATION_MS, lambda: step(frame + 1))
            else:
                self.rank_progress = progress
                self.rank_meter.set(progress)
                self.rank_animation_after = None

        step()

    def load_today_apps(self):
        apps = sorted(self.engine.get_app_totals(days=1).items(), key=lambda item: item[1]["time"], reverse=True)
        max_time = apps[0][1]["time"] if apps else 1

        specs = []
        for index, (app, data) in enumerate(apps[:12], start=1):
            accent = CATEGORY_COLORS.get(data["category"], COLORS["cyan"])
            specs.append(
                {
                    "key": app,
                    "name": app_name(app),
                    "value": format_duration(data["time"]),
                    "progress": data["time"] / max_time,
                    "accent": accent,
                    "prefix": f"#{index} {data['emoji']} ",
                    "suffix": f" · {data['opens']}x",
                }
            )

        sync_progress_rows(
            self.today_list,
            self.today_rows,
            specs,
            self.today_empty,
            "Start using apps and the board lights up.",
        )

    def load_categories(self):
        categories = sorted(self.engine.get_category_totals(days=1).items(), key=lambda item: item[1]["time"], reverse=True)
        total = sum(row["time"] for _, row in categories) or 1

        specs = []
        for category, row in categories[:8]:
            accent = CATEGORY_COLORS.get(category, COLORS["muted"])
            specs.append(
                {
                    "key": category,
                    "name": category,
                    "value": format_duration(row["time"]),
                    "progress": row["time"] / total,
                    "accent": accent,
                }
            )

        sync_progress_rows(
            self.category_list,
            self.category_rows,
            specs,
            self.category_empty,
            "No categories yet today.",
        )


class VisualizeView(ctk.CTkFrame):
    def __init__(self, master, engine):
        super().__init__(master, fg_color="transparent")
        self.engine = engine
        self.last_render_at = 0
        self.insight_cards = {}

        ctk.CTkLabel(self, text="Visualize", font=ctk.CTkFont(size=30, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(self, text="Last 30 days, plotted like a mini focus skyline.", text_color=COLORS["muted"]).pack(anchor="w", pady=(2, 16))

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="both", expand=True)
        top.grid_columnconfigure(0, weight=3)
        top.grid_columnconfigure(1, weight=2)
        top.grid_rowconfigure(0, weight=1)

        self.trend_chart = TrendChart(top)
        self.trend_chart.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.donut_chart = DonutChart(top)
        self.donut_chart.grid(row=0, column=1, sticky="nsew")

        self.insights = ctk.CTkFrame(self, fg_color="transparent")
        self.insights.pack(fill="x", pady=(16, 0))
        for column in range(4):
            self.insights.grid_columnconfigure(column, weight=1)

        for column, (key, label, accent) in enumerate(
            [
                ("best_day", "Best day", COLORS["pink"]),
                ("daily_avg", "Daily avg", COLORS["cyan"]),
                ("focus_ratio", "Focus ratio", COLORS["green"]),
                ("total_aura", "Total aura", COLORS["yellow"]),
            ]
        ):
            card = StatCard(self.insights, label, accent=accent)
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
            self.insight_cards[key] = card

    def update_view(self, force=False):
        now = time.time()
        if not force and now - self.last_render_at < VISUAL_REFRESH_SECONDS:
            return
        self.last_render_at = now

        self.trend_chart.set_data(self.engine.get_daily_totals(RETENTION_DAYS), force=force)
        self.donut_chart.set_data(self.engine.get_category_totals(RETENTION_DAYS), force=force)
        self.load_insights()

    def load_insights(self):
        summary = self.engine.get_summary(RETENTION_DAYS)
        best_day, best_seconds = self.engine.get_best_day(RETENTION_DAYS)
        daily = self.engine.get_daily_totals(RETENTION_DAYS)
        avg_seconds = sum(seconds for _, seconds in daily) / max(1, len(daily))

        self.insight_cards["best_day"].set(short_date(best_day) if best_day else "--", format_duration(best_seconds), COLORS["pink"])
        self.insight_cards["daily_avg"].set(format_duration(avg_seconds), "30-day mean", COLORS["cyan"])
        self.insight_cards["focus_ratio"].set(f"{round(summary['focus_ratio'] * 100)}%", "productive share", COLORS["green"])
        self.insight_cards["total_aura"].set(str(summary["vibe_score"]), summary["tier"], COLORS["yellow"])


class RankingsView(ctk.CTkFrame):
    def __init__(self, master, engine):
        super().__init__(master, fg_color="transparent")
        self.engine = engine
        self.days = RETENTION_DAYS
        self.last_render_at = 0
        self.badge_cards = {}
        self.board_rows = {}

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(header, text="Rankings", font=ctk.CTkFont(size=30, weight="bold")).pack(side="left")

        self.range_picker = ctk.CTkSegmentedButton(
            header,
            values=["Today", "7 Days", "30 Days"],
            command=self.change_range,
            selected_color=COLORS["pink"],
            selected_hover_color=COLORS["purple"],
            unselected_color=COLORS["surface"],
            unselected_hover_color=COLORS["surface_2"],
        )
        self.range_picker.pack(side="right")

        self.badges = ctk.CTkFrame(self, fg_color="transparent")
        self.badges.pack(fill="x", pady=(0, 14))
        for column in range(4):
            self.badges.grid_columnconfigure(column, weight=1)

        for column, (key, label, accent) in enumerate(
            [
                ("rank", "Rank", COLORS["yellow"]),
                ("tracked", "Tracked", COLORS["cyan"]),
                ("top_lane", "Top lane", COLORS["pink"]),
                ("focus_ratio", "Focus ratio", COLORS["green"]),
            ]
        ):
            card = StatCard(self.badges, label, accent=accent)
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
            self.badge_cards[key] = card

        ctk.CTkLabel(self, text="App Leaderboard", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", pady=(0, 8))
        self.board = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.board.pack(fill="both", expand=True)
        self.board_empty = ctk.CTkLabel(self.board, text="", text_color=COLORS["muted"])
        self.range_picker.set("30 Days")

    def change_range(self, value):
        self.days = {"Today": 1, "7 Days": 7, "30 Days": RETENTION_DAYS}[value]
        self.update_view(force=True)

    def update_view(self, force=False):
        now = time.time()
        if not force and now - self.last_render_at < RANKINGS_REFRESH_SECONDS:
            return
        self.last_render_at = now
        self.load_badges()
        self.load_board()

    def load_badges(self):
        summary = self.engine.get_summary(self.days)
        categories = self.engine.get_category_totals(self.days)
        top_category = max(categories.items(), key=lambda item: item[1]["time"]) if categories else ("--", {"time": 0})

        self.badge_cards["rank"].set(summary["tier"], f"{round(summary['tier_progress'] * 100)}% to next", COLORS["yellow"])
        self.badge_cards["tracked"].set(format_duration(summary["total"]), f"{summary['opens']} app opens", COLORS["cyan"])
        self.badge_cards["top_lane"].set(top_category[0], format_duration(top_category[1]["time"]), CATEGORY_COLORS.get(top_category[0], COLORS["pink"]))
        self.badge_cards["focus_ratio"].set(f"{round(summary['focus_ratio'] * 100)}%", f"{summary['vibe_score']} aura", COLORS["green"])

    def load_board(self):
        apps = sorted(self.engine.get_app_totals(self.days).items(), key=lambda item: item[1]["time"], reverse=True)
        max_time = apps[0][1]["time"] if apps else 1

        specs = []
        for index, (app, data) in enumerate(apps[:20], start=1):
            accent = CATEGORY_COLORS.get(data["category"], COLORS["cyan"])
            score = round(data["score"])
            suffix = f" · {data['category']} · {data['opens']}x · {score:+} aura"
            specs.append(
                {
                    "key": app,
                    "name": app_name(app),
                    "value": format_duration(data["time"]),
                    "progress": data["time"] / max_time,
                    "accent": accent,
                    "prefix": f"#{index} {data['emoji']} ",
                    "suffix": suffix,
                }
            )

        sync_progress_rows(
            self.board,
            self.board_rows,
            specs,
            self.board_empty,
            "No ranking data in this range yet.",
        )


class SkillTreeView(ctk.CTkFrame):
    def __init__(self, master, engine):
        super().__init__(master, fg_color="transparent")
        self.engine = engine
        self.last_render_at = 0
        self.skill_rows = {}

        ctk.CTkLabel(self, text="RPG Skill Tree", font=ctk.CTkFont(size=30, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(self, text="Skills level from your last 30 days of app energy.", text_color=COLORS["muted"]).pack(anchor="w", pady=(2, 16))

        self.skills_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.skills_container.pack(fill="both", expand=True)
        self.skills_empty = ctk.CTkLabel(self.skills_container, text="", text_color=COLORS["muted"])

    def update_view(self, force=False):
        now = time.time()
        if not force and now - self.last_render_at < SKILLS_REFRESH_SECONDS:
            return
        self.last_render_at = now

        skills = self.engine.get_total_skills(RETENTION_DAYS)
        top_seconds = max(skills.values()) if skills else 1

        specs = []
        for skill, seconds in sorted(skills.items(), key=lambda item: item[1], reverse=True):
            level = int(seconds // 3600)
            progress_to_next = (seconds % 3600) / 3600
            accent = SKILL_COLORS.get(skill, COLORS["cyan"])
            specs.append(
                {
                    "key": skill,
                    "name": f"Lv. {level} {skill}",
                    "value": f"{round(progress_to_next * 100)}%",
                    "progress": max(progress_to_next, seconds / max(1, top_seconds) * 0.15),
                    "accent": accent,
                    "suffix": " to next",
                }
            )

        sync_progress_rows(
            self.skills_container,
            self.skill_rows,
            specs,
            self.skills_empty,
            "No skill data yet.",
        )


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, engine):
        super().__init__(master, fg_color="transparent")
        self.engine = engine
        self.last_render_at = 0
        self.status_cards = {}

        ctk.CTkLabel(self, text="Options & Data", font=ctk.CTkFont(size=30, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(self, text="30-day memory, local JSON, no cloud drama.", text_color=COLORS["muted"]).pack(anchor="w", pady=(2, 18))

        self.status = ctk.CTkFrame(self, fg_color="transparent")
        self.status.pack(fill="x", pady=(0, 18))
        for column in range(3):
            self.status.grid_columnconfigure(column, weight=1)

        for column, (key, label, accent) in enumerate(
            [
                ("tracked_days", "Tracked days", COLORS["cyan"]),
                ("storage", "Storage", COLORS["green"]),
                ("total_time", "Total time", COLORS["pink"]),
            ]
        ):
            card = StatCard(self.status, label, accent=accent)
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
            self.status_cards[key] = card

        data_card = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=8)
        data_card.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(data_card, text="Data Retention", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(data_card, text=f"Only the latest {RETENTION_DAYS} calendar days are kept in {DATA_FILE.name}.", text_color=COLORS["muted"]).pack(anchor="w", padx=16, pady=(0, 12))
        ctk.CTkLabel(data_card, text=str(DATA_FILE), text_color=COLORS["cyan"], wraplength=760, justify="left").pack(anchor="w", padx=16, pady=(0, 14))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x")
        ctk.CTkButton(actions, text="💾 Save Now", fg_color=COLORS["green"], text_color="#05070D", hover_color="#24D96B", command=self.save_now).pack(side="left", padx=(0, 8))
        ctk.CTkButton(actions, text="🧹 Clean 30-Day Window", fg_color=COLORS["blue"], hover_color="#357ED8", command=self.clean_now).pack(side="left", padx=(0, 8))
        ctk.CTkButton(actions, text="Reset All Data", fg_color=COLORS["red"], hover_color="#B8334C", command=self.reset_all).pack(side="left")

    def update_view(self, force=False):
        now = time.time()
        if not force and now - self.last_render_at < SETTINGS_REFRESH_SECONDS:
            return
        self.last_render_at = now

        summary = self.engine.get_summary(RETENTION_DAYS)
        tracked_days = sum(1 for _, seconds in self.engine.get_daily_totals(RETENTION_DAYS) if seconds > 0)
        self.status_cards["tracked_days"].set(str(tracked_days), f"of {RETENTION_DAYS}", COLORS["cyan"])
        self.status_cards["storage"].set(DATA_FILE.name, "local file", COLORS["green"])
        self.status_cards["total_time"].set(format_duration(summary["total"]), f"{summary['vibe_score']} aura", COLORS["pink"])

    def save_now(self):
        self.engine.save_data()
        messagebox.showinfo("DigitalWebling", "Data saved.")

    def clean_now(self):
        self.engine.prune_old_data()
        self.engine.save_data()
        self.update_view(force=True)
        messagebox.showinfo("DigitalWebling", "Old data cleaned.")

    def reset_all(self):
        if not messagebox.askyesno("Reset DigitalWebling", "Delete all tracked app data?"):
            return
        self.engine.reset_all_data()
        self.engine.save_data()
        self.update_view(force=True)


# =====================================================
# MAIN APPLICATION CONTROLLER
# =====================================================
class MainApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.engine = AuraEngine()
        self.nav_buttons = {}

        self.title("DigitalWebling Ultra Tracker")
        self.geometry("1120x720")
        self.minsize(980, 620)
        self.configure(fg_color=COLORS["bg"])

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.setup_sidebar()

        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=22, pady=22)

        self.views = {
            "Dashboard": DashboardView(self.main_container, self.engine),
            "Visualize": VisualizeView(self.main_container, self.engine),
            "Rankings": RankingsView(self.main_container, self.engine),
            "Skills": SkillTreeView(self.main_container, self.engine),
            "Settings": SettingsView(self.main_container, self.engine),
        }

        self.current_view_name = "Dashboard"
        self.switch_view("Dashboard")
        self.after(TRACK_INTERVAL_MS, self.background_loop)

    def setup_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=COLORS["sidebar"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(8, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.sidebar, text="✨ DigitalWebling", font=ctk.CTkFont(size=21, weight="bold")).grid(row=0, column=0, padx=18, pady=(28, 4), sticky="w")
        ctk.CTkLabel(self.sidebar, text="ultra tracker", text_color=COLORS["muted"]).grid(row=1, column=0, padx=18, pady=(0, 22), sticky="w")

        nav_items = [
            ("Dashboard", "📡 Dashboard"),
            ("Visualize", "📊 Visualize"),
            ("Rankings", "🏆 Rankings"),
            ("Skills", "⚔️ Skill Tree"),
            ("Settings", "⚙️ Options"),
        ]

        for row, (name, text) in enumerate(nav_items, start=2):
            button = ctk.CTkButton(
                self.sidebar,
                text=text,
                fg_color="transparent",
                hover_color=COLORS["surface_2"],
                anchor="w",
                height=40,
                corner_radius=8,
                command=lambda target=name: self.switch_view(target),
            )
            button.grid(row=row, column=0, padx=12, pady=4, sticky="ew")
            self.nav_buttons[name] = button

        footer = ctk.CTkFrame(self.sidebar, fg_color=COLORS["surface"], corner_radius=8)
        footer.grid(row=9, column=0, padx=12, pady=18, sticky="ew")
        ctk.CTkLabel(footer, text="30-day memory", text_color=COLORS["muted"], font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=12, pady=(10, 0))
        ctk.CTkLabel(footer, text="Local. Fast. Vibe-aware.", text_color=COLORS["text"]).pack(anchor="w", padx=12, pady=(2, 10))

    def switch_view(self, name):
        self.current_view_name = name
        for view in self.views.values():
            view.pack_forget()
        self.views[name].pack(fill="both", expand=True)
        self.views[name].update_view(force=True)
        self.update_nav_state()

    def update_nav_state(self):
        for name, button in self.nav_buttons.items():
            if name == self.current_view_name:
                button.configure(fg_color=COLORS["pink"], hover_color=COLORS["purple"])
            else:
                button.configure(fg_color="transparent", hover_color=COLORS["surface_2"])

    def background_loop(self):
        self.engine.tick()
        view = self.views.get(self.current_view_name)
        if view and hasattr(view, "update_view"):
            view.update_view()
        self.engine.autosave()
        self.after(TRACK_INTERVAL_MS, self.background_loop)


if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except (ImportError, AttributeError, OSError):
        pass

    app = MainApp()

    def on_close():
        app.engine.save_data()
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_close)
    app.mainloop()
