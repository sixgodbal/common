using System;
using System.IO;
using UnityEngine;

[Serializable]
public sealed class MapEditorSettingsData
{
    public string mapElemDirectory = string.Empty;
    public string mapDirectory = string.Empty;
    public string mapPreviewDirectory = string.Empty;

    public MapEditorSettingsData Clone()
    {
        return new MapEditorSettingsData
        {
            mapElemDirectory = mapElemDirectory,
            mapDirectory = mapDirectory,
            mapPreviewDirectory = mapPreviewDirectory,
        };
    }
}

public sealed class MapEditorSettingsValidation
{
    public bool mapElemValid;
    public bool mapValid;
    public bool mapPreviewValid;
    public string mapElemMessage;
    public string mapMessage;
    public string mapPreviewMessage;

    public bool IsFullyValid
    {
        get { return mapElemValid && mapValid && mapPreviewValid; }
    }
}

public static class MapEditorSettingsStore
{
    private const string FileName = "MapEditorSettings.json";
    private static MapEditorSettingsData current;
    private static bool loaded;

    public static event Action Changed;

    public static MapEditorSettingsData Current
    {
        get
        {
            Load();
            return current.Clone();
        }
    }

    public static void Load()
    {
        if (loaded)
        {
            return;
        }

        current = ReadFile(GetPersistentPath());
#if UNITY_EDITOR
        if (current == null)
        {
            current = ReadFile(GetProjectSettingsPath());
        }
#endif
        if (current == null)
        {
            current = new MapEditorSettingsData();
        }

        Normalize(current);
        // Android 首次启动时直接使用应用目录，桌面端保持原有“未配置”状态。
        if (AndroidSupport.IsAndroid)
        {
            AndroidSupport.ApplyDefaultPathsIfEmpty(current);
        }
        loaded = true;
    }

    public static bool Save(MapEditorSettingsData settings, bool saveProjectSettings)
    {
        if (settings == null)
        {
            return false;
        }

        Normalize(settings);
        try
        {
            WriteFile(GetPersistentPath(), settings);
#if UNITY_EDITOR
            if (saveProjectSettings)
            {
                WriteFile(GetProjectSettingsPath(), settings);
            }
#endif
            current = settings.Clone();
            loaded = true;
            if (Changed != null)
            {
                Changed.Invoke();
            }
            return true;
        }
        catch (Exception exception)
        {
            Debug.LogError("保存地图编辑器资源目录配置失败: " + exception.Message);
            return false;
        }
    }

    public static void Apply(MapEditorSettingsData settings)
    {
        Save(settings, false);
    }

    public static MapEditorSettingsValidation Validate(MapEditorSettingsData settings)
    {
        MapEditorSettingsValidation result = new MapEditorSettingsValidation();
        if (settings == null)
        {
            result.mapElemMessage = "配置为空";
            result.mapMessage = "配置为空";
            result.mapPreviewMessage = "配置为空";
            return result;
        }

        result.mapElemValid = ValidateMapElemDirectory(settings.mapElemDirectory, out result.mapElemMessage);
        result.mapValid = ValidateDirectory(settings.mapDirectory, false, out result.mapMessage);
        result.mapPreviewValid = ValidateDirectory(settings.mapPreviewDirectory, true, out result.mapPreviewMessage);
        return result;
    }

    public static string GetPersistentPath()
    {
        return Path.Combine(Application.persistentDataPath, FileName);
    }

#if UNITY_EDITOR
    public static string GetProjectSettingsPath()
    {
        DirectoryInfo projectRoot = Directory.GetParent(Application.dataPath);
        return projectRoot == null
            ? string.Empty
            : Path.Combine(projectRoot.FullName, "ProjectSettings", FileName);
    }
#endif

    private static bool ValidateMapElemDirectory(string path, out string message)
    {
        if (string.IsNullOrWhiteSpace(path) || !Directory.Exists(path))
        {
            message = "目录不存在";
            return false;
        }

        try
        {
            foreach (string typeDirectory in Directory.GetDirectories(path))
            {
                if (!MapElemTypeUtility.TryParse(Path.GetFileName(typeDirectory), out _))
                {
                    continue;
                }

                foreach (string idDirectory in Directory.GetDirectories(typeDirectory))
                {
                    string idleDirectory = Path.Combine(idDirectory, "idle");
                    if (int.TryParse(Path.GetFileName(idDirectory), out int assetID)
                        && assetID > 2
                        && (Directory.GetFiles(idDirectory, "*.png", SearchOption.TopDirectoryOnly).Length > 0
                            || (Directory.Exists(idleDirectory)
                                && Directory.GetFiles(idleDirectory, "*.png", SearchOption.TopDirectoryOnly).Length > 0)))
                    {
                        message = string.Empty;
                        return true;
                    }
                }

                foreach (string file in Directory.GetFiles(typeDirectory, "*.png", SearchOption.TopDirectoryOnly))
                {
                    if (int.TryParse(Path.GetFileNameWithoutExtension(file), out int assetID) && assetID > 2)
                    {
                        message = string.Empty;
                        return true;
                    }
                }
            }
        }
        catch (Exception exception)
        {
            message = "目录不可读: " + exception.Message;
            return false;
        }

        message = "未找到合法的 <类别>/<ID>/<状态>/*.png 或 <类别>/<ID>.png";
        return false;
    }

    private static bool ValidateDirectory(string path, bool allowCreate, out string message)
    {
        message = string.Empty;
        if (string.IsNullOrWhiteSpace(path))
        {
            message = "未选择目录";
            return false;
        }

        try
        {
            if (!Directory.Exists(path))
            {
                if (!allowCreate)
                {
                    message = "目录不存在";
                    return false;
                }

                Directory.CreateDirectory(path);
            }

            using (var entries = Directory.EnumerateFileSystemEntries(path).GetEnumerator())
            {
                entries.MoveNext();
            }

            string probe = Path.Combine(path, ".map-editor-write-test");
            File.WriteAllText(probe, string.Empty);
            File.Delete(probe);
            return true;
        }
        catch (Exception exception)
        {
            message = "目录不可写: " + exception.Message;
            return false;
        }
    }

    private static MapEditorSettingsData ReadFile(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
        {
            return null;
        }

        try
        {
            MapEditorSettingsData data = JsonUtility.FromJson<MapEditorSettingsData>(File.ReadAllText(path));
            return data == null ? null : data;
        }
        catch (Exception exception)
        {
            Debug.LogWarning("读取地图编辑器资源目录配置失败: " + exception.Message);
            return null;
        }
    }

    private static void WriteFile(string path, MapEditorSettingsData data)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            throw new InvalidOperationException("配置文件路径为空");
        }

        string directory = Path.GetDirectoryName(path);
        if (!Directory.Exists(directory))
        {
            Directory.CreateDirectory(directory);
        }

        File.WriteAllText(path, JsonUtility.ToJson(data, true));
    }

    private static void Normalize(MapEditorSettingsData data)
    {
        data.mapElemDirectory = NormalizePath(data.mapElemDirectory);
        data.mapDirectory = NormalizePath(data.mapDirectory);
        data.mapPreviewDirectory = NormalizePath(data.mapPreviewDirectory);
    }

    private static string NormalizePath(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return string.Empty;
        }

        try
        {
            return Path.GetFullPath(path.Trim());
        }
        catch
        {
            return path.Trim();
        }
    }
}
