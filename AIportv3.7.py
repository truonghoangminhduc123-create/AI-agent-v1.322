import os
import time
import json
import base64
import requests
import pyautogui
import threading
import datetime
from tkinter import messagebox, scrolledtext
import tempfile
from PIL import Image, ImageTk
from gtts import gTTS
from playsound import playsound
import langdetect

# Import the CustomTkinter library
import customtkinter as ctk

# One UI-like color palette
ONEUI_COLORS = {
    "primary": "#4a85fa",
    "secondary": "#2c2c2c",
    "text": "#e0e0e0",
    "dark_bg": "#181818",
    "widget_bg": "#2a2a2a"
}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class UsageMonitor:
    """Manages tracking, displaying, and logging AI usage and costs."""
    
    def __init__(self, root):
        self.root = root
        self.start_time = None
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.total_requests = 0
        self.current_model = ""
        self.is_running = False
        self.update_job = None

        # Estimated prices per 1 million tokens (in USD) and RPM limits
        # These are estimates and may be subject to change.
        self.PRICES = {
            "gpt-4o": {"in": 5.0, "out": 15.0, "rpm": 60},
            "gemini-2.5-flash": {"in": 0.35, "out": 1.05, "rpm": 20},
            "claude-3-5-sonnet-20240620": {"in": 3.0, "out": 15.0, "rpm": 40},
            "llama3": {"in": 0, "out": 0, "rpm": 90},  # Free for local usage
            "phi3": {"in": 0, "out": 0, "rpm": 90},    # Free for local usage
            "default": {"in": 0, "out": 0, "rpm": 30}
        }
        
        self.usage_window = None

    def start_tracking(self, model):
        self.start_time = time.time()
        self.current_model = model
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        self.total_requests = 0
        self.is_running = True

    def stop_tracking(self):
        self.is_running = False
        if self.usage_window and self.usage_window.winfo_exists() and self.update_job:
            self.root.after_cancel(self.update_job)

    def update_tokens(self, tokens_in, tokens_out):
        self.total_tokens_in += tokens_in
        self.total_tokens_out += tokens_out
        self.total_requests += 1

    def _get_model_price(self):
        return self.PRICES.get(self.current_model, self.PRICES["default"])

    def _calculate_costs(self):
        prices = self._get_model_price()
        
        current_cost = (self.total_tokens_in / 1_000_000) * prices["in"] + \
                       (self.total_tokens_out / 1_000_000) * prices["out"]
        
        uptime = time.time() - self.start_time if self.start_time else 0
        
        if uptime > 0:
            avg_hourly_cost = current_cost / (uptime / 3600)
            avg_daily_cost = current_cost / (uptime / 86400)
        else:
            avg_hourly_cost = 0
            avg_daily_cost = 0

        return {
            "current_cost": current_cost,
            "hourly": avg_hourly_cost,
            "daily": avg_daily_cost
        }

    def _calculate_stats(self):
        uptime = time.time() - self.start_time if self.start_time else 0
        rpm = (self.total_requests / uptime * 60) if uptime > 0 else 0
        
        return {
            "uptime": uptime,
            "rpm": rpm
        }

    def _show_usage_window_internal(self):
        if self.usage_window and self.usage_window.winfo_exists():
            self.usage_window.lift()
            return
            
        self.usage_window = ctk.CTkToplevel(self.root)
        self.usage_window.title("AI Usage & Costs")
        self.usage_window.geometry("450x450")
        self.usage_window.configure(fg_color=ONEUI_COLORS["dark_bg"])
        self.usage_window.transient(self.root)
        self.usage_window.grab_set()

        main_frame = ctk.CTkFrame(self.usage_window, fg_color=ONEUI_COLORS["widget_bg"])
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        ctk.CTkLabel(main_frame, text="Current Usage & Costs", font=("Roboto", 16, "bold"), text_color=ONEUI_COLORS["text"]).pack(pady=(10, 20))

        # Stats Labels
        self.uptime_label = ctk.CTkLabel(main_frame, text="AI Uptime: 0s", text_color=ONEUI_COLORS["text"])
        self.uptime_label.pack(anchor="w", padx=20, pady=5)
        
        self.rpm_label = ctk.CTkLabel(main_frame, text="RPM: 0", text_color=ONEUI_COLORS["text"])
        self.rpm_label.pack(anchor="w", padx=20, pady=5)
        
        self.tokens_label = ctk.CTkLabel(main_frame, text="Tokens Used: 0 In / 0 Out", text_color=ONEUI_COLORS["text"])
        self.tokens_label.pack(anchor="w", padx=20, pady=5)

        # Costs Labels
        self.cost_label = ctk.CTkLabel(main_frame, text="Current Cost: $0.00", font=("Roboto", 12, "bold"), text_color=ONEUI_COLORS["primary"])
        self.cost_label.pack(anchor="w", padx=20, pady=(15, 5))
        
        self.hourly_cost_label = ctk.CTkLabel(main_frame, text="Est. Hourly Cost: $0.00", text_color=ONEUI_COLORS["text"])
        self.hourly_cost_label.pack(anchor="w", padx=20, pady=5)
        
        self.daily_cost_label = ctk.CTkLabel(main_frame, text="Est. Daily Cost: $0.00", text_color=ONEUI_COLORS["text"])
        self.daily_cost_label.pack(anchor="w", padx=20, pady=5)
        
        self.model_limit_label = ctk.CTkLabel(main_frame, text=f"RPM Limit for {self.current_model}: {self._get_model_price()['rpm']}", text_color=ONEUI_COLORS["text"])
        self.model_limit_label.pack(anchor="w", padx=20, pady=(15, 5))

        # Close button
        close_button = ctk.CTkButton(main_frame, text="Close & Save", command=self._save_data_and_close)
        close_button.pack(pady=(20, 10))
        
        self.update_stats()
        self.usage_window.protocol("WM_DELETE_WINDOW", self._save_data_and_close)

    def _save_data_and_close(self):
        self._save_daily_usage()
        if self.usage_window and self.usage_window.winfo_exists():
            self.usage_window.destroy()

    def update_stats(self):
        if not self.usage_window or not self.usage_window.winfo_exists():
            return
            
        costs = self._calculate_costs()
        stats = self._calculate_stats()
        
        self.uptime_label.configure(text=f"AI Uptime: {stats['uptime']:.1f}s")
        self.rpm_label.configure(text=f"RPM: {stats['rpm']:.2f}")
        self.tokens_label.configure(text=f"Tokens Used: {self.total_tokens_in} In / {self.total_tokens_out} Out")
        self.cost_label.configure(text=f"Current Cost: ${costs['current_cost']:.4f}")
        self.hourly_cost_label.configure(text=f"Est. Hourly Cost: ${costs['hourly']:.4f}")
        self.daily_cost_label.configure(text=f"Est. Daily Cost: ${costs['daily']:.4f}")
        self.model_limit_label.configure(text=f"RPM Limit for {self.current_model}: {self._get_model_price()['rpm']}")
        
        if self.is_running:
            self.update_job = self.root.after(1000, self.update_stats)

    def _save_daily_usage(self):
        # Path to the data file
        file_path = "money_usage.json"
        
        # Load existing data or initialize a new dictionary
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        
        today = datetime.date.today().isoformat()
        
        # Prepare today's data entry
        costs = self._calculate_costs()
        stats = self._calculate_stats()
        
        today_entry = {
            "model": self.current_model,
            "tokens_in": self.total_tokens_in,
            "tokens_out": self.total_tokens_out,
            "total_requests": self.total_requests,
            "uptime_seconds": stats['uptime'],
            "current_cost_usd": costs['current_cost'],
            "hourly_cost_est_usd": costs['hourly'],
            "daily_cost_est_usd": costs['daily']
        }
        
        data[today] = today_entry
        
        # Save the updated data
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving daily usage data: {e}")

class AIportGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Agent Control")
        self.root.geometry("600x650")
        self.root.configure(fg_color=ONEUI_COLORS["dark_bg"])
        
        self.api_key = ctk.StringVar()
        self.api_provider = ctk.StringVar(value="Ollama")
        self.model = ctk.StringVar()
        self.stop_flag = False
        self.agent_thread = None
        self.last_screenshot_path = None
        self.tutorial_content = None
        self.cursor_image = None
        self.usage_monitor = UsageMonitor(self.root)
        
        # Cố gắng tải hình ảnh con trỏ chuột
        try:
            self.cursor_image = Image.open("cursor.png").convert("RGBA")
        except FileNotFoundError:
            messagebox.showwarning("Warning", "File 'cursor.png' not found. Screenshots will be taken without a cursor.")

        main_frame = ctk.CTkFrame(root, fg_color=ONEUI_COLORS["dark_bg"], corner_radius=10)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(main_frame, text="AI Agent Control", font=("Roboto", 24, "bold"), text_color=ONEUI_COLORS["text"]).pack(anchor="w", pady=(0, 20))

        ctk.CTkLabel(main_frame, text="Select API:", font=("Roboto", 12, "bold"), text_color=ONEUI_COLORS["text"]).pack(anchor="w", pady=(0, 5))
        self.api_provider_combobox = ctk.CTkOptionMenu(main_frame, variable=self.api_provider, values=["Ollama", "Gemini", "OpenRouter", "OpenAI", "Claude"], command=self._on_api_change)
        self.api_provider_combobox.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(main_frame, text="API Key:", font=("Roboto", 12, "bold"), text_color=ONEUI_COLORS["text"]).pack(anchor="w", pady=(0, 5))
        self.api_key_entry = ctk.CTkEntry(main_frame, textvariable=self.api_key, placeholder_text="Enter your API key", show="*", fg_color=ONEUI_COLORS["widget_bg"])
        self.api_key_entry.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(main_frame, text="Select AI Model:", font=("Roboto", 12, "bold"), text_color=ONEUI_COLORS["text"]).pack(anchor="w", pady=(0, 5))
        self.model_combobox = ctk.CTkOptionMenu(main_frame, variable=self.model, values=["llama3"])
        self.model_combobox.set("llama3")
        self.model_combobox.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(main_frame, text="Enter command for AI:", font=("Roboto", 12, "bold"), text_color=ONEUI_COLORS["text"]).pack(anchor="w", pady=(0, 5))
        self.prompt_text = scrolledtext.ScrolledText(main_frame, height=8, wrap="word", font=("Roboto", 10),
                                                    bg=ONEUI_COLORS["widget_bg"], fg=ONEUI_COLORS["text"])
        self.prompt_text.pack(fill="x", pady=(0, 15))
        self.prompt_text.insert("1.0", "Find Chrome browser and open google.com")
        
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(pady=(0, 15), expand=True, fill="x")
        
        self.start_button = ctk.CTkButton(button_frame, text="▶️ Start", command=self.start_agent)
        self.start_button.pack(side="left", expand=True, padx=5)

        self.stop_button = ctk.CTkButton(button_frame, text="⏹️ Stop", command=self.stop_agent, state="disabled", fg_color="red")
        self.stop_button.pack(side="left", expand=True, padx=5)

        self.view_image_button = ctk.CTkButton(button_frame, text="🖼️ View Screenshot", command=self.view_last_screenshot)
        self.view_image_button.pack(side="left", expand=True, padx=5)
        
        self.view_usage_button = ctk.CTkButton(button_frame, text="💰 View Usage", command=self.usage_monitor._show_usage_window_internal)
        self.view_usage_button.pack(side="left", expand=True, padx=5)


        ctk.CTkLabel(main_frame, text="AI activity log:", font=("Roboto", 12, "bold"), text_color=ONEUI_COLORS["text"]).pack(anchor="w", pady=(0, 5))
        self.log_area = scrolledtext.ScrolledText(main_frame, height=15, wrap="word", state="disabled", font=("TkFixedFont", 10),
                                                bg=ONEUI_COLORS["widget_bg"], fg=ONEUI_COLORS["text"])
        self.log_area.pack(fill="both", expand=True)

        self._on_api_change("Ollama")
    
    # New method to log messages with smooth scrolling
    def _log_with_animation(self, message):
        self.log_area.configure(state="normal")
        self.log_area.insert("end", message + "\n")
        self.log_area.configure(state="disabled")
        self._smooth_scroll()

    # Smooth scroll to the end of the log
    def _smooth_scroll(self):
        current_y = float(self.log_area.yview()[0])
        end_y = float(self.log_area.yview()[1])
        
        if end_y < 1.0:
            scroll_by = 0.05
            new_y = current_y + scroll_by
            if new_y > 1.0:
                new_y = 1.0
            
            self.log_area.yview_moveto(new_y)
            self.root.after(10, self._smooth_scroll)

    def _on_api_change(self, choice):
        if choice == "Ollama":
            self.model_combobox.configure(values=["llama3", "phi3"])
            self.model_combobox.set("llama3")
        elif choice == "OpenRouter":
            self.model_combobox.configure(values=["openrouter/cinematika-7b", "google/gemini-flash-1.5-preview", "mistralai/mixtral-8x7b-instruct"])
            self.model_combobox.set("openrouter/cinematika-7b")
        elif choice == "Gemini":
            self.model_combobox.configure(values=["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro"])
            self.model_combobox.set("gemini-2.5-flash")
        elif choice == "OpenAI":
            self.model_combobox.configure(values=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"])
            self.model_combobox.set("gpt-4o")
        elif choice == "Claude":
            self.model_combobox.configure(values=["claude-3-5-sonnet-20240620", "claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"])
            self.model_combobox.set("claude-3-5-sonnet-20240620")

    def start_agent(self):
        if not self.api_key.get() and self.api_provider.get() != "Ollama":
            messagebox.showerror("Error", "Please enter an API Key!")
            return
        if not self.prompt_text.get("1.0", "end").strip():
            messagebox.showerror("Error", "Please enter a command for AI!")
            return

        self.stop_flag = False
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", "end")
        self.log_area.configure(state="disabled")

        self.agent_thread = threading.Thread(target=self._run_agent_loop, daemon=True)
        self.agent_thread.start()

    def stop_agent(self):
        self.stop_flag = True
        self.usage_monitor.stop_tracking()
        self._log_with_animation("⏹️ Sending stop signal to AI...")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
    
    def _encode_image(self, filename):
        with open(filename, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _fetch_tutorial(self):
        self._log_with_animation("🔗 Loading tutorial from GitHub URL...")
        url = "https://raw.githubusercontent.com/truonghoangminhduc123-create/Training-data/refs/heads/main/Trainingdata.txt"
        try:
            response = requests.get(url)
            response.raise_for_status()
            self.tutorial_content = response.text
            self._log_with_animation("✅ Tutorial loaded successfully!")
        except requests.exceptions.RequestException as e:
            self._log_with_animation(f"❌ Error loading tutorial: {e}")
            messagebox.showerror("Error", f"Failed to load tutorial from URL.\nError: {e}")
            self.stop_agent()

    def _send_to_ollama(self, img_b64, user_prompt):
        model = self.model.get()
        url = "http://localhost:11434/api/generate"
        headers = {"Content-Type": "application/json"}
        
        payload = {
            "model": model,
            "prompt": f"{self.tutorial_content}\n\n{user_prompt}",
            "stream": False,
            "images": [img_b64],
            "options": {
                "num_ctx": 4096
            }
        }
        
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        res.raise_for_status()
        response_data = res.json()
        
        # Estimate token usage
        # This is a rough estimate, a real tokenizer would be more accurate
        tokens_in = len((self.tutorial_content + user_prompt).split()) + 500  # Estimate image tokens
        tokens_out = len(response_data.get("response", "").split())
        self.usage_monitor.update_tokens(tokens_in, tokens_out)
        
        return response_data.get("response", "")

    def _send_to_gemini(self, img_b64, user_prompt):
        api_key = self.api_key.get()
        model = self.model.get()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        
        payload = {"contents": [{"parts": [{"text": self.tutorial_content}, {"inline_data": {"mime_type": "image/png", "data": img_b64}}, {"text": user_prompt}]}]}
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        res.raise_for_status()
        
        response_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
        
        # Estimate token usage
        tokens_in = len((self.tutorial_content + user_prompt).split()) + 500
        tokens_out = len(response_text.split())
        self.usage_monitor.update_tokens(tokens_in, tokens_out)

        return response_text

    def _send_to_openrouter(self, img_b64, user_prompt):
        api_key = self.api_key.get()
        model = self.model.get()
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": [
                    {"type": "text", "text": self.tutorial_content + "\n\n" + user_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]}
            ]
        }
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        res.raise_for_status()
        response_json = res.json()

        # Update token usage from API response (if available) or estimate
        tokens_in = response_json["usage"]["prompt_tokens"] if "usage" in response_json else len((self.tutorial_content + user_prompt).split()) + 500
        tokens_out = response_json["usage"]["completion_tokens"] if "usage" in response_json else len(response_json["choices"][0]["message"]["content"].split())
        self.usage_monitor.update_tokens(tokens_in, tokens_out)

        return response_json["choices"][0]["message"]["content"]
    
    def _send_to_openai(self, img_b64, user_prompt):
        api_key = self.api_key.get()
        model = self.model.get()
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.tutorial_content + "\n\n" + user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ]
                }
            ],
            "max_tokens": 4096
        }
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        response_json = res.json()
        
        # Update token usage from API response
        tokens_in = response_json["usage"]["prompt_tokens"]
        tokens_out = response_json["usage"]["completion_tokens"]
        self.usage_monitor.update_tokens(tokens_in, tokens_out)
        
        return response_json["choices"][0]["message"]["content"]

    def _send_to_claude(self, img_b64, user_prompt):
        api_key = self.api_key.get()
        model = self.model.get()
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                        {"type": "text", "text": self.tutorial_content + "\n\n" + user_prompt}
                    ]
                }
            ]
        }
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
        response_json = res.json()

        # Update token usage from API response
        tokens_in = response_json["usage"]["input_tokens"]
        tokens_out = response_json["usage"]["output_tokens"]
        self.usage_monitor.update_tokens(tokens_in, tokens_out)
        
        return response_json["content"][0]["text"]

    def _execute_actions(self, actions):
        for action in actions:
            t = action.get("type")
            self._log_with_animation(f"   - Executing: {t} with {action}")
            if t == "move":
                pyautogui.moveTo(action["x"], action["y"], duration=0.5)
            elif t == "click":
                pyautogui.click(button=action.get("button", "left"), clicks=action.get("count", 1))
            elif t == "click_down":
                pyautogui.mouseDown(button=action.get("button", "left"))
            elif t == "click_up":
                pyautogui.mouseUp(button=action.get("button", "left"))
            elif t == "scroll":
                pyautogui.scroll(action.get("dy", 0))
            elif t == "type":
                pyautogui.typewrite(action["text"], interval=0.05)
            elif t == "hotkey":
                pyautogui.hotkey(*action["keys"])
            elif t == "speak":
                text_to_speak = action.get("text", "")
                if text_to_speak:
                    self._log_with_animation(f"   - Speaking: {text_to_speak}")
                    try:
                        try:
                            detected_lang = langdetect.detect(text_to_speak)
                            self._log_with_animation(f"     -> Detected language: {detected_lang}")
                        except langdetect.lang_detect_exception.LangDetectException:
                            detected_lang = 'en'
                            self._log_with_animation("     -> Could not detect language. Defaulting to 'en'.")
                        
                        tts = gTTS(text=text_to_speak, lang=detected_lang)
                        temp_file_path = os.path.join(tempfile.gettempdir(), f"speech_{int(time.time())}.mp3")
                        tts.save(temp_file_path)
                        
                        self._log_with_animation(f"     -> Playing audio from Google TTS...")
                        playsound(temp_file_path)
                        
                        os.remove(temp_file_path)
                    except Exception as e:
                        self._log_with_animation(f"❌ Error during text-to-speech with gTTS: {e}")
            elif t == "multi_click":
                for _ in range(action.get("count", 2)):
                    pyautogui.click(action["x"], action["y"])
                    time.sleep(0.05)
            elif t == "key_down_for_seconds":
                key = action.get("key")
                duration = action.get("duration", 1.0)
                if key:
                    pyautogui.keyDown(key)
                    self._log_with_animation(f"   - Holding key: {key} for {duration} seconds")
                    time.sleep(duration)
                    pyautogui.keyUp(key)
            time.sleep(0.5)

    def view_last_screenshot(self):
        if not self.last_screenshot_path or not os.path.exists(self.last_screenshot_path):
            messagebox.showinfo("Notice", "No screenshots have been taken yet.")
            return

        view_window = ctk.CTkToplevel(self.root)
        view_window.title("Screenshot")
        
        img = Image.open(self.last_screenshot_path)
        max_size = (800, 600)
        img.thumbnail(max_size)
        
        tk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
        
        label = ctk.CTkLabel(view_window, image=tk_img, text="")
        label.pack()

        close_button = ctk.CTkButton(view_window, text="Close", command=view_window.destroy)
        close_button.pack(pady=10)

    def _run_agent_loop(self):
        self._log_with_animation("▶️ AI agent starting...")
        user_prompt = self.prompt_text.get("1.0", "end").strip()
        
        self._fetch_tutorial()
        if not self.tutorial_content:
            self._log_with_animation("❌ Failed to load tutorial. Stopping agent.")
            self.stop_agent()
            return
            
        self.usage_monitor.start_tracking(self.model.get())

        temp_dir = tempfile.gettempdir()
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        while not self.stop_flag:
            self._cleanup_temp_files()
            try:
                self.last_screenshot_path = os.path.join(temp_dir, f"screenshot_{int(time.time())}.png")

                self._log_with_animation(f"\n[1] Taking new screenshot: {self.last_screenshot_path}")
                
                screenshot = pyautogui.screenshot()
                mouse_x, mouse_y = pyautogui.position()
                self._log_with_animation(f"   -> Mouse position: ({mouse_x}, {mouse_y})")

                if self.cursor_image:
                    cursor_copy = self.cursor_image.copy()
                    screen_width, screen_height = pyautogui.size()
                    ratio = min(screen_width / 1920, screen_height / 1080)
                    new_size = (int(cursor_copy.width * ratio), int(cursor_copy.height * ratio))
                    cursor_copy = cursor_copy.resize(new_size, Image.Resampling.LANCZOS)
                    
                    paste_x = mouse_x - int(cursor_copy.width / 2)
                    paste_y = mouse_y - int(cursor_copy.height / 2)
                    
                    screenshot.paste(cursor_copy, (paste_x, paste_y), cursor_copy)

                screenshot.save(self.last_screenshot_path)
                
                img_b64 = self._encode_image(self.last_screenshot_path)

                self._log_with_animation("[2] Sending image and command to AI...")

                api_provider = self.api_provider.get()
                if api_provider == "Ollama":
                    response_text = self._send_to_ollama(img_b64, user_prompt)
                elif api_provider == "Gemini":
                    response_text = self._send_to_gemini(img_b64, user_prompt)
                elif api_provider == "OpenRouter":
                    response_text = self._send_to_openrouter(img_b64, user_prompt)
                elif api_provider == "OpenAI":
                    response_text = self._send_to_openai(img_b64, user_prompt)
                elif api_provider == "Claude":
                    response_text = self._send_to_claude(img_b64, user_prompt)
                else:
                    self._log_with_animation("❌ Error: Unsupported API Provider.")
                    break
                
                self._log_with_animation("[3] AI response:\n" + response_text)

                try:
                    clean_ai_text = response_text.strip().replace("```json", "").replace("```", "")
                    actions = json.loads(clean_ai_text)
                    
                    if not actions:
                        self._log_with_animation("✅ AI thinks the task is complete. Stopping.")
                        break

                    self._log_with_animation("[4] Executing actions:")
                    self._execute_actions(actions)
                except Exception as e:
                    self._log_with_animation(f"❌ Error parsing JSON or executing: {e}")

                time.sleep(2)

            except Exception as e:
                self._log_with_animation(f"❌ Error in main loop: {e}")
                if "API_KEY_INVALID" in str(e) or "AuthenticationError" in str(e):
                    self._log_with_animation("ERROR: Invalid API Key. Please check again.")
                elif "404" in str(e):
                    self._log_with_animation("ERROR: API path not found. You might have selected a model that doesn't support screenshots.")
                    self._log_with_animation("Please try again with a different model, for example 'gpt-4o'.")
                break
                time.sleep(2)
        
        if self.stop_flag:
             self._log_with_animation("⏹️ AI stopped by user.")
        self.stop_agent()
        self._cleanup_temp_files()

    def _cleanup_temp_files(self):
        temp_dir = tempfile.gettempdir()
        for filename in os.listdir(temp_dir):
            if filename.startswith("screenshot_") and filename.endswith(".png"):
                file_path = os.path.join(temp_dir, filename)
                try:
                    os.remove(file_path)
                except OSError as e:
                    self._log_with_animation(f"Error deleting temporary file {file_path}: {e}")

# ================== RUN ==================
if __name__ == "__main__":
    root = ctk.CTk()
    app = AIportGUI(root)
    root.mainloop()
