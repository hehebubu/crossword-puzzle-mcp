#!/usr/bin/env python3
"""
한국어 가로세로 퍼즐 생성기
매일 날짜 기반으로 새로운 퍼즐 생성
"""

import random
import sys
import os
from datetime import date, timedelta

from words import WORD_DATABASE
from crossword import build_crossword
from renderer import render, render_answer

THREADS_TAG = "@heison_imdang"

OUTPUT_DIR = "output"
NUM_WORDS = 14      # 후보 단어 수 (여유분 포함)
MIN_PLACED = 5      # 최소 배치 단어 수 (이 이하면 재시도)
MAX_RETRY = 5


def select_words(pool: list, num: int, rng: random.Random, must_word: str = None) -> list:
    """다양한 음절 클러스터를 망라하는 단어 선택. must_word가 있으면 반드시 포함."""
    from collections import defaultdict

    syl_to_words = defaultdict(list)
    for idx, (word, _) in enumerate(pool):
        for ch in word:
            syl_to_words[ch].append(idx)

    # 각 단어의 연결 이웃
    def neighbors_of(idx):
        word = pool[idx][0]
        nb = set()
        for ch in word:
            for n in syl_to_words[ch]:
                if n != idx:
                    nb.add(n)
        return nb

    # must_word가 있으면 해당 인덱스를 시작점으로 고정
    must_idx = None
    if must_word:
        for idx, (word, _) in enumerate(pool):
            if word == must_word:
                must_idx = idx
                break

    # 여러 시작점에서 BFS 시도 → 가장 많이 연결된 클러스터 선택
    shuffled_idx = list(range(len(pool)))
    rng.shuffle(shuffled_idx)

    best_selected: list[int] = []

    if must_idx is not None:
        # must_word를 시작점으로 우선 시도
        starts = [must_idx]
        starts += [i for i in shuffled_idx if len(pool[i][0]) == 3 and i != must_idx][:5]
    else:
        starts = [i for i in shuffled_idx if len(pool[i][0]) == 3][:6]
        starts += [i for i in shuffled_idx if len(pool[i][0]) == 2][:4]
        if not starts:
            starts = shuffled_idx[:6]

    for start_idx in starts:
        init_set = {start_idx}
        if must_idx is not None:
            init_set.add(must_idx)
        selected_idx: set[int] = init_set
        queue = list(init_set)
        seen_syls: set[str] = set()
        for i in init_set:
            seen_syls.update(pool[i][0])

        while len(selected_idx) < num and queue:
            cur = queue.pop(0)
            nbs = list(neighbors_of(cur))
            # 새로운 음절을 가진 이웃 우선 (다양성 확보)
            nbs.sort(key=lambda n: -len(set(pool[n][0]) - seen_syls))
            for nb in nbs:
                if nb not in selected_idx:
                    selected_idx.add(nb)
                    seen_syls.update(pool[nb][0])
                    queue.append(nb)
                    if len(selected_idx) >= num:
                        break

        if len(selected_idx) > len(best_selected):
            best_selected = list(selected_idx)
        if len(best_selected) >= num:
            break

    selected = [pool[i] for i in best_selected[:num]]
    # 3음절 단어 우선, 그 다음 긴 단어 순
    selected.sort(key=lambda x: (-len(x[0]), x[0]))
    return selected


def generate_for_date(target_date: date, answer: bool = False, must_word: str = None) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    seed = int(target_date.strftime("%Y%m%d"))

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pool = [(w, c) for w, c in WORD_DATABASE if 2 <= len(w) <= 6]
    # 중복 단어 제거
    seen = set()
    pool = [(w, c) for w, c in pool if w not in seen and not seen.add(w)]

    if must_word:
        if not any(w == must_word for w, _ in pool):
            print(f"경고: '{must_word}'이(가) DB에 없습니다. 무시합니다.")
            must_word = None
        else:
            print(f"필수 단어: {must_word}")

    # 두 클러스터 생성 후 하나의 그리드로 합치기
    def build_cluster(rng_seed, must=None, exclude=None):
        exclude = exclude or set()
        sub_pool = [(w, c) for w, c in pool if w not in exclude]
        for attempt in range(MAX_RETRY):
            attempt_rng = random.Random(rng_seed + attempt * 7)
            selected = select_words(sub_pool, NUM_WORDS // 2 + 4, attempt_rng, must_word=must)
            g = build_crossword(selected, attempt_rng, min_placed=3, must_word=must)
            if len(g.placed) >= 3:
                return g
        return g

    grid1 = build_cluster(seed, must=must_word)
    used_words = {pw.word for pw in grid1.placed}
    grid2 = build_cluster(seed + 9999, exclude=used_words)

    # 두 그리드를 하나로 합치기
    from crossword import CrosswordGrid as CWGrid
    g1_rows = len(grid1.grid)
    g1_cols = grid1.width if hasattr(grid1, 'width') else len(grid1.grid[0])
    g2_rows = len(grid2.grid)
    g2_cols = grid2.width if hasattr(grid2, 'width') else len(grid2.grid[0])

    GAP = 1  # 두 클러스터 사이 빈 열
    merged_rows = max(g1_rows, g2_rows)
    merged_cols = g1_cols + GAP + g2_cols

    merged = CWGrid(size=max(merged_rows, merged_cols) + 5)
    merged.grid = [["#"] * merged_cols for _ in range(merged_rows)]
    merged.width = merged_cols

    # grid1 복사
    for r in range(g1_rows):
        for c in range(g1_cols):
            merged.grid[r][c] = grid1.grid[r][c]

    # grid2 복사 (g1_cols + GAP 오프셋)
    col_offset = g1_cols + GAP
    for r in range(g2_rows):
        for c in range(g2_cols):
            merged.grid[r][col_offset + c] = grid2.grid[r][c]

    # placed 단어 이동
    from crossword import PlacedWord
    for pw in grid1.placed:
        merged.placed.append(PlacedWord(pw.word, pw.clue, pw.row, pw.col, pw.direction))
    for pw in grid2.placed:
        merged.placed.append(PlacedWord(pw.word, pw.clue, pw.row, pw.col + col_offset, pw.direction))

    merged.assign_numbers()
    merged.height = merged_rows

    all_placed = merged.placed
    total = len(all_placed)

    puzzle_path = os.path.join(OUTPUT_DIR, f"crossword_{date_str}.png")
    render(merged, date_str, puzzle_path)

    answer_path = os.path.join(OUTPUT_DIR, f"crossword_{date_str}_answer.png")
    render_answer(merged, date_str, answer_path)

    print(f"\n날짜: {date_str}")
    print(f"배치된 단어: {total}개 (클러스터1: {len(grid1.placed)}, 클러스터2: {len(grid2.placed)})")
    for pw in sorted(all_placed, key=lambda x: x.number):
        direction_str = "가로" if pw.direction == "across" else "세로"
        print(f"  [{pw.number}] {direction_str} | {pw.word} — {pw.clue}")

    # 스레드 캡션 생성
    caption = _make_threads_caption(all_placed, date_str)
    print("\n" + "=" * 50)
    print("📱 스레드 캡션 (복사해서 사용하세요)")
    print("=" * 50)
    print(caption)
    print("=" * 50)

    caption_path = os.path.join(OUTPUT_DIR, f"crossword_{date_str}_caption.txt")
    with open(caption_path, "w", encoding="utf-8") as f:
        f.write(caption)
    print(f"캡션 저장: {caption_path}")

    return puzzle_path


def _make_threads_caption(placed, date_str: str) -> str:
    from crossword import ACROSS, DOWN
    across_clues = sorted(
        [pw for pw in placed if pw.direction == ACROSS and pw.number > 0],
        key=lambda x: x.number
    )
    down_clues = sorted(
        [pw for pw in placed if pw.direction == DOWN and pw.number > 0],
        key=lambda x: x.number
    )

    lines = [f"스레드 가로세로퍼즐 [{date_str}]", ""]
    lines.append("▶ 가로")
    for pw in across_clues:
        lines.append(f"{pw.number}. {pw.clue}")
    lines.append("")
    lines.append("▼ 세로")
    for pw in down_clues:
        lines.append(f"{pw.number}. {pw.clue}")
    lines.append("")
    lines.append(THREADS_TAG)
    return "\n".join(lines)


def update_word_db(count: int = 20):
    """Claude API로 새 단어/설명 쌍을 생성하여 words.py에 추가"""
    try:
        import anthropic
    except ImportError:
        print("오류: anthropic 패키지가 필요합니다. 'pip install anthropic'으로 설치하세요.")
        sys.exit(1)

    # 기존 단어 수집 (중복 방지용)
    existing = {w for w, _ in WORD_DATABASE}

    client = anthropic.Anthropic()
    prompt = f"""한국어 가로세로 퍼즐용 단어와 설명을 {count}개 생성해주세요.

조건:
- 각 단어는 2~5글자 한글 단어
- 일상적이고 친숙한 단어 (명사 위주)
- 설명은 퍼즐 힌트로 적합하게 간결하게 (10~25자)
- 다양한 주제: 자연, 음식, 동물, 스포츠, 일상 등
- 이미 있는 단어 제외: {', '.join(sorted(existing)[:50])}...

출력 형식 (파이썬 튜플 리스트, 다른 설명 없이):
("단어", "설명"),
("단어", "설명"),
...

각 줄에 정확히 하나의 튜플만 출력하세요."""

    print(f"Claude API로 단어 {count}개 생성 중...")
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()

    # 파싱
    new_pairs = []
    for line in response_text.splitlines():
        line = line.strip().rstrip(",")
        if line.startswith('("') and line.endswith('")'):
            try:
                pair = eval(line)
                if (isinstance(pair, tuple) and len(pair) == 2
                        and isinstance(pair[0], str) and isinstance(pair[1], str)
                        and 2 <= len(pair[0]) <= 5
                        and pair[0] not in existing):
                    new_pairs.append(pair)
                    existing.add(pair[0])
            except Exception:
                pass

    if not new_pairs:
        print("추출된 단어가 없습니다. API 응답을 확인하세요:")
        print(response_text[:500])
        return

    # words.py에 추가
    words_path = os.path.join(os.path.dirname(__file__), "words.py")
    with open(words_path, "a", encoding="utf-8") as f:
        f.write(f"\n# Claude API로 추가된 단어 ({date.today()})\n")
        for word, clue in new_pairs:
            f.write(f'    ("{word}", "{clue}"),\n')

    print(f"✓ {len(new_pairs)}개 단어를 words.py에 추가했습니다:")
    for word, clue in new_pairs:
        print(f"  {word}: {clue}")


def main():
    args = sys.argv[1:]

    target_date = date.today()
    show_answer = False
    must_word = None

    for arg in args:
        if arg in ("-a", "--answer"):
            show_answer = True
        elif arg in ("-t", "--tomorrow"):
            target_date = date.today() + timedelta(days=1)
        elif arg in ("-y", "--yesterday"):
            target_date = date.today() - timedelta(days=1)
        elif arg.startswith("--date="):
            try:
                target_date = date.fromisoformat(arg.split("=", 1)[1])
            except ValueError:
                print("날짜 형식 오류. 예: --date=2026-06-26")
                sys.exit(1)
        elif arg.startswith("--must="):
            must_word = arg.split("=", 1)[1].strip()
        elif arg == "--update-db":
            count_arg = next((a for a in args if a.startswith("--count=")), None)
            count = int(count_arg.split("=", 1)[1]) if count_arg else 20
            update_word_db(count)
            return
        elif arg in ("-h", "--help"):
            print(__doc__)
            print("사용법: python main.py [옵션]")
            print("  -a, --answer       정답 이미지도 함께 생성")
            print("  -t, --tomorrow     내일 퍼즐 생성")
            print("  -y, --yesterday    어제 퍼즐 생성")
            print("  --date=YYYY-MM-DD  특정 날짜 퍼즐 생성")
            print("  --must=단어        특정 단어를 반드시 포함")
            print("  --update-db        Claude API로 단어 DB 보강 (--count=N 으로 수량 지정)")
            sys.exit(0)

    path = generate_for_date(target_date, answer=show_answer, must_word=must_word)

    # macOS에서 자동으로 이미지 열기
    if sys.platform == "darwin":
        os.system(f'open "{path}"')


if __name__ == "__main__":
    main()
