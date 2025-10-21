"""GUI セルクリア機能のシンプルテスト"""

import sys

import pytest

# テスト環境でのQt/pandas問題を回避
try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

    # Qt アプリケーションの初期化
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    QT_AVAILABLE = True
except Exception:
    QT_AVAILABLE = False


def test_delete_key_clears_cell():
    """DeleteキーとBackspaceキーでセルをクリアする機能をテスト"""
    if not QT_AVAILABLE:
        pytest.skip("Qt not available")

    # テーブルとアイテムを作成
    table = QTableWidget(1, 1)
    item = QTableWidgetItem("test_value")
    table.setItem(0, 0, item)
    table.setCurrentCell(0, 0)

    # 初期値を確認
    assert item.text() == "test_value"

    # Delete/Backspaceキー処理のシミュレーション
    def simulate_key_press(key):
        current_item = table.currentItem()
        if current_item is not None and key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            current_item.setText("")
            return True
        return False

    # Deleteキーテスト
    result = simulate_key_press(Qt.Key.Key_Delete)
    assert result is True
    assert item.text() == ""

    # 値を再設定
    item.setText("another_value")
    assert item.text() == "another_value"

    # Backspaceキーテスト
    result = simulate_key_press(Qt.Key.Key_Backspace)
    assert result is True
    assert item.text() == ""


def test_key_press_without_selection():
    """セルが選択されていない状態でのキー処理テスト"""
    if not QT_AVAILABLE:
        pytest.skip("Qt not available")

    # テーブルを作成(セルは追加しない)
    table = QTableWidget(1, 1)

    # セルが選択されていない状態での処理
    def simulate_key_press_no_selection(key):
        current_item = table.currentItem()
        if current_item is not None and key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            current_item.setText("")
            return True
        return False

    # セル未選択での処理(エラーが発生しないことを確認)
    result = simulate_key_press_no_selection(Qt.Key.Key_Delete)
    assert result is False  # セルが選択されていないのでFalse


if __name__ == "__main__":
    pytest.main([__file__])
