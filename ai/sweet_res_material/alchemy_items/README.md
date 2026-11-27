# 炼金材料 / 药草资源（45×45 / 142×142 / 256×256 母版）

一套 10 个正式物品 + 2 个备选，同一画风、同一光源。
`icons_45/` 按 `道具材料尺寸参照1.png`、`道具材料尺寸参照2.png` 的 **45×45** 游戏内物品尺寸导出；
`icons_142/` 按 `Object尺寸参照1.png`、`Object尺寸参照2.png` 的 **142×142** Object 尺寸导出；
`icons_256/` 保留 256×256 母版，方便后续改图或另做 UI 大图。
大图由方舟 `doubao-seedream-5-5` 一次生成 4×3 选型表，再按格切分、统一内容高度。

## 看这里

| 文件 | 说明 |
|---|---|
| `out/_select_45.png` | **45×45 总选择表**（放大 8 倍预览） |
| `out/icons_45/` | **12 张 45×45 PNG，透明底，游戏内直接用** |
| `out/preview_8x/` | 45×45 的 8 倍最近邻预览图（360×360） |
| `out/_select_142.png` | **142×142 Object 总选择表**（放大 2 倍预览） |
| `out/icons_142/` | **12 张 142×142 PNG，透明底** |
| `out/preview_2x/` | 142×142 的 2 倍最近邻预览图（284×284） |
| `out/_select_alchemy.png` | 256×256 母版选择表 |
| `out/icons_256/` | 12 张 256×256 PNG 母版 |
| `out/alchemy_sheet_a.png` | 方舟原图，2304×1728 |
| `out/alchemy_sheet_a_cut.png` | 去底中间图 |
| `out/single/` | 单物品重绘（回魂草）及其 256 归一化结果 |
| `prompts/alchemy_sheet.json` | 整张选型表的提示词、参考图、seed |
| `prompts/soulgrass_single.json` | 回魂草 45px 简化重绘提示词 |
| `tools/slice_grid.ps1` | 通用网格切图：去底、按格取包围盒、统一缩放 |
| `tools/make_game_icons.py` | 256 母版 → 目标尺寸：缩放、二值透明边、主体 1px 描边 |
| `tools/make_contact_sheet.ps1` | 通用带标签选择表 |

## 物品清单

| 文件名 | 名称 | 内容 |
|---|---|---|
| `dew.png` | 露水 | 叶上单滴露珠，冰蓝白高光 + 星点 |
| `spring_water.png` | 山涧泉水 | 卷起的清泉水花，白浪与气泡，无容器 |
| `bottle_small.png` | 小小的瓶子 | 空玻璃瓶，矮圆瓶身 + 木塞，最简 |
| `bottle_medium.png` | 大一点的瓶子 | 空玻璃瓶，长颈、银颈环 + 蓝缎带 |
| `bottle_large.png` | 大很多的瓶子 | 空玻璃瓶，金底座 + 宝石塞，最华丽 |
| `fruit_unripe.png` | 未成熟的水果 | 青绿色硬果，小、哑光、带叶 |
| `fruit_ripe.png` | 成熟的水果 | 同种果实，红橙色、饱满、有光泽 |
| `herb_bundle.png` | 草药 | 一束绿叶草药，棕色麻绳扎中 |
| `lingzhi.png` | 灵芝 | 红棕漆面菌盖 + 同心环纹 + 米色菌腹 |
| `soulgrass.png` | 回魂草 | 淡蓝白发光草叶 + 灵体星点 |
| `dew_alt.png` | 露水·备选 | 四叶草上的三滴露珠 |
| `spring_water_alt.png` | 泉水·备选 | 竹筒盛装的泉水 |

三档瓶子共用同一瓶型语言，只加高、加装饰；未熟/成熟水果共用同一轮廓，只变大小、颜色和光泽。

## 药瓶选型（第一轮）

以这三只空瓶为瓶型，做了 **3 种尺寸 × 4 种药液 = 12 版**：

| 文件 | 说明 |
|---|---|
| `out/potions/potion_sheet_1024x768.png` | **4×3 总表，每格正好 256×256** |
| `out/potions/_select_potions.png` | 带中文标签的选择表（每格 256） |
| `out/potions/icons_256/` | 12 张 256×256 透明底单图 |
| `out/potions/potion_small_sheet.png` 等 | 3 张 2×2 方舟源图（1024×1024） |
| `out/potions/ref_bottles_vertical.png` | 三只空瓶竖向参考图 |
| `prompts/potion_sheets_3.json` | 三张源图的提示词与 seed |
| `tools/assemble_potions.py` | 去底、按行统一高度、拼 1024×768 总表 |

- 行 = 尺寸：小药瓶 / 中药瓶 / 大药瓶；256 画布内内容高度 **184 / 210 / 236 px**，底部对齐。
- 列 = 药液：红心恢复 / 蓝星法力 / 绿叶自然 / 金冠皇家。
- 瓶型对应空瓶：矮圆瓶+木塞 / 长颈+银环+蓝缎带 / 金座+宝石塞。
- 第一版混合大图（瓶型有漂移）已归档到 `out/potions/archive/`。

### v1 红色三瓶（45 / 142）

从 `out/potions/archive/potion_sheet_a_v1_mixed.png` 第 1 列抽出三只红色药瓶，按同一比例缩放到 256 母版后导出 45 与 142：

| 文件 | 说明 |
|---|---|
| `out/potions/v1_red/icons_45/` | 3 张 45×45 透明 PNG |
| `out/potions/v1_red/icons_142/` | 3 张 142×142 透明 PNG |
| `out/potions/v1_red/icons_256/` | 3 张 256 母版（内容高度 188 / 230 / 236） |
| `out/potions/v1_red/_select_45.png` | 45 三瓶选择表（8 倍预览） |
| `out/potions/v1_red/_select_142.png` | 142 三瓶选择表（2 倍预览） |
| `tools/extract_v1_red.py` | 从 v1 大图抽列、去底、统一比例 |

## 彼岸花（选中：第 2 行第 3 个，发光版）

按新流程：选型阶段只出一张 **1280×768、5×3 格、每格 256×256** 的大图，不切图；确认后才切项目用图。

| 文件 | 说明 |
|---|---|
| `out/lycoris/lycoris_sheet_a.png` | 15 版选型大图，1280×768 |
| `out/lycoris/cut/icons_45/lycoris_glow.png` | **45×45 透明 PNG** |
| `out/lycoris/cut/icons_142/lycoris_glow.png` | **142×142 透明 PNG** |
| `out/lycoris/cut/icons_256/lycoris_glow.png` | 256 母版（保留柔光） |
| `out/lycoris/cut/_preview.png` | 45 / 142 / 256 三尺寸预览 |
| `prompts/lycoris_sheet.json` | 选型提示词与 seed |
| `tools/cut_glow_icon.py` | 裁格 + 柔光 alpha；45px 自动收紧光晕 |

- 45px：用二值透明阈值收紧外发光，保证小尺寸下花瓣和轮廓可读。
- 142 / 256：保留完整柔光、火星和光晕。
- 1024×768 低于方舟最小像素面积（921,600），所以 4×3 的 256 格实际用 **1280×768（5×3）**。

## 规格

- 物品尺寸：**45×45**，RGBA，透明底，内容约 90% 填充并居中。
- Object 尺寸：**142×142**，RGBA，透明底，同一套构图与描边处理。
- 母版：256×256，RGBA，透明底；源图 2304×1728（4 列 × 3 行，每格 576×576）。
- 缩放处理：LANCZOS 缩放 → alpha 二值化 → 只给主体（≥20px 的连通块）补 1px 深色描边，星点等小碎块不描边，避免缩成空心圈。
- 风格：16bit 像素风、1px 选择性深色描边、2–3 阶硬边平涂、左上打光、饱和玩具配色。
- `回魂草` 在 45px 下细叶会糊，已按单物品重新简化重绘（5 片粗叶 + 中心光点），并同步替换了 256 母版。

## 复现 / 改款

```powershell
# 1) 出大图（seed 在 prompts/alchemy_sheet.json 里）
& D:\ai\git_tools\common\ai\sweet_cg\tools\ark_image.ps1 `
  -Prompts .\prompts\alchemy_sheet.json -OutDir .\out -Size 2304x1728

# 2) 切图（名字按行优先顺序，用 - 跳过空格）
& .\tools\slice_grid.ps1 -Sheet .\out\alchemy_sheet_a.png -OutDir .\out\icons_256 -Prefix alchemy `
  -Cols 4 -Rows 3 -Cell 256 -Fill 0.9 `
  -Names "dew,spring_water,bottle_small,bottle_medium,bottle_large,fruit_unripe,fruit_ripe,herb_bundle,lingzhi,soulgrass,dew_alt,spring_water_alt"

# 3) 256 选择表
& .\tools\make_contact_sheet.ps1 -Dir .\out\icons_256 -Out .\out\_select_alchemy.png `
  -Title "炼金材料 / 药草资源（256x256）" -Cols 4 -Rows 3 -Cell 256 `
  -Labels "1 露水|2 山涧泉水|3 小瓶（空）|4 中瓶（空）|5 大瓶（空）|6 未成熟水果|7 成熟水果|8 草药|9 灵芝|10 回魂草|11 露水·备选|12 泉水·备选" `
  -Files "dew|spring_water|bottle_small|bottle_medium|bottle_large|fruit_unripe|fruit_ripe|herb_bundle|lingzhi|soulgrass|dew_alt|spring_water_alt"

# 4) 出 45×45 游戏图标 + 8 倍预览
python .\tools\make_game_icons.py --src .\out\icons_256 --out .\out\icons_45 --size 45 --preview-scale 8

# 5) 45 选择表（用 8 倍预览图，避免放大发虚）
& .\tools\make_contact_sheet.ps1 -Dir .\out\preview_8x -Out .\out\_select_45.png `
  -Title "炼金材料 / 药草资源（45x45 游戏图标）" -Cols 4 -Rows 3 -Cell 360 `
  -Labels "1 露水|2 山涧泉水|3 小瓶（空）|4 中瓶（空）|5 大瓶（空）|6 未成熟水果|7 成熟水果|8 草药|9 灵芝|10 回魂草|11 露水·备选|12 泉水·备选" `
  -Files "dew|spring_water|bottle_small|bottle_medium|bottle_large|fruit_unripe|fruit_ripe|herb_bundle|lingzhi|soulgrass|dew_alt|spring_water_alt"

# 6) 出 142×142 Object 图标 + 2 倍预览
python .\tools\make_game_icons.py --src .\out\icons_256 --out .\out\icons_142 --size 142 --preview-scale 2

# 7) 142 选择表
& .\tools\make_contact_sheet.ps1 -Dir .\out\preview_2x -Out .\out\_select_142.png `
  -Title "炼金材料 / 药草资源（142x142 Object 图标）" -Cols 4 -Rows 3 -Cell 284 `
  -Labels "1 露水|2 山涧泉水|3 小瓶（空）|4 中瓶（空）|5 大瓶（空）|6 未成熟水果|7 成熟水果|8 草药|9 灵芝|10 回魂草|11 露水·备选|12 泉水·备选" `
  -Files "dew|spring_water|bottle_small|bottle_medium|bottle_large|fruit_unripe|fruit_ripe|herb_bundle|lingzhi|soulgrass|dew_alt|spring_water_alt"
```

只换单个物品时：改 JSON 里的主题描述、换 `seed` 再跑一次；或者按同一提示词单瓶重出 1024×1024，再整数降采样到 256。

## 注意

- 45×45 与 142×142 都是由 256 母版缩放得到的，配色和构图与母版一致。
- `Object尺寸参照` 只按尺寸对齐，仍保持本套像素风；如果 142 这套需要像 Object 参照图那样的亮面 2.5D 风格（无像素格、带外发光），需要另起一套提示词重新生成。
- 45×45 参考图（手绘像素）的“块状像素”更硬，如果要完全达到那种手感，还需要在 Aseprite 里按 45 网格手工修一轮。
- 256 单图是 2304 大图切出后缩放的**选型/预览版**，边缘有轻微重采样。
- 定稿后若要真正的整数像素，按单物品重出 1024×1024 → 4× 降采样到 256 → 限色 12–20 → 补 1px 选择性描边。
- 空瓶三件套内部完全无液体、无标签、无符号；后续“装药水”的版本沿用同一瓶型与光源。
