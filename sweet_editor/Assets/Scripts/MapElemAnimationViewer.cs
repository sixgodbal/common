using System.Collections.Generic;
using UnityEngine;

public sealed class MapElemAnimationViewer : MonoBehaviour
{
    private static Rect WindowRect
    {
        get
        {
            float width = Mathf.Min(AndroidSupport.IsAndroid ? 900f : 780f, Screen.width - 40f);
            float height = Mathf.Min(AndroidSupport.IsAndroid ? 620f : 500f, Screen.height - 40f);
            return new Rect(
                Mathf.Max(20f, (Screen.width - width) * 0.5f),
                Mathf.Max(20f, (Screen.height - height) * 0.5f),
                width,
                height);
        }
    }
    private static readonly Color MaskColor = new Color(0f, 0f, 0f, 0.55f);
    private static readonly Color WindowBackdropColor = new Color(0.16f, 0.18f, 0.2f, 1f);
    private static readonly Color SelectedStateColor = new Color(0.12f, 0.68f, 0.36f, 1f);
    private static readonly Color UnselectedStateColor = new Color(0.32f, 0.34f, 0.37f, 1f);

    private static MapElemAnimationViewer instance;
    private MapElemResourceDefinition resource;
    private List<string> states = new List<string>();
    private List<Sprite> sprites = new List<Sprite>();
    private MapElemClipDefinition clip;
    private int stateIndex;
    private int frameIndex;
    private float elapsed;
    private bool playing;
    private Vector2 stateScroll;

    public static bool IsVisible
    {
        get { return instance != null && instance.resource != null; }
    }

    public static void Show(MapElemResourceDefinition definition)
    {
        if (definition == null)
        {
            return;
        }

        if (instance == null)
        {
            GameObject host = new GameObject("MapElemAnimationViewer");
            DontDestroyOnLoad(host);
            instance = host.AddComponent<MapElemAnimationViewer>();
        }

        instance.Open(definition);
    }

    public static void Close()
    {
        if (instance == null)
        {
            return;
        }

        instance.resource = null;
        instance.playing = false;
        instance.sprites.Clear();
    }

    private void Open(MapElemResourceDefinition definition)
    {
        resource = definition;
        states = new List<string>(resource.GetStates());
        stateIndex = FindStateIndex("idle");
        if (stateIndex < 0)
        {
            stateIndex = 0;
        }
        LoadState(true);
    }

    private void Update()
    {
        if (!IsVisible || !playing || sprites.Count <= 1 || clip == null || clip.duration <= 0f)
        {
            return;
        }

        float frameDuration = Mathf.Max(clip.duration / sprites.Count, 0.01f);
        elapsed += Time.unscaledDeltaTime;
        while (elapsed >= frameDuration)
        {
            elapsed -= frameDuration;
            frameIndex++;
            if (frameIndex < sprites.Count)
            {
                continue;
            }

            if (clip.loop)
            {
                frameIndex = 0;
                continue;
            }

            playing = false;
            frameIndex = sprites.Count - 1;
            break;
        }
    }

    private void OnGUI()
    {
        if (!IsVisible)
        {
            return;
        }

        if (AndroidSupport.IsAndroid)
        {
            GUI.skin.label.fontSize = 16;
            GUI.skin.button.fontSize = 17;
        }

        Color oldColor = GUI.color;
        GUI.color = MaskColor;
        GUI.DrawTexture(new Rect(0f, 0f, Screen.width, Screen.height), Texture2D.whiteTexture);
        GUI.color = WindowBackdropColor;
        GUI.DrawTexture(WindowRect, Texture2D.whiteTexture);
        GUI.color = oldColor;

        Event currentEvent = Event.current;
        if (currentEvent.type == EventType.MouseDown && !WindowRect.Contains(currentEvent.mousePosition))
        {
            Close();
            currentEvent.Use();
            return;
        }

        GUI.Window(GetInstanceID(), WindowRect, DrawWindow, "地图元素动画查看");
    }

    private void DrawWindow(int windowID)
    {
        float buttonHeight = AndroidSupport.IsAndroid ? 42f : 30f;
        GUILayout.BeginHorizontal();
        GUILayout.BeginVertical(GUILayout.Width(220f));
        GUILayout.Label(string.Format("ID: {0}   类别: {1}", resource.assetID, resource.type));
        stateScroll = GUILayout.BeginScrollView(stateScroll, GUILayout.Height(350f));
        for (int i = 0; i < states.Count; i++)
        {
            string state = states[i];
            int frameCount = resource.GetStateFilesForClipState(state).Count;
            string label = string.Format("{0} ({1}帧)", state, frameCount);
            bool selected = i == stateIndex;
            Color oldBackgroundColor = GUI.backgroundColor;
            Color oldContentColor = GUI.contentColor;
            GUI.backgroundColor = selected ? SelectedStateColor : UnselectedStateColor;
            GUI.contentColor = selected ? Color.white : new Color(0.82f, 0.82f, 0.82f, 1f);
            GUIStyle stateButtonStyle = new GUIStyle(GUI.skin.button)
            {
                alignment = TextAnchor.MiddleLeft,
                fontStyle = selected ? FontStyle.Bold : FontStyle.Normal,
            };
            bool clicked = GUILayout.Button(
                selected ? "已选  " + label : "      " + label,
                stateButtonStyle,
                GUILayout.Height(buttonHeight));
            GUI.backgroundColor = oldBackgroundColor;
            GUI.contentColor = oldContentColor;
            if (clicked && !selected)
            {
                stateIndex = i;
                LoadState(true);
            }
        }
        GUILayout.EndScrollView();
        GUILayout.EndVertical();

        GUILayout.BeginVertical();
        Rect previewRect = GUILayoutUtility.GetRect(470f, 310f, GUILayout.ExpandWidth(true));
        if (sprites.Count > 0 && frameIndex < sprites.Count && sprites[frameIndex] != null)
        {
            GUI.DrawTexture(previewRect, sprites[frameIndex].texture, ScaleMode.ScaleToFit, true);
        }
        else
        {
            GUI.Label(previewRect, "未找到当前状态图片");
        }

        string durationText = clip != null && clip.hasTiming
            ? string.Format("{0:0.###} 秒", clip.duration)
            : "未配置";
        GUILayout.Label(string.Format(
            "状态: {0}    帧: {1}/{2}    时长: {3}    {4}",
            states.Count > 0 ? states[stateIndex] : "-",
            sprites.Count == 0 ? 0 : frameIndex + 1,
            sprites.Count,
            durationText,
            clip != null && clip.loop ? "循环" : "单次"));

        GUILayout.BeginHorizontal();
        if (GUILayout.Button("重新播放", GUILayout.Height(buttonHeight)))
        {
            frameIndex = 0;
            elapsed = 0f;
            playing = CanAutoPlay();
        }
        if (GUILayout.Button("上一帧", GUILayout.Height(buttonHeight)))
        {
            playing = false;
            frameIndex = Mathf.Max(frameIndex - 1, 0);
            elapsed = 0f;
        }
        if (GUILayout.Button("下一帧", GUILayout.Height(buttonHeight)))
        {
            playing = false;
            frameIndex = Mathf.Min(frameIndex + 1, Mathf.Max(sprites.Count - 1, 0));
            elapsed = 0f;
        }
        GUILayout.EndHorizontal();

        if (!clipHasTiming())
        {
            GUILayout.Label("当前状态缺少 duration，无法按客户端速度自动播放，可使用逐帧查看。", GUI.skin.box);
        }

        if (GUILayout.Button("关闭", GUILayout.Height(buttonHeight)))
        {
            resource = null;
            playing = false;
        }
        GUILayout.EndVertical();
        GUILayout.EndHorizontal();
        GUI.DragWindow(new Rect(0f, 0f, 10000f, 24f));
    }

    private bool clipHasTiming()
    {
        return clip != null && clip.hasTiming && clip.duration > 0f;
    }

    private bool CanAutoPlay()
    {
        return sprites.Count > 1
            && clip != null
            && clip.isSequence
            && clip.hasTiming
            && clip.duration > 0f;
    }

    private int FindStateIndex(string state)
    {
        return states.FindIndex(item => string.Equals(item, state, System.StringComparison.OrdinalIgnoreCase));
    }

    private void LoadState(bool autoPlay = false)
    {
        sprites.Clear();
        elapsed = 0f;
        frameIndex = 0;
        playing = false;
        if (resource == null || states.Count == 0)
        {
            clip = null;
            return;
        }

        string state = states[Mathf.Clamp(stateIndex, 0, states.Count - 1)];
        if (!resource.visual.TryGetClip(state, out clip))
        {
            clip = new MapElemClipDefinition
            {
                state = state,
                resourceState = state,
                isSequence = true,
                hasTiming = false,
            };
        }

        foreach (string path in resource.GetStateFilesForClipState(state))
        {
            Sprite sprite = MapEditorTextureLoader.LoadSprite(path);
            if (sprite != null)
            {
                sprites.Add(sprite);
            }
        }

        playing = autoPlay && CanAutoPlay();
    }
}
