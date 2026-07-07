#!/usr/bin/env python3
"""
가로세로퍼즐 MCP 서버
"가세퍼" 또는 "가로세로퍼즐" 입력 시 오늘의 퍼즐 이미지를 반환
"""

import base64
import os
import sys
from datetime import date

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP

import os as _os
mcp = FastMCP(
    "가로세로퍼즐",
    host="0.0.0.0",
    port=int(_os.environ.get("PORT", 8000)),
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def _generate_puzzle(target_date: date, must_word: str = None) -> tuple[str, str]:
    """퍼즐 생성 후 (puzzle_path, answer_path) 반환"""
    import random
    from words import WORD_DATABASE
    from crossword import build_crossword, CrosswordGrid, PlacedWord
    from renderer import render, render_answer

    # main.py의 로직을 직접 인라인
    NUM_WORDS = 14
    MIN_PLACED = 5
    MAX_RETRY = 5

    date_str = target_date.strftime("%Y-%m-%d")
    seed = int(target_date.strftime("%Y%m%d"))

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pool = [(w, c) for w, c in WORD_DATABASE if 2 <= len(w) <= 6]
    seen = set()
    pool = [(w, c) for w, c in pool if w not in seen and not seen.add(w)]

    if must_word and not any(w == must_word for w, _ in pool):
        must_word = None

    def select_words(sub_pool, num, rng, mw=None):
        from collections import defaultdict
        syl_to_words = defaultdict(list)
        for idx, (word, _) in enumerate(sub_pool):
            for ch in word:
                syl_to_words[ch].append(idx)

        def neighbors_of(idx):
            nb = set()
            for ch in sub_pool[idx][0]:
                for n in syl_to_words[ch]:
                    if n != idx:
                        nb.add(n)
            return nb

        must_idx = None
        if mw:
            for idx, (word, _) in enumerate(sub_pool):
                if word == mw:
                    must_idx = idx
                    break

        shuffled = list(range(len(sub_pool)))
        rng.shuffle(shuffled)

        if must_idx is not None:
            starts = [must_idx] + [i for i in shuffled if len(sub_pool[i][0]) == 3 and i != must_idx][:5]
        else:
            starts = [i for i in shuffled if len(sub_pool[i][0]) == 3][:6]
            starts += [i for i in shuffled if len(sub_pool[i][0]) == 2][:4]
            if not starts:
                starts = shuffled[:6]

        best: list[int] = []
        for start_idx in starts:
            init = {start_idx}
            if must_idx is not None:
                init.add(must_idx)
            sel: set[int] = init
            queue = list(init)
            syls: set[str] = set()
            for i in init:
                syls.update(sub_pool[i][0])
            while len(sel) < num and queue:
                cur = queue.pop(0)
                nbs = sorted(neighbors_of(cur), key=lambda n: -len(set(sub_pool[n][0]) - syls))
                for nb in nbs:
                    if nb not in sel:
                        sel.add(nb)
                        syls.update(sub_pool[nb][0])
                        queue.append(nb)
                        if len(sel) >= num:
                            break
            if len(sel) > len(best):
                best = list(sel)
            if len(best) >= num:
                break

        result = [sub_pool[i] for i in best[:num]]
        result.sort(key=lambda x: (-len(x[0]), x[0]))
        return result

    def build_cluster(rng_seed, must=None, exclude=None):
        exclude = exclude or set()
        sub_pool = [(w, c) for w, c in pool if w not in exclude]
        for attempt in range(MAX_RETRY):
            rng = random.Random(rng_seed + attempt * 7)
            selected = select_words(sub_pool, NUM_WORDS // 2 + 4, rng, mw=must)
            g = build_crossword(selected, rng, min_placed=3, must_word=must)
            if len(g.placed) >= 3:
                return g
        return g

    grid1 = build_cluster(seed, must=must_word)
    used = {pw.word for pw in grid1.placed}
    grid2 = build_cluster(seed + 9999, exclude=used)

    # 두 그리드 병합
    g1r = len(grid1.grid)
    g1c = grid1.width if hasattr(grid1, 'width') else len(grid1.grid[0])
    g2r = len(grid2.grid)
    g2c = grid2.width if hasattr(grid2, 'width') else len(grid2.grid[0])
    GAP = 1
    mr = max(g1r, g2r)
    mc = g1c + GAP + g2c
    merged = CrosswordGrid(size=max(mr, mc) + 5)
    merged.grid = [["#"] * mc for _ in range(mr)]
    merged.width = mc
    for r in range(g1r):
        for c in range(g1c):
            merged.grid[r][c] = grid1.grid[r][c]
    col_off = g1c + GAP
    for r in range(g2r):
        for c in range(g2c):
            merged.grid[r][col_off + c] = grid2.grid[r][c]
    for pw in grid1.placed:
        merged.placed.append(PlacedWord(pw.word, pw.clue, pw.row, pw.col, pw.direction))
    for pw in grid2.placed:
        merged.placed.append(PlacedWord(pw.word, pw.clue, pw.row, pw.col + col_off, pw.direction))
    merged.assign_numbers()
    merged.height = mr

    puzzle_path = os.path.join(OUTPUT_DIR, f"crossword_{date_str}.png")
    answer_path = os.path.join(OUTPUT_DIR, f"crossword_{date_str}_answer.png")
    render(merged, date_str, puzzle_path)
    render_answer(merged, date_str, answer_path)
    return puzzle_path, answer_path, merged


def _make_caption(merged, date_str: str) -> str:
    from crossword import ACROSS, DOWN
    across = sorted([pw for pw in merged.placed if pw.direction == ACROSS and pw.number > 0],
                    key=lambda x: x.number)
    down = sorted([pw for pw in merged.placed if pw.direction == DOWN and pw.number > 0],
                  key=lambda x: x.number)
    lines = [f"스레드 가로세로퍼즐 [{date_str}]", "", "▶ 가로"]
    for pw in across:
        lines.append(f"{pw.number}. {pw.clue}")
    lines += ["", "▼ 세로"]
    for pw in down:
        lines.append(f"{pw.number}. {pw.clue}")
    lines += ["", "@heison_imdang"]
    return "\n".join(lines)


def _img_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


@mcp.tool()
def get_today_puzzle(must_word: str = "") -> list:
    """
    오늘의 가로세로퍼즐을 생성합니다.
    '가세퍼' 또는 '가로세로퍼즐' 입력 시 호출하세요.

    Args:
        must_word: 반드시 포함할 단어 (선택사항). 예: '대한민국'
    """
    target = date.today()
    date_str = target.strftime("%Y-%m-%d")

    mw = must_word.strip() if must_word.strip() else None
    puzzle_path, answer_path, merged = _generate_puzzle(target, must_word=mw)
    caption = _make_caption(merged, date_str)

    puzzle_b64 = _img_to_base64(puzzle_path)

    return [
        {
            "type": "image",
            "data": puzzle_b64,
            "mimeType": "image/png",
        },
        {
            "type": "text",
            "text": caption,
        },
    ]


@mcp.tool()
def get_puzzle_answer() -> list:
    """
    오늘 가로세로퍼즐의 정답 이미지를 반환합니다.
    '정답 보여줘' 입력 시 호출하세요.
    """
    target = date.today()
    date_str = target.strftime("%Y-%m-%d")
    answer_path = os.path.join(OUTPUT_DIR, f"crossword_{date_str}_answer.png")

    # 오늘 퍼즐이 아직 없으면 먼저 생성
    if not os.path.exists(answer_path):
        _, answer_path, _ = _generate_puzzle(target)

    answer_b64 = _img_to_base64(answer_path)

    return [
        {
            "type": "image",
            "data": answer_b64,
            "mimeType": "image/png",
        },
        {
            "type": "text",
            "text": f"📋 {date_str} 정답입니다!",
        },
    ]


if __name__ == "__main__":
    mcp.run(transport="sse")
