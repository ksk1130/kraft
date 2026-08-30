#!/usr/bin/env python
"""自前の file_editor ツールの動作をテストする。"""
from pathlib import Path

from kraft.tools.file_editor_wrapper import file_editor


def test_file_editor_wrapper_round_trip(tmp_path):
    """create/view/edit/delete の基本パターンを確認する。"""
    target = tmp_path / "notes.txt"

    create_result = file_editor("create {} with hello world".format(target))
    assert "作成" in create_result
    assert target.exists()

    view_result = file_editor(f"view {target}")
    assert "hello world" in view_result

    edit_result = file_editor(f"edit {target} with hello -> goodbye")
    assert "編集" in edit_result
    assert "goodbye world" in file_editor(f"view {target}")

    delete_result = file_editor(f"delete {target}")
    assert "削除" in delete_result
    assert not target.exists()

