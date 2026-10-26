using System;
using UnityEngine;

/// <summary>
/// Android 触屏浮动工具栏：删除模式、撤销、保存、选取、缩放、适应、导出。
/// 用 IMGUI 实现，避免修改场景里的 uGUI 结构。
/// </summary>
public sealed class MobileControlsPanel : MonoBehaviour
{
    private static MobileControlsPanel instance;
    private GUIStyle buttonStyle;
    private GUIStyle statusStyle;

    public static void EnsureInstance()
    {
        if (!AndroidSupport.IsAndroid || instance != null)
        {
            return;
        }

        GameObject host = new GameObject("MobileControlsPanel");
        DontDestroyOnLoad(host);
        instance = host.AddComponent<MobileControlsPanel>();
    }

    private static bool IsVisible
    {
        get
        {
            if (!AndroidSupport.IsAndroid || instance == null)
            {
                return false;
            }

            if (MapEditorSettingsPanel.IsVisible || MapElemAnimationViewer.IsVisible)
            {
                return false;
            }

            if (MapEditorBootstrap.BlocksInput)
            {
                return false;
            }

            return ViewManager.Instance == null || !ViewManager.Instance.IsConfirmOpen;
        }
    }

    private static float ButtonHeight
    {
        get { return Mathf.Clamp(Screen.height * 0.075f, 54f, 96f); }
    }

    private static float ButtonWidth
    {
        get { return Mathf.Clamp(Screen.width * 0.05f, 86f, 144f); }
    }

    private static float Spacing
    {
        get { return Mathf.Clamp(Screen.height * 0.011f, 6f, 14f); }
    }

    private static float Margin
    {
        get { return Mathf.Clamp(Screen.height * 0.02f, 12f, 28f); }
    }

    private static float StatusHeight
    {
        get { return Mathf.Clamp(Screen.height * 0.038f, 30f, 52f); }
    }

    private const int ButtonCount = 9;

    private static Rect GetToolbarArea()
    {
        float buttonWidth = ButtonWidth;
        float spacing = Spacing;
        float margin = Margin;
        float statusHeight = StatusHeight;
        float buttonHeight = ButtonHeight;

        float totalWidth = ButtonCount * buttonWidth + (ButtonCount - 1) * spacing;
        float maxWidth = Screen.width - margin * 2f;
        if (totalWidth > maxWidth)
        {
            buttonWidth = Mathf.Max(60f, (maxWidth - (ButtonCount - 1) * spacing) / ButtonCount);
            totalWidth = maxWidth;
        }

        float width = totalWidth + 20f;
        float height = buttonHeight + statusHeight + 24f;
        return new Rect(margin - 10f, Screen.height - margin - height, width, height);
    }

    /// <summary>
    /// 传入 Unity 屏幕坐标（左下角原点，和 Input.mousePosition 一致）。
    /// </summary>
    public static bool BlocksPoint(Vector2 screenPosition)
    {
        if (!IsVisible)
        {
            return false;
        }

        Vector2 guiPosition = new Vector2(screenPosition.x, Screen.height - screenPosition.y);
        return GetToolbarArea().Contains(guiPosition);
    }

    private void OnGUI()
    {
        if (!IsVisible || ViewManager.Instance == null)
        {
            return;
        }

        EnsureStyles();
        ViewManager manager = ViewManager.Instance;
        Rect area = GetToolbarArea();
        float padding = 10f;
        float statusHeight = StatusHeight;
        float buttonHeight = ButtonHeight;
        float buttonWidth = (area.width - padding * 2f - (ButtonCount - 1) * Spacing) / ButtonCount;
        float y = area.y + area.height - padding - buttonHeight;

        Color oldColor = GUI.color;
        GUI.color = new Color(0f, 0f, 0f, 0.55f);
        GUI.DrawTexture(area, Texture2D.whiteTexture);
        GUI.color = new Color(0.12f, 0.15f, 0.17f, 0.92f);
        GUI.DrawTexture(
            new Rect(area.x + 2f, area.y + 2f, area.width - 4f, area.height - 4f),
            Texture2D.whiteTexture);
        GUI.color = oldColor;

        GUI.Label(
            new Rect(area.x + padding, area.y + 4f, area.width - padding * 2f, statusHeight),
            manager.GetMobileStatusText(),
            statusStyle);

        float x = area.x + padding;
        DrawButton(
            new Rect(x, y, buttonWidth, buttonHeight),
            manager.IsDeleteMode ? "删除开" : "删除",
            manager.IsDeleteMode ? new Color(0.82f, 0.3f, 0.26f) : Color.white,
            delegate { manager.ToggleDeleteMode(); });
        x += buttonWidth + Spacing;

        DrawButton(
            new Rect(x, y, buttonWidth, buttonHeight),
            "撤销",
            Color.white,
            delegate { manager.UndoLastElementEdit(); });
        x += buttonWidth + Spacing;

        DrawButton(
            new Rect(x, y, buttonWidth, buttonHeight),
            "保存",
            new Color(0.3f, 0.66f, 0.9f),
            delegate { manager.SaveMap(); });
        x += buttonWidth + Spacing;

        DrawButton(
            new Rect(x, y, buttonWidth, buttonHeight),
            manager.IsPickingMapElem ? "选取开" : "选取",
            manager.IsPickingMapElem ? new Color(0.2f, 0.62f, 0.55f) : Color.white,
            delegate { manager.ToggleMapElemPicker(); });
        x += buttonWidth + Spacing;

        DrawButton(
            new Rect(x, y, buttonWidth, buttonHeight),
            "缩小",
            Color.white,
            delegate { manager.ZoomByStep(-1f); });
        x += buttonWidth + Spacing;

        DrawButton(
            new Rect(x, y, buttonWidth, buttonHeight),
            "放大",
            Color.white,
            delegate { manager.ZoomByStep(1f); });
        x += buttonWidth + Spacing;

        DrawButton(
            new Rect(x, y, buttonWidth, buttonHeight),
            "适应",
            Color.white,
            delegate { manager.FitCameraToMap(); });
        x += buttonWidth + Spacing;

        DrawButton(
            new Rect(x, y, buttonWidth, buttonHeight),
            "导出全部",
            new Color(0.85f, 0.7f, 0.3f),
            delegate { MapEditorBootstrap.ExportMapsToDownloads(); });
        x += buttonWidth + Spacing;

        DrawButton(
            new Rect(x, y, buttonWidth, buttonHeight),
            "导出当前",
            new Color(0.3f, 0.66f, 0.9f),
            delegate { manager.ExportCurrentMap(); });
    }

    private void DrawButton(Rect rect, string label, Color color, Action action)
    {
        Color oldBackground = GUI.backgroundColor;
        Color oldColor = GUI.color;
        GUI.backgroundColor = color;
        GUI.color = Color.white;
        bool clicked = GUI.Button(rect, label, buttonStyle);
        GUI.color = oldColor;
        GUI.backgroundColor = oldBackground;
        if (clicked && action != null)
        {
            action();
        }
    }

    private void EnsureStyles()
    {
        if (buttonStyle != null)
        {
            return;
        }

        float buttonHeight = ButtonHeight;
        buttonStyle = new GUIStyle(GUI.skin.button)
        {
            fontSize = Mathf.RoundToInt(buttonHeight * 0.32f),
            alignment = TextAnchor.MiddleCenter,
            wordWrap = false,
            clipping = TextClipping.Clip,
            fontStyle = FontStyle.Bold,
        };
        statusStyle = new GUIStyle(GUI.skin.label)
        {
            fontSize = Mathf.RoundToInt(StatusHeight * 0.52f),
            alignment = TextAnchor.MiddleLeft,
            wordWrap = false,
            clipping = TextClipping.Clip,
        };
        statusStyle.normal.textColor = new Color(0.82f, 0.9f, 0.94f, 1f);
    }
}
