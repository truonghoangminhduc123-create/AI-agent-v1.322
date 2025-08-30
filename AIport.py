import os
import time
import json
import base64
import requests
import pyautogui
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import tempfile
from PIL import Image, ImageTk

# =================================================================
# GIAO DIỆN VÀ LOGIC TÍCH HỢM
# =================================================================

class AIportGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Agent Control")
        self.root.geometry("600x650")
        self.root.configure(bg="#2c2c2c") 

        self.api_key = tk.StringVar()
        self.api_provider = tk.StringVar(value="Gemini")
        self.model = tk.StringVar()
        self.stop_flag = False
        self.agent_thread = None
        self.last_screenshot_path = None

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#2c2c2c")
        style.configure("TLabel", background="#2c2c2c", foreground="#e0e0e0")
        style.configure("TButton", background="#555555", foreground="#ffffff", font=("Helvetica", 10, "bold"), borderwidth=0, focusthickness=3, focuscolor='none')
        style.map("TButton", background=[('active', '#777777')])
        style.configure("TEntry", background="#444444", foreground="#e0e0e0", borderwidth=0)
        style.configure("TScrolledtext", background="#444444", foreground="#e0e0e0", borderwidth=0)
        style.configure("TCombobox", background="#444444", foreground="#e0e0e0")
        
        main_frame = ttk.Frame(root, padding=15)
        main_frame.pack(fill="both", expand=True)

        # 1. Chọn API
        ttk.Label(main_frame, text="Chọn API:").grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.api_provider_combobox = ttk.Combobox(main_frame, textvariable=self.api_provider, state="readonly")
        self.api_provider_combobox["values"] = ("Gemini", "OpenRouter")
        self.api_provider_combobox.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        self.api_provider_combobox.bind("<<ComboboxSelected>>", self._on_api_change)

        # 2. API Key
        ttk.Label(main_frame, text="API Key:").grid(row=2, column=0, sticky="w", pady=(0, 5))
        self.api_key_entry = ttk.Entry(main_frame, textvariable=self.api_key, width=70, show="*")
        self.api_key_entry.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 15))

        # 3. Chọn mô hình
        ttk.Label(main_frame, text="Chọn Mô hình AI:").grid(row=4, column=0, sticky="w", pady=(0, 5))
        self.model_combobox = ttk.Combobox(main_frame, textvariable=self.model, state="readonly")
        self.model_combobox["values"] = ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro")
        self.model_combobox.current(0)
        self.model_combobox.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 15))

        # 4. Lệnh cho AI
        ttk.Label(main_frame, text="Nhập lệnh cho AI:").grid(row=6, column=0, sticky="w", pady=(0, 5))
        self.prompt_text = scrolledtext.ScrolledText(main_frame, height=8, wrap=tk.WORD, font=("Helvetica", 10))
        self.prompt_text.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        self.prompt_text.insert(tk.END, "Tìm trình duyệt Chrome và mở trang google.com")

        # 5. Nút điều khiển
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=2, pady=(0, 15))
        
        self.start_button = ttk.Button(button_frame, text="▶️ Bắt đầu", command=self.start_agent)
        self.start_button.pack(side="left", padx=10)

        self.stop_button = ttk.Button(button_frame, text="⏹️ Dừng", command=self.stop_agent, state="disabled")
        self.stop_button.pack(side="left", padx=10)

        self.view_image_button = ttk.Button(button_frame, text="🖼️ Xem Ảnh Chụp", command=self.view_last_screenshot)
        self.view_image_button.pack(side="left", padx=10)

        # 6. Log/Output
        ttk.Label(main_frame, text="Log hoạt động của AI:").grid(row=9, column=0, sticky="w", pady=(0, 5))
        self.log_area = scrolledtext.ScrolledText(main_frame, height=15, wrap=tk.WORD, state="disabled", bg="#f0f0f0")
        self.log_area.grid(row=10, column=0, columnspan=2, sticky="nsew")

        main_frame.grid_rowconfigure(10, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

    def _on_api_change(self, event=None):
        api_provider = self.api_provider.get()
        if api_provider == "OpenRouter":
            self.model_combobox["values"] = (
                "openrouter/cinematika-7b",
                "google/gemini-flash-1.5-preview", 
                "mistralai/mixtral-8x7b-instruct",
                "nousresearch/nous-hermes-2-mixtral-8x7b-dpo"
            )
            self.model.set("openrouter/cinematika-7b")
        elif api_provider == "Gemini":
            self.model_combobox["values"] = (
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-1.0-pro"
            )
            self.model.set("gemini-2.5-flash")

    def log(self, message):
        self.log_area.configure(state="normal")
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.configure(state="disabled")
        self.log_area.see(tk.END)
        self.root.update_idletasks()

    def start_agent(self):
        if not self.api_key.get():
            messagebox.showerror("Lỗi", "Vui lòng nhập API Key!")
            return
        if not self.prompt_text.get("1.0", tk.END).strip():
            messagebox.showerror("Lỗi", "Vui lòng nhập lệnh cho AI!")
            return

        self.stop_flag = False
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", tk.END)
        self.log_area.configure(state="disabled")

        self.agent_thread = threading.Thread(target=self._run_agent_loop, daemon=True)
        self.agent_thread.start()

    def stop_agent(self):
        self.stop_flag = True
        self.log("⏹️ Đang gửi tín hiệu dừng tới AI...")
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")

    def _encode_image(self, filename):
        with open(filename, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _send_to_gemini(self, img_b64, user_prompt):
        api_key = self.api_key.get()
        model = self.model.get()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        tutorial = """
        Bạn là AI điều khiển máy tính qua JSON. Luôn luôn trả về JSON hợp lệ, không giải thích thêm.
        Các action hợp lệ:
        - move: { "type":"move","x":int,"y":int }
        - click: { "type":"click","button":"left/right","count":1 }
        - click_down: { "type":"click_down","button":"left/right" }
        - click_up: { "type":"click_up","button":"left/right" }
        - scroll: { "type":"scroll","dx":0,"dy":int }
        - type: { "type":"type","text":"abc" }
        - hotkey: { "type":"hotkey","keys":["ctrl","c"] }
        - multi_click: { "type":"multi_click","x":int,"y":int,"count":int }
        - key_down_for_seconds: { "type":"key_down_for_seconds","key":"key_name","duration":float }
        Luôn trả về mảng JSON [] chỉ chứa lệnh.
        Ví dụ:
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
        Bạn là AI điều khiển máy tính qua JSON. Luôn luôn trả về JSON hợp lệ, không giải thích thêm.
        Các action hợp lệ:
        - move: { "type":"move","x":int,"y":int }
        - click: { "type":"click","button":"left/right","count":1 }
        - click_down: { "type":"click_down","button":"left/right" }
        - click_up: { "type":"click_up","button":"left/right" }
        - scroll: { "type":"scroll","dx":0,"dy":int }
        - type: { "type":"type","text":"abc" }
        - hotkey: { "type":"hotkey","keys":["ctrl","c"] }
        - multi_click: { "type":"multi_click","x":int,"y":int,"count":int }
        - key_down_for_seconds: { "type":"key_down_for_seconds","key":"key_name","duration":float }
        Luôn trả về mảng JSON [] chỉ chứa lệnh.
        Ví dụ:
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

    def _execute_actions(self, actions):
        for action in actions:
            t = action.get("type")
            self.log(f"   - Thực thi: {t} với {action}")
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
                    self.log(f"   - Giữ phím: {key} trong {duration} giây")
                    time.sleep(duration)
                    pyautogui.keyUp(key)
            time.sleep(0.5)

    def view_last_screenshot(self):
        if not self.last_screenshot_path or not os.path.exists(self.last_screenshot_path):
            messagebox.showinfo("Thông báo", "Chưa có ảnh chụp màn hình nào.")
            return

        view_window = tk.Toplevel(self.root)
        view_window.title("Ảnh Chụp Màn Hình")
        
        img = Image.open(self.last_screenshot_path)
        max_size = (800, 600)
        img.thumbnail(max_size)
        
        tk_img = ImageTk.PhotoImage(img)
        
        label = ttk.Label(view_window, image=tk_img)
        label.image = tk_img
        label.pack()

        close_button = ttk.Button(view_window, text="Đóng", command=view_window.destroy)
        close_button.pack(pady=10)

    def _run_agent_loop(self):
        self.log("▶️ AI bắt đầu điều khiển...")
        user_prompt = self.prompt_text.get("1.0", tk.END).strip()

        temp_dir = tempfile.gettempdir()
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        while not self.stop_flag:
            self._cleanup_temp_files()
            try:
                self.last_screenshot_path = os.path.join(temp_dir, f"screenshot_{int(time.time())}.png")

                self.log(f"\n[1] Chụp ảnh màn hình mới: {self.last_screenshot_path}")
                pyautogui.screenshot(self.last_screenshot_path)
                
                img_b64 = self._encode_image(self.last_screenshot_path)

                self.log("[2] Gửi ảnh và lệnh tới AI...")

                api_provider = self.api_provider.get()
                if api_provider == "Gemini":
                    response_text = self._send_to_gemini(img_b64, user_prompt)
                elif api_provider == "OpenRouter":
                    response_text = self._send_to_openrouter(img_b64, user_prompt)
                else:
                    self.log("❌ Lỗi: API Provider không được hỗ trợ.")
                    break
                
                self.log("[3] AI phản hồi:\n" + response_text)

                try:
                    clean_ai_text = response_text.strip().replace("```json", "").replace("```", "")
                    actions = json.loads(clean_ai_text)
                    
                    if not actions:
                        self.log("✅ AI cho rằng đã hoàn thành nhiệm vụ. Dừng lại.")
                        break

                    self.log("[4] Thực thi các hành động:")
                    self._execute_actions(actions)
                except Exception as e:
                    self.log(f"❌ Lỗi khi phân tích JSON hoặc thực thi: {e}")

                time.sleep(2)

            except Exception as e:
                self.log(f"❌ Lỗi trong vòng lặp chính: {e}")
                if "API_KEY_INVALID" in str(e) or "AuthenticationError" in str(e):
                    self.log("LỖI: API Key không hợp lệ. Vui lòng kiểm tra lại.")
                elif "404" in str(e):
                    self.log("LỖI: Đường dẫn API không tìm thấy. Có thể do bạn đã chọn một mô hình không hỗ trợ ảnh chụp màn hình.")
                    self.log("Vui lòng thử lại với một mô hình khác, ví dụ như 'openrouter/cinematika-7b'.")
                break
                time.sleep(2)
        
        if self.stop_flag:
             self.log("⏹️ AI đã dừng bởi người dùng.")
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
                    self.log(f"Lỗi khi xóa file tạm {file_path}: {e}")

# ================== RUN ==================
if __name__ == "__main__":
    root = tk.Tk()
    app = AIportGUI(root)
    root.mainloop()
