#!/usr/bin/env python3
"""
가로세로퍼즐 MCP 서버
Korean Crossword Puzzle MCP Server
"""

import base64
import os
import sys
from datetime import date

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP

import os as _os

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

mcp = FastMCP(
    "가로세로퍼즐",
    host="0.0.0.0",
    port=int(_os.environ.get("PORT", 8000)),
    stateless_http=True,
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


def _state_path(date_str: str) -> str:
    return os.path.join(OUTPUT_DIR, f"state_{date_str}.json")


def _load_state(date_str: str) -> dict:
    path = _state_path(date_str)
    if os.path.exists(path):
        import json
        with open(path) as f:
            return json.load(f)
    return {"solved": []}  # solved: list of "번호-방향" e.g. "1-가로"


def _save_state(date_str: str, state: dict):
    import json
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(_state_path(date_str), "w") as f:
        json.dump(state, f, ensure_ascii=False)


def _get_puzzle_words(date_str: str):
    """오늘 퍼즐의 PlacedWord 목록 반환 (없으면 생성)"""
    from crossword import ACROSS, DOWN
    target = date.fromisoformat(date_str)
    puzzle_path = os.path.join(OUTPUT_DIR, f"crossword_{date_str}.png")
    if not os.path.exists(puzzle_path):
        _generate_puzzle(target)
    # 퍼즐을 다시 생성해서 단어 목록 추출 (같은 seed라 동일)
    _, _, merged = _generate_puzzle(target)
    words = []
    for pw in merged.placed:
        if pw.number > 0:
            direction = "가로" if pw.direction == ACROSS else "세로"
            words.append({"number": pw.number, "direction": direction, "word": pw.word})
    return words


def _summary(solved: list, all_words: list) -> str:
    total = len(all_words)
    count = len(solved)
    remaining = [f"{w['number']}번 {w['direction']}" for w in all_words
                 if f"{w['number']}-{w['direction']}" not in solved]
    lines = [f"📊 진행 상황: {count}/{total}"]
    if remaining:
        lines.append(f"남은 칸: {', '.join(remaining)}")
    else:
        lines.append("🎉 모두 완성!")
    return "\n".join(lines)


@mcp.tool(
    annotations={
        "title": "Today's Korean Crossword Puzzle",
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
        "idempotentHint": True,
    }
)
def get_today_puzzle(must_word: str = "") -> list:
    """
    Generate today's Korean crossword puzzle (가로세로퍼즐).
    Call this when the user says '가세퍼', '가로세로퍼즐', or asks for today's puzzle.
    Returns the puzzle image and clue text for Threads caption.

    Args:
        must_word: A Korean word that must appear in the puzzle (optional). e.g. '대한민국'
    """
    target = date.today()
    date_str = target.strftime("%Y-%m-%d")

    mw = must_word.strip() if must_word.strip() else None
    puzzle_path, answer_path, merged = _generate_puzzle(target, must_word=mw)
    caption = _make_caption(merged, date_str)

    puzzle_url = f"{BASE_URL}/images/crossword_{date_str}.png"
    return f"🧩 오늘의 가로세로퍼즐\n퍼즐 이미지: {puzzle_url}\n\n{caption}"


@mcp.tool(
    annotations={
        "title": "Submit Answer Word",
        "readOnlyHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
        "idempotentHint": False,
    }
)
def submit_answer(word: str) -> str:
    """
    Submit a word as an answer for today's crossword puzzle (가로세로퍼즐).
    Call this when the user types a Korean word trying to solve the puzzle.
    Returns whether the word matches any unsolved slot, current progress, and remaining slots.
    If all slots are solved, returns the answer image URL.

    Args:
        word: A Korean word to check against the puzzle answers.
    """
    word = word.strip()
    date_str = date.today().strftime("%Y-%m-%d")
    all_words = _get_puzzle_words(date_str)
    state = _load_state(date_str)
    solved = state["solved"]

    # 이미 맞춘 단어인지 확인
    already = [w for w in all_words if w["word"] == word and f"{w['number']}-{w['direction']}" in solved]
    if already:
        w = already[0]
        return f"'{word}'은 이미 맞춘 {w['number']}번 {w['direction']}이에요!\n\n{_summary(solved, all_words)}"

    # 정답 매칭
    matches = [w for w in all_words if w["word"] == word and f"{w['number']}-{w['direction']}" not in solved]
    if matches:
        for w in matches:
            key = f"{w['number']}-{w['direction']}"
            if key not in solved:
                solved.append(key)
        state["solved"] = solved
        _save_state(date_str, state)

        matched_slots = ", ".join(f"{w['number']}번 {w['direction']}" for w in matches)
        result_lines = [f"✅ 정답! '{word}' = {matched_slots}"]
        summary = _summary(solved, all_words)
        result_lines.append("")
        result_lines.append(summary)

        # 전부 맞췄으면 정답 이미지 제공
        if len(solved) == len(all_words):
            answer_url = f"{BASE_URL}/images/crossword_{date_str}_answer.png"
            result_lines.append(f"\n🎊 축하해요! 모두 맞췄어요!\n정답 이미지: {answer_url}")

        return "\n".join(result_lines)
    else:
        return f"❌ '{word}'은 퍼즐에 없는 단어예요.\n\n{_summary(solved, all_words)}"


@mcp.tool(
    annotations={
        "title": "Today's Crossword Answer",
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": False,
        "idempotentHint": True,
    }
)
def get_puzzle_answer() -> str:
    """
    Return the answer image for today's Korean crossword puzzle.
    Only available after all slots are solved via submit_answer.
    Call this when the user says '정답 보여줘' or asks to reveal the answer.
    """
    date_str = date.today().strftime("%Y-%m-%d")
    all_words = _get_puzzle_words(date_str)
    state = _load_state(date_str)
    solved = state["solved"]

    if len(solved) < len(all_words):
        summary = _summary(solved, all_words)
        return f"아직 다 못 맞췄어요! 남은 칸을 먼저 풀어보세요 🙂\n\n{summary}"

    answer_url = f"{BASE_URL}/images/crossword_{date_str}_answer.png"
    return f"✅ {date_str} 정답\n정답 이미지: {answer_url}"


if __name__ == "__main__":
    import uvicorn
    from starlette.staticfiles import StaticFiles

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    mcp_app = mcp.streamable_http_app()
    mcp_app.mount("/images", StaticFiles(directory=OUTPUT_DIR), name="images")

    port = int(_os.environ.get("PORT", 8000))
    uvicorn.run(mcp_app, host="0.0.0.0", port=port)
