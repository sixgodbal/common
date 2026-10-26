using System;
using System.Collections;
using System.IO;
using UnityEngine;

/// <summary>
/// Android 启动引导：首次运行把 StreamingAssets 里的内置资源解压到应用目录，
/// 并在顶部显示进度；同时提供地图导出功能。
/// </summary>
public sealed class MapEditorBootstrap : MonoBehaviour
{
    private const float OverlayWidth = 760f;
    private const float OverlayHeight = 220f;

    public static MapEditorBootstrap Instance { get; private set; }

    public static bool BlocksInput
    {
        get
        {
            return Instance != null && (Instance.seeding || Instance.failed || Instance.exporting);
        }
    }

    private AndroidSupport.SeedExtractionState extraction;
    private AndroidSupport.ExportState exportState;
    private bool initializing;
    private bool seeding;
    private bool failed;
    private bool exporting;
    private string status = string.Empty;
    private string error = string.Empty;
    private float exportProgress;
    private string exportStatus = string.Empty;
    private GUIStyle titleStyle;
    private GUIStyle bodyStyle;
    private GUIStyle buttonStyle;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void CreateInstance()
    {
        if (!AndroidSupport.IsAndroid || Instance != null)
        {
            return;
        }

        GameObject host = new GameObject("MapEditorBootstrap");
        DontDestroyOnLoad(host);
        host.AddComponent<MapEditorBootstrap>();
    }

    private void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }

        Instance = this;
        Application.targetFrameRate = 60;
        Screen.sleepTimeout = SleepTimeout.NeverSleep;
        Screen.orientation = ScreenOrientation.AutoRotation;
        Screen.autorotateToPortrait = false;
        Screen.autorotateToPortraitUpsideDown = false;
        Screen.autorotateToLandscapeLeft = true;
        Screen.autorotateToLandscapeRight = true;
        MobileControlsPanel.EnsureInstance();
    }

    private void Start()
    {
        StartCoroutine(InitializeRoutine());
    }

    private IEnumerator InitializeRoutine()
    {
        if (initializing)
        {
            yield break;
        }

        initializing = true;
        failed = false;
        error = string.Empty;

        if (AndroidSupport.SeedReady && AndroidSupport.DirectoriesReady)
        {
            initializing = false;
            RunSelfTest();
            yield break;
        }

        seeding = true;
        status = "正在读取内置地图资源…";
        yield return null;

        byte[] zipBytes = null;
        string loadError = null;
        yield return AndroidSupport.LoadSeedBundle(
            delegate (byte[] bytes) { zipBytes = bytes; },
            delegate (string message) { loadError = message; });

        if (zipBytes == null || zipBytes.Length == 0)
        {
            seeding = false;
            initializing = false;
            failed = true;
            error = "未找到内置资源包 MapEditorSeed.zip。\n" + (loadError ?? string.Empty);
            yield break;
        }

        status = "正在解压内置地图资源…";
        extraction = AndroidSupport.ExtractSeedAsync(zipBytes);
        while (extraction != null && !extraction.done)
        {
            status = string.Format(
                "正在解压内置地图资源… {0}/{1}",
                extraction.processed,
                extraction.total);
            yield return null;
        }

        if (extraction == null || extraction.failed)
        {
            seeding = false;
            initializing = false;
            failed = true;
            error = extraction == null ? "解压任务未启动" : extraction.error;
            yield break;
        }

        AndroidSupport.WriteSeedMarker();
        MapEditorSettingsData settings = MapEditorSettingsStore.Current;
        AndroidSupport.ApplyDefaultPathsIfEmpty(settings);
        MapEditorSettingsStore.Save(settings, false);

        string message = string.Format(
            "内置资源已就绪：元素 {0} 张、地图 {1} 个",
            AndroidSupport.CountFiles(AndroidSupport.MapElemDirectory, "*.png"),
            AndroidSupport.CountFiles(AndroidSupport.MapDirectory, "*.bytes"));
        status = message;
        Debug.Log("[MapEditor] " + message);

        if (ViewManager.Instance != null)
        {
            ViewManager.Instance.ShowTips(message);
        }

        seeding = false;
        initializing = false;
        yield return new WaitForSeconds(0.6f);
        RunSelfTest();
    }

    private void RunSelfTest()
    {
        string result = AndroidSupport.RunSerializationSelfTest();
        Debug.Log("[MapEditor] BinaryFormatter 自检: " + result);
        if (!string.Equals(result, "OK", StringComparison.Ordinal) && ViewManager.Instance != null)
        {
            ViewManager.Instance.ShowTips("地图序列化自检异常，请把日志发给开发者: " + result);
        }
    }

    public static void ExportMapsToDownloads()
    {
        if (Instance == null)
        {
            return;
        }

        Instance.StartCoroutine(Instance.ExportRoutine());
    }

    public static string GetDiagnostics()
    {
        return AndroidSupport.BuildDiagnostics();
    }

    private IEnumerator ExportRoutine()
    {
        if (exporting)
        {
            yield break;
        }

        MapEditorSettingsData settings = MapEditorSettingsStore.Current;
        if (string.IsNullOrWhiteSpace(settings.mapDirectory) || !Directory.Exists(settings.mapDirectory))
        {
            if (ViewManager.Instance != null)
            {
                ViewManager.Instance.ShowTips("地图目录不可用，无法导出");
            }
            yield break;
        }

        exporting = true;
        exportStatus = "正在打包地图…";
        exportProgress = 0f;

        string exportDirectory = Path.Combine(Application.persistentDataPath, "Export");
        Directory.CreateDirectory(exportDirectory);
        string fileName = "MapEditor_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".zip";
        string zipPath = Path.Combine(exportDirectory, fileName);

        exportState = AndroidSupport.CreateExportZipAsync(
            settings.mapDirectory,
            settings.mapPreviewDirectory,
            zipPath);

        while (exportState != null && !exportState.done)
        {
            exportStatus = exportState.status;
            exportProgress = exportState.total <= 0
                ? 0f
                : (float)exportState.processed / exportState.total;
            yield return null;
        }

        if (exportState == null || exportState.failed)
        {
            exporting = false;
            string message = exportState == null ? "导出任务未启动" : exportState.error;
            Debug.LogError("[MapEditor] 导出失败: " + message);
            if (ViewManager.Instance != null)
            {
                ViewManager.Instance.ShowTips("导出失败：" + message);
            }
            yield break;
        }

        exportStatus = "正在写入下载目录…";
        exportProgress = 1f;
        yield return null;

        string savedPath = AndroidSupport.SaveFileToDownloads(zipPath, fileName, "application/zip");
        exporting = false;

        string result = string.IsNullOrEmpty(savedPath)
            ? "已导出到应用目录：" + zipPath
            : "已导出：" + savedPath;
        Debug.Log("[MapEditor] " + result);
        if (ViewManager.Instance != null)
        {
            ViewManager.Instance.ShowTips(result);
        }
    }

    private void OnGUI()
    {
        if (!seeding && !failed && !exporting)
        {
            return;
        }

        EnsureStyles();
        float scale = Mathf.Clamp(Screen.height / 768f, 1f, 2f);
        float width = Mathf.Min(OverlayWidth * scale, Screen.width - 40f);
        float height = OverlayHeight * scale;
        Rect panel = new Rect(
            (Screen.width - width) * 0.5f,
            (Screen.height - height) * 0.5f,
            width,
            height);

        Color oldColor = GUI.color;
        GUI.color = new Color(0f, 0f, 0f, 0.72f);
        GUI.DrawTexture(new Rect(0f, 0f, Screen.width, Screen.height), Texture2D.whiteTexture);
        GUI.color = new Color(0.14f, 0.17f, 0.2f, 1f);
        GUI.DrawTexture(panel, Texture2D.whiteTexture);
        GUI.color = oldColor;

        float padding = 24f * scale;
        Rect content = new Rect(
            panel.x + padding,
            panel.y + padding,
            panel.width - padding * 2f,
            panel.height - padding * 2f);
        GUI.Label(new Rect(content.x, content.y, content.width, 42f * scale), "MapEditor", titleStyle);

        if (exporting)
        {
            GUI.Label(
                new Rect(content.x, content.y + 50f * scale, content.width, 40f * scale),
                exportStatus,
                bodyStyle);
            DrawProgressBar(
                new Rect(content.x, content.y + 104f * scale, content.width, 26f * scale),
                exportProgress);
            GUI.Label(
                new Rect(content.x, content.y + 140f * scale, content.width, 32f * scale),
                "完成后会写入系统下载目录 Download/MapEditor",
                bodyStyle);
            GUI.color = oldColor;
            return;
        }

        if (failed)
        {
            GUI.Label(
                new Rect(content.x, content.y + 48f * scale, content.width, 90f * scale),
                error,
                bodyStyle);
            if (GUI.Button(
                    new Rect(content.x, content.yMax - 54f * scale, 200f * scale, 44f * scale),
                    "重试",
                    buttonStyle))
            {
                StartCoroutine(InitializeRoutine());
            }
            if (GUI.Button(
                    new Rect(content.x + 220f * scale, content.yMax - 54f * scale, 200f * scale, 44f * scale),
                    "继续",
                    buttonStyle))
            {
                failed = false;
                error = string.Empty;
            }
            GUI.color = oldColor;
            return;
        }

        GUI.Label(
            new Rect(content.x, content.y + 50f * scale, content.width, 40f * scale),
            status,
            bodyStyle);
        float progress = extraction == null || extraction.total <= 0
            ? 0f
            : (float)extraction.processed / extraction.total;
        DrawProgressBar(
            new Rect(content.x, content.y + 104f * scale, content.width, 26f * scale),
            progress);
        GUI.Label(
            new Rect(content.x, content.y + 140f * scale, content.width, 32f * scale),
            "首次启动需要解压约 45MB 内置资源，请稍候…",
            bodyStyle);
        GUI.color = oldColor;
    }

    private void DrawProgressBar(Rect rect, float progress)
    {
        Color oldColor = GUI.color;
        GUI.color = new Color(0.24f, 0.27f, 0.3f, 1f);
        GUI.DrawTexture(rect, Texture2D.whiteTexture);
        GUI.color = new Color(0.2f, 0.75f, 0.55f, 1f);
        GUI.DrawTexture(
            new Rect(rect.x, rect.y, Mathf.Clamp01(progress) * rect.width, rect.height),
            Texture2D.whiteTexture);
        GUI.color = oldColor;
    }

    private void EnsureStyles()
    {
        if (titleStyle != null)
        {
            return;
        }

        float scale = Mathf.Clamp(Screen.height / 768f, 1f, 2f);
        titleStyle = new GUIStyle(GUI.skin.label)
        {
            fontSize = Mathf.RoundToInt(26f * scale),
            fontStyle = FontStyle.Bold,
            alignment = TextAnchor.MiddleLeft,
        };
        titleStyle.normal.textColor = Color.white;
        bodyStyle = new GUIStyle(GUI.skin.label)
        {
            fontSize = Mathf.RoundToInt(16f * scale),
            wordWrap = true,
            alignment = TextAnchor.MiddleLeft,
        };
        bodyStyle.normal.textColor = new Color(0.86f, 0.9f, 0.92f, 1f);
        buttonStyle = new GUIStyle(GUI.skin.button)
        {
            fontSize = Mathf.RoundToInt(17f * scale),
        };
    }
}
