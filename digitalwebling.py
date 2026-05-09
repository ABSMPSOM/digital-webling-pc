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
PROGRESS_ANIMATION_STEPS = 10
PROGRESS_ANIMATION_MS = 20

# ── NEW PALETTE: #402E7A → #4C3BCF → #4B70F5 → #3DC2EC ──────────────────────
COLORS = {
    "bg":         "#0D0B1A",
    "sidebar":    "#100D22",
    "surface":    "#13102A",
    "surface_2":  "#1A1635",
    "surface_3":  "#221E42",
    "border":     "#2D2860",
    "text":       "#F0EEFF",
    "muted":      "#8B84B8",
    # palette stops
    "p1":         "#402E7A",
    "p2":         "#4C3BCF",
    "p3":         "#4B70F5",
    "p4":         "#3DC2EC",
    # accents
    "pink":       "#FF6BF5",
    "green":      "#39FFBD",
    "yellow":     "#FFD166",
    "red":        "#FF5E78",
    "orange":     "#FF9F1C",
}

CATEGORY_COLORS = {
    "Coding":   COLORS["p3"],
    "Study":    COLORS["yellow"],
    "Creating": COLORS["pink"],
    "Music":    COLORS["green"],
    "Social":   COLORS["muted"],
    "Browsing": COLORS["p4"],
    "Gaming":   COLORS["red"],
    "System":   COLORS["muted"],
    "App":      COLORS["muted"],
}

SKILL_COLORS = {
    "Intelligence": COLORS["p3"],
    "Focus":        COLORS["p4"],
    "Creativity":   COLORS["pink"],
    "Charisma":     COLORS["yellow"],
    "Exploration":  COLORS["green"],
    "Reflexes":     COLORS["red"],
}

SKILL_EMOJI = {
    "Intelligence": "🧠",
    "Focus":        "🎯",
    "Creativity":   "✨",
    "Charisma":     "💬",
    "Exploration":  "🌐",
    "Reflexes":     "⚡",
}

# (Emoji, Category, Vibe Multiplier, Skill Target)
APP_CATEGORIES = {
    "code":               ("💻", "Coding",   2.0,  "Intelligence"),
    "code - insiders":    ("💻", "Coding",   2.0,  "Intelligence"),
    "cursor":             ("💻", "Coding",   2.0,  "Intelligence"),
    "pycharm":            ("🐍", "Coding",   2.0,  "Intelligence"),
    "webstorm":           ("🌐", "Coding",   2.0,  "Intelligence"),
    "devenv":             ("💻", "Coding",   2.0,  "Intelligence"),
    "powershell":         ("⚡", "Coding",   1.5,  "Intelligence"),
    "windowsterminal":    ("⚡", "Coding",   1.5,  "Intelligence"),
    "cmd":                ("⚡", "Coding",   1.2,  "Intelligence"),
    "python":             ("🐍", "Coding",   2.0,  "Intelligence"),
    "notepad++":          ("📝", "Study",    1.0,  "Focus"),
    "winword":            ("📄", "Study",    1.2,  "Focus"),
    "excel":              ("📊", "Study",    1.2,  "Focus"),
    "powerpnt":           ("📽️", "Study",    1.1,  "Focus"),
    "onenote":            ("📒", "Study",    1.2,  "Focus"),
    "obs":                ("🎥", "Creating", 1.5,  "Creativity"),
    "photoshop":          ("🎨", "Creating", 1.5,  "Creativity"),
    "illustrator":        ("🎨", "Creating", 1.5,  "Creativity"),
    "figma":              ("🎨", "Creating", 1.5,  "Creativity"),
    "spotify":            ("🎧", "Music",    0.8,  "Creativity"),
    "discord":            ("💬", "Social",  -1.9,  "Charisma"),
    "slack":              ("💬", "Social",   0.6,  "Charisma"),
    "teams":              ("💬", "Social",   0.6,  "Charisma"),
    "zoom":               ("🎙️", "Social",   0.6,  "Charisma"),
    "chrome":             ("🌐", "Browsing", 0.1,  "Exploration"),
    "brave":              ("🦁", "Browsing", 0.1,  "Exploration"),
    "firefox":            ("🦊", "Browsing", 0.1,  "Exploration"),
    "msedge":             ("🌐", "Browsing", 0.1,  "Exploration"),
    "valorant":           ("🎮", "Gaming",  -22.0, "Reflexes"),
    "steam":              ("🎮", "Gaming",  -0.8,  "Reflexes"),
    "epicgameslauncher":  ("🎮", "Gaming",  -0.8,  "Reflexes"),
    "minecraftlauncher":  ("⛏️", "Gaming",  -0.8,  "Reflexes"),
    "system idle":        ("💤", "System",   0,    "Focus"),
}

APP_DISPLAY_NAMES = {
    "code":            "VS Code",
    "code - insiders": "VS Code Insiders",
    "cmd":             "Command Prompt",
    "msedge":          "Microsoft Edge",
    "winword":         "Microsoft Word",
    "powerpnt":        "PowerPoint",
    "windowsterminal": "Terminal",
}

RANK_TIERS = [
    ("Starter",  0),
    ("Bronze",   1),
    ("Silver",   5),
    ("Gold",     15),
    ("Diamond",  30),
    ("Mythic",   60),
]

RANK_EMOJI = {
    "Starter":  "🌱",
    "Bronze":   "🥉",
    "Silver":   "🥈",
    "Gold":     "🥇",
    "Diamond":  "💎",
    "Mythic":   "👑",
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
    hours   = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs    = seconds % 60
    if live and hours == 0:
        return f"{minutes}m {secs:02d}s"
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


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def blend_hex(c1, c2, t=0.5):
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


# =====================================================
# DATA & GAMIFICATION ENGINE
# =====================================================
class AuraEngine:
    def __init__(self):
        self.lock = threading.RLock()
        self.db   = self.load_and_clean_data()
        self.today = self.date_key()
        self.db.setdefault(self.today, {})
        self.current_app    = None
        self.start_time     = time.time()
        self.app_started_at = self.start_time
        self.last_save_at   = 0
        self.pid_cache      = {}

    def date_key(self, when=None):
        return (when or datetime.now()).strftime("%Y-%m-%d")

    def recent_days(self, days=RETENTION_DAYS):
        today = datetime.now().date()
        return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]

    def normalize_app_data(self, apps):
        out = {}
        if not isinstance(apps, dict):
            return out
        for app, raw in apps.items():
            if not isinstance(app, str) or not isinstance(raw, dict):
                continue
            try:
                s = float(raw.get("time", 0) or 0)
                o = int(raw.get("opens", 0) or 0)
            except (TypeError, ValueError):
                continue
            out[app] = {"time": max(0.0, s), "opens": max(0, o)}
        return out

    def load_and_clean_data(self):
        db = {}
        if DATA_FILE.exists():
            try:
                with DATA_FILE.open("r", encoding="utf-8") as f:
                    db = json.load(f)
            except (json.JSONDecodeError, OSError):
                db = {}
        cutoff = datetime.now().date() - timedelta(days=RETENTION_DAYS - 1)
        cleaned = {}
        for ds, apps in db.items():
            try:
                if datetime.strptime(ds, "%Y-%m-%d").date() >= cutoff:
                    cleaned[ds] = self.normalize_app_data(apps)
            except ValueError:
                continue
        return cleaned

    def save_data(self):
        with self.lock:
            snapshot = json.loads(json.dumps(self.db))
        tmp = DATA_FILE.with_name(f"{DATA_FILE.name}.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=4)
        os.replace(tmp, DATA_FILE)

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
        cur = self.date_key(datetime.fromtimestamp(now))
        if cur == self.today:
            return
        if self.current_app and self.current_app != "system idle":
            self.add_time(self.today, self.current_app, now - self.start_time)
        self.today = cur
        self.db.setdefault(self.today, {})
        self.start_time     = now
        self.app_started_at = now

    def touch_app(self, day, app, opened=False):
        if not app or app == "system idle":
            return
        self.db.setdefault(day, {}).setdefault(app, {"time": 0.0, "opens": 0})
        if opened:
            self.db[day][app]["opens"] += 1

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
                self.current_app    = new_app
                self.app_started_at = now
                self.touch_app(self.today, new_app, opened=True)
            else:
                self.add_time(self.today, self.current_app, elapsed)
                if new_app != self.current_app:
                    self.current_app    = new_app
                    self.app_started_at = now
                    self.touch_app(self.today, new_app, opened=True)
            self.start_time = now
            return self.get_day_stats(self.today)

    def get_day_stats(self, day):
        with self.lock:
            return {a: {"time": d.get("time", 0), "opens": d.get("opens", 0)}
                    for a, d in self.db.get(day, {}).items()}

    def get_app_totals(self, days=RETENTION_DAYS):
        totals = {}
        with self.lock:
            for day in self.recent_days(days):
                for app, data in self.db.get(day, {}).items():
                    emoji, cat, vibe, skill = app_meta(app)
                    if app not in totals:
                        totals[app] = {"time": 0.0, "opens": 0,
                                       "emoji": emoji, "category": cat,
                                       "vibe": vibe, "skill": skill, "score": 0.0}
                    totals[app]["time"]  += data.get("time", 0)
                    totals[app]["opens"] += data.get("opens", 0)
                    totals[app]["score"] += (data.get("time", 0) / 60) * vibe
        return totals

    def get_category_totals(self, days=RETENTION_DAYS):
        cats = {}
        for data in self.get_app_totals(days).values():
            c = data["category"]
            cats.setdefault(c, {"time": 0.0, "score": 0.0, "opens": 0})
            cats[c]["time"]  += data["time"]
            cats[c]["score"] += data["score"]
            cats[c]["opens"] += data["opens"]
        return cats

    def get_daily_totals(self, days=RETENTION_DAYS):
        with self.lock:
            return [(day, sum(d.get("time", 0) for d in self.db.get(day, {}).values()))
                    for day in self.recent_days(days)]

    def get_total_skills(self, days=RETENTION_DAYS):
        skills = {s: 0.0 for s in SKILL_COLORS}
        with self.lock:
            for day in self.recent_days(days):
                for app, data in self.db.get(day, {}).items():
                    _, _, vibe, skill = app_meta(app)
                    mult = max(0.25, vibe) if vibe > 0 else 0.25
                    skills.setdefault(skill, 0.0)
                    skills[skill] += data.get("time", 0) * mult
        return skills

    def get_streak(self, min_seconds=600):
        streak = 0
        with self.lock:
            for day in reversed(self.recent_days(RETENTION_DAYS)):
                total = sum(d.get("time", 0) for d in self.db.get(day, {}).values())
                if total >= min_seconds:
                    streak += 1
                else:
                    break
        return streak

    def get_best_day(self, days=RETENTION_DAYS):
        daily = self.get_daily_totals(days)
        return max(daily, key=lambda x: x[1]) if daily else (None, 0)

    def get_rank_tier(self, productive_seconds):
        ph = productive_seconds / 3600
        current = RANK_TIERS[0]
        next_t  = RANK_TIERS[1]
        for i, tier in enumerate(RANK_TIERS):
            if ph >= tier[1]:
                current = tier
                next_t  = RANK_TIERS[min(i + 1, len(RANK_TIERS) - 1)]
        if current == next_t:
            return current[0], 1.0, "maxed"
        span     = max(1, next_t[1] - current[1])
        progress = clamp((ph - current[1]) / span)
        return current[0], progress, f"{next_t[0]} at {next_t[1]}h"

    def get_summary(self, days=RETENTION_DAYS):
        apps       = self.get_app_totals(days)
        total      = sum(d["time"] for d in apps.values())
        opens      = sum(d["opens"] for d in apps.values())
        productive = sum(d["time"] for d in apps.values() if d["vibe"] > 0)
        vibe_score = round(sum(d["score"] for d in apps.values()))
        top_app    = max(apps.items(), key=lambda x: x[1]["time"]) if apps else None
        tier, tier_progress, next_label = self.get_rank_tier(productive)
        return {
            "total": total, "opens": opens, "productive": productive,
            "vibe_score": vibe_score, "focus_ratio": (productive / total) if total else 0,
            "top_app": top_app, "tier": tier, "tier_progress": tier_progress,
            "next_label": next_label, "streak": self.get_streak(),
        }

    def prune_old_data(self):
        with self.lock:
            cleaned = self.load_and_clean_data()
            cleaned.setdefault(self.today, {})
            self.db = cleaned

    def reset_all_data(self):
        with self.lock:
            self.db          = {self.today: {}}
            self.current_app = None
            self.start_time  = time.time()
            self.app_started_at = self.start_time


# =====================================================
# REUSABLE UI COMPONENTS
# =====================================================
class StatCard(ctk.CTkFrame):
    """Compact stat card with top accent stripe via a coloured inner frame."""

    def __init__(self, master, label, value="--", subvalue="", accent=COLORS["p3"]):
        super().__init__(master, fg_color=COLORS["surface"],
                         corner_radius=12, border_width=1,
                         border_color=COLORS["border"])
        self.accent          = accent
        self._value          = value
        self._subvalue       = subvalue
        self.grid_columnconfigure(0, weight=1)

        # Accent stripe
        stripe = ctk.CTkFrame(self, fg_color=accent, corner_radius=0, height=3)
        stripe.grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(self, text=label.upper(),
                     text_color=COLORS["muted"],
                     font=ctk.CTkFont(size=10, weight="bold")).grid(
            row=1, column=0, sticky="w", padx=14, pady=(10, 0))

        self._val_lbl = ctk.CTkLabel(self, text=value, text_color=COLORS["text"],
                                     font=ctk.CTkFont(size=22, weight="bold"))
        self._val_lbl.grid(row=2, column=0, sticky="w", padx=14, pady=(2, 0))

        self._sub_lbl = ctk.CTkLabel(self, text=subvalue, text_color=accent,
                                     font=ctk.CTkFont(size=11, weight="bold"))
        self._sub_lbl.grid(row=3, column=0, sticky="w", padx=14, pady=(0, 12))

    def set(self, value, subvalue="", accent=None):
        if accent:
            self.accent = accent
        if value != self._value:
            self._val_lbl.configure(text=value)
            self._value = value
        if subvalue != self._subvalue:
            self._sub_lbl.configure(text=subvalue)
            self._subvalue = subvalue
        self._sub_lbl.configure(text_color=self.accent)


class GlowProgressBar(ctk.CTkFrame):
    """App / skill row with animated neon progress bar."""

    def __init__(self, master, name="", value="", progress=0.0,
                 accent=COLORS["p3"], prefix="", suffix=""):
        super().__init__(master, fg_color=COLORS["surface"],
                         corner_radius=10, border_width=1,
                         border_color=COLORS["border"])
        self.grid_columnconfigure(0, weight=1)
        self._progress     = clamp(progress)
        self._target       = self._progress
        self._start        = self._progress
        self._step         = 0
        self._after_id     = None
        self._cur_name     = ""
        self._cur_value    = ""
        self.accent        = accent

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 3))
        top.grid_columnconfigure(0, weight=1)

        self._name_lbl = ctk.CTkLabel(top, text="", text_color=COLORS["text"],
                                      font=ctk.CTkFont(size=13, weight="bold"))
        self._name_lbl.grid(row=0, column=0, sticky="w")

        self._val_lbl = ctk.CTkLabel(top, text="", text_color=accent,
                                     font=ctk.CTkFont(size=12, weight="bold"))
        self._val_lbl.grid(row=0, column=1, sticky="e")

        self._bar = ctk.CTkProgressBar(self, height=6,
                                       fg_color=COLORS["surface_3"],
                                       progress_color=accent,
                                       corner_radius=3)
        self._bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))
        self._bar.set(self._progress)
        self.update_row(name, value, progress, accent, prefix, suffix, animate=False)

    def update_row(self, name, value, progress, accent,
                   prefix="", suffix="", animate=True):
        n = f"{prefix}{name}"
        v = f"{value}{suffix}"
        if n != self._cur_name:
            self._name_lbl.configure(text=n)
            self._cur_name = n
        if v != self._cur_value:
            self._val_lbl.configure(text=v)
            self._cur_value = v
        if accent != self.accent:
            self.accent = accent
            self._val_lbl.configure(text_color=accent)
            self._bar.configure(progress_color=accent)
        self._set_progress(progress, animate)

    def _set_progress(self, progress, animate=True):
        progress = clamp(progress)
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except (ValueError, tk.TclError):
                pass
            self._after_id = None
        if not animate or abs(progress - self._progress) < 0.01:
            self._progress = progress
            self._target   = progress
            self._bar.set(progress)
            return
        self._target = progress
        self._start  = self._progress
        self._step   = 0
        self._animate()

    def _animate(self):
        self._step += 1
        t     = self._step / PROGRESS_ANIMATION_STEPS
        eased = 1 - (1 - t) ** 3
        val   = self._start + (self._target - self._start) * eased
        self._progress = clamp(val)
        self._bar.set(self._progress)
        if self._step < PROGRESS_ANIMATION_STEPS:
            self._after_id = self.after(PROGRESS_ANIMATION_MS, self._animate)
        else:
            self._progress = self._target
            self._bar.set(self._target)
            self._after_id = None


def sync_rows(parent, cache, specs, empty_lbl, empty_text):
    """Efficiently sync a list of GlowProgressBar rows."""
    if not specs:
        for row in cache.values():
            row.pack_forget()
        parent.synced_order = []
        empty_lbl.configure(text=empty_text)
        if not empty_lbl.winfo_ismapped():
            empty_lbl.pack(anchor="w", pady=12)
        return

    empty_lbl.pack_forget()
    desired = [s["key"] for s in specs]
    active  = set(desired)
    order_changed = desired != getattr(parent, "synced_order", [])
    if order_changed:
        for row in cache.values():
            row.pack_forget()

    for spec in specs:
        key  = spec["key"]
        args = {k: v for k, v in spec.items() if k != "key"}
        if key not in cache:
            cache[key] = GlowProgressBar(parent, **args)
            animate = False
        else:
            cache[key].update_row(**args, animate=True)
            animate = True
        if order_changed or not cache[key].winfo_ismapped():
            cache[key].pack(fill="x", pady=4)

    for key, row in cache.items():
        if key not in active:
            row.pack_forget()

    parent.synced_order = desired


# =====================================================
# TREND BAR CHART  (canvas-drawn)
# =====================================================
class TrendChart(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["surface"],
                         corner_radius=12, border_width=1,
                         border_color=COLORS["border"])
        self._sig  = None
        self._data = []
        self._canvas = tk.Canvas(self, bg=COLORS["surface"],
                                 highlightthickness=0, height=200)
        self._canvas.pack(fill="both", expand=True, padx=14, pady=12)
        self._canvas.bind("<Configure>", lambda _: self._draw_chart())

    def set_data(self, data, force=False):
        sig = tuple((d, int(s // 10)) for d, s in data)
        if not force and sig == self._sig:
            return
        self._sig  = sig
        self._data = data
        self._draw_chart()

    def _draw_chart(self):
        c = self._canvas
        c.delete("all")
        W = max(1, c.winfo_width())
        H = max(1, c.winfo_height())
        if not self._data:
            c.create_text(W / 2, H / 2, text="No tracked data yet",
                          fill=COLORS["muted"], font=("Segoe UI", 11, "bold"))
            return

        px, py  = 38, 28
        cw      = max(1, W - px * 2)
        ch      = max(1, H - py * 2)
        gap     = 3
        n       = len(self._data)
        bar_w   = max(3, (cw - gap * (n - 1)) / n)
        max_val = max(s for _, s in self._data) or 1

        # grid lines
        for i in range(1, 5):
            y = H - py - (ch * i / 4)
            c.create_line(px, y, W - px, y, fill=COLORS["surface_3"], dash=(4, 4))

        # gradient-ish palette cycling through p1→p4
        palette = [COLORS["p1"], COLORS["p2"], COLORS["p3"], COLORS["p4"],
                   COLORS["pink"], COLORS["green"]]
        for i, (dk, secs) in enumerate(self._data):
            x1    = px + i * (bar_w + gap)
            bh    = (secs / max_val) * ch
            y1    = H - py - bh
            x2    = x1 + bar_w
            y2    = H - py
            color = palette[i % len(palette)]
            c.create_rectangle(x1, y1, x2, y2, fill=color, outline="")
            if i in (0, n - 1) or n <= 10:
                c.create_text((x1 + x2) / 2, H - 10,
                              text=short_date(dk),
                              fill=COLORS["muted"],
                              font=("Segoe UI", 8, "bold"))

        peak_d, peak_s = max(self._data, key=lambda x: x[1])
        c.create_text(px, 12,
                      text=f"30-day activity  ·  peak {short_date(peak_d)} / {format_duration(peak_s)}",
                      fill=COLORS["text"], anchor="w",
                      font=("Segoe UI", 11, "bold"))


# =====================================================
# CATEGORY DONUT CHART
# =====================================================
class DonutChart(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["surface"],
                         corner_radius=12, border_width=1,
                         border_color=COLORS["border"])
        self._sig    = None
        self._data   = {}
        self._canvas = tk.Canvas(self, bg=COLORS["surface"],
                                 highlightthickness=0, height=240)
        self._canvas.pack(fill="both", expand=True, padx=12, pady=12)
        self._canvas.bind("<Configure>", lambda _: self._draw_chart())

    def set_data(self, data, force=False):
        sig = tuple(sorted((n, int(d["time"] // 10)) for n, d in data.items()))
        if not force and sig == self._sig:
            return
        self._sig  = sig
        self._data = data
        self._draw_chart()

    def _draw_chart(self):
        c = self._canvas
        c.delete("all")
        W = max(1, c.winfo_width())
        H = max(1, c.winfo_height())
        totals = {n: d["time"] for n, d in self._data.items() if d["time"] > 0}
        total  = sum(totals.values())
        if not totals:
            c.create_text(W / 2, H / 2, text="Category mix loading",
                          fill=COLORS["muted"], font=("Segoe UI", 11, "bold"))
            return

        size = min(W, H) - 60
        cx   = 24 + size / 2
        cy   = 34 + size / 2
        x1, y1, x2, y2 = 24, 34, 24 + size, 34 + size
        start = 90

        for cat, secs in sorted(totals.items(), key=lambda x: x[1], reverse=True):
            extent = (secs / total) * 359.9
            color  = CATEGORY_COLORS.get(cat, COLORS["muted"])
            c.create_arc(x1, y1, x2, y2, start=start, extent=-extent,
                         style="arc", outline=color, width=20)
            start -= extent

        c.create_text(cx, cy - 10, text=format_duration(total),
                      fill=COLORS["text"], font=("Segoe UI", 16, "bold"))
        c.create_text(cx, cy + 12, text="tracked",
                      fill=COLORS["muted"], font=("Segoe UI", 10, "bold"))

        lx, ly = x2 + 22, 38
        for cat, secs in sorted(totals.items(), key=lambda x: x[1], reverse=True)[:7]:
            color = CATEGORY_COLORS.get(cat, COLORS["muted"])
            c.create_oval(lx, ly + 2, lx + 10, ly + 12, fill=color, outline="")
            c.create_text(lx + 18, ly + 7,
                          text=f"{cat}  {format_duration(secs)}",
                          fill=COLORS["text"], anchor="w",
                          font=("Segoe UI", 10, "bold"))
            ly += 24


# =====================================================
# AURA HERO BANNER  (canvas gradient-style)
# =====================================================
class AuraBanner(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["p1"],
                         corner_radius=16, border_width=1,
                         border_color=COLORS["p2"])
        self.grid_columnconfigure((0, 1, 2), weight=1)

        # Left: big aura number
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=20, pady=18)
        ctk.CTkLabel(left, text="TOTAL AURA",
                     text_color=COLORS["p4"],
                     font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w")
        self._aura_lbl = ctk.CTkLabel(left, text="0",
                                      text_color=COLORS["text"],
                                      font=ctk.CTkFont(size=44, weight="bold"))
        self._aura_lbl.pack(anchor="w")
        self._tier_lbl = ctk.CTkLabel(left, text="Starter",
                                      text_color=COLORS["p4"],
                                      font=ctk.CTkFont(size=14, weight="bold"))
        self._tier_lbl.pack(anchor="w")

        # Middle: rank bar
        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.grid(row=0, column=1, sticky="nsew", padx=10, pady=18)
        ctk.CTkLabel(mid, text="RANK PROGRESS",
                     text_color=COLORS["muted"],
                     font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w")
        self._rank_bar = ctk.CTkProgressBar(mid, height=10,
                                            fg_color=COLORS["surface_3"],
                                            progress_color=COLORS["p4"],
                                            corner_radius=5)
        self._rank_bar.pack(fill="x", pady=(8, 4))
        self._rank_bar.set(0)
        self._next_lbl = ctk.CTkLabel(mid, text="",
                                      text_color=COLORS["p4"],
                                      font=ctk.CTkFont(size=11, weight="bold"))
        self._next_lbl.pack(anchor="w")

        # Right: streak
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=2, sticky="nsew", padx=20, pady=18)
        ctk.CTkLabel(right, text="STREAK",
                     text_color=COLORS["muted"],
                     font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w")
        self._streak_lbl = ctk.CTkLabel(right, text="0 days 🔥",
                                        text_color=COLORS["yellow"],
                                        font=ctk.CTkFont(size=22, weight="bold"))
        self._streak_lbl.pack(anchor="w")
        self._streak_sub = ctk.CTkLabel(right, text="10m+ tracked daily",
                                        text_color=COLORS["muted"],
                                        font=ctk.CTkFont(size=11))
        self._streak_sub.pack(anchor="w")

        self._rank_progress = 0.0
        self._rank_after    = None

    def update(self, summary):
        emoji = RANK_EMOJI.get(summary["tier"], "🌱")
        self._aura_lbl.configure(text=str(summary["vibe_score"]))
        self._tier_lbl.configure(text=f"{emoji} {summary['tier']}")
        self._next_lbl.configure(text=f"Next: {summary['next_label']}")
        self._streak_lbl.configure(text=f"{summary['streak']} days 🔥")
        self._animate_rank(summary["tier_progress"])

    def _animate_rank(self, target):
        target = clamp(target)
        if self._rank_after:
            try:
                self.after_cancel(self._rank_after)
            except (ValueError, tk.TclError):
                pass
            self._rank_after = None
        if abs(target - self._rank_progress) < 0.01:
            self._rank_progress = target
            self._rank_bar.set(target)
            return
        start = self._rank_progress

        def step(fr=1):
            t     = fr / PROGRESS_ANIMATION_STEPS
            eased = 1 - (1 - t) ** 3
            self._rank_progress = start + (target - start) * eased
            self._rank_bar.set(self._rank_progress)
            if fr < PROGRESS_ANIMATION_STEPS:
                self._rank_after = self.after(PROGRESS_ANIMATION_MS, lambda: step(fr + 1))
            else:
                self._rank_progress = target
                self._rank_bar.set(target)
                self._rank_after = None
        step()


# =====================================================
# VIEWS
# =====================================================
class DashboardView(ctk.CTkFrame):
    def __init__(self, master, engine):
        super().__init__(master, fg_color="transparent")
        self.engine       = engine
        self.cards        = {}
        self.today_rows   = {}
        self.cat_rows     = {}

        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(hdr, text="DigitalWebling Ultra",
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color=COLORS["text"]).pack(anchor="w")
        ctk.CTkLabel(hdr, text="Live aura · focus streaks · 30-day glow-up ✨",
                     text_color=COLORS["muted"]).pack(anchor="w", pady=(2, 0))

        # Aura banner
        self.banner = AuraBanner(self)
        self.banner.pack(fill="x", pady=(0, 14))

        # Stat cards
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", pady=(0, 14))
        for i in range(4):
            cards_frame.grid_columnconfigure(i, weight=1)

        card_defs = [
            ("active",  "Active Now",  COLORS["p4"]),
            ("session", "Session",     COLORS["pink"]),
            ("today",   "Today",       COLORS["green"]),
            ("focus",   "Focus Ratio", COLORS["yellow"]),
        ]
        for i, (key, label, accent) in enumerate(card_defs):
            self.cards[key] = StatCard(cards_frame, label, accent=accent)
            self.cards[key].grid(row=0, column=i, sticky="nsew",
                                 padx=(0 if i == 0 else 8, 0))

        # Body
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        left  = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")

        # Today leaderboard
        ctk.CTkLabel(left, text="Today Leaderboard",
                     font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", pady=(0, 8))
        self.today_list = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.today_list.pack(fill="both", expand=True)
        self.today_empty = ctk.CTkLabel(self.today_list, text="",
                                        text_color=COLORS["muted"])

        # Category pulse
        ctk.CTkLabel(right, text="Category Pulse",
                     font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", pady=(0, 8))
        self.cat_list  = ctk.CTkFrame(right, fg_color="transparent")
        self.cat_list.pack(fill="x")
        self.cat_empty = ctk.CTkLabel(self.cat_list, text="",
                                      text_color=COLORS["muted"])

    def update_view(self, force=False):
        cur   = self.engine.current_app or "system idle"
        emoji, cat, vibe, _ = app_meta(cur)
        today = self.engine.get_summary(days=1)
        month = self.engine.get_summary(days=RETENTION_DAYS)
        sess  = self.engine.app_started_at and (time.time() - self.engine.app_started_at)

        self.banner.update(month)
        cat_color = CATEGORY_COLORS.get(cat, COLORS["p4"])
        self.cards["active"].set(f"{emoji} {app_name(cur)}", cat, cat_color)
        self.cards["session"].set(format_duration(sess, live=True), "current focus", COLORS["pink"])
        self.cards["today"].set(format_duration(today["total"]),
                                f"{today['opens']} opens", COLORS["green"])
        focus_pct = round(month["focus_ratio"] * 100)
        self.cards["focus"].set(f"{focus_pct}%", f"{month['vibe_score']} aura", COLORS["yellow"])
        self._load_today_apps()
        self._load_categories()

    def _load_today_apps(self):
        apps    = sorted(self.engine.get_app_totals(days=1).items(),
                         key=lambda x: x[1]["time"], reverse=True)
        max_t   = apps[0][1]["time"] if apps else 1
        specs   = []
        for i, (app, data) in enumerate(apps[:12], 1):
            accent = CATEGORY_COLORS.get(data["category"], COLORS["p3"])
            aura   = round((data["time"] / 60) * data["vibe"])
            aura_s = f"{aura:+}" if aura != 0 else "±0"
            specs.append({
                "key":      app,
                "name":     app_name(app),
                "value":    format_duration(data["time"]),
                "progress": data["time"] / max_t,
                "accent":   accent,
                "prefix":   f"#{i} {data['emoji']} ",
                "suffix":   f" · {data['opens']}x · {aura_s} aura",
            })
        sync_rows(self.today_list, self.today_rows, specs,
                  self.today_empty, "Start using apps and the board lights up.")

    def _load_categories(self):
        cats  = sorted(self.engine.get_category_totals(days=1).items(),
                       key=lambda x: x[1]["time"], reverse=True)
        total = sum(r["time"] for _, r in cats) or 1
        specs = []
        for cat, row in cats[:8]:
            accent = CATEGORY_COLORS.get(cat, COLORS["muted"])
            specs.append({
                "key":      cat,
                "name":     cat,
                "value":    format_duration(row["time"]),
                "progress": row["time"] / total,
                "accent":   accent,
            })
        sync_rows(self.cat_list, self.cat_rows, specs,
                  self.cat_empty, "No categories yet today.")


# ── Visualize ──────────────────────────────────────────────────────────────────
class VisualizeView(ctk.CTkFrame):
    def __init__(self, master, engine):
        super().__init__(master, fg_color="transparent")
        self.engine       = engine
        self._last        = 0
        self._insight_cards = {}

        ctk.CTkLabel(self, text="Visualize",
                     font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(self, text="Last 30 days · your focus skyline 📈",
                     text_color=COLORS["muted"]).pack(anchor="w", pady=(2, 14))

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="both", expand=True)
        top.grid_columnconfigure(0, weight=3)
        top.grid_columnconfigure(1, weight=2)
        top.grid_rowconfigure(0, weight=1)

        self.trend = TrendChart(top)
        self.trend.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.donut = DonutChart(top)
        self.donut.grid(row=0, column=1, sticky="nsew")

        ins = ctk.CTkFrame(self, fg_color="transparent")
        ins.pack(fill="x", pady=(14, 0))
        for i in range(4):
            ins.grid_columnconfigure(i, weight=1)

        for i, (key, label, accent) in enumerate([
            ("best_day",    "Best Day",    COLORS["pink"]),
            ("daily_avg",   "Daily Avg",   COLORS["p4"]),
            ("focus_ratio", "Focus Ratio", COLORS["green"]),
            ("total_aura",  "Total Aura",  COLORS["yellow"]),
        ]):
            card = StatCard(ins, label, accent=accent)
            card.grid(row=0, column=i, sticky="nsew",
                      padx=(0 if i == 0 else 8, 0))
            self._insight_cards[key] = card

    def update_view(self, force=False):
        now = time.time()
        if not force and now - self._last < VISUAL_REFRESH_SECONDS:
            return
        self._last = now
        self.trend.set_data(self.engine.get_daily_totals(RETENTION_DAYS), force=force)
        self.donut.set_data(self.engine.get_category_totals(RETENTION_DAYS), force=force)
        self._load_insights()

    def _load_insights(self):
        s         = self.engine.get_summary(RETENTION_DAYS)
        best_d, best_s = self.engine.get_best_day(RETENTION_DAYS)
        daily     = self.engine.get_daily_totals(RETENTION_DAYS)
        avg       = sum(x[1] for x in daily) / max(1, len(daily))
        self._insight_cards["best_day"].set(
            short_date(best_d) if best_d else "--", format_duration(best_s), COLORS["pink"])
        self._insight_cards["daily_avg"].set(
            format_duration(avg), "30-day mean", COLORS["p4"])
        self._insight_cards["focus_ratio"].set(
            f"{round(s['focus_ratio'] * 100)}%", "productive share", COLORS["green"])
        self._insight_cards["total_aura"].set(
            str(s["vibe_score"]), s["tier"], COLORS["yellow"])


# ── Rankings ───────────────────────────────────────────────────────────────────
class RankingsView(ctk.CTkFrame):
    def __init__(self, master, engine):
        super().__init__(master, fg_color="transparent")
        self.engine     = engine
        self.days       = RETENTION_DAYS
        self._last      = 0
        self._badge_cards = {}
        self._board_rows  = {}

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(hdr, text="Rankings",
                     font=ctk.CTkFont(size=28, weight="bold")).pack(side="left")

        self._range = ctk.CTkSegmentedButton(
            hdr, values=["Today", "7 Days", "30 Days"],
            command=self._change_range,
            selected_color=COLORS["p2"],
            selected_hover_color=COLORS["p1"],
            unselected_color=COLORS["surface"],
            unselected_hover_color=COLORS["surface_2"],
        )
        self._range.pack(side="right")

        badges = ctk.CTkFrame(self, fg_color="transparent")
        badges.pack(fill="x", pady=(0, 14))
        for i in range(4):
            badges.grid_columnconfigure(i, weight=1)

        for i, (key, label, accent) in enumerate([
            ("rank",        "Rank",        COLORS["yellow"]),
            ("tracked",     "Tracked",     COLORS["p4"]),
            ("top_lane",    "Top Lane",    COLORS["pink"]),
            ("focus_ratio", "Focus Ratio", COLORS["green"]),
        ]):
            card = StatCard(badges, label, accent=accent)
            card.grid(row=0, column=i, sticky="nsew",
                      padx=(0 if i == 0 else 8, 0))
            self._badge_cards[key] = card

        ctk.CTkLabel(self, text="App Leaderboard",
                     font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", pady=(0, 8))
        self._board = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._board.pack(fill="both", expand=True)
        self._empty = ctk.CTkLabel(self._board, text="",
                                   text_color=COLORS["muted"])
        self._range.set("30 Days")

    def _change_range(self, val):
        self.days = {"Today": 1, "7 Days": 7, "30 Days": RETENTION_DAYS}[val]
        self.update_view(force=True)

    def update_view(self, force=False):
        now = time.time()
        if not force and now - self._last < RANKINGS_REFRESH_SECONDS:
            return
        self._last = now
        self._load_badges()
        self._load_board()

    def _load_badges(self):
        s    = self.engine.get_summary(self.days)
        cats = self.engine.get_category_totals(self.days)
        top  = max(cats.items(), key=lambda x: x[1]["time"]) if cats else ("--", {"time": 0})
        emoji = RANK_EMOJI.get(s["tier"], "🌱")
        self._badge_cards["rank"].set(
            f"{emoji} {s['tier']}", f"{round(s['tier_progress']*100)}% to next", COLORS["yellow"])
        self._badge_cards["tracked"].set(
            format_duration(s["total"]), f"{s['opens']} opens", COLORS["p4"])
        self._badge_cards["top_lane"].set(
            top[0], format_duration(top[1]["time"]),
            CATEGORY_COLORS.get(top[0], COLORS["pink"]))
        self._badge_cards["focus_ratio"].set(
            f"{round(s['focus_ratio']*100)}%", f"{s['vibe_score']} aura", COLORS["green"])

    def _load_board(self):
        apps  = sorted(self.engine.get_app_totals(self.days).items(),
                       key=lambda x: x[1]["time"], reverse=True)
        max_t = apps[0][1]["time"] if apps else 1
        specs = []
        for i, (app, data) in enumerate(apps[:20], 1):
            accent = CATEGORY_COLORS.get(data["category"], COLORS["p3"])
            score  = round(data["score"])
            specs.append({
                "key":      app,
                "name":     app_name(app),
                "value":    format_duration(data["time"]),
                "progress": data["time"] / max_t,
                "accent":   accent,
                "prefix":   f"#{i} {data['emoji']} ",
                "suffix":   f" · {data['category']} · {data['opens']}x · {score:+} aura",
            })
        sync_rows(self._board, self._board_rows, specs,
                  self._empty, "No ranking data in this range yet.")


# ── Skill Tree ─────────────────────────────────────────────────────────────────
class SkillTreeView(ctk.CTkFrame):
    def __init__(self, master, engine):
        super().__init__(master, fg_color="transparent")
        self.engine     = engine
        self._last      = 0
        self._rows      = {}

        ctk.CTkLabel(self, text="RPG Skill Tree",
                     font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(self, text="Skills leveled from your 30-day app energy ⚔️",
                     text_color=COLORS["muted"]).pack(anchor="w", pady=(2, 14))

        self._container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._container.pack(fill="both", expand=True)
        self._empty = ctk.CTkLabel(self._container, text="",
                                   text_color=COLORS["muted"])

    def update_view(self, force=False):
        now = time.time()
        if not force and now - self._last < SKILLS_REFRESH_SECONDS:
            return
        self._last = now
        skills  = self.engine.get_total_skills(RETENTION_DAYS)
        top_s   = max(skills.values()) if skills else 1
        specs   = []
        for skill, secs in sorted(skills.items(), key=lambda x: x[1], reverse=True):
            level    = int(secs // 3600)
            pct_next = (secs % 3600) / 3600
            accent   = SKILL_COLORS.get(skill, COLORS["p3"])
            emoji    = SKILL_EMOJI.get(skill, "⭐")
            specs.append({
                "key":      skill,
                "name":     f"Lv.{level} {skill}",
                "value":    f"{round(pct_next * 100)}%",
                "progress": max(pct_next, secs / max(1, top_s) * 0.15),
                "accent":   accent,
                "prefix":   f"{emoji} ",
                "suffix":   " to next",
            })
        sync_rows(self._container, self._rows, specs,
                  self._empty, "No skill data yet.")


# ── Settings ───────────────────────────────────────────────────────────────────
class SettingsView(ctk.CTkFrame):
    def __init__(self, master, engine):
        super().__init__(master, fg_color="transparent")
        self.engine  = engine
        self._last   = 0
        self._cards  = {}

        ctk.CTkLabel(self, text="Options & Data",
                     font=ctk.CTkFont(size=28, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(self, text="30-day memory · local JSON · no cloud drama ☁️",
                     text_color=COLORS["muted"]).pack(anchor="w", pady=(2, 16))

        status = ctk.CTkFrame(self, fg_color="transparent")
        status.pack(fill="x", pady=(0, 16))
        for i in range(3):
            status.grid_columnconfigure(i, weight=1)

        for i, (key, label, accent) in enumerate([
            ("tracked_days", "Tracked Days",  COLORS["p4"]),
            ("storage",      "Storage",       COLORS["green"]),
            ("total_time",   "Total Time",    COLORS["pink"]),
        ]):
            card = StatCard(status, label, accent=accent)
            card.grid(row=0, column=i, sticky="nsew",
                      padx=(0 if i == 0 else 8, 0))
            self._cards[key] = card

        info = ctk.CTkFrame(self, fg_color=COLORS["surface"],
                            corner_radius=12, border_width=1,
                            border_color=COLORS["border"])
        info.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(info, text="Data Retention",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(info,
                     text=f"Only the latest {RETENTION_DAYS} calendar days are kept in "
                          f"{DATA_FILE.name}.",
                     text_color=COLORS["muted"]).pack(anchor="w", padx=16, pady=(0, 4))
        ctk.CTkLabel(info, text=str(DATA_FILE),
                     text_color=COLORS["p4"],
                     wraplength=740, justify="left").pack(anchor="w", padx=16, pady=(0, 14))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x")
        ctk.CTkButton(actions, text="💾  Save Now",
                      fg_color=COLORS["green"], text_color="#05070D",
                      hover_color="#24D96B",
                      command=self._save_now).pack(side="left", padx=(0, 8))
        ctk.CTkButton(actions, text="🧹  Clean 30-Day Window",
                      fg_color=COLORS["p3"], hover_color=COLORS["p2"],
                      command=self._clean_now).pack(side="left", padx=(0, 8))
        ctk.CTkButton(actions, text="💀  Reset All Data",
                      fg_color=COLORS["red"], hover_color="#B8334C",
                      command=self._reset_all).pack(side="left")

    def update_view(self, force=False):
        now = time.time()
        if not force and now - self._last < SETTINGS_REFRESH_SECONDS:
            return
        self._last = now
        s = self.engine.get_summary(RETENTION_DAYS)
        tracked = sum(1 for _, sec in self.engine.get_daily_totals(RETENTION_DAYS) if sec > 0)
        try:
            size = DATA_FILE.stat().st_size
            size_str = f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"
        except OSError:
            size_str = "—"
        self._cards["tracked_days"].set(str(tracked), f"of {RETENTION_DAYS}", COLORS["p4"])
        self._cards["storage"].set(size_str, DATA_FILE.name, COLORS["green"])
        self._cards["total_time"].set(format_duration(s["total"]),
                                      f"{s['vibe_score']} aura", COLORS["pink"])

    def _save_now(self):
        self.engine.save_data()
        messagebox.showinfo("DigitalWebling", "✅ Data saved successfully.")

    def _clean_now(self):
        self.engine.prune_old_data()
        self.engine.save_data()
        self.update_view(force=True)
        messagebox.showinfo("DigitalWebling", "🧹 Old data pruned.")

    def _reset_all(self):
        if not messagebox.askyesno("Reset DigitalWebling",
                                   "Delete ALL tracked app data? This cannot be undone."):
            return
        self.engine.reset_all_data()
        self.engine.save_data()
        self.update_view(force=True)


# =====================================================
# MAIN APPLICATION
# =====================================================
class MainApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.engine      = AuraEngine()
        self._nav_btns   = {}

        self.title("DigitalWebling Ultra Tracker")
        self.geometry("1180x740")
        self.minsize(1000, 640)
        self.configure(fg_color=COLORS["bg"])

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=0, column=1, sticky="nsew", padx=22, pady=22)

        self.views = {
            "Dashboard": DashboardView(container, self.engine),
            "Visualize": VisualizeView(container, self.engine),
            "Rankings":  RankingsView(container, self.engine),
            "Skills":    SkillTreeView(container, self.engine),
            "Settings":  SettingsView(container, self.engine),
        }

        self._current = "Dashboard"
        self.switch_view("Dashboard")
        self.after(TRACK_INTERVAL_MS, self._loop)

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, width=230, corner_radius=0,
                          fg_color=COLORS["sidebar"])
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_rowconfigure(8, weight=1)
        sb.grid_columnconfigure(0, weight=1)

        # Logo
        logo_frame = ctk.CTkFrame(sb, fg_color="transparent")
        logo_frame.grid(row=0, column=0, sticky="ew", padx=18, pady=(26, 0))
        ctk.CTkLabel(logo_frame, text="✨ DigitalWebling",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=COLORS["p4"]).pack(anchor="w")
        ctk.CTkLabel(logo_frame, text="ultra tracker v2.0",
                     text_color=COLORS["muted"],
                     font=ctk.CTkFont(size=11)).pack(anchor="w")

        # Separator
        sep = ctk.CTkFrame(sb, fg_color=COLORS["border"], height=1)
        sep.grid(row=1, column=0, sticky="ew", padx=14, pady=14)

        # Nav
        nav_items = [
            ("Dashboard", "📡  Dashboard"),
            ("Visualize", "📊  Visualize"),
            ("Rankings",  "🏆  Rankings"),
            ("Skills",    "⚔️  Skill Tree"),
            ("Settings",  "⚙️  Options"),
        ]
        for row, (name, text) in enumerate(nav_items, start=2):
            btn = ctk.CTkButton(
                sb, text=text,
                fg_color="transparent",
                hover_color=COLORS["surface_2"],
                anchor="w", height=42,
                corner_radius=10,
                command=lambda n=name: self.switch_view(n),
            )
            btn.grid(row=row, column=0, padx=12, pady=3, sticky="ew")
            self._nav_btns[name] = btn

        # Live badge
        live = ctk.CTkFrame(sb, fg_color=COLORS["surface"],
                            corner_radius=10, border_width=1,
                            border_color=COLORS["p2"])
        live.grid(row=9, column=0, padx=12, pady=18, sticky="ew")
        live.grid_columnconfigure(0, weight=1)

        top_live = ctk.CTkFrame(live, fg_color="transparent")
        top_live.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        # Animated dot via canvas
        dot_cv = tk.Canvas(top_live, width=10, height=10,
                           bg=COLORS["surface"], highlightthickness=0)
        dot_cv.pack(side="left", padx=(0, 6))
        self._dot = dot_cv.create_oval(1, 1, 9, 9, fill=COLORS["p4"], outline="")
        self._dot_cv = dot_cv
        ctk.CTkLabel(top_live, text="LIVE", text_color=COLORS["p4"],
                     font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")

        ctk.CTkLabel(live, text="Local · Fast · Vibe-aware",
                     text_color=COLORS["muted"],
                     font=ctk.CTkFont(size=11)).grid(
            row=1, column=0, sticky="w", padx=12, pady=(0, 10))

        self._pulse_dot()

    def _pulse_dot(self, on=True):
        color = COLORS["p4"] if on else COLORS["p1"]
        self._dot_cv.itemconfig(self._dot, fill=color)
        self.after(700, lambda: self._pulse_dot(not on))

    def switch_view(self, name):
        self._current = name
        for view in self.views.values():
            view.pack_forget()
        self.views[name].pack(fill="both", expand=True)
        self.views[name].update_view(force=True)
        self._update_nav()

    def _update_nav(self):
        for name, btn in self._nav_btns.items():
            if name == self._current:
                btn.configure(fg_color=COLORS["p2"],
                              hover_color=COLORS["p1"],
                              text_color=COLORS["text"])
            else:
                btn.configure(fg_color="transparent",
                              hover_color=COLORS["surface_2"],
                              text_color=COLORS["muted"])

    def _loop(self):
        self.engine.tick()
        view = self.views.get(self._current)
        if view and hasattr(view, "update_view"):
            view.update_view()
        self.engine.autosave()
        self.after(TRACK_INTERVAL_MS, self._loop)


# =====================================================
# ENTRY POINT
# =====================================================
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
