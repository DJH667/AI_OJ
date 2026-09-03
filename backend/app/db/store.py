"""全 JSON 文件存储层。

需求文档 §4（用户决策 dec-0f895a1ddd678090）：全 JSON 文件——
题目每题一个 JSON、用户/提交/日志以 JSON 条目存于各自目录；
reset 清空即删目录内文件重建。数据量小且评测单用户串行，无并发写压力。

文件命名：key 经 URL 百分号编码（urllib.quote）防路径注入/非法字符
（题目 id、用户名等可含 : / * ? 等），实际 key 存于文件内容或可由文件名反解。
"""
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple
from urllib.parse import quote, unquote

from app import config


def encode_key(key: str) -> str:
    return quote(str(key), safe="")


def decode_key(filename: str) -> str:
    return unquote(filename)


def ensure_dirs() -> None:
    for d in config.ALL_DATA_DIRS:
        d.mkdir(parents=True, exist_ok=True)


def save_json(directory: Path, key: str, data: Dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{encode_key(key)}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(directory: Path, key: str) -> Optional[Dict[str, Any]]:
    path = directory / f"{encode_key(key)}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def delete_json(directory: Path, key: str) -> bool:
    path = directory / f"{encode_key(key)}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def list_keys(directory: Path) -> list[str]:
    if not directory.exists():
        return []
    return sorted(decode_key(p.stem) for p in directory.glob("*.json"))


def iter_all(directory: Path) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """遍历目录全部条目，产出 (key, data)。"""
    for p in sorted(directory.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        yield decode_key(p.stem), data


def clear_dir(directory: Path) -> None:
    """删除目录内全部内容（保留目录本身），供 reset 使用。"""
    if directory.exists():
        for child in directory.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    directory.mkdir(parents=True, exist_ok=True)


def clear_all() -> None:
    """清空全部业务数据子目录（reset 语义：清空测试产生的数据并重建初始状态）。"""
    for d in config.ALL_DATA_DIRS:
        clear_dir(d)
