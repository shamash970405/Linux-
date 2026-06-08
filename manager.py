import os
import shutil
import asyncio
import subprocess
from google import genai
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Markdown, Label, DataTable, OptionList
from textual.widgets.option_list import Option
from textual.screen import ModalScreen
from morefunction import ThemeMenuScreen

# ================= 1. Gemini AI 模組 =================
class GeminiExplainer:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key) if api_key else None

    async def ask_gemini(self, package_name: str) -> str:
        if not self.client:
            return "⚠️ 未偵測到 `GEMINI_API_KEY` 環境變數。"
        prompt = f"請用繁體中文（台灣習慣用語）白話文解釋 Linux 套件 '{package_name}' 的用途，並列出 2 個核心特點。總字數限制在 80 字內。"
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            )
            return response.text
        except Exception as e:
            return f"❌ AI 查詢失敗: {str(e)}"

# ================= 2. ESC 按鍵彈出的控制選單 =================
class EscMenuScreen(ModalScreen):
    """按 ESC 鍵彈出的系統選單"""
    
    CSS = """
    EscMenuScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #esc-container {
        width: 45;
        height: auto;
        background: #1f2335;
        border: thick #ff5555;
        padding: 1;
    }
    #esc-title {
        text-align: center;
        text-style: bold;
        color: #ff9e64;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="esc-container"):
            yield Label("系統控制選單", id="esc-title")
            yield OptionList(
                Option("更改介面主題", id="change_theme"),
                Option("結束並退出程式", id="quit")
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

# ================= 3. 主介面模組 =================
class LinuxPackageManagerApp(App):
    BINDINGS = [
        ("f1", "focus_search", "搜尋選中套件"),
        ("escape", "open_esc_menu", "系統選單"),
        ("ctrl+left", "resize_left_pane(-2)", "縮小左欄"),
        ("ctrl+right", "resize_left_pane(2)", "放大左欄"),
        ("ctrl+up", "resize_bottom_pane(1)", "放大下欄"),
        ("ctrl+down", "resize_bottom_pane(-1)", "縮小下欄"),
    ]
    
    CSS = """
    Screen { background: #1a1b26; layout: vertical; }
    .top-box { height: 40%; layout: horizontal; border-bottom: solid #3b4261; }
    .left-pane { width: 40%; border-right: solid #3b4261; padding: 1; }
    .right-pane { width: 1fr; padding: 1; background: #1f2335; }
    .bottom-pane { height: 60%; padding: 1; background: #16161e; }
    .status-label { color: #7aa2f7; }
    .disk-label { color: #e0af68; margin-top: 1; }
    .section-title { color: #bb9af3; text-style: bold; margin-bottom: 1; }
    #pkg-input { margin-bottom: 1; }
    DataTable { height: 1fr; border: solid #292e42; }
    """

    def __init__(self):
        super().__init__()
        self.ENABLE_COMMAND_PALETTE = False
        
        # 💡 ✨ 就是漏了這行！請把它補上去，把 AI 通靈模組綁定回主程式
        self.ai = GeminiExplainer()

        # 全自動硬體環境偵測
        self.sys_status = {
            "pacman": shutil.which("pacman") is not None,
            "apt": shutil.which("apt") is not None,
            "snap": shutil.which("snap") is not None
        }
        self.left_pane_width = 40
        self.bottom_pane_height = 60
        self.sort_descending = True
        self.raw_packages = []

    def parse_size_to_bytes(self, size_str: str) -> float:
        clean_str = size_str.replace("[bold #e0af68]", "").replace("[/bold #e0af68]", "")
        clean_str = clean_str.replace("[b white on #ff5555]", "").replace("[/b white on #ff5555]", "").strip().lower()
        if "未知" in clean_str or not clean_str: return 0.0
        try:
            parts = clean_str.split()
            number = float(parts[0])
            unit = parts[1] if len(parts) > 1 else ""
            if "tb" in unit or "t" == unit: return number * (1024 ** 4)
            elif "gb" in unit or "g" == unit: return number * (1024 ** 3)
            elif "mb" in unit or "m" == unit: return number * (1024 ** 2)
            elif "kb" in unit or "k" in unit: return number * 1024
            return number
        except Exception: return 0.0

    def get_disk_info(self) -> str:
        try:
            total, used, free = shutil.disk_usage("/")
            total_gb = total / (1024 ** 3)
            used_gb = used / (1024 ** 3)
            free_gb = free / (1024 ** 3)
            used_percent = (used / total) * 100
            bar_length = 20
            filled_length = int(round(bar_length * used / float(total)))
            bar_color = "red" if used_percent > 85 else ("yellow" if used_percent > 60 else "green")
            bar = f"[{bar_color}]" + "█" * filled_length + f"[/{bar_color}]" + "░" * (bar_length - filled_length)
            return (
                f"💾 系統容量狀態 (根目錄 /)：\n"
                f"  {bar}  {used_percent:.1f}%\n"
                f"  - 總大小: {total_gb:.1f} GB\n"
                f"  - 已使用: {used_gb:.1f} GB\n"
                f"  - 剩餘可用: [bold green]{free_gb:.1f} GB[/bold green]"
            )
        except Exception: return "💾 系統容量狀態: 無法讀取"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(classes="top-box", id="top-box"):
            with Vertical(classes="left-pane", id="left-pane"):
                yield Label("🔍 系統環境偵測：", classes="section-title")
                status_text = "\n".join(f"  - {mgr}: {'✅ 可用' if avail else '❌ 未安裝'}" for mgr, avail in self.sys_status.items())
                yield Label(status_text, classes="status-label")
                yield Label(self.get_disk_info(), classes="disk-label")
            with Vertical(classes="right-pane"):
                yield Label("🤖 Gemini AI 智慧解說與查詢：", classes="section-title")
                yield Input(placeholder="在此輸入套件名稱，下方將自動高亮定位...", id="pkg-input")
                yield Markdown("等待輸入中...", id="ai-output")
        with Vertical(classes="bottom-pane", id="bottom-pane"):
            yield Label("📦 全通路已安裝套件 (點擊欄位切換排序)：", classes="section-title")
            yield DataTable(id="installed-packages-table")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one("#installed-packages-table", DataTable)
        table.cursor_type = "row"
        table.add_column("來源", width=12)
        table.add_column("套件名稱", width=40)
        table.add_column("目前版本", width=25)
        table.add_column("佔用容量", width=18)
        asyncio.create_task(self.load_installed_packages())

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        # 📊 點擊「套件名稱」欄位 (Index 為 1)
        if event.column_index == 1:
            # 借用原本的布林值來切換：True 代表 A~Z，False 代表 Z~A
            self.sort_descending = not self.sort_descending
            current_input = self.query_one("#pkg-input", Input).value
            self.refresh_table_view(highlight_keyword=current_input, sort_by="name")
            self.notify(f"🔤 已切換名稱排序 (由{'A到Z' if self.sort_descending else 'Z到A'})")
            
        # 📊 點擊「佔用容量」欄位 (Index 為 3)
        elif event.column_index == 3:
            self.sort_descending = not self.sort_descending
            current_input = self.query_one("#pkg-input", Input).value
            self.refresh_table_view(highlight_keyword=current_input, sort_by="size")
            self.notify(f"📊 已切換容量排序 (由{'大到小' if self.sort_descending else '小到大'})")

    async def load_installed_packages(self) -> None:
        table = self.query_one("#installed-packages-table", DataTable)
        table.clear()
        self.raw_packages = []

        tasks = []
        if self.sys_status["pacman"]: tasks.append(self._scan_pacman())
        if self.sys_status["apt"]: tasks.append(self._scan_apt())
        if self.sys_status["snap"]: tasks.append(self._scan_snap())

        if tasks:
            await asyncio.gather(*tasks)

        self.refresh_table_view()

    async def _scan_pacman(self):
        try:
            process = await asyncio.create_subprocess_exec("pacman", "-Qi", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, _ = await process.communicate()
            if process.returncode == 0:
                package_blocks = stdout.decode().strip().split("\n\n")
                for block in package_blocks:
                    name, version, size = None, None, "未知"
                    for line in block.split("\n"):
                        if "名稱" in line or "Name" in line: name = line.split(":", 1)[1].strip() if ":" in line else name
                        elif "版本" in line or "Version" in line: version = line.split(":", 1)[1].strip() if ":" in line else version
                        elif "大小" in line or "Size" in line: size = line.split(":", 1)[1].strip() if ":" in line else size
                    if name and version:
                        display_size = size.replace("KiB", "KB").replace("MiB", "MB").replace("GiB", "GB").replace("TiB", "TB")
                        self.raw_packages.append({"manager": "pacman", "name": name, "version": version, "size": display_size})
        except Exception: pass

    async def _scan_apt(self):
        try:
            process = await asyncio.create_subprocess_exec(
                "dpkg-query", "-W", "-f=${Status}\t${Package}\t${Version}\t${Installed-Size}\n",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            if process.returncode == 0:
                for line in stdout.decode().strip().split("\n"):
                    parts = line.split("\t")
                    if len(parts) >= 4 and "install ok installed" in parts[0]:
                        name, version, raw_size = parts[1], parts[2], parts[3].strip()
                        if raw_size and raw_size.isdigit():
                            size_kb = float(raw_size)
                            display_size = f"{size_kb / 1024:.2f} MB" if size_kb > 1024 else f"{size_kb:.2f} KB"
                        else: display_size = "未知"
                        self.raw_packages.append({"manager": "apt", "name": name, "version": version, "size": display_size})
        except Exception: pass

    async def _scan_snap(self):
        try:
            process = await asyncio.create_subprocess_exec("snap", "list", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, _ = await process.communicate()
            if process.returncode == 0:
                lines = stdout.decode().strip().split("\n")
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 3:
                        name = parts[0]
                        version = parts[1]
                        self.raw_packages.append({"manager": "snap", "name": name, "version": version, "size": "沙盒管理"})
        except Exception: pass

    def refresh_table_view(self, highlight_keyword: str = "", sort_by: str = "size") -> None:
        table = self.query_one("#installed-packages-table", DataTable)
        table.clear()
        
        # 🎯 根據點擊的欄位，執行不同的排序
        if sort_by == "name":
            # 照套件名稱字母排序 (A~Z 或 Z~A)
            # 因為 A~Z 是正序，所以 reverse 要帶入與 self.sort_descending 相反的值
            self.raw_packages.sort(key=lambda x: x["name"].lower(), reverse=not self.sort_descending)
        else:
            # 照容量大小排序 (原本的邏輯)
            self.raw_packages.sort(key=lambda x: self.parse_size_to_bytes(x["size"]), reverse=self.sort_descending)
            
        target = highlight_keyword.strip().lower()
        matched_row_key = None

        # 🔄 下方的渲染表格迴圈 (完全不用動，維持原樣)
        for pkg in self.raw_packages:
            if pkg["manager"] == "pacman": mgr_style = "[b green]pacman[/b green]"
            elif pkg["manager"] == "apt": mgr_style = "[b cyan]apt[/b cyan]"
            elif pkg["manager"] == "snap": mgr_style = "[b #ff79c6]snap[/b #ff79c6]"
            else: mgr_style = pkg["manager"]

            is_match = target and (target == pkg["name"].lower() or target in pkg["name"].lower())
            if is_match:
                row_key = table.add_row(
                    f"[b white on #ff5555]{pkg['manager']}[/b white on #ff5555]",
                    f"[b white on #ff5555]{pkg['name']}[/b white on #ff5555]",
                    f"[b white on #ff5555]{pkg['version']}[/b white on #ff5555]",
                    f"[b white on #ff5555]{pkg['size']}[/b white on #ff5555]"
                )
                matched_row_key = row_key
            else:
                table.add_row(mgr_style, pkg["name"], pkg["version"], f"[bold #e0af68]{pkg['size']}[/bold #e0af68]")
                
        if matched_row_key:
            try:
                row_index = table.get_row_index(matched_row_key)
                table.cursor_coordinate = (row_index, 1)
                table.scroll_to_row(row_index)
            except Exception: pass

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = self.query_one("#installed-packages-table", DataTable)
        row_data = table.get_row(event.row_key)
        
        # 🧼 萬用純 Python 黑魔法：用正規表達式把所有 [...] 形式的標籤通通洗掉！
        import re
        def clean_markup(text_str: str) -> str:
            # 這行會把所有像 [b green] 或 [/b white on #ff5555] 的標籤直接抹消
            return re.sub(r'\[\/?[a-zA-Z0-9#\s_@-]+\]', '', text_str).strip()
        
        raw_mgr = clean_markup(str(row_data[0]))
        package_name = clean_markup(str(row_data[1]))
        
        # 🤖 動作 1：同時在右側呼叫 Gemini AI 進行智慧解說
        markdown_widget = self.query_one("#ai-output", Markdown)
        markdown_widget.update(f"⏳ 正在幫您通靈已安裝的 `{package_name}`...")
        asyncio.create_task(self.update_ai_pane(package_name, markdown_widget))

        # 🚪 動作 2：核心功能：根據不同來源調用專屬終端機進行解除安裝
        self.notify(f"🛠️ 正在準備為您卸載 {raw_mgr} 套件：{package_name}")
        
        if raw_mgr == "pacman":
            uninstall_cmd = f"sudo pacman -Rns {package_name}"
        elif raw_mgr == "apt":
            uninstall_cmd = f"sudo apt purge -y {package_name}"
        elif raw_mgr == "snap":
            uninstall_cmd = f"sudo snap remove {package_name}"
        else:
            uninstall_cmd = f"echo '未知的套件來源，無法自動刪除'"

        terminal_cmd = None
        common_terminals = ["konsole", "gnome-terminal", "xfce4-terminal", "kitty", "alacritty", "xterm"]
        for term in common_terminals:
            if shutil.which(term) is not None:
                terminal_cmd = term
                break

        try:
            if terminal_cmd == "gnome-terminal":
                # GNOME 終端機 (Ubuntu 預設) 的新版命令格式
                subprocess.Popen([
                    "gnome-terminal", "--", "bash", "-c",
                    f"{uninstall_cmd}; echo; echo \"=============================\"; read -p \"卸載程序執行完畢，按 [Enter] 鍵關閉視窗...\""
                ])
            elif terminal_cmd in ["konsole", "xfce4-terminal", "kitty", "alacritty", "xterm"]:
                # KDE Konsole (你的 Arch 預設) 與其他終端機的通用 -e 格式
                subprocess.Popen([
                    terminal_cmd, "-e", 
                    f"bash -c '{uninstall_cmd}; echo; echo \"=============================\"; read -p \"卸載程序執行完畢，按 [Enter] 鍵關閉視窗...\"'"
                ])
            else:
                # 🛡️ 終極防呆：背景靜默執行
                self.notify("⚠️ 系統未偵測到主流終端機，改由背景嘗試安全解除安裝...", severity="warning")
                subprocess.Popen(["bash", "-c", uninstall_cmd])

            # 刪除完後，自動在 3 秒後重新整理表格
            async def delayed_refresh():
                await asyncio.sleep(3)
                await self.load_installed_packages()
                self.notify("🔄 已自動為您刷新全通路套件清單！")

            asyncio.create_task(delayed_refresh())

        except Exception as e:
            self.notify(f"❌ 無法開啟外部終端機: {str(e)}", severity="error")


    async def update_ai_pane(self, package_name, widget):
        ai_response = await self.ai.ask_gemini(package_name)
        widget.update(ai_response)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        pkg_name = event.value.strip()
        if not pkg_name:
            self.refresh_table_view()
            return
        markdown_widget = self.query_one("#ai-output", Markdown)
        markdown_widget.update(f"⏳ 正在分析 `{pkg_name}`...")
        self.refresh_table_view(highlight_keyword=pkg_name)
        ai_response = await self.ai.ask_gemini(pkg_name)
        markdown_widget.update(ai_response)

    def action_resize_left_pane(self, delta: int) -> None:
        self.left_pane_width = max(20, min(70, self.left_pane_width + delta))
        self.query_one("#left-pane").styles.width = f"{self.left_pane_width}%"

    def action_resize_bottom_pane(self, delta: int) -> None:
        self.bottom_pane_height = max(20, min(80, self.bottom_pane_height + delta))
        self.query_one("#bottom-pane").styles.height = f"{self.bottom_pane_height}%"
        self.query_one("#top-box").styles.height = f"{100 - self.bottom_pane_height}%"

    def action_focus_search(self) -> None:
        try:
            table = self.query_one("#installed-packages-table", DataTable)
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            row_data = table.get_row(row_key)
            package_name = row_data[1].replace("[b white on #ff5555]", "").replace("[/b white on #ff5555]", "").strip()
            search_input = self.query_one("#pkg-input", Input)
            search_input.value = package_name
            search_input.focus()
            self.refresh_table_view(highlight_keyword=package_name)
            self.notify(f"🔍 已自動鎖定並搜尋：{package_name}")
        except Exception:
            self.query_one("#pkg-input", Input).focus()

    def action_open_esc_menu(self) -> None:
        def handle_esc_callback(action: str) -> None:
            if action == "change_theme":
                def apply_theme_callback(new_css: str) -> None:
                    if new_css:
                        self.app.css = new_css
                        self.refresh()
                        self.notify("🎨 佈景主題切換成功！")
                self.push_screen(ThemeMenuScreen(), apply_theme_callback)
            elif action == "quit":
                self.action_quit()
        self.push_screen(EscMenuScreen(), handle_esc_callback)

if __name__ == "__main__":
    app = LinuxPackageManagerApp()
    app.run()