import os
import shutil
import asyncio
import subprocess
import Theme
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
            yield Label("⚙️ 系統控制選單", id="esc-title")
            yield OptionList(
                Option("🎨 更改介面主題", id="change_theme"),
                Option("🚪 結束並退出程式", id="quit")
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

# ================= 3. 主介面模組 =================
class LinuxPackageManagerApp(App):
    # 📥 重新精簡過的快捷鍵綁定
    BINDINGS = [
        ("f1", "focus_search", "🔍 搜尋選中套件"),
        ("escape", "open_esc_menu", "⚙️ 系統選單"),
        ("ctrl+left", "resize_left_pane(-2)", "⬅️ 縮小左欄"),
        ("ctrl+right", "resize_left_pane(2)", "➡️ 放大左欄"),
        ("ctrl+up", "resize_bottom_pane(1)", "🔼 放大下欄"),
        ("ctrl+down", "resize_bottom_pane(-1)", "🔽 縮小下欄"),
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

        self.ai = GeminiExplainer()

        self.sys_status = {
            "apt": shutil.which("apt") is not None,
            "pacman": shutil.which("pacman") is not None,
            "snap": shutil.which("snap") is not None
        }
        self.left_pane_width = 40
        self.bottom_pane_height = 60
        self.sort_descending = True
        self.raw_packages = []

    def parse_size_to_bytes(self, size_str: str) -> float:
        clean_str = size_str.replace("[bold #e0af68]", "").replace("[/bold #e0af68]", "")
        clean_str = clean_str.replace("[b white on #ff5555]", "").replace("[/b white on #ff5555]", "")
        clean_str = clean_str.strip().lower()
        if "未知" in clean_str or not clean_str: return 0.0
        try:
            parts = clean_str.split()
            number = float(parts[0])
            unit = parts[1] if len(parts) > 1 else ""
            if "tb" in unit or "t" == unit: return number * 1024 * 1024 * 1024 * 1024
            elif "gb" in unit or "g" == unit: return number * 1024 * 1024 * 1024
            elif "mb" in unit or "m" == unit: return number * 1024 * 1024
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
            yield Label("📦 已安裝套件 (點擊標題可切換排序)：", classes="section-title")
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
        if event.column_index == 3:
            self.sort_descending = not self.sort_descending
            current_input = self.query_one("#pkg-input", Input).value
            self.refresh_table_view(highlight_keyword=current_input)
            self.notify(f"📊 已切換容量排序 (由{'大到小' if self.sort_descending else '小到大'})")

    async def load_installed_packages(self) -> None:
        table = self.query_one("#installed-packages-table", DataTable)
        table.clear()
        self.raw_packages = []
        if self.sys_status["pacman"]:
            try:
                process = await asyncio.create_subprocess_exec("pacman", "-Qi", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, _ = await process.communicate()
                if process.returncode == 0:
                    raw_data = stdout.decode()
                    package_blocks = raw_data.strip().split("\n\n")
                    for block in package_blocks:
                        name, version, size = None, None, "未知"
                        for line in block.split("\n"):
                            if "名稱" in line or "Name" in line: name = line.split(":", 1)[1].strip() if ":" in line else name
                            elif "版本" in line or "Version" in line: version = line.split(":", 1)[1].strip() if ":" in line else version
                            elif "大小" in line or "Size" in line: size = line.split(":", 1)[1].strip() if ":" in line else size
                        if name and version:
                            display_size = size.replace("KiB", "KB").replace("MiB", "MB").replace("GiB", "GB").replace("TiB", "TB")
                            self.raw_packages.append({"manager": "pacman", "name": name, "version": version, "size": display_size})
                    self.refresh_table_view()
            except Exception as e:
                table.add_row("錯誤", "無法讀取 pacman 清單", str(e), "-")

    def refresh_table_view(self, highlight_keyword: str = "") -> None:
        table = self.query_one("#installed-packages-table", DataTable)
        table.clear()
        self.raw_packages.sort(key=lambda x: self.parse_size_to_bytes(x["size"]), reverse=self.sort_descending)
        target = highlight_keyword.strip().lower()
        matched_row_key = None

        for pkg in self.raw_packages:
            is_match = target and (target == pkg["name"].lower() or target in pkg["name"].lower())
            if is_match:
                manager_str = f"[b white on #ff5555]{pkg['manager']}[/b white on #ff5555]"
                name_str = f"[b white on #ff5555]{pkg['name']}[/b white on #ff5555]"
                version_str = f"[b white on #ff5555]{pkg['version']}[/b white on #ff5555]"
                size_str = f"[b white on #ff5555]{pkg['size']}[/b white on #ff5555]"
                row_key = table.add_row(manager_str, name_str, version_str, size_str)
                matched_row_key = row_key
            else:
                table.add_row("[b green]pacman[/b green]", pkg["name"], pkg["version"], f"[bold #e0af68]{pkg['size']}[/bold #e0af68]")
        if matched_row_key:
            try:
                row_index = table.get_row_index(matched_row_key)
                table.cursor_coordinate = (row_index, 1)
                table.scroll_to_row(row_index)
            except Exception: pass

    # 💡 點擊套件改為「純呼叫 AI 解說」，徹底移除直接開外部終端機刪除套件的危險功能！
    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table = self.query_one("#installed-packages-table", DataTable)
        row_data = table.get_row(event.row_key)
        package_name = row_data[1].replace("[b white on #ff5555]", "").replace("[/b white on #ff5555]", "").strip()
        markdown_widget = self.query_one("#ai-output", Markdown)
        markdown_widget.update(f"⏳ 正在幫您通靈已安裝的 `{package_name}`...")
        asyncio.create_task(self.update_ai_pane(package_name, markdown_widget))

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

    # ✨ 核心功能 1：按一下套件再按 F1，直接把名稱塞入右上角搜尋框並聚焦
    def action_focus_search(self) -> None:
        try:
            table = self.query_one("#installed-packages-table", DataTable)
            cursor_row = table.cursor_coordinate.row
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            row_data = table.get_row(row_key)
            
            # 清理 Rich 標籤，拿到乾淨的套件名稱
            package_name = row_data[1].replace("[b white on #ff5555]", "").replace("[/b white on #ff5555]", "").strip()
            
            # 連動到右上角搜尋框
            search_input = self.query_one("#pkg-input", Input)
            search_input.value = package_name
            search_input.focus()
            
            # 自動觸發高亮重新整理
            self.refresh_table_view(highlight_keyword=package_name)
            self.notify(f"🔍 已自動鎖定並搜尋：{package_name}")
        except Exception:
            # 如果表格還沒載入完或游標沒對準，就直接聚焦空白搜尋框
            self.query_one("#pkg-input", Input).focus()

    # ✨ 核心功能 2：按一下 ESC 鍵跳出控制選單
    def action_open_esc_menu(self) -> None:
        def handle_esc_callback(action: str) -> None:
            if action == "change_theme":
                # 👉 當第二層選單回傳一整串 CSS 字串時
                def apply_theme_callback(new_css: str) -> None:
                    if new_css:
                        # 💥 萬用老版本寫法：直接將新樣式強制灌進主程式的 CSS 屬性中
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