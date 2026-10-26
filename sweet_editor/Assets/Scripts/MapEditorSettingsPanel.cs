using System;
using UnityEngine;

public sealed class MapEditorSettingsPanel : MonoBehaviour
{
    private static Rect LauncherRect
    {
        get
        {
            return AndroidSupport.IsAndroid
                ? new Rect(16f, 16f, 230f, 62f)
                : new Rect(10f, 10f, 160f, 32f);
        }
    }

    private static Rect GuideLauncherRect
    {
        get
        {
            return AndroidSupport.IsAndroid
                ? new Rect(258f, 16f, 170f, 62f)
                : new Rect(180f, 10f, 120f, 32f);
        }
    }

    private static Rect WindowRect
    {
        get
        {
            float width = Mathf.Min(AndroidSupport.IsAndroid ? 860f : 760f, Screen.width - 40f);
            float height = Mathf.Min(AndroidSupport.IsAndroid ? 540f : 430f, Screen.height - 40f);
            return new Rect(
                Mathf.Max(20f, (Screen.width - width) * 0.5f),
                Mathf.Max(20f, (Screen.height - height) * 0.5f),
                width,
                height);
        }
    }

    private static Rect GuideWindowRect
    {
        get
        {
            float width = Mathf.Min(AndroidSupport.IsAndroid ? 880f : 760f, Screen.width - 40f);
            float height = Mathf.Min(AndroidSupport.IsAndroid ? 700f : 620f, Screen.height - 40f);
            return new Rect(
                Mathf.Max(20f, (Screen.width - width) * 0.5f),
                Mathf.Max(20f, (Screen.height - height) * 0.5f),
                width,
                height);
        }
    }
    private static readonly Color MaskColor = new Color(0f, 0f, 0f, 0.55f);
    private static readonly Color WindowBackdropColor = new Color(0.16f, 0.18f, 0.2f, 1f);

    private static MapEditorSettingsPanel instance;
    private bool visible;
    private bool guideVisible;
    private MapEditorSettingsData draft;
    private Vector2 scrollPosition;
    private Vector2 guideScrollPosition;
    private string message = string.Empty;
    private MapEditorSettingsValidation validation;
    private string validationKey = string.Empty;

    public static bool IsVisible
    {
        get { return instance != null && (instance.visible || instance.guideVisible); }
    }

    public static bool BlocksMapInput
    {
        get
        {
            if (IsVisible)
            {
                return true;
            }

            Vector2 mousePosition = Input.mousePosition;
            mousePosition.y = Screen.height - mousePosition.y;
            return LauncherRect.Contains(mousePosition) || GuideLauncherRect.Contains(mousePosition);
        }
    }

    public static MapEditorSettingsPanel EnsureInstance()
    {
        if (instance != null)
        {
            return instance;
        }

        GameObject host = new GameObject("MapEditorSettingsPanel");
        DontDestroyOnLoad(host);
        instance = host.AddComponent<MapEditorSettingsPanel>();
        return instance;
    }

    public static void Show()
    {
        MapEditorSettingsPanel panel = EnsureInstance();
        panel.draft = MapEditorSettingsStore.Current;
        panel.message = string.Empty;
        panel.validation = null;
        panel.validationKey = string.Empty;
        panel.guideVisible = false;
        panel.visible = true;
    }

    private void OnDestroy()
    {
        if (instance == this)
        {
            instance = null;
        }
    }

    private void OnGUI()
    {
        ApplyMobileSkin();

        if (MapEditorBootstrap.BlocksInput)
        {
            return;
        }

        if (!visible && !guideVisible)
        {
            if (GUI.Button(LauncherRect, "资源目录配置"))
            {
                Show();
            }
            if (GUI.Button(GuideLauncherRect, "操作说明"))
            {
                guideScrollPosition = Vector2.zero;
                guideVisible = true;
            }
            return;
        }

        Rect activeWindowRect = visible ? WindowRect : GuideWindowRect;

        Color oldColor = GUI.color;
        GUI.color = MaskColor;
        GUI.DrawTexture(new Rect(0f, 0f, Screen.width, Screen.height), Texture2D.whiteTexture);
        GUI.color = WindowBackdropColor;
        GUI.DrawTexture(activeWindowRect, Texture2D.whiteTexture);
        GUI.color = oldColor;

        Event currentEvent = Event.current;
        if (currentEvent.type == EventType.MouseDown && !activeWindowRect.Contains(currentEvent.mousePosition))
        {
            visible = false;
            guideVisible = false;
            currentEvent.Use();
            return;
        }

        if (visible)
        {
            GUI.Window(GetInstanceID(), WindowRect, DrawWindow, "地图编辑器资源目录");
        }
        else
        {
            GUI.Window(GetInstanceID(), GuideWindowRect, DrawGuideWindow, "地图编辑器操作指南");
        }
    }

    private static void ApplyMobileSkin()
    {
        if (!AndroidSupport.IsAndroid)
        {
            return;
        }

        GUI.skin.label.fontSize = 18;
        GUI.skin.button.fontSize = 18;
        GUI.skin.textField.fontSize = 18;
        GUI.skin.window.fontSize = 20;
    }

    private void DrawWindow(int windowID)
    {
        GUILayout.BeginVertical();
        float controlHeight = AndroidSupport.IsAndroid ? 42f : 24f;
        float scrollHeight = Mathf.Max(
            180f,
            WindowRect.height - (AndroidSupport.IsAndroid ? 300f : 220f));

        GUILayout.Label(
            AndroidSupport.IsAndroid
                ? "Android 版默认使用应用内目录，无需额外存储权限。可手动修改路径，或使用下方按钮导出地图。"
                : "打包版和 Unity Editor 均可在这里选择外部资源目录。目录变更后会立即重新扫描。",
            GUI.skin.label);
        if (AndroidSupport.IsAndroid)
        {
            GUILayout.Label("应用目录：" + AndroidSupport.RootDirectory);
        }

        scrollPosition = GUILayout.BeginScrollView(scrollPosition, GUILayout.Height(scrollHeight));
        DrawDirectoryRow("地图元素目录（MapElem）", ref draft.mapElemDirectory, AndroidSupport.MapElemDirectory);
        DrawDirectoryRow("地图文件目录（Map）", ref draft.mapDirectory, AndroidSupport.MapDirectory);
        DrawDirectoryRow("地图预览目录（MapPreview）", ref draft.mapPreviewDirectory, AndroidSupport.MapPreviewDirectory);
        GUILayout.EndScrollView();

        MapEditorSettingsValidation currentValidation = GetValidation();
        DrawValidation("MapElem", currentValidation.mapElemValid, currentValidation.mapElemMessage);
        DrawValidation("Map", currentValidation.mapValid, currentValidation.mapMessage);
        DrawValidation("MapPreview", currentValidation.mapPreviewValid, currentValidation.mapPreviewMessage);
        if (!string.IsNullOrWhiteSpace(message))
        {
            GUILayout.Label(message, GUI.skin.box);
        }

        if (AndroidSupport.IsAndroid)
        {
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("导出地图 ZIP 到下载目录", GUILayout.Height(controlHeight)))
            {
                MapEditorBootstrap.ExportMapsToDownloads();
                visible = false;
            }
            if (GUILayout.Button("诊断信息", GUILayout.Height(controlHeight)))
            {
                string diagnostics = AndroidSupport.BuildDiagnostics();
                Debug.Log(diagnostics);
                message = "诊断信息已输出到日志。";
            }
            if (GUILayout.Button("恢复默认目录", GUILayout.Height(controlHeight)))
            {
                draft = AndroidSupport.CreateDefaultSettings();
                validation = null;
                validationKey = string.Empty;
            }
            GUILayout.EndHorizontal();
        }

        GUILayout.BeginHorizontal();
        if (GUILayout.Button("应用并重新扫描", GUILayout.Height(controlHeight)))
        {
            MapEditorSettingsValidation applied = GetValidation();
            if (MapEditorSettingsStore.Save(draft, false))
            {
                visible = !applied.IsFullyValid;
                message = applied.IsFullyValid
                    ? string.Empty
                    : "配置已保存；无效目录对应的功能已禁用，请修正后再次应用。";
                if (ViewManager.Instance != null)
                {
                    ViewManager.Instance.ShowTips("外部资源目录配置已保存并重新扫描");
                }
            }
            else
            {
                message = "配置保存失败，请检查目录权限";
            }
        }
        if (GUILayout.Button("取消", GUILayout.Height(controlHeight)))
        {
            visible = false;
        }
        GUILayout.EndHorizontal();
        GUILayout.EndVertical();
        GUI.DragWindow(new Rect(0f, 0f, 10000f, AndroidSupport.IsAndroid ? 34f : 24f));
    }

    private void DrawGuideWindow(int windowID)
    {
        bool mobile = AndroidSupport.IsAndroid;
        GUIStyle headingStyle = new GUIStyle(GUI.skin.label)
        {
            fontSize = mobile ? 22 : 15,
            fontStyle = FontStyle.Bold,
            wordWrap = true,
        };
        GUIStyle bodyStyle = new GUIStyle(GUI.skin.label)
        {
            fontSize = mobile ? 18 : 13,
            wordWrap = true,
        };

        GUILayout.BeginVertical();
        float scrollHeight = Mathf.Max(220f, GuideWindowRect.height - 100f);
        guideScrollPosition = GUILayout.BeginScrollView(
            guideScrollPosition,
            GUILayout.Height(scrollHeight));
        DrawGuideSection(
            "一、资源目录配置",
            "点击左上角“资源目录配置”，分别选择 MapElem、Map 和 MapPreview 目录，然后点击“应用并重新扫描”。\n" +
            "MapElem 用于读取地图元素图片；Map 用于读取和保存 .bytes 地图文件；MapPreview 用于保存地图预览图。目录状态均显示为有效后即可正常编辑。",
            headingStyle,
            bodyStyle);
        DrawGuideSection(
            "二、新建、加载与保存地图",
            "地图 ID 必须为数字。输入地图 ID、行数和列数后点击“新建地图”；尺寸范围为 15 x 13 至 50 x 50。\n" +
            "点击右侧地图列表中的项目可加载地图；输入地图 ID 后点击“Goto”，可定位列表并直接加载对应地图；点击“刷新地图目录”可重新扫描文件。\n" +
            "点击“保存地图”并确认后，会保存地图数据并生成对应预览图。缩小尺寸、清空地图或覆盖保存前会弹出确认窗口。",
            headingStyle,
            bodyStyle);
        DrawGuideSection(
            "三、放置与删除元素",
            "先在元素分类中选择类别，再单击元素图标。将鼠标移到地图格子可查看半透明预览，按住鼠标左键放置，按住鼠标右键删除当前类别的元素。\n" +
            "“元素放置”下拉框可切换单个、整行、奇偶行列和全部等批量放置范围。双击外部地图元素图标可打开动画查看窗口。",
            headingStyle,
            bodyStyle);
        DrawGuideSection(
            "四、选取与撤销",
            "按 I 或点击“选取元素（I）”进入选取模式，再单击地图中已有元素，即可将其设为当前元素。按 I 或 Esc 可取消选取。\n" +
            "按 Ctrl+Z 或点击“撤销”可撤销上一次地图元素放置或删除操作，最多保留 50 步。",
            headingStyle,
            bodyStyle);
        DrawGuideSection(
            "五、地图视图",
            "滚动鼠标滚轮可缩放地图；按住鼠标中键拖动可平移视图。\n" +
            "“适应全图”会缩放并居中显示完整地图；“回到中心”仅将视图移回地图中心；“显示网格”可切换辅助网格。",
            headingStyle,
            bodyStyle);

        if (mobile)
        {
            DrawGuideSection(
                "六、Android 触屏操作",
                "单指在地图上按下并拖动，可连续放置当前元素；双指拖动可平移视图，双指捏合可缩放视图。\n" +
                "屏幕左下角工具栏提供：删除模式、撤销、保存、元素选取、缩小、放大、适应全图、导出全部、导出当前。\n" +
                "“导出当前”只导出当前正在编辑的地图，文件名为 <地图ID>.bytes，写到 Download/MapEditor/；不需要先保存，适合改完一张图立刻传到 PC 测试。\n" +
                "删除模式下单指拖动会删除当前类别的元素；再次点击“删除开”退出。\n" +
                "地图与元素默认保存在应用目录中，无需额外存储权限。点击“导出”可把 Map 与 MapPreview 打包到系统下载目录 Download/MapEditor，方便拷回电脑。\n" +
                "如需从电脑更新手机上的资源，可把文件放到 Android/data/com.sixgod.mapeditor/files/MapEditor 对应目录，或重新生成内置资源包后覆盖安装 APK。",
                headingStyle,
                bodyStyle);
        }

        GUILayout.EndScrollView();

        if (GUILayout.Button("关闭", GUILayout.Height(mobile ? 46f : 32f)))
        {
            guideVisible = false;
        }
        GUILayout.EndVertical();
        GUI.DragWindow(new Rect(0f, 0f, 10000f, 24f));
    }

    private void DrawGuideSection(string heading, string body, GUIStyle headingStyle, GUIStyle bodyStyle)
    {
        GUILayout.Label(heading, headingStyle);
        GUILayout.Label(body, bodyStyle);
        GUILayout.Space(10f);
    }

    private void DrawDirectoryRow(string label, ref string path, string androidDefault)
    {
        float controlHeight = AndroidSupport.IsAndroid ? 40f : 24f;
        GUILayout.BeginHorizontal();
        GUILayout.Label(label, GUILayout.Width(AndroidSupport.IsAndroid ? 230f : 190f));
        path = GUILayout.TextField(path ?? string.Empty, GUILayout.Height(controlHeight));
        if (AndroidSupport.IsAndroid)
        {
            if (GUILayout.Button("默认", GUILayout.Width(90f), GUILayout.Height(controlHeight)))
            {
                path = androidDefault;
                validation = null;
                validationKey = string.Empty;
            }
            GUILayout.EndHorizontal();
            return;
        }

        if (GUILayout.Button("选择", GUILayout.Width(80f), GUILayout.Height(controlHeight)))
        {
            if (!RuntimeFolderPicker.IsSupported)
            {
                message = "当前平台不支持运行时目录选择，请手动输入绝对路径。";
                GUILayout.EndHorizontal();
                return;
            }

            string selected = RuntimeFolderPicker.PickFolder(label, path);
            if (!string.IsNullOrWhiteSpace(selected))
            {
                path = selected;
                validation = null;
            }
        }
        GUILayout.EndHorizontal();
    }

    private void DrawValidation(string name, bool valid, string detail)
    {
        string text = valid ? name + ": 有效" : name + ": " + (string.IsNullOrWhiteSpace(detail) ? "无效" : detail);
        Color oldColor = GUI.color;
        GUI.color = valid ? new Color(0.2f, 0.75f, 0.25f) : new Color(0.9f, 0.35f, 0.25f);
        GUILayout.Label(text);
        GUI.color = oldColor;
    }

    private MapEditorSettingsValidation GetValidation()
    {
        string key = string.Join("\n", new[]
        {
            draft.mapElemDirectory ?? string.Empty,
            draft.mapDirectory ?? string.Empty,
            draft.mapPreviewDirectory ?? string.Empty,
        });
        if (validation == null || !string.Equals(key, validationKey, StringComparison.Ordinal))
        {
            validation = MapEditorSettingsStore.Validate(draft);
            validationKey = key;
        }
        return validation;
    }
}
