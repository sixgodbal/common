# 丛林深处（Jungle Depths）40×40 地图资源

淡绿 / 多树 / 少量蛇元素的炸弹人式地图。风格取自第二批 L2（中等柔和光）。

## 关键文件

| 文件 | 说明 |
|---|---|
| `out/map_40x40_assembled.png` | **最终拼装地图，1600×1600（40px/格），元素底座 100% 对格** |
| `out/map_40x40_assembled_2x.png` | 2× 最近邻预览，3200×3200 |
| `out/map_40x40_assembled_gridcheck.png` | 40px 红线网格 + 中央 4×2 门高亮，用于验收对齐 |
| `out/_elements_preview.png` | 15 个元素 8× 预览（棋盘格透明底） |
| `out/elements/` | 40px 游戏用元素 PNG |
| `out/layout_40x40.json` | 40×40 布局数据（0 地板 / 1 树墙 / 2 树砖 / 3 门 / 4 水 / 5 出生点 / 6 蛇纹砖） |
| `out/layout_40x40.png` | 布局可视化 |
| `prompts/` | 各次方舟生图提示词与 seed |
| `tools/` | 切图、元素处理、拼装、网格检查脚本 |

## 元素规格（严格对格）

- 地板：**40×40**，无缝平铺，4 向翻转复用。
- 树墙 / 树砖：画布 **40×60**，其中底座 40×40，向上溢出 20px；底座中心 = 格子中心，底边 = 格子底边。
- 组合墙（空心古树门）：画布 **160×100**，底座 4×2 格（160×80），向上溢出 20px。
- 放置公式：`x = c*40`，`y = (r+1)*40 - sprite.height`。所有元素由脚本放置，不依赖 AI 对格。

## 元素清单

| 类别 | 文件 |
|---|---|
| 地板（旧，路径用） | `floor_stone` |
| 地板（新，草地） | `floor2_grass_plain` / `grass_flowers` / `grass_moss` |
| 地板（新，泥土备用） | `floor2_earth_plain` / `earth_leaves` |
| 水面 | `pond_4x4_160`（4×4 连续水纹理，整块贴，无内部接缝） |
| 树墙 | `wall_tree` / `wall_bush` / `wall_root` / `wall_stump` / `wall_fern` / `wall_snake_totem` |
| 树砖 | `brick_log` / `brick_sapling` / `brick_bush` / `brick_stump` / `brick_snake` |
| 组合墙 | `gate_ancient_tree` |

## 复现

```powershell
cd D:\ai\git_tools\common\ai\sweet_res_material\jungle_depths

# 1) 布局（如需改格子，改 build_layout.py 后重跑）
python tools\build_layout.py

# 2) 从元素大图切 40px 元素（依赖 out/jungle_depths_elements_a.png 与 gate 图）
python tools\build_elements.py

# 3) 从地板大图切 40px 地板（依赖 out/jungle_depths_floors_b.png）
python tools\build_floor_set.py

# 4) 拼装 40×40 地图
python tools\assemble_map.py

# 5) 40px 网格验收图
python tools\overlay_grid.py out\map_40x40_assembled.png
```

## 已知待改进

- 元素底部仍带 AI 生成的轻微投影；正式进游戏前建议在 Aseprite 里擦掉（指南要求无投影）。
- 水面是整块 4×4 纹理，池边是 1px 深色岸线，还不是自然岸；后续可补 4 边/4 角的水岸 tile。
- 地板为 AI 纹理降采样，1x 下还能看到 40px 重复；正式版建议手工清理接缝或再出 3–4 个变体。
- 当前布局偏开阔，若用于对战可再加 10–20 个单树/树砖掩体。
