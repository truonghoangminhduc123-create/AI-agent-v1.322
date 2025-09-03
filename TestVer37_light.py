import os
import time
import json
import base64
import requests
import pyautogui
import threading
from tkinter import messagebox, scrolledtext
import tempfile
from PIL import Image

import customtkinter as ctk

# Light, modern color palette
MODERN_COLORS = {
    "primary": "#4776f6",
    "bg": "#f7f9fa",
    "widget_bg": "#ffffff",
    "text": "#1b1b1b",
    "accent": "#e7eaf3"
}

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class AIportGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Agent Control")
        self.root.geometry("560x580")
        self.root.minsize(480, 420)
        self.root.configure(fg_color=MODERN_COLORS["bg"])
        
        self.api_key = ctk.StringVar()
        self.api_provider = ctk.StringVar(value="Ollama")
        self.model = ctk.StringVar()
        self.stop_flag = False
        self.agent_thread = None
        self.last_screenshot_path = None
        self.tutorial_content = None

        main_frame = ctk.CTkFrame(root, fg_color=MODERN_COLORS["widget_bg"], corner_radius=18)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(main_frame, text="🧠 AI Agent", font=("Segoe UI", 22, "bold"), text_color=MODERN_COLORS["primary"]).pack(anchor="w", pady=(0, 12))

        # API Provider
        ctk.CTkLabel(main_frame, text="API Provider", font=("Segoe UI", 11), text_color=MODERN_COLORS["text"]).pack(anchor="w", pady=(0, 3))
        self.api_provider_combobox = ctk.CTkOptionMenu(main_frame, variable=self.api_provider, values=["Ollama", "Gemini", "OpenRouter", "OpenAI", "Claude"], command=self._on_api_change)
        self.api_provider_combobox.pack(fill="x", pady=(0, 10))

        # API Key
        ctk.CTkLabel(main_frame, text="API Key", font=("Segoe UI", 11), text_color=MODERN_COLORS["text"]).pack(anchor="w", pady=(0, 3))
        self.api_key_entry = ctk.CTkEntry(main_frame, textvariable=self.api_key, placeholder_text="Enter your API key", show="*", fg_color=MODERN_COLORS["accent"])
        self.api_key_entry.pack(fill="x", pady=(0, 10))

        # Model
        ctk.CTkLabel(main_frame, text="AI Model", font=("Segoe UI", 11), text_color=MODERN_COLORS["text"]).pack(anchor="w", pady=(0, 3))
        self.model_combobox = ctk.CTkOptionMenu(main_frame, variable=self.model, values=["llama3"])
        self.model_combobox.set("llama3")
        self.model_combobox.pack(fill="x", pady=(0, 10))

        # Prompt
        ctk.CTkLabel(main_frame, text="AI Command", font=("Segoe UI", 11), text_color=MODERN_COLORS["text"]).pack(anchor="w", pady=(0, 3))
        self.prompt_text = scrolledtext.ScrolledText(main_frame, height=5, wrap="word", font=("Segoe UI", 10), bg=MODERN_COLORS["accent"], fg=MODERN_COLORS["text"], borderwidth=0)
        self.prompt_text.pack(fill="x", pady=(0, 10))
        self.prompt_text.insert("1.0", "Find Chrome browser and open google.com")
        
        # Buttons
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=(0, 10), fill="x")
        self.start_button = ctk.CTkButton(btn_frame, text="Start", command=self.start_agent)
        self.start_button.pack(side="left", expand=True, padx=3)
        self.stop_button = ctk.CTkButton(btn_frame, text="Stop", command=self.stop_agent, state="disabled", fg_color="#fc5c65")
        self.stop_button.pack(side="left", expand=True, padx=3)
        self.view_image_button = ctk.CTkButton(btn_frame, text="View Screenshot", command=self.view_last_screenshot)
        self.view_image_button.pack(side="left", expand=True, padx=3)

        # Logging
        ctk.CTkLabel(main_frame, text="Activity Log", font=("Segoe UI", 11), text_color=MODERN_COLORS["text"]).pack(anchor="w", pady=(0, 3))
        self.log_area = scrolledtext.ScrolledText(main_frame, height=10, wrap="word", state="disabled", font=("Consolas", 9), bg=MODERN_COLORS["accent"], fg=MODERN_COLORS["text"], borderwidth=0)
        self.log_area.pack(fill="both", expand=True)

        self._on_api_change("Ollama")

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

    def _log(self, message):
        self.log_area.configure(state="normal")
        self.log_area.insert("end", message + "\n")
        self.log_area.see("end")
        self.log_area.configure(state="disabled")

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
        self._log("⏹️ Stopping AI...")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

    def _encode_image(self, filename):
        with open(filename, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _fetch_tutorial(self):
        self._log("🔗 Loading tutorial data...")
        url = "https://raw.githubusercontent.com/truonghoangminhduc123-create/Training-data/refs/heads/main/Trainingdata.txt"
        try:
            response = requests.get(url)
            response.raise_for_status()
            self.tutorial_content = response.text
            self._log("✅ Tutorial loaded.")
        except requests.exceptions.RequestException as e:
            self._log(f"❌ Error loading tutorial: {e}")
            messagebox.showerror("Error", f"Failed to load tutorial.\n{e}")
            self.stop_agent()

    def _send_to_api(self, api_provider, img_b64, user_prompt):
        model = self.model.get()
        api_key = self.api_key.get()
        tutorial = self.tutorial_content or ""
        if api_provider == "Ollama":
            url = "http://localhost:11434/api/generate"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": model,
                "prompt": f"{tutorial}\n\n{user_prompt}",
                "stream": False,
                "images": [img_b64],
                "options": {"num_ctx": 4096}
            }
            res = requests.post(url, headers=headers, data=json.dumps(payload))
            res.raise_for_status()
            response_data = res.json()
            return response_data.get("response", "")
        elif api_provider == "Gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {"contents": [{"parts": [{"text": tutorial}, {"inline_data": {"mime_type": "image/png", "data": img_b64}}, {"text": user_prompt}]}]}
            res = requests.post(url, headers=headers, data=json.dumps(payload))
            res.raise_for_status()
            return res.json()["candidates"][0]["content"]["parts"][0]["text"]
        elif api_provider == "OpenRouter":
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": [
                    {"role": "user", "content": [
                        {"type": "text", "text": tutorial + "\n\n" + user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ]}
                ]
            }
            res = requests.post(url, headers=headers, data=json.dumps(payload))
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"]
        elif api_provider == "OpenAI":
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
                            {"type": "text", "text": tutorial + "\n\n" + user_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                        ]
                    }
                ],
                "max_tokens": 4096
            }
            res = requests.post(url, headers=headers, json=payload)
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"]
        elif api_provider == "Claude":
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
                            {"type": "text", "text": tutorial + "\n\n" + user_prompt}
                        ]
                    }
                ]
            }
            res = requests.post(url, headers=headers, json=payload)
            res.raise_for_status()
            return res.json()["content"][0]["text"]
        else:
            raise Exception("Unsupported API Provider.")

    def _execute_actions(self, actions):
        for action in actions:
            t = action.get("type")
            self._log(f"   - {t}: {action}")
            if t == "move":
                pyautogui.moveTo(action["x"], action["y"], duration=0.4)
            elif t == "click":
                pyautogui.click(button=action.get("button", "left"), clicks=action.get("count", 1))
            elif t == "click_down":
                pyautogui.mouseDown(button=action.get("button", "left"))
            elif t == "click_up":
                pyautogui.mouseUp(button=action.get("button", "left"))
            elif t == "scroll":
                pyautogui.scroll(action.get("dy", 0))
            elif t == "type":
                pyautogui.typewrite(action["text"], interval=0.035)
            elif t == "hotkey":
                pyautogui.hotkey(*action["keys"])
            elif t == "multi_click":
                for _ in range(action.get("count", 2)):
                    pyautogui.click(action["x"], action["y"])
                    time.sleep(0.04)
            elif t == "key_down_for_seconds":
                key = action.get("key")
                duration = action.get("duration", 1.0)
                if key:
                    pyautogui.keyDown(key)
                    self._log(f"   - Holding key: {key} for {duration}s")
                    time.sleep(duration)
                    pyautogui.keyUp(key)
            time.sleep(0.3)

    def view_last_screenshot(self):
        if not self.last_screenshot_path or not os.path.exists(self.last_screenshot_path):
            messagebox.showinfo("Notice", "No screenshots have been taken yet.")
            return

        view_window = ctk.CTkToplevel(self.root)
        view_window.title("Screenshot")
        img = Image.open(self.last_screenshot_path)
        img.thumbnail((700, 500))
        # Use PIL's ImageTk for lightweight display
        from PIL import ImageTk
        tk_img = ImageTk.PhotoImage(img)
        import tkinter as tk
        tk_label = tk.Label(view_window, image=tk_img)
        tk_label.image = tk_img
        tk_label.pack()
        ctk.CTkButton(view_window, text="Close", command=view_window.destroy).pack(pady=8)

    def _run_agent_loop(self):
        self._log("▶️ AI agent starting...")
        user_prompt = self.prompt_text.get("1.0", "end").strip()
        self._fetch_tutorial()
        if not self.tutorial_content:
            self._log("❌ Tutorial load failed. Stopping agent.")
            self.stop_agent()
            return

        temp_dir = tempfile.gettempdir()
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        while not self.stop_flag:
            self._cleanup_temp_files()
            try:
                self.last_screenshot_path = os.path.join(temp_dir, f"screenshot_{int(time.time())}.png")
                self._log(f"[1] Screenshot: {self.last_screenshot_path}")
                pyautogui.screenshot(self.last_screenshot_path)
                img_b64 = self._encode_image(self.last_screenshot_path)

                self._log("[2] Sending to AI...")
                api_provider = self.api_provider.get()
                response_text = self._send_to_api(api_provider, img_b64, user_prompt)
                self._log("[3] AI response:\n" + response_text)

                try:
                    clean_ai_text = response_text.strip().replace("```json", "").replace("```", "")
                    actions = json.loads(clean_ai_text)
                    if not actions:
                        self._log("✅ Task complete. Stopping.")
                        break
                    self._log("[4] Executing actions:")
                    self._execute_actions(actions)
                except Exception as e:
                    self._log(f"❌ Error parsing/executing: {e}")

                time.sleep(1.5)

            except Exception as e:
                self._log(f"❌ Error in main loop: {e}")
                if "API_KEY_INVALID" in str(e) or "AuthenticationError" in str(e):
                    self._log("ERROR: Invalid API Key.")
                elif "404" in str(e):
                    self._log("ERROR: API path not found. Try a different model.")
                break
                time.sleep(1.5)

        if self.stop_flag:
            self._log("⏹️ AI stopped by user.")
        self.stop_agent()
        self._cleanup_temp_files()

    def _cleanup_temp_files(self):
        temp_dir = tempfile.gettempdir()
        for filename in os.listdir(temp_dir):
            if filename.startswith("screenshot_") and filename.endswith(".png"):
                file_path = os.path.join(temp_dir, filename)
                try:
                    os.remove(file_path)
                except OSError:
                    pass

if __name__ == "__main__":
    root = ctk.CTk()
    app = AIportGUI(root)
    root.mainloop()