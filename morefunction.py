# morefunction.py
from textual.app import ComposeResult
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option
from textual.containers import Vertical
from textual.screen import ModalScreen
import theme  # 引入剛改好的純字串 Theme.py

class ThemeMenuScreen(ModalScreen):
    """自訂的主題切換跳窗"""
    
    CSS = """
    ThemeMenuScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }
    #theme-container {
        width: 40;
        height: auto;
        background: #1f2335;
        border: thick #7aa2f7;
        padding: 1;
    }
    #theme-title {
        text-align: center;
        text-style: bold;
        color: #e0af68;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="theme-container"):
            yield Label("🎨 請選擇介面佈景主題", id="theme-title")
            yield OptionList(
                Option("🗼 Tokyo Night (東京暗夜)", id="tokyo"),
                Option("🧛 Dracula (吸血鬼暗黑)", id="dracula"),
                Option("❄️ Nord (北歐冰雪藍灰)", id="nord")
            )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        theme_choice = event.option.id
        
        # 🎯 滿血進化：只回傳安全的純文字字串，徹底拔除變數找不到的閃退引信！
        if theme_choice == "tokyo":
            self.dismiss("tokyonight")
        elif theme_choice == "dracula":
            self.dismiss("dracula")
        elif theme_choice == "nord":
            self.dismiss("nord")
        else:
            self.dismiss("")