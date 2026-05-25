"""
生成屏幕使用时间图标
靛蓝色圆角背景 + 白色时钟柱状图 + 马头角标
输出标准多尺寸 .ico 文件
"""

import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

PROJECT_DIR = Path(__file__).parent
ICON_PATH = PROJECT_DIR / "icon.ico"
MARVIS_HEAD = Path(r"C:\Users\zikua\AppData\Roaming\Tencent\Marvis\marvis-offline-page\using\assets\icon-logo-head-DPd_M1sY.png")

# 颜色
BG_COLOR = (94, 92, 230)  # 靛蓝
WHITE = (255, 255, 255)
CLOCK_COLOR = (255, 255, 255)

def create_icon(size=256):
    """创建图标，返回 PIL Image"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 圆角矩形背景
    radius = int(size * 0.22)
    # 绘制圆角矩形
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([0, 0, size - 1, size - 1], radius, fill=255)
    bg = Image.new("RGBA", (size, size), BG_COLOR)
    img = Image.composite(bg, img, mask)
    draw = ImageDraw.Draw(img)

    # 计算比例
    cx, cy = size / 2, size / 2
    bar_area_top = int(size * 0.25)
    bar_area_bottom = int(size * 0.65)

    # 绘制时钟
    clock_r = int(size * 0.12)
    clock_x = int(size * 0.13)
    clock_y = int(size * 0.14)
    # 时钟外圈
    draw.ellipse([clock_x - clock_r, clock_y - clock_r, clock_x + clock_r, clock_y + clock_r],
                 outline=WHITE, width=max(2, int(size * 0.018)))
    # 时钟指针
    import math
    line_len = int(clock_r * 0.55)
    angle1 = math.radians(-60)
    angle2 = math.radians(150)
    x1 = clock_x + int(math.cos(angle1) * line_len)
    y1 = clock_y + int(math.sin(angle1) * line_len)
    x2 = clock_x + int(math.cos(angle2) * line_len * 0.7)
    y2 = clock_y + int(math.sin(angle2) * line_len * 0.7)
    draw.line([clock_x, clock_y, x1, y1], fill=WHITE, width=max(2, int(size * 0.015)))
    draw.line([clock_x, clock_y, x2, y2], fill=WHITE, width=max(2, int(size * 0.012)))
    # 时钟中心点
    dot_r = max(2, int(size * 0.025))
    draw.ellipse([clock_x - dot_r, clock_y - dot_r, clock_x + dot_r, clock_y + dot_r], fill=WHITE)

    # 绘制柱状图（5根柱子，不同高度）
    bar_count = 5
    bar_w = int(size * 0.065)
    bar_gap = int(size * 0.04)
    total_w = bar_count * bar_w + (bar_count - 1) * bar_gap
    start_x = int((size - total_w) / 2)
    base_y = bar_area_bottom
    heights = [0.55, 0.82, 0.65, 0.95, 0.72]

    for i, h_ratio in enumerate(heights):
        bh = int((base_y - bar_area_top) * h_ratio)
        x = start_x + i * (bar_w + bar_gap)
        y = base_y - bh
        # 圆角柱子
        bar_r = max(1, int(bar_w * 0.3))
        draw.rounded_rectangle([x, y, x + bar_w, base_y], bar_r, fill=WHITE)

    # 绘制马头角标
    try:
        if MARVIS_HEAD.exists():
            horse = Image.open(MARVIS_HEAD).convert("RGBA")
            badge_size = int(size * 0.26)
            horse = horse.resize((badge_size, badge_size), Image.LANCZOS)

            # 圆形裁剪马头
            circle_mask = Image.new("L", (badge_size, badge_size), 0)
            mask_d = ImageDraw.Draw(circle_mask)
            mask_d.ellipse([0, 0, badge_size - 1, badge_size - 1], fill=255)
            horse = Image.composite(horse, Image.new("RGBA", (badge_size, badge_size), (0, 0, 0, 0)), circle_mask)

            # 白色描边（画在稍大一点的圆上）
            stroke_r = badge_size // 2
            stroke_img = Image.new("RGBA", (badge_size + 4, badge_size + 4), (0, 0, 0, 0))
            stroke_draw = ImageDraw.Draw(stroke_img)
            stroke_draw.ellipse([0, 0, badge_size + 3, badge_size + 3], outline=WHITE,
                                width=max(2, int(badge_size * 0.08)))

            # 粘贴
            badge_x = size - badge_size - int(size * 0.04)
            badge_y = size - badge_size - int(size * 0.04)
            # 先贴描边
            img.paste(stroke_img, (badge_x - 2, badge_y - 2), stroke_img)
            img.paste(horse, (badge_x, badge_y), horse)
    except Exception as e:
        print(f"Warning: 无法加载马头图标: {e}")

    return img


def save_ico():
    """生成多尺寸 ICO 文件"""
    sizes = [256, 128, 64, 48, 40, 32, 24, 16]
    images = []
    for s in sizes:
        images.append(create_icon(s))
    images[0].save(str(ICON_PATH), format="ICO", sizes=[(s, s) for s in sizes], append_images=images[1:])
    print(f"图标已生成: {ICON_PATH}")


if __name__ == "__main__":
    save_ico()