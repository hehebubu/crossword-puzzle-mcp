from PIL import Image, ImageDraw, ImageFont
from crossword import CrosswordGrid, ACROSS, DOWN
import os, platform

CELL = 52          # 셀 크기 (px)
PADDING = 40       # 그리드 외부 여백
NUM_FONT_SIZE = 13
LETTER_FONT_SIZE = 24
CLUE_FONT_SIZE = 17
TITLE_FONT_SIZE = 26

BG      = (245, 245, 245)
WHITE   = (255, 255, 255)
BLACK   = (30, 30, 30)
GRAY    = (180, 180, 180)
ACCENT  = (50, 100, 200)

def _get_font(size: int, bold: bool = False):
    """시스템 한글 폰트 자동 탐색"""
    # 프로젝트 내 번들 폰트 우선
    _here = os.path.dirname(os.path.abspath(__file__))
    bundled = os.path.join(_here, "fonts", "NotoSansKR-Regular.ttf")
    candidates = [bundled]

    sys = platform.system()
    if sys == "Darwin":
        candidates += [
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
            "/Library/Fonts/NanumGothic.ttf",
        ]
    elif sys == "Linux":
        candidates += [
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf",
        ]
    elif sys == "Windows":
        candidates += [
            "C:/Windows/Fonts/malgun.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_grid(draw, grid: CrosswordGrid, gx: int, gy: int,
               num_font, show_letters: bool = False, letter_font=None):
    """단일 그리드를 (gx, gy) 오프셋에 그림"""
    rows = len(grid.grid)
    cols = grid.width if hasattr(grid, 'width') else len(grid.grid[0])

    numbered_cells = {}
    for pw in grid.placed:
        numbered_cells[(pw.row, pw.col)] = pw.number

    for r in range(rows):
        for c in range(cols):
            x = gx + c * CELL
            y = gy + r * CELL
            cell = grid.grid[r][c]
            if cell == "#":
                draw.rectangle([x, y, x + CELL, y + CELL], fill=BLACK)
            else:
                draw.rectangle([x, y, x + CELL, y + CELL], fill=WHITE, outline=GRAY, width=1)
                num = numbered_cells.get((r, c), 0)
                if num:
                    draw.text((x + 3, y + 2), str(num), fill=ACCENT, font=num_font)
                if show_letters and letter_font:
                    draw.text((x + CELL // 2, y + CELL // 2 + 4), cell,
                              fill=BLACK, font=letter_font, anchor="mm")

    grid_w = cols * CELL
    grid_h = rows * CELL
    draw.rectangle([gx, gy, gx + grid_w, gy + grid_h], outline=BLACK, width=2)
    return grid_w, grid_h


def _draw_tag(draw, gx: int, gy: int, grid_w: int, grid_h: int, tag_font):
    tag_text = "@heison_imdang"
    tag_bbox = draw.textbbox((0, 0), tag_text, font=tag_font)
    tag_w = tag_bbox[2] - tag_bbox[0]
    tag_h = tag_bbox[3] - tag_bbox[1]
    tag_x = gx + (grid_w - tag_w) // 2
    tag_y = gy + grid_h - tag_h - 6
    draw.text((tag_x, tag_y), tag_text, fill=WHITE, font=tag_font)


def render(grid: CrosswordGrid, date_str: str, output_path: str):
    clue_font = _get_font(CLUE_FONT_SIZE)
    title_font = _get_font(TITLE_FONT_SIZE, bold=True)
    num_font = _get_font(NUM_FONT_SIZE)
    hdr_font = _get_font(CLUE_FONT_SIZE + 2, bold=True)
    tag_font = _get_font(18, bold=True)

    def clue_line(pw):
        return f"{pw.number}. {pw.clue}"

    clue_line_h = CLUE_FONT_SIZE + 8
    section_title_h = CLUE_FONT_SIZE + 16

    across_clues = sorted([pw for pw in grid.placed if pw.direction == ACROSS and pw.number > 0],
                          key=lambda x: x.number)
    down_clues = sorted([pw for pw in grid.placed if pw.direction == DOWN and pw.number > 0],
                        key=lambda x: x.number)
    clue_col_items = max(len(across_clues), len(down_clues))
    clue_section_h = section_title_h + clue_col_items * clue_line_h + 30

    rows = len(grid.grid)
    cols = grid.width if hasattr(grid, 'width') else len(grid.grid[0])
    grid_w = cols * CELL
    grid_h = rows * CELL

    total_w = max(grid_w + PADDING * 2, 900)
    total_h = PADDING + TITLE_FONT_SIZE + 16 + grid_h + PADDING + clue_section_h + PADDING

    img = Image.new("RGB", (total_w, total_h), BG)
    draw = ImageDraw.Draw(img)

    title = f"오늘의 십자말풀이  [{date_str}]"
    draw.text((total_w // 2, PADDING // 2 + 8), title,
              fill=ACCENT, font=title_font, anchor="mt")

    gx = (total_w - grid_w) // 2
    gy = PADDING + TITLE_FONT_SIZE + 16

    _draw_grid(draw, grid, gx, gy, num_font)
    _draw_tag(draw, gx, gy, grid_w, grid_h, tag_font)

    # 단서 섹션
    cy = gy + grid_h + PADDING
    margin = PADDING
    col_w = (total_w - margin * 3) // 2

    draw.text((margin, cy), "▶ 가로", fill=ACCENT, font=hdr_font)
    cy2 = cy + section_title_h
    for pw in across_clues:
        draw.text((margin, cy2), clue_line(pw), fill=BLACK, font=clue_font)
        cy2 += clue_line_h

    dx = margin + col_w + margin
    draw.text((dx, cy), "▼ 세로", fill=ACCENT, font=hdr_font)
    cy3 = cy + section_title_h
    for pw in down_clues:
        draw.text((dx, cy3), clue_line(pw), fill=BLACK, font=clue_font)
        cy3 += clue_line_h

    img.save(output_path, dpi=(150, 150))
    print(f"저장 완료: {output_path}")
    return output_path


def render_answer(grid: CrosswordGrid, date_str: str, output_path: str):
    """정답이 채워진 버전 렌더링"""
    letter_font = _get_font(LETTER_FONT_SIZE, bold=True)
    num_font = _get_font(NUM_FONT_SIZE)
    title_font = _get_font(TITLE_FONT_SIZE, bold=True)
    tag_font = _get_font(18, bold=True)

    rows = len(grid.grid)
    cols = grid.width if hasattr(grid, 'width') else len(grid.grid[0])
    grid_w = cols * CELL
    grid_h = rows * CELL

    total_w = max(grid_w + PADDING * 2, 500)
    total_h = PADDING + TITLE_FONT_SIZE + 16 + grid_h + PADDING

    img = Image.new("RGB", (total_w, total_h), BG)
    draw = ImageDraw.Draw(img)

    title = f"정답  [{date_str}]"
    draw.text((total_w // 2, PADDING // 2 + 8), title,
              fill=ACCENT, font=title_font, anchor="mt")

    gx = (total_w - grid_w) // 2
    gy = PADDING + TITLE_FONT_SIZE + 16

    _draw_grid(draw, grid, gx, gy, num_font, show_letters=True, letter_font=letter_font)
    _draw_tag(draw, gx, gy, grid_w, grid_h, tag_font)

    img.save(output_path, dpi=(150, 150))
    print(f"정답 저장 완료: {output_path}")
    return output_path
