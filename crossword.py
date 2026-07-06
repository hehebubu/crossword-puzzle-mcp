import random
from dataclasses import dataclass

ACROSS = "across"
DOWN = "down"

@dataclass
class PlacedWord:
    word: str
    clue: str
    row: int
    col: int
    direction: str
    number: int = 0


class CrosswordGrid:
    def __init__(self, size=25):
        self.size = size
        self.grid = [["#"] * size for _ in range(size)]
        self.placed: list[PlacedWord] = []

    def _get(self, r, c):
        if 0 <= r < self.size and 0 <= c < self.size:
            return self.grid[r][c]
        return None

    def can_place(self, word: str, row: int, col: int, direction: str) -> bool:
        chars = list(word)
        n = len(chars)
        has_intersection = False

        if direction == ACROSS:
            if col < 0 or col + n > self.size or not (0 <= row < self.size):
                return False
            if self._get(row, col - 1) not in (None, "#"):
                return False
            if self._get(row, col + n) not in (None, "#"):
                return False
            for i, ch in enumerate(chars):
                c = col + i
                cell = self.grid[row][c]
                if cell == "#":
                    if self._get(row - 1, c) not in (None, "#"):
                        return False
                    if self._get(row + 1, c) not in (None, "#"):
                        return False
                elif cell == ch:
                    has_intersection = True
                else:
                    return False
        else:  # DOWN
            if row < 0 or row + n > self.size or not (0 <= col < self.size):
                return False
            if self._get(row - 1, col) not in (None, "#"):
                return False
            if self._get(row + n, col) not in (None, "#"):
                return False
            for i, ch in enumerate(chars):
                r = row + i
                cell = self.grid[r][col]
                if cell == "#":
                    if self._get(r, col - 1) not in (None, "#"):
                        return False
                    if self._get(r, col + 1) not in (None, "#"):
                        return False
                elif cell == ch:
                    has_intersection = True
                else:
                    return False

        return has_intersection

    def place(self, word: str, clue: str, row: int, col: int, direction: str):
        chars = list(word)
        if direction == ACROSS:
            for i, ch in enumerate(chars):
                self.grid[row][col + i] = ch
        else:
            for i, ch in enumerate(chars):
                self.grid[row + i][col] = ch
        self.placed.append(PlacedWord(word, clue, row, col, direction))

    def unplace(self, pw: PlacedWord):
        shared = set()
        for other in self.placed:
            if other is pw:
                continue
            if other.direction == ACROSS:
                for i in range(len(other.word)):
                    shared.add((other.row, other.col + i))
            else:
                for i in range(len(other.word)):
                    shared.add((other.row + i, other.col))

        if pw.direction == ACROSS:
            for i in range(len(pw.word)):
                pos = (pw.row, pw.col + i)
                if pos not in shared:
                    self.grid[pw.row][pw.col + i] = "#"
        else:
            for i in range(len(pw.word)):
                pos = (pw.row + i, pw.col)
                if pos not in shared:
                    self.grid[pw.row + i][pw.col] = "#"
        self.placed.remove(pw)

    def find_placements(self, word: str) -> list[tuple[int, int, str]]:
        chars = list(word)
        candidates = []
        seen = set()

        for pw in self.placed:
            opp = DOWN if pw.direction == ACROSS else ACROSS
            pw_chars = list(pw.word)

            for i, ch in enumerate(chars):
                for j, pw_ch in enumerate(pw_chars):
                    if ch != pw_ch:
                        continue
                    if pw.direction == ACROSS:
                        r = pw.row - i
                        c = pw.col + j
                    else:
                        r = pw.row + j
                        c = pw.col - i
                    key = (r, c, opp)
                    if key not in seen and self.can_place(word, r, c, opp):
                        candidates.append(key)
                        seen.add(key)

        return candidates

    def assign_numbers(self) -> dict:
        numbered = {}
        num = 1
        rows = len(self.grid)
        cols = len(self.grid[0]) if rows else 0
        for r in range(rows):
            for c in range(cols):
                if self.grid[r][c] == "#":
                    continue
                is_across_start = (
                    (c == 0 or self.grid[r][c - 1] == "#") and
                    c + 1 < cols and self.grid[r][c + 1] != "#"
                )
                is_down_start = (
                    (r == 0 or self.grid[r - 1][c] == "#") and
                    r + 1 < rows and self.grid[r + 1][c] != "#"
                )
                if is_across_start or is_down_start:
                    numbered[(r, c)] = num
                    num += 1

        for pw in self.placed:
            pw.number = numbered.get((pw.row, pw.col), 0)

        return numbered

    def crop(self):
        rows = len(self.grid)
        cols = len(self.grid[0]) if rows else 0
        used_rows = [r for r in range(rows) if any(self.grid[r][c] != "#" for c in range(cols))]
        used_cols = [c for c in range(cols) if any(self.grid[r][c] != "#" for r in range(rows))]
        if not used_rows or not used_cols:
            return
        rmin = max(0, used_rows[0] - 1)
        rmax = min(rows - 1, used_rows[-1] + 1)
        cmin = max(0, used_cols[0] - 1)
        cmax = min(cols - 1, used_cols[-1] + 1)

        self.grid = [row[cmin:cmax + 1] for row in self.grid[rmin:rmax + 1]]
        self.height = len(self.grid)
        self.width = len(self.grid[0]) if self.grid else 0

        for pw in self.placed:
            pw.row -= rmin
            pw.col -= cmin


def build_crossword(words_clues: list[tuple[str, str]], rng: random.Random,
                    min_placed: int = 5, must_word: str = None) -> CrosswordGrid:
    """
    여러 단어 순서와 방향을 시도하여 최대한 많은 단어를 배치.
    첫 단어를 가로/세로 두 방향으로 모두 시도하고,
    그리디하게 배치 후 결과가 좋은 것을 반환.
    must_word가 있으면 해당 단어를 반드시 첫 번째로 배치.
    """
    best_grid: CrosswordGrid | None = None
    words_clues = list(words_clues)

    for first_dir in [ACROSS, DOWN]:
        for perm_seed in range(8):
            attempt_rng = random.Random(rng.randint(0, 10**9) + perm_seed)
            shuffled = list(words_clues)
            attempt_rng.shuffle(shuffled)
            # 긴 단어 우선
            shuffled.sort(key=lambda x: -len(x[0]))
            # must_word가 있으면 맨 앞으로 이동
            if must_word:
                must_items = [item for item in shuffled if item[0] == must_word]
                rest = [item for item in shuffled if item[0] != must_word]
                shuffled = must_items + rest

            grid = CrosswordGrid(size=25)
            first_word, first_clue = shuffled[0]
            mid = grid.size // 2
            if first_dir == ACROSS:
                start_col = mid - len(first_word) // 2
                grid.place(first_word, first_clue, mid, start_col, ACROSS)
            else:
                start_row = mid - len(first_word) // 2
                grid.place(first_word, first_clue, start_row, mid, DOWN)

            remaining = shuffled[1:]
            _greedy_place(grid, remaining, attempt_rng)

            if best_grid is None or len(grid.placed) > len(best_grid.placed):
                best_grid = grid
                # 시도할 복제본 (crop은 나중에)
                import copy
                best_grid = copy.deepcopy(grid)

            if len(best_grid.placed) >= min_placed + 3:
                break
        if best_grid and len(best_grid.placed) >= min_placed + 3:
            break

    if best_grid is None:
        best_grid = CrosswordGrid(size=25)

    best_grid.crop()
    best_grid.assign_numbers()
    return best_grid


def _score_placement(grid: CrosswordGrid, word: str, r: int, c: int, direction: str) -> float:
    """배치 점수: 중앙에 가깝고, 교차점이 내부에 있을수록 높음"""
    chars = list(word)
    n = len(chars)

    # 교차점 위치 (단어 내 중간 위치일수록 좋음)
    if direction == ACROSS:
        intersect_scores = [
            min(i, n - 1 - i)
            for i, ch in enumerate(chars)
            if grid.grid[r][c + i] != "#"
        ]
    else:
        intersect_scores = [
            min(i, n - 1 - i)
            for i, ch in enumerate(chars)
            if grid.grid[r + i][c] != "#"
        ]
    interior_score = sum(intersect_scores) if intersect_scores else 0

    # 그리드 중심에서의 거리 (가까울수록 좋음)
    center = grid.size / 2
    dist = abs(r - center) + abs(c - center)

    return interior_score * 10 - dist


def _greedy_place(grid: CrosswordGrid, remaining: list, rng: random.Random):
    """배치 점수 기반 그리디 배치"""
    placed_any = True
    while placed_any and remaining:
        placed_any = False
        best_score = -1e9
        best_item = None
        best_placement = None

        for item in remaining:
            cands = grid.find_placements(item[0])
            for (r, c, d) in cands:
                score = _score_placement(grid, item[0], r, c, d)
                # 약간의 랜덤성 추가
                score += rng.uniform(0, 2)
                if score > best_score:
                    best_score = score
                    best_item = item
                    best_placement = (r, c, d)

        if best_item is None:
            break

        word, clue = best_item
        r, c, d = best_placement
        grid.place(word, clue, r, c, d)
        remaining.remove(best_item)
        placed_any = True
