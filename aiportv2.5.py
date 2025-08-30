import os
import time
import json
import base64
import requests
import pyautogui
import threading
from tkinter import messagebox, scrolledtext, font
import tempfile
from PIL import Image, ImageTk

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

class AIportGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Agent Control")
        self.root.geometry("600x650")
        self.root.configure(fg_color=ONEUI_COLORS["dark_bg"])
        
        self.api_key = ctk.StringVar()
        self.api_provider = ctk.StringVar(value="Gemini")
        self.model = ctk.StringVar()
        self.stop_flag = False
        self.agent_thread = None
        self.last_screenshot_path = None

        main_frame = ctk.CTkFrame(root, fg_color=ONEUI_COLORS["dark_bg"], corner_radius=10)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Large, bold title for the main section, like One UI
        ctk.CTkLabel(main_frame, text="AI Agent Control", font=("Roboto", 24, "bold"), text_color=ONEUI_COLORS["text"]).pack(anchor="w", pady=(0, 20))

        # 1. API Provider
        ctk.CTkLabel(main_frame, text="Select API:", font=("Roboto", 12, "bold"), text_color=ONEUI_COLORS["text"]).pack(anchor="w", pady=(0, 5))
        self.api_provider_combobox = ctk.CTkOptionMenu(main_frame, variable=self.api_provider, values=["Gemini", "OpenRouter", "OpenAI", "Claude"], command=self._on_api_change)
        self.api_provider_combobox.pack(fill="x", pady=(0, 15))

        # 2. API Key
        ctk.CTkLabel(main_frame, text="API Key:", font=("Roboto", 12, "bold"), text_color=ONEUI_COLORS["text"]).pack(anchor="w", pady=(0, 5))
        self.api_key_entry = ctk.CTkEntry(main_frame, textvariable=self.api_key, placeholder_text="Enter your API key", show="*", fg_color=ONEUI_COLORS["widget_bg"])
        self.api_key_entry.pack(fill="x", pady=(0, 15))

        # 3. Model
        ctk.CTkLabel(main_frame, text="Select AI Model:", font=("Roboto", 12, "bold"), text_color=ONEUI_COLORS["text"]).pack(anchor="w", pady=(0, 5))
        self.model_combobox = ctk.CTkOptionMenu(main_frame, variable=self.model, values=["gemini-2.5-flash", "gemini-1.5-pro"])
        self.model_combobox.set("gemini-2.5-flash")
        self.model_combobox.pack(fill="x", pady=(0, 15))

        # 4. Prompt
        ctk.CTkLabel(main_frame, text="Enter command for AI:", font=("Roboto", 12, "bold"), text_color=ONEUI_COLORS["text"]).pack(anchor="w", pady=(0, 5))
        self.prompt_text = scrolledtext.ScrolledText(main_frame, height=8, wrap="word", font=("Roboto", 10),
                                                    bg=ONEUI_COLORS["widget_bg"], fg=ONEUI_COLORS["text"])
        self.prompt_text.pack(fill="x", pady=(0, 15))
        self.prompt_text.insert("1.0", "Find Chrome browser and open google.com")
        
        # New Feature: Load Tutorial from GitHub URL
        ctk.CTkLabel(main_frame, text="Load tutorial from GitHub URL:", font=("Roboto", 12, "bold"), text_color=ONEUI_COLORS["text"]).pack(anchor="w", pady=(0, 5))
        github_frame = ctk.CTkFrame(main_frame, fg_color=ONEUI_COLORS["widget_bg"], corner_radius=10)
        github_frame.pack(fill="x", pady=(0, 15))
        self.github_url_entry = ctk.CTkEntry(github_frame, placeholder_text="e.g., https://raw.githubusercontent.com/user/repo/file.md", fg_color=ONEUI_COLORS["widget_bg"])
        self.github_url_entry.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=5)
        self.load_button = ctk.CTkButton(github_frame, text="Load", command=self.load_tutorial)
        self.load_button.pack(side="right", padx=(5, 10), pady=5)

        # 5. Buttons
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(pady=(0, 15), expand=True, fill="x")
        
        self.start_button = ctk.CTkButton(button_frame, text="▶️ Start", command=self.start_agent)
        self.start_button.pack(side="left", expand=True, padx=5)

        self.stop_button = ctk.CTkButton(button_frame, text="⏹️ Stop", command=self.stop_agent, state="disabled", fg_color="red")
        self.stop_button.pack(side="left", expand=True, padx=5)

        self.view_image_button = ctk.CTkButton(button_frame, text="🖼️ View Screenshot", command=self.view_last_screenshot)
        self.view_image_button.pack(side="left", expand=True, padx=5)

        # 6. Log/Output
        ctk.CTkLabel(main_frame, text="AI activity log:", font=("Roboto", 12, "bold"), text_color=ONEUI_COLORS["text"]).pack(anchor="w", pady=(0, 5))
        self.log_area = scrolledtext.ScrolledText(main_frame, height=15, wrap="word", state="disabled", font=("Roboto Mono", 10),
                                                bg=ONEUI_COLORS["widget_bg"], fg=ONEUI_COLORS["text"])
        self.log_area.pack(fill="both", expand=True)

        self._on_api_change("Gemini")

    def _on_api_change(self, choice):
        if choice == "OpenRouter":
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

    def log(self, message):
        self.log_area.configure(state="normal")
        self.log_area.insert("end", message + "\n")
        self.log_area.configure(state="disabled")
        self.log_area.see("end")
        self.root.update_idletasks()

    def start_agent(self):
        if not self.api_key.get():
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
        self.log("⏹️ Sending stop signal to AI...")
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
    
    def load_tutorial(self):
        url = self.github_url_entry.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a GitHub URL.")
            return

        self.log(f"🔗 Loading tutorial from URL: {url}...")
        try:
            response = requests.get(url)
            response.raise_for_status()
            tutorial_content = response.text
            self.prompt_text.delete("1.0", "end")
            self.prompt_text.insert("end", tutorial_content)
            self.log("✅ Tutorial loaded successfully!")
        except requests.exceptions.RequestException as e:
            self.log(f"❌ Error loading tutorial: {e}")
            messagebox.showerror("Error", f"Failed to load tutorial from URL.\nError: {e}")

    def _encode_image(self, filename):
        with open(filename, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _send_to_gemini(self, img_b64, user_prompt):
        api_key = self.api_key.get()
        model = self.model.get()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        tutorial = """
        You are an AI that controls a computer via JSON. Always return valid JSON, no extra explanation.
        Valid actions:
        - move: { "type":"move","x":int,"y":int }
        - click: { "type":"click","button":"left/right","count":1 }
        - click_down: { "type":"click_down","button":"left/right" }
        - click_up: { "type":"click_up","button":"left/right" }
        - scroll: { "type":"scroll","dx":0,"dy":int }
        - type: { "type":"type","text":"abc" }
        - hotkey: { "type":"hotkey","keys":["ctrl","c"] }
        - multi_click: { "type":"multi_click","x":int,"y":int,"count":int }
        - key_down_for_seconds: { "type":"key_down_for_seconds","key":"key_name","duration":float }
        Always return a JSON array [] with only commands.
        Example:
        [{"type":"move","x":500,"y":300},{"type":"click","button":"left","count":2}]
        """
        payload = {"contents": [{"parts": [{"text": tutorial}, {"inline_data": {"mime_type": "image/png", "data": img_b64}}, {"text": user_prompt}]}]}
        res = requests.post(url, headers=headers, data=json.dumps(payload))
        res.raise_for_status()
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]

    def _send_to_openrouter(self, img_b64, user_prompt):
        api_key = self.api_key.get()
        model = self.model.get()
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        tutorial = """
        You are an AI that controls a computer via JSON. Always return valid JSON, no extra explanation.
        Valid actions:
        - move: { "type":"move","x":int,"y":int }
        - click: { "type":"click","button":"left/right","count":1 }
        - click_down: { "type":"click_down","button":"left/right" }
        - click_up: { "type":"click_up","button":"left/right" }
        - scroll: { "type":"scroll","dx":0,"dy":int }
        - type: { "type":"type","text":"abc" }
        - hotkey: { "type":"hotkey","keys":["ctrl","c"] }
        - multi_click: { "type":"multi_click","x":int,"y":int,"count":int }
        - key_down_for_seconds: { "type":"key_down_for_seconds","key":"key_name","duration":float }
        Always return a JSON array [] with only commands.
        Example:
        [{"type":"move","x":500,"y":300},{"type":"click","button":"left","count":2}]
        """
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
    
    def _send_to_openai(self, img_b64, user_prompt):
        api_key = self.api_key.get()
        model = self.model.get()
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        tutorial = """
        You are an AI that controls a computer via JSON. Always return valid JSON, no extra explanation.
        Valid actions:
        - move: { "type":"move","x":int,"y":int }
        - click: { "type":"click","button":"left/right","count":1 }
        - click_down: { "type":"click_down","button":"left/right" }
        - click_up: { "type":"click_up","button":"left/right" }
        - scroll: { "type":"scroll","dx":0,"dy":int }
        - type: { "type":"type","text":"abc" }
        - hotkey: { "type":"hotkey","keys":["ctrl","c"] }
        - multi_click: { "type":"multi_click","x":int,"y":int,"count":int }
        - key_down_for_seconds: { "type":"key_down_for_seconds","key":"key_name","duration":float }
        Always return a JSON array [] with only commands.
        Example:
        [{"type":"move","x":500,"y":300},{"type":"click","button":"left","count":2}]
        """
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

    def _send_to_claude(self, img_b64, user_prompt):
        api_key = self.api_key.get()
        model = self.model.get()
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        tutorial = """
        You are an AI that controls a computer via JSON. Always return valid JSON, no extra explanation.
        Valid actions:
        - move: { "type":"move","x":int,"y":int }
        - click: { "type":"click","button":"left/right","count":1 }
        - click_down: { "type":"click_down","button":"left/right" }
        - click_up: { "type":"click_up","button":"left/right" }
        - scroll: { "type":"scroll","dx":0,"dy":int }
        - type: { "type":"type","text":"abc" }
        - hotkey: { "type":"hotkey","keys":["ctrl","c"] }
        - multi_click: { "type":"multi_click","x":int,"y":int,"count":int }
        - key_down_for_seconds: { "type":"key_down_for_seconds","key":"key_name","duration":float }
        Always return a JSON array [] with only commands.
        Example:
        [{"type":"move","x":500,"y":300},{"type":"click","button":"left","count":2}]
        """
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


    def _execute_actions(self, actions):
        for action in actions:
            t = action.get("type")
            self.log(f"   - Executing: {t} with {action}")
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
            elif t == "multi_click":
                for _ in range(action.get("count", 2)):
                    pyautogui.click(action["x"], action["y"])
                    time.sleep(0.05)
            elif t == "key_down_for_seconds":
                key = action.get("key")
                duration = action.get("duration", 1.0)
                if key:
                    pyautogui.keyDown(key)
                    self.log(f"   - Holding key: {key} for {duration} seconds")
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
        self.log("▶️ AI agent starting...")
        user_prompt = self.prompt_text.get("1.0", "end").strip()

        temp_dir = tempfile.gettempdir()
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        while not self.stop_flag:
            self._cleanup_temp_files()
            try:
                self.last_screenshot_path = os.path.join(temp_dir, f"screenshot_{int(time.time())}.png")

                self.log(f"\n[1] Taking new screenshot: {self.last_screenshot_path}")
                pyautogui.screenshot(self.last_screenshot_path)
                
                img_b64 = self._encode_image(self.last_screenshot_path)

                self.log("[2] Sending image and command to AI...")

                api_provider = self.api_provider.get()
                if api_provider == "Gemini":
                    response_text = self._send_to_gemini(img_b64, user_prompt)
                elif api_provider == "OpenRouter":
                    response_text = self._send_to_openrouter(img_b64, user_prompt)
                elif api_provider == "OpenAI":
                    response_text = self._send_to_openai(img_b64, user_prompt)
                elif api_provider == "Claude":
                    response_text = self._send_to_claude(img_b64, user_prompt)
                else:
                    self.log("❌ Error: Unsupported API Provider.")
                    break
                
                self.log("[3] AI response:\n" + response_text)

                try:
                    clean_ai_text = response_text.strip().replace("```json", "").replace("```", "")
                    actions = json.loads(clean_ai_text)
                    
                    if not actions:
                        self.log("✅ AI thinks the task is complete. Stopping.")
                        break

                    self.log("[4] Executing actions:")
                    self._execute_actions(actions)
                except Exception as e:
                    self.log(f"❌ Error parsing JSON or executing: {e}")

                time.sleep(2)

            except Exception as e:
                self.log(f"❌ Error in main loop: {e}")
                if "API_KEY_INVALID" in str(e) or "AuthenticationError" in str(e):
                    self.log("ERROR: Invalid API Key. Please check again.")
                elif "404" in str(e):
                    self.log("ERROR: API path not found. You might have selected a model that doesn't support screenshots.")
                    self.log("Please try again with a different model, for example 'gpt-4o'.")
                break
                time.sleep(2)
        
        if self.stop_flag:
             self.log("⏹️ AI stopped by user.")
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
                    self.log(f"Error deleting temporary file {file_path}: {e}")

# ================== RUN ==================
if __name__ == "__main__":
    root = ctk.CTk()
    app = AIportGUI(root)
    root.mainloop()
