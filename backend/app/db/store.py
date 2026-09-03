"""全 JSON 文件存储层。

需求文档 §4（用户决策 dec-0f895a1ddd678090）：全 JSON 文件——
题目每题一个 JSON、用户/提交/日志以 JSON 条目存于各自目录；
reset 清空即删目录内文件重建。数据量小且评测单用户串行，无并发写压力。

文件命名：key 经 URL 百分号编码（urllib.quote）防路径注入/非法字符
（题目 id、用户名等可含 : / * ? 等），实际 key 存于文件内容或可由文件名反解。
"""
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple
from urllib.parse import quote, unquote

from app import config

logger = logging.getLogger("oj.store")


def encode_key(key: str) -> str:
    return quote(str(key), safe="")


def decode_key(filename: str) -> str:
    return unquote(filename)


def ensure_dirs() -> None:
    for d in config.ALL_DATA_DIRS:
        d.mkdir(parents=True, exist_ok=True)


def save_json(directory: Path, key: str, data: Dict[str, Any]) -> None:
    """原子写入：先写同目录临时文件再 os.replace（评审意见 P3，2026-09-03）。

    避免进程中断留下半截 JSON；数据量增大（题目/提交）后仍保持健壮。
    """
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{encode_key(key)}.json"
    tmp = directory / f".{encode_key(key)}.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, target)


def load_json(directory: Path, key: str) -> Optional[Dict[str, Any]]:
    path = directory / f"{encode_key(key)}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # 评审意见 P2（2026-09-03）：损坏文件记日志，便于与"不存在"区分排查。
        logger.warning("corrupted json file (treat as missing): %s", path)
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
            logger.warning("corrupted json file (skip): %s", p)
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
