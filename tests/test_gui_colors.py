"""GUI色付け機能のテスト"""

import sys

import pytest

# テスト環境でのQt/pandas問題を回避
try:
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication, QTableWidgetItem

    # Qt アプリケーションの初期化
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    QT_AVAILABLE = True
except Exception:
    # テスト環境でQt初期化に問題がある場合のフォールバック
    QT_AVAILABLE = False

    # Mock classes for testing without Qt
    class MockQColor:
        def __init__(self, color_str="#000000"):
            self.color_str = color_str

        def __eq__(self, other):
            if isinstance(other, MockQColor):
                return self.color_str == other.color_str
            return False

    class MockQTableWidgetItem:
        def __init__(self, text=""):
            self._text = text
            self._foreground = MockQColor()

        def text(self):
            return self._text

        def setText(self, text):
            self._text = text

        def setForeground(self, color):
            self._foreground = color

        def foreground(self):
            class MockBrush:
                def __init__(self, color):
                    self._color = color

                def color(self):
                    return self._color

            return MockBrush(self._foreground)

    class MockQTableWidget:
        def __init__(self):
            self._rows = 0
            self._cols = 0
            self._items = {}
            self._headers = []

        def rowCount(self):
            return self._rows

        def setRowCount(self, count):
            self._rows = count

        def columnCount(self):
            return self._cols

        def setColumnCount(self, count):
            self._cols = count

        def setItem(self, row, col, item):
            self._items[(row, col)] = item

        def item(self, row, col):
            return self._items.get((row, col))

        def setHorizontalHeaderLabels(self, labels):
            self._headers = labels

        def horizontalHeaderItem(self, col):
            if col < len(self._headers):

                class MockHeaderItem:
                    def __init__(self, text):
                        self._text = text

                    def text(self):
                        return self._text

                return MockHeaderItem(self._headers[col])
            return None

        def resizeColumnsToContents(self):
            pass

        def scrollToBottom(self):
            pass

    QColor = MockQColor
    QTableWidgetItem = MockQTableWidgetItem


class MockMainTab:
    """MainTabのモック実装"""

    def __init__(self):
        if QT_AVAILABLE:
            from PySide6.QtWidgets import QTableWidget

            self.table = QTableWidget()
        else:
            self.table = MockQTableWidget()

    def log_append(self, message: str, color: str | None = None) -> None:
        """ログメッセージをテーブルに追加(MainTab.log_appendのシミュレーション)"""
        current_rows = self.table.rowCount()
        self.table.setRowCount(current_rows + 1)

        # 時刻を追加
        import datetime

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        time_item = QTableWidgetItem(timestamp)
        message_item = QTableWidgetItem(message)

        # 色指定がある場合はテキスト色を設定
        if color:
            message_item.setForeground(QColor(color))

        # 2列のテーブルにする
        if self.table.columnCount() == 0:
            self.table.setColumnCount(2)
            self.table.setHorizontalHeaderLabels(["時刻", "メッセージ"])

        self.table.setItem(current_rows, 0, time_item)
        self.table.setItem(current_rows, 1, message_item)
        self.table.resizeColumnsToContents()
        self.table.scrollToBottom()


class TestGUIColors:
    """GUI色付け機能のテストクラス"""

    def setup_method(self):
        """各テストメソッドの前に実行される設定"""
        self.main_tab = MockMainTab()

    def test_log_append_without_color(self):
        """色指定なしのログ出力テスト"""
        message = "テストメッセージ"
        self.main_tab.log_append(message)

        # テーブルに1行追加されることを確認
        assert self.main_tab.table.rowCount() == 1

        # メッセージが正しく設定されることを確認
        message_item = self.main_tab.table.item(0, 1)
        assert message_item is not None
        assert message_item.text() == message

        # デフォルト色(色が設定されていない状態)であることを確認
        if QT_AVAILABLE:
            # Qtではデフォルトは有効な黒色
            assert message_item.foreground().color().isValid()
        else:
            # Mockでは明示的にデフォルト色をチェック
            assert message_item.foreground().color() == QColor("#000000")

    def test_log_append_with_red_color(self):
        """赤色指定のログ出力テスト(人員不足用)"""
        message = "⚠️ 人員不足が検出されました:"
        color = "#DC143C"  # 赤色

        self.main_tab.log_append(message, color)

        # テーブルに1行追加されることを確認
        assert self.main_tab.table.rowCount() == 1

        # メッセージが正しく設定されることを確認
        message_item = self.main_tab.table.item(0, 1)
        assert message_item is not None
        assert message_item.text() == message

        # 赤色が設定されることを確認
        expected_color = QColor(color)
        actual_color = message_item.foreground().color()
        assert actual_color == expected_color

    def test_log_append_with_orange_color(self):
        """オレンジ色指定のログ出力テスト(ペナルティ用)"""
        message = "ペナルティ詳細:"
        color = "#FF8C00"  # オレンジ色

        self.main_tab.log_append(message, color)

        # テーブルに1行追加されることを確認
        assert self.main_tab.table.rowCount() == 1

        # メッセージが正しく設定されることを確認
        message_item = self.main_tab.table.item(0, 1)
        assert message_item is not None
        assert message_item.text() == message

        # オレンジ色が設定されることを確認
        expected_color = QColor(color)
        actual_color = message_item.foreground().color()
        assert actual_color == expected_color

    def test_multiple_colored_messages(self):
        """複数の色付きメッセージのテスト"""
        messages = [
            ("通常メッセージ", None),
            ("⚠️ 人員不足が検出されました:", "#DC143C"),
            ("ペナルティ詳細:", "#FF8C00"),
            ("通常メッセージ2", None),
        ]

        for message, color in messages:
            self.main_tab.log_append(message, color)

        # 4行追加されることを確認
        assert self.main_tab.table.rowCount() == 4

        # 各行の色が正しく設定されることを確認
        for i, (message, color) in enumerate(messages):
            message_item = self.main_tab.table.item(i, 1)
            assert message_item is not None
            assert message_item.text() == message

            if color:
                expected_color = QColor(color)
                actual_color = message_item.foreground().color()
                assert actual_color == expected_color
            else:
                # デフォルト色
                if QT_AVAILABLE:
                    # Qtではデフォルトは有効な黒色
                    assert message_item.foreground().color().isValid()
                else:
                    # Mockでは明示的にデフォルト色をチェック
                    assert message_item.foreground().color() == QColor("#000000")

    def test_shortage_message_color_consistency(self):
        """人員不足メッセージの色一貫性テスト"""
        shortage_messages = [
            "⚠️ 人員不足が検出されました:",
            "  2025-01-15 HospitalA: 2人不足",
            "  2025-01-16 HospitalB: 1人不足",
        ]

        shortage_color = "#DC143C"

        for message in shortage_messages:
            self.main_tab.log_append(message, shortage_color)

        # 全ての人員不足メッセージが同じ赤色であることを確認
        expected_color = QColor(shortage_color)
        for i in range(len(shortage_messages)):
            message_item = self.main_tab.table.item(i, 1)
            actual_color = message_item.foreground().color()
            assert actual_color == expected_color

    def test_penalty_message_color_consistency(self):
        """ペナルティメッセージの色一貫性テスト"""
        penalty_messages = [
            "ペナルティ詳細:",
            "制約別ペナルティ詳細:",
            "  [制約名] 合計: 10.5",
            "    - 変数名: 5.2 (値:1.0 x 重み:5.2)",
        ]

        penalty_color = "#FF8C00"

        for message in penalty_messages:
            self.main_tab.log_append(message, penalty_color)

        # 全てのペナルティメッセージが同じオレンジ色であることを確認
        expected_color = QColor(penalty_color)
        for i in range(len(penalty_messages)):
            message_item = self.main_tab.table.item(i, 1)
            actual_color = message_item.foreground().color()
            assert actual_color == expected_color

    def test_table_structure_with_colors(self):
        """色付きメッセージでテーブル構造が正しく保たれることをテスト"""
        self.main_tab.log_append("テストメッセージ", "#FF0000")

        # テーブルが2列であることを確認
        assert self.main_tab.table.columnCount() == 2

        # ヘッダーラベルが正しく設定されることを確認
        headers = [
            self.main_tab.table.horizontalHeaderItem(0).text(),
            self.main_tab.table.horizontalHeaderItem(1).text(),
        ]
        assert headers == ["時刻", "メッセージ"]

        # 時刻が設定されることを確認
        time_item = self.main_tab.table.item(0, 0)
        assert time_item is not None
        assert len(time_item.text()) == 8  # HH:MM:SS format


if __name__ == "__main__":
    pytest.main([__file__])
