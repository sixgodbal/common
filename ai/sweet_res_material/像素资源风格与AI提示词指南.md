# 像素资源风格 & AI 提示词指南 v1.0

> 分析对象：`D:\sixgod\gitproject\test\Code\Demo\Assets\Data`（Sprites / Prefabs / Scripts）
> 用途：给新角色（衣服、头发、拼装整体）、地板、墙、组合墙、砖块等资源做 AI 生图 / 外包 / 内部制作的统一规范与提示词。
> 参考图：同目录 `art-style-refs/`（01~18 号图，均为本次从原资源拼的对照图）。

---

## 0. 一句话风格

**16bit 复古街机像素风 + 现代手游高饱和“玩具/糖果感”配色 + 2.5D 俯视视角的 Q 版换装角色，以及“每一块墙/砖都是一件小道具”的装饰化关卡美术。**

关键词（可直接复用）：
`16-bit pixel art / top-down 3-4 view / bomberman-like / chibi paper-doll character / saturated toy palette / 1px selective outline / candy & toy prop / Chinese festival & pop-culture themed / clean readable silhouette`

---

## 1. 资源地图（实际有什么）

### 1.1 角色（`Sprites/Dress`，纸娃娃分层系统）

代码里共 **16 个换装槽位**（`HeroPart` 枚举），从后往前叠：

| 顺序 | 槽位 | 实际内容（实测） | 画布参考 |
|---|---|---|---|
| 1 | `PrimeBody0` | **基础裸身 Q 版身体**（100×100，粉肤色）或**整套特殊形态**（盔甲武士、猫、蛇、美杜莎、足球少年…） | 100×100 |
| 2 | `PrimeBody0Mask` | 基础身体的**灰度版**，用于运行时染色 | 100×100 |
| 3 | `PrimeBody1` | 整身套装 / 变身皮肤（如白色绵羊服） | 100×100 |
| 4 | `Pack` | 背部挂饰：翅膀、披风、弓、法杖、蝴蝶结 | ~97×73 |
| 5 | `Foot` | 鞋子 | ~31×19 |
| 6 | `ClothMask` | 衣服灰度版（染色用） | ~31×41 |
| 7 | `Cloth` | 上衣 / 套装 / 连体睡衣 / 球衣 | ~67×59 |
| 8 | `Body` | 手持大件 / 武器槽：锤、斧、狼牙棒、枪、弓、汉堡… | ~39×31 |
| 9 | `Hand` | 手持小道具槽：冰淇淋、法杖、书、炸弹、啤酒… | ~75×59 |
| 10 | `Mask` | 面饰：墨镜、护目镜、头盔、口罩、脸谱 | ~55×71 |
| 11 | `Face` | **五官层**（只有眼睛、嘴、腮红） | ~43×25 |
| 12 | `Ghost` | 跟宠 / 漂浮特效：幽灵、气球、小龙、UFO | ~111×55 |
| 13 | `Head` | 头顶漂浮挂饰：光环、钥匙、花、爱心、星星、骷髅 | ~59×65 |
| 14 | `Hair` | 发型（含刘海/鬓角，不含脸） | ~59×55 |
| 15 | `Cap` | 帽子 / 头饰：圣诞帽、猫耳、皇冠、恶魔角 | ~81×73 |
| 16 | `HairMask` | 头发灰度版（染色用） | ~61×61 |

> 说明：`Body`/`Hand` 在资源里都是“手持物”，可理解为武器槽 + 小道具槽；真正的手臂/腿在 `PrimeBody0` 基础身体里。`Ghost` 是跟随特效，可做“宠物/守护灵”卖点。
>
> 源码依据：`Scripts/View/Role/HeroViewCtrl.cs`、`EquipmentCache.cs`；渲染排序约 350–366（影子 320）。

### 1.2 对局地图（`Sprites/MapElem`）

| 目录 | 数量（png） | 说明 |
|---|---|---|
| `Floor` | 165 | 40×40 地面，含纯色/纹理/过渡边/箭头/井盖/裂纹等地砖 |
| `Wall` | 131 | 单格不可破坏装饰块（部分可被技能影响），40 底宽，向上溢出 9–41px 表现高度 |
| `ComposeWall` | 56 张 / 约 50 组 | 多格组合建筑/道具，2×2 ~ 5×4 格，长条可到 17×4、3×13 |
| `Brick` | 60+ 组 | 可炸软砖，顶部印图标（数字/图案/星星/宝箱…），含 idle/hit/die |
| `WoodenBrick` | 2 组 | 木箱类 |
| `MoveBrick` | 9 组 | 可推动滑行的砖 |
| `Door` | 11 组 | 传送门/门，enter 动画 |
| `Grass` | 2 组 | 可割草丛，enter/die 动画 |
| `River` | 13 | 40×40 水面/水流，部分多帧 |
| `SpikeWallUp/Down/Left/Right` | 4 | 四方向尖刺墙 |
| `Totem` | 5 组 | 图腾，idle/四方向攻击 |
| `Sculpture` | 3 组 | 雕像，多阶段石化解谜 |
| `PinFloor / PoisonFloor / PropFloor / SculptureStoneFloor / BrickSpawnFloor` | 各 1 | 特殊功能地砖 |

### 1.3 美术双轨制（重要）

- **游戏内**：全部是**低分辨率像素 sprite**（1x 像素点，40px 一格）。
- **UI/头像/剧情**：`Sprites/Head`、`RoomPage/selRole_*` 是**日系 Q 版插画**（非像素、软阴影、干净线稿）。
- 新资源不要把两套混在一起：**做对局资源就纯像素；做头像再走插画风**。

---

## 2. 风格 DNA（12 条，生成时必须体现）

1. **真像素**：每个像素点都是实心色块，不做半透明羽化、不抗锯齿、不缩放模糊。
2. **低分辨率、高信息密度**：地板 40×40，砖块 40×40，角色画布 100×100（内容约 43×63）；靠 2–4 阶明暗和 1px 细节表达材质。
3. **高饱和玩具色**：正红、柠檬黄、草绿、天蓝、薄荷青、奶油白；阴影用同色相压暗（红→酒红、绿→墨绿），高光用奶白 `#FFFEF5`。
4. **选择性描边**：外轮廓 1px，颜色为**固有色加深**（如红衣 `#4E0000`）或近黑 `#181818`；皮肤/浅色物体可以只靠暗部收边，不描黑边。
5. **左上主光**：顶面最亮 → 正面中间调 → 侧面/底面最暗；高光常点在左上角。
6. **硬边平涂 + 少量抖动**：拒绝柔和渐变；需要过渡时用棋盘格/点状 dither。
7. **Q 版二头身**：头约占身高一半，大头、短手短脚、五官集中在脸下半部。
8. **装饰化道具**：墙不是“砖纹墙”，而是鼓、宝箱、雪人、仙人掌、冰淇淋机、城楼、猫巴士……**每格一个主题小雕塑**。
9. **厚顶薄底**：砖块/墙都有“顶面大平面 + 正面深色底座/侧面”的立体感，像巧克力/软糖。
10. **主题化配色**：同一张图的地板/墙/砖共享一套 6–10 色主色，换主题=换色板 + 换道具，而不是换画风。
11. **剪影优先**：1x 缩小后仍能一眼分辨“能走/不能走/能炸/危险”。
12. **干净背景**：资源一律透明底，不带投影（投影由引擎影子/角色自带 shadow 处理），不带 UI 边框。

---

## 3. 技术规格（硬约束）

### 3.1 网格与画布

| 项 | 规格 |
|---|---|
| 基础格 | **40×40 px**（100 PPU = 0.4 Unity 单位） |
| 地面/水 | 40×40，四边可无缝平铺 |
| 墙 | 宽 40（可 42），高 49–81（底 40 + 向上溢出 9–41px），**底边贴格、底座居中** |
| 砖块 | 底面 40×40 + 10–20px 高度，成品约 42–48×49–60；特殊大砖 80×80（2×2） |
| 组合墙 | N×M 格，整图一张；实测：161×110(4×2.75)、200×154(5×3.85)、600×80(15×2)、120×520(3×13) |
| **元素对格** | **所有单独元素的底座（footprint）中心必须与格子中心重合**；底座按 40×40 设计占地计算，不是可见窄底。元素可高矮不同，只允许向上溢出，水平/纵深不得偏移半格或整格。画布可比 40 宽（如 42），但多出的像素必须左右对称。 |
| 角色整体 | 画布 100×100；裸身实际绘制区域约 **43×63**，叠帽子/背饰后可超出画布 |
| 角色部件 | 各自独立画布，围绕**同一中心点**绘制（中心 pivot 0.5,0.5），叠合即成型 |
| 锚点 | 地图元素：**bottom-left**（Unity alignment 6, pivot 0,0）；角色部件：**center** |
| 透明 | RGBA PNG，Alpha 干净，无白边/黑边残留 |
| 导入 | 关闭 Mipmap，保留 Alpha，PPU=100，Filter 跟随项目（现为 Bilinear）；像素必须落在整数像素上 |
| 缩放 | 禁止非整数缩放导出；预览放大只用 Nearest |

### 3.2 角色动画与命名

- 四方向编号：**1=右，2=上（背面），3=左，4=下（正面）**
- 状态：`stand`（每方向 1 帧）、`move`（每方向 6 帧）、`trigger`（5 帧，放炸弹/受击）、`cry`（2 帧，失败）
- 帧文件名：`<ID> <方向>-<帧>.png`，例：`280001 4-1.png` = 下方向第 1 帧
- 目录：`Dress/<part>/<ID>/<状态>/<方向>/`
- 所有帧**同画布尺寸、同中心点**，身体不能上下抖（除刻意做弹跳）
- 特殊整套形态（PrimeBody0）可有自定义动画名与帧数（如 boss 走路、蛇游行）

### 3.3 地图资源命名

```
MapElem/Floor/<ID>.png
MapElem/Wall/<ID>.png
MapElem/ComposeWall/<ID>.png           或  <ID>/idle/<ID>_<帧>.png
MapElem/Brick/<ID>/idle|hit|die/<ID>_<帧>.png
MapElem/River/<ID>.png
MapElem/Door/<ID>/idle|enter/<ID>_<帧>.png
```
- ID 分段规律：地面 `1xxx`、墙 `2xxx`、门 `25xx`、木箱/砖 `30xx`、可推砖 `35xx`、组合墙 `40xx`、草 `50xx`、特殊地砖 `60xx`、水 `70xx`、尖刺 `8xxx–11xxx`、图腾 `120xx`。

### 3.4 动画节奏（实测）

- 砖块 `die`：3–7 帧；碎成 4–6 块 + **白色像素烟尘/星点**，碎块缩小消失。
- 冰块：碎裂成白色雪花/冰晶点。
- 木箱：木片崩开 + 白烟。
- `hit`：3–4 帧，整体抖动/闪白/裂痕。
- 组合墙：多为 1 张静帧；少数 4–6 帧循环（霓虹灯呼吸、灵体浮动、水波）。

---

## 4. 调色板与材质

### 4.1 从原资源实测的核心色

| 用途 | 色值 |
|---|---|
| 奶白高光 | `#FFFEF5` `#FFF791` `#F8F4C0` |
| 正红 / 亮红 | `#D03430` `#E84838` `#C83430` |
| 红色暗部（阴影/描边） | `#4E0000` `#800603` `#903430` |
| 暖黄 / 金 | `#FAB51A` `#FFD14C` `#DF812F` |
| 草绿 / 亮绿 | `#188600` `#4AB600` `#10A820` `#68E048` |
| 薄荷青 / 水 | `#68A0A8` `#B0DCE0` `#C8E8E8` |
| 深蓝 / 科技蓝 | `#105098` `#003468` |
| 木棕 / 土 | `#522C18` `#391808` `#6B4129` |
| 肤色 | `#EBAF8A` `#D48062` |
| 腮红 / 粉 | `#A03B54` `#DD5640` |
| 黑描边 | `#000000` `#181818` `#282828` |

### 4.2 材质画法

| 材质 | 画法 |
|---|---|
| 石砖/城墙 | 大块面 + 2–3 阶灰米色，砖缝 1px 深色，随机裂纹/缺角 |
| 木头 | 横向木纹 + 年轮 + 深棕描边，边缘磨圆 |
| 冰 | 青白高反差，白高光斜条，半透明感靠“冷色暗部 + 亮边”，不要真透明 |
| 水 | 蓝色底 + 浅色波纹弧线 + 白色浪花点；可循环位移 |
| 金属 | 灰色高反差 + 铆钉 + 一条竖向高光 |
| 草地/植物 | 3–4 阶绿，叶团用圆形像素簇，暗部偏蓝绿 |
| 糖果/软糖 | 高饱和粉/薄荷/柠檬，圆角 + 奶油高光 + 糖针点 |
| 岩浆 | 深红底 + 橙黄裂缝 + 黑火山岩块，发光靠亮色像素而非外发光 |
| 国风 | 米白/朱红/鎏金/青玉，回纹、云纹、匾额、灯笼 |

---

## 5. 角色提示词

### 5.1 整体拼装效果（最重要的“像不像”）

- 正面：大头 + 齐刘海/双马尾/丸子头，眼睛占脸 1/2，腮红 1–2 个像素点；小身子、短腿。
- 侧面：只画一只眼，鼻尖 1px，后脑勺圆润，头发/帽子外轮廓清晰。
- 背面：不画脸，用后脑勺 + 发缝/发饰/帽子背面 + 背包来识别。
- 叠装后不能互相打架：头发不能盖住眼睛，帽子压住发顶，背包在身体后方，手持物在手的右侧/前方。
- 换装卖点：同一身体上换发型、帽子、面饰、背饰、手持物、跟宠，要能一眼看出“新物品”。

### 5.2 英文主提示词（角色）

```text
16-bit pixel art, cute chibi game character, 2-heads-tall proportions, oversized head,
tiny body, stubby limbs, front-facing idle pose, big anime eyes, small mouth, blush,
[HAIR: black twin buns with red ribbons], [OUTFIT: white and blue soccer jersey with shorts],
[SHOES: red sneakers], [ACCESSORY: silver sunglasses], [BACK: small angel wings],
1px selective dark outline, 14-color saturated toy palette, flat cel shading, top-left light,
clean readable silhouette, transparent background, centered, no shadow, game-ready sprite, 100x100 canvas
```

### 5.3 中文主提示词（角色）

```text
16bit像素风，Q版二头身游戏角色，正俯视正面站立，大头小身短手脚，日系大眼睛小嘴腮红，
黑色双丸子头配红发带，白蓝足球球衣短裤，红色运动鞋，银色墨镜，小型天使翅膀背饰，
1像素选择性深色描边，14色高饱和玩具配色，硬边平涂，左上打光，剪影清晰，
透明背景，居中，无投影，游戏可用精灵图，100×100画布
```

### 5.4 分部件提示词

> 关键：**一次只生成一个槽位**，画布比例按表 1.1 给，全部透明底、同中心点，最后在 Aseprite/PS 里对齐。

**头发（Hair）**
```text
pixel art hairpiece only for a chibi character, isolated on transparent background,
front view, [black twin buns with red ribbons], glossy 3-tone shading, 1px dark outline,
59x55 px, centered, no head, no face, no body
```
`中文：像素风假发/发型单品，透明背景，正面，黑色双丸子头+红发带，3阶高光，1px深色描边，59×55，居中，不含头/脸/身体`

**衣服（Cloth）**
```text
pixel art top garment only, chibi character clothing, [red Chinese-style short jacket with gold trim],
front view, 3-tone fabric shading, 1px outline, transparent background, 67x59 px, no body, no arms
```
`中文：像素风上衣单品，[红色国风短褂+金边]，正面，3阶布料明暗，1px描边，透明底，67×59，不含身体和手臂`

**脸部（Face）**
```text
pixel art anime face features only, [big ruby eyes with white highlights, tiny smile, blush],
transparent background, 43x25 px, front view, no head shape, no hair
```
`中文：像素风五官贴图，[红宝石大眼+白高光、小嘴、腮红]，透明底，43×25，正面，不含头型和头发`

**帽子（Cap）**
```text
pixel art hat only, [Santa hat with white fur trim], 3/4 top-down view, 1px outline,
glossy highlight, transparent background, 81x73 px, centered
```

**面饰（Mask）**
```text
pixel art face accessory only, [silver aviator sunglasses], front view, transparent background,
55x71 px, 1px outline, metal highlight
```

**背饰（Pack）**
```text
pixel art back accessory only, [pair of white angel wings], symmetrical, transparent background,
97x73 px, soft 3-tone shading, no body
```

**跟宠（Ghost）**
```text
pixel art floating companion, [tiny cute ghost / balloon / baby dragon], 3-4 frame idle bob,
transparent background, 111x55 px, soft glow made of light pixels (no blur)
```

**基础身体（PrimeBody0）**
```text
pixel art chibi base body, bald head, 2-heads-tall, peach skin, no face, no clothes,
front/side/back views, 1px darker-skin outline, transparent background, 100x100 px, centered
```
> 肤色染色用灰度版 `PrimeBody0Mask`：只保留明度，白=高光，灰=中间调，深灰=暗部，不要彩色。

**整套形态 / 皮肤（PrimeBody0 特殊 / PrimeBody1）**
```text
pixel art full-body mascot costume character, [armored warrior / green snake / white sheep],
chibi proportions, front-facing idle, full 4-direction sprite, 1px outline, 20-color palette,
transparent background, 100x100 px, feet aligned to same baseline
```

### 5.5 四方向 / 行走帧提示词

```text
pixel art character sprite sheet, same chibi character, 4 directions (front, back, left, right),
each direction: 1 idle frame + 6-frame walk cycle, consistent baseline and head anchor,
1px outline, 14-color palette, transparent background, even grid spacing, no labels
```
`中文：像素角色四方向精灵表，正面/背面/左/右，每方向1帧站立+6帧行走，脚底线与头部锚点一致，1px描边，14色，透明底，等距网格，无文字`

---

## 6. 地板（Floor）

### 6.1 设计规则

- 40×40 **四边无缝**；纹理不能有明显方向性，避免一眼看出重复。
- 明度中等、对比中低：**不能比砖块/角色更抢眼**。
- 每套主题 3–6 张基础变体 + 1–2 张过渡/边缘 + 少量装饰砖（裂缝、花纹、箭头、井盖、地毯、路线）。
- 不画投影、不画立体厚度；纯俯视。
- 允许少量主题性图案：足球场白线、国风回纹/方砖、箭头地砖、目标圆环、门垫。

### 6.2 主题与参考色

| 主题 | 参考资源 | 色感 |
|---|---|---|
| 灰石庭院 | Floor 1001/1002/1187 | 米灰 + 深灰缝 |
| 草地 | 1007/1008/1041/1147 | 草绿 + 深绿点 |
| 泥土/沙 | 1004–1006/1069 | 沙金/土黄 + 棕点 |
| 木地板 | 1021 | 深棕木纹 |
| 水面 | 1035/1103/1106/1156 | 青蓝 + 白浪 |
| 冰雪 | 1163/1166 | 青白 + 冷蓝阴影 |
| 岩浆/火山 | 深色火山岩地（参考地图 1500）+ Wall 2021–2026 | 黑岩 + 橙红裂缝 |
| 金属/科技 | 1013/1083/1151 | 冷灰 + 蓝光 |
| 国风地砖 | 1001/1002 米灰方砖 | 米白 + 朱红点 |
| 暗夜丛林 | 1023（暗草+红蘑菇） | 墨绿 + 紫/红点 |
| 糖果/甜品 | 粉色/奶油色变体 | 粉 + 薄荷 + 奶油 |

### 6.3 提示词

```text
seamless 40x40 pixel art floor tile, [mossy gray stone bricks], top-down view,
perfectly tileable on all four edges, medium-low contrast, subtle cracks and dithering,
6-color palette, no objects, no lighting gradient, no shadow, no border, game tile
```
`中文：40×40无缝像素地砖，[青苔灰石砖]，正俯视，四边可平铺，中低对比，细微裂纹与抖动，6色，无物件无渐变无阴影无边框`

过渡砖：
```text
pixel art terrain transition tile, grass to sand, 40x40, top-down, tileable edge,
organic irregular boundary with small pebbles, 8-color, transparent outside shape
```

---

## 7. 墙（Wall，单格装饰块）

### 7.1 设计规则

- 占 1 格（40×40 底座），**向上长高 9–41px** 表现体积；**底座中心必须与格子中心重合**，底边贴格子底边，只向上溢出，不左右偏移。
- 轮廓必须清晰、饱满，像“摆在地图上的玩具/雕塑”，而不是墙纸。
- 顶面受光最亮，正面中间调，底座/侧面最暗；可加 1px 高光线。
- 主题可以是任何东西：鼓、蛋糕、宝箱、雪人、仙人掌、树、冰晶、机器人、售卖机、城楼、墓碑、路牌……
- 一般不做 die 动画（不可破坏墙）；少数有 idle 微动（火把、喷泉、霓虹、水车）。
- 四方向尖刺墙（SpikeWall）要严格按上/下/左/右出图，尖刺朝向明确。

### 7.2 提示词

```text
single destructible block prop for a bomberman-style game, [Chinese drum / treasure chest / snowman],
40x40 footprint with 12 px height overhang, front-facing 3/4 top-down view,
base footprint centered exactly on the grid cell (base midpoint = cell centre), no half-cell offset,
top face brightest, front face darker, 1px selective dark outline, 16-color saturated palette,
transparent background, bottom aligned, centered, no shadow
```
`中文：炸弹人玩法单格装饰块，[国风大鼓/宝箱/雪人]，40×40占地+12px向上高度，正面微俯视，**底座中心严格对齐格子中心、不允许半格偏移**，顶面最亮正面偏暗，1px深色描边，16色高饱和，透明底，底边对齐，居中，无投影`

---

## 8. 组合墙（ComposeWall）

### 8.1 设计规则

- 多格拼合的大型装饰物：城门、城堡、树、猫巴士、汽车、小店、咖啡机、海盗船、冰雕、竹林水柱……
- 尺寸按整格：2×2、3×2、4×3、5×4，长条可 17×4 / 15×2，竖向 3×13。
- **底座按整数格覆盖，底座中心与网格中心重合**；不允许半格偏移，也不允许“2.5×3.5”这种非整数占地。
- 结构要有“地基—主体—屋顶/招牌—装饰”层次；门/窗/招牌是视觉焦点。
- 剪影清楚：玩家要能立刻判断哪里能走、哪里挡路。
- 与单格墙同画风、同光源、同描边；可以更精细（20–30 色），但**单像素点大小不变**。
- 动画只做局部：霓虹呼吸、灵体上下浮动、水波、灯闪烁；不要整体大幅位移。

### 8.2 提示词

```text
pixel art multi-tile structure for a top-down bomberman game, [Chinese palace gate],
footprint 5x3 tiles (200x120 px), built on a 40 px grid, base footprint covers whole tiles and is centered on the grid (no half-tile offset), layered depth,
bright top surfaces, darker base, 1px selective outline, 20-color saturated palette,
transparent background, bottom aligned, no shadow
```
`中文：像素风多格组合建筑，[国风城楼门]，占5×3格(200×120)，按40px网格构建，**底座按整数格覆盖且居中、不允许半格偏移**，层次分明，顶亮底暗，1px描边，20色高饱和，透明底，底边对齐，无投影`

长条/竖向：
```text
pixel art long fence strip, 17x4 tiles (680x160 px), repeated modular segments,
seamless horizontally, 1px outline, transparent background
```

---

## 9. 砖块（Brick / WoodenBrick / MoveBrick）

### 9.1 设计规则

- **顶面大、正面矮**：顶面 40×40 与格子完全重合，正面 10–15px 深色底座，像软糖/巧克力块。
- **底座中心 = 格子中心**：正面高度只做视觉溢出，底座不得水平/纵深错位；2×2 大砖按 80×80 整数格居中。
- 顶面印图标或符号：数字、问号、星星、宝箱、炸弹、猫脸、汉字（武/爵）、花纹。
- 颜色承担功能语义：普通（绿/木/石）、高价值（金/宝箱）、特殊（冰蓝、南瓜橙、礼物红）。
- 可推砖（MoveBrick）要更像“箱子/冰块”，侧面有滑轨感。
- `die`：3–7 帧，碎块 + 白色像素烟尘/星点，碎块缩小并淡出；**同画布，不位移**。
- `hit`：3–4 帧，抖动/闪白/裂痕，不碎。

### 9.2 提示词

```text
soft destructible block for a bomberman game, 40x40 top face + 12 px tall front,
top face centered exactly on the grid cell (base midpoint = cell centre), no half-cell offset,
[star icon / number 5 / bomb symbol] printed on the top, beveled candy-like edges,
dark base band, 1px selective outline, glossy highlight, 12-color saturated palette,
transparent background, centered, bottom aligned
```
`中文：炸弹人可破坏软砖，40×40顶面+12px正面高度，**底座中心严格对齐格子中心、不允许半格偏移**，顶面印[星星/数字5/炸弹图标]，圆角软糖质感，深色底座，1px描边，高光，12色高饱和，透明底，居中，底边对齐`

破坏动画：
```text
5-frame pixel art destruction animation sheet, same 48x60 canvas each frame,
block cracks, bursts into 4-6 chunks with white pixel smoke puffs and sparkles,
chunks shrink and fade out, no motion blur, transparent background
```
`中文：5帧像素破坏动画，每帧同48×60画布，砖块开裂→炸成4-6块+白色像素烟尘/星点，碎块缩小淡出，无动态模糊，透明底`

---

## 10. 主题套装（换皮不换风格）

| 主题 | 地面 | 墙 | 组合墙 | 砖块 | 配色关键词 |
|---|---|---|---|---|---|
| 国风庭院/宫殿 | 1001/1002 米灰方砖 | 2146 城楼、2148 井、2069 金器 | 4001 城门 | 3010「武」3011「爵」 | 米白/朱红/鎏金/青玉 |
| 足球场 | 草地 + 白线 | 看台/围栏（可按需新做） | — | 球衣风（Cloth 280050） | 草绿/白/天蓝 |
| 冰雪世界 | 1163/1166 | 2040/2043/2110/2114/2118 | 4053 冰城堡 | 3001/3035/3056 | 青白/冰蓝/奶油 |
| 熔岩火山 | 深色火山岩地（见地图预览 1500） | 2021–2026 熔岩块 | — | 3028 炸弹、3021 宝箱 | 黑/橙红/亮黄 |
| 暗夜丛林 | 1023 暗草 | 2067/2075/2079/2130 | 4006 巨树、4013 霓虹猫 | 3064 灌木、3073/3074 | 墨绿/紫/荧光青 |
| 深海/水族 | 1035/1103/1106 | 2114 水纹墙 | 4051/4052 水浪 | 3009/3025 水纹 | 青蓝/白浪/珊瑚 |
| 沙漠遗迹 | 1004–1006/1069 | 2070 烛台、2122 鹿 | 4047 猛犸拱门 | 3055 沙袋 | 沙金/土黄/赭石 |
| 墓地/万圣 | 1023 暗草+蘑菇 | 2028/2029 骷髅骑士、2030 盾牌、2037 紫树 | 4045 骷髅王座 | 3070 骨头、3072 骷髅 | 墨绿/紫/骨白/橙 |
| 未来科技/工厂 | 1013/1083/1151 | 2003/2004 集装箱、2105 金属板、2135 蓝箱 | 4024 猫巴士、4042 机器人、4048 机器 | 3012 面板、3047/3048 音箱 | 冷灰/科技蓝/荧光绿 |
| 美食街/甜品 | 奶油/粉砖 | 2144 冰淇淋机、2061 礼物 | 4032/4033 面包房、4034 TIDE、4041 咖啡店、4056 条纹店 | 3043 汤锅、3044 面盒、3021 宝箱 | 粉/薄荷/柠檬/奶油 |
| 圣诞/礼物 | 雪地 | 2061 礼物盒、2008 宝箱 | 4056 红白店 | 3076 星星礼盒 | 正红/白/金 |
| 游乐园/玩具 | 彩砖 | 2001 大鼓、2010/2011 路锥 | 4016/4017 摇摇马、4019 扭蛋机、4020 机器人、4025 城堡、4027 齿轮、4061 扭蛋、4063 海盗船 | 3060/3061 宝箱 | 糖果色/高饱和撞色 |

> 做法：**固定画法与色数，只替换“主题道具 + 主色”**。这样新主题和旧资源放一起不违和。

---

## 11. 提示词模板库（可直接复制）

### 11.1 通用风格前缀（英文）

```text
16-bit pixel art, 2D top-down bomberman-style game asset, crisp hand-placed pixels,
every prop's 40x40 base footprint centered exactly on its grid cell (base midpoint = cell centre),
only height may overhang upward, no half-cell or full-cell offset,
1px selective dark outline, saturated toy-like palette (12-20 colors),
flat cel shading with 2-3 tones, subtle dithering, top-left light,
clean readable silhouette, no anti-aliasing, no blur, isolated on transparent background,
game-ready sprite
```

### 11.2 负面提示词（英文）

```text
3d render, realistic, photo texture, blurry, soft gradient, vector flat, thick outline,
outer glow, drop shadow, perspective camera, isometric grid, anti-aliasing, mixed pixel density,
text, watermark, jpeg artifacts, busy background, cropped, extra limbs, deformed face
```

### 11.3 中文通用前缀

```text
16bit像素风，2D俯视角炸弹人玩法游戏资源，像素点清晰，1像素选择性深色描边，
**所有元素底座中心严格对齐格子中心，只允许向上增高，不允许半格或整格偏移**，
12–20色高饱和玩具配色，2–3阶硬边平涂，少量抖动，左上打光，剪影清晰，
无抗锯齿无模糊，透明背景，游戏可用精灵图
```

### 11.4 中文负面词

```text
3D渲染，写实，照片纹理，模糊，柔和渐变，矢量扁平，粗描边，外发光，投影，
透视相机，等距网格，抗锯齿，像素大小不一致，文字，水印，JPEG噪点，复杂背景，裁切，多手多脚，脸崩
```

### 11.5 拼装总览图（用于给团队看整体）

```text
pixel art character lineup sheet, three chibi characters in the same style,
front view full body, different outfits (school uniform / Chinese festival / animal onesie),
same palette and 1px outline, transparent background, even spacing, no labels
```
`中文：像素角色三视图总览，三个同风格Q版角色正面全身，不同服装（校园/国风/动物连体衣），同色板同描边，透明底，等距排列，无文字`

---

## 12. 生产流程（AI 生图 → 可用资源）

1. **定主题与色板**：从第 10 节选主题，锁定 6–10 个主色（写进 prompt）。
2. **先出 1 张风格锚点**（地板或一块墙），确认像素密度、描边、光源；后续都带这张图做 reference / image prompt。
3. **单物件单图生成**：一次只出一个槽位/一块砖，避免模型把多层画糊。
4. **按 4x/8x 生成再降采样**：生成尺寸取目标整数倍（如 160×160 → 40×40），用 Nearest 缩小；不要直接让模型出 40px。
5. **像素清理**（Aseprite/PS）：
   - 统一到 1px 网格，去掉半透明羽化；
   - 限制色数（Indexed 12–20 色）；
   - 补 1px 选择性描边；
   - 统一光源到左上；
   - 检查四边无缝（地板）/底边对齐（墙、砖）。
6. **切片与命名**：按第 3 节命名规则；角色按 `<ID> <方向>-<帧>`。
7. **拼装验证**：把所有槽位叠在 100×100 中心画布上看是否打架；在地图 40px 网格里看 1x 剪影。
8. **导出**：PNG-8/PNG-32 透明底，PPU=100，关 Mipmap；进 Unity 后 Play 检查是否存在 1px 抖动/缝隙。

### 12.1 提高一致性的技巧

- 用**同一张参考图 + 同一段风格前缀 + 只替换主题词**；
- 固定随机种子/风格参考权重；
- 建一个 `palette.ase` 或 16 色 swatch 图，生成后强制索引化；
- 角色部件全部按**同一中心点**出图（生成时加 "centered, same canvas, isolated part"）；
- 先做“裸身 + 发型 + 五官”三件套，确认比例后再做衣服/帽子，否则衣服永远对不上肩线；
- 组合墙先画 40px 网格草图，再让 AI 细化，避免格数对不上。

---

## 13. 验收清单（逐项打勾）

**通用**
- [ ] 40×40 网格对齐，无半像素
- [ ] **所有元素底座（footprint）中心与格子中心重合，无半格/整格偏移；只有高度可向上溢出**
- [ ] 透明底干净，无白边/黑边
- [ ] 1px 选择性描边，颜色为固有色加深或近黑
- [ ] 左上光源一致，顶亮底暗
- [ ] 色数 ≤ 20（组合墙可到 30）
- [ ] 1x 下剪影可读
- [ ] 与现有资源并排不违和（同屏对比）

**角色**
- [ ] 二头身比例，头约占身高一半
- [ ] 四方向齐全（1右/2上/3左/4下）
- [ ] stand 1 帧、move 6 帧、trigger 5 帧、cry 2 帧
- [ ] 各部件同中心点、同画布、可叠合
- [ ] 头发不遮眼、帽子压发、背包在身后
- [ ] 灰度 mask 版本（需要染色的部位）
- [ ] 脚底在同一基线，行走不漂移

**地图**
- [ ] 地板四边无缝
- [ ] **墙/砖底座 40×40 与格子完全重合、中心对齐；组合墙按整数格覆盖并居中**
- [ ] 墙/砖底边对齐格子，向上溢出高度一致
- [ ] 砖块 die 帧同画布、碎块+白烟
- [ ] 组合墙格数正确（宽高均为 40 的整数倍或明确溢出）
- [ ] 危险物（尖刺/岩浆/毒）有明确颜色语义
- [ ] 不画投影，不画 UI 边框

---

## 附录 A：实测资源清单（抽样）

| 类别 | 示例 ID | 备注 |
|---|---|---|
| 基础身体 | `primebody0/309010~309013` | 裸身 Q 版，100×100，四方向 |
| 特殊整套 | `primebody0/309006,309014~309025` | 盔甲、猫、蛇（多色）、美杜莎、足球少年 |
| 整身皮肤 | `primebody1/409000` | 白羊连体服 |
| 发型 | `hair/330000`（黑双丸子）、`330001`（青绿双马尾）、`330002`（棕卷） | 59×55 |
| 衣服 | `cloth/280001`（红国风）、`280050`（足球球衣）、`280004`（蓝外套） | 67×59 |
| 帽子 | `cap/260000`（圣诞帽）、`260001`（青蛙帽）、`260020`（皇冠）、`260030`（恶魔角） | 81×73 |
| 面饰 | `mask/360000`（墨镜）等 | 55×71 |
| 背饰 | `pack/290000`（天使翼）、`290004`（黑翼）、`290010`（弓） | 97×73 |
| 头顶挂饰 | `head/260002`（钥匙）、`260014`（冬青）、`340000`（头顶小翅膀） | 59×65 |
| 手持 | `body/320002`（锤）、`320003`（斧）、`hand/320000`（蛇）、`hand` 法杖/书 | — |
| 跟宠 | `ghost/350001`（小幽灵）、气球、小龙、UFO | 111×55 |
| 地板 | `Floor/1001`（石砖）、`1003`（草）、`1021`（木）、`1035`（水）、`1163`（冰）、`1187`（石） | 40×40 |
| 墙 | `Wall/2001`（大鼓）、`2008`（宝箱）、`2040`（雪块）、`2067`（树丛）、`2146`（城楼） | 40 宽 + 高度 |
| 组合墙 | `ComposeWall/4001`（城门）、`4006`（巨树）、`4013`（霓虹猫）、`4024`（猫巴士）、`4053`（冰城堡）、`4060`（城堡）、`4063`（海盗船） | 多格 |
| 砖块 | `Brick/3001`（冰）、`3010`（武）、`3021`（宝箱）、`3028`（炸弹）、`3055`（沙袋）、`3076`（星星礼盒） | 40×40 + 高度 |
| 动画 | `Brick/3076/die`（礼物炸开）、`3085/die`（冰块碎成雪花）、`3022/die`（木箱碎） | 3–7 帧 |

## 附录 B：参考图索引（`art-style-refs/`）

| 文件 | 内容 |
|---|---|
| `01-地图整体风格总览.png` | 16 张关卡预览：国风、足球、熔岩、丛林、水下、沙漠、冰雪、室内等 |
| `02-地板瓦片.png` | 58 张地面/水/过渡砖 |
| `03-墙-单格装饰块.png` | 58 个单格墙道具 |
| `04-组合墙.png` | 全部组合墙 |
| `05-砖块.png` | 70 个砖块 idle |
| `06-砖块破坏动画.png` | 木箱/冰块/礼盒的 die 帧 |
| `07-基础身体四方向.png` | 裸身 Q 版 4 方向放大 |
| `08-角色部件.png` / `09-角色部件放大.png` | 头/发/衣/帽/背饰/面饰/跟宠 |
| `10-发型服装帽子背饰.png` | 槽位内容风格样本 |
| `11-灰度遮罩.png` | 头发/衣服/身体灰度染色版 |
| `12-游戏内拼合参考-国风.png` | 角色叠装 + 国风砖块实景 |
| `13-游戏内拼合参考-夜色丛林.png` | 暗夜丛林 + 灵体猫 |
| `14~18-*槽.png` | 武器、头顶挂饰、手持道具、跟宠、面饰全量样本 |

---

### 附：最省事的“起步三连”

1. 先生成 **1 张 40×40 灰石地砖 + 1 块 40×40 星星软砖 + 1 座 3×2 小建筑**，用它们定死画风。
2. 再生成 **裸身 Q 版四方向 + 黑丸子头 + 白蓝球衣 + 红鞋 + 大眼睛**，验证拼装。
3. 最后按主题表批量换皮：同一套提示词，只替换 `[主题道具]`、`[主色]`、`[材质]` 三个变量。
