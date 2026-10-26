using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

[Serializable]
public sealed class MapElemVisualConfigTable
{
    public int version;
    public MapElemVisualDefaultsConfig defaults;
    public MapElemVisualTypeDefaultConfig[] typeDefaults;
    public MapElemVisualProfileGroupConfig[] profileGroups;
}

[Serializable]
public sealed class MapElemVisualDefaultsConfig
{
    public float[] localPosition;
    public float[] localScale;
    public bool rendererActive = true;
    public bool rendererEnabled = true;
    public MapElemDefaultAnimationConfig defaultAnimation;
}

[Serializable]
public sealed class MapElemDefaultAnimationConfig
{
    public float duration;
    public bool loop;
}

[Serializable]
public sealed class MapElemVisualTypeDefaultConfig
{
    public string type;
    public float[] localPosition;
    public int sortingOrder;
    public MapElemClipConfig[] clips;
}

[Serializable]
public sealed class MapElemVisualProfileGroupConfig
{
    public string type;
    public int[] ids;
    public float[] localPosition;
    public bool overrideSortingOrder;
    public int sortingOrder;
    public bool overrideRendererActive;
    public bool rendererActive;
    public bool overrideRendererEnabled;
    public bool rendererEnabled;
    public MapElemClipConfig[] clips;
}

[Serializable]
public sealed class MapElemClipConfig
{
    public string state;
    public string resourceState;
    public float duration;
    public bool loop;
    public bool holdFirstFrame;
    public string completionState;
}

public sealed class MapElemClipDefinition
{
    public string state;
    public string resourceState;
    public float duration;
    public bool loop;
    public bool isSequence;
    public string completionState;
    public bool hasTiming;

    public MapElemClipDefinition Clone()
    {
        return new MapElemClipDefinition
        {
            state = state,
            resourceState = resourceState,
            duration = duration,
            loop = loop,
            isSequence = isSequence,
            completionState = completionState,
            hasTiming = hasTiming,
        };
    }
}

public sealed class MapElemVisualDefinition
{
    public Vector3 localPosition = Vector3.zero;
    public Vector3 localScale = Vector3.one;
    public int sortingOrder;
    public bool rendererActive = true;
    public bool rendererEnabled = true;
    public bool hasConfig;
    public readonly Dictionary<string, MapElemClipDefinition> clips =
        new Dictionary<string, MapElemClipDefinition>(StringComparer.OrdinalIgnoreCase);

    public MapElemVisualDefinition Clone()
    {
        MapElemVisualDefinition result = new MapElemVisualDefinition
        {
            localPosition = localPosition,
            localScale = localScale,
            sortingOrder = sortingOrder,
            rendererActive = rendererActive,
            rendererEnabled = rendererEnabled,
            hasConfig = hasConfig,
        };

        foreach (var clip in clips)
        {
            result.clips[clip.Key] = clip.Value.Clone();
        }

        return result;
    }

    public bool TryGetClip(string state, out MapElemClipDefinition clip)
    {
        if (clips.TryGetValue(state ?? string.Empty, out clip))
        {
            return true;
        }

        clip = null;
        return false;
    }
}

public sealed class MapElemResourceDefinition
{
    public int assetID;
    public MapElemType type;
    public string typeName;
    public string rootDirectory;
    public MapElemVisualDefinition visual;
    public readonly Dictionary<string, List<string>> stateFiles =
        new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);

    public bool HasIdle
    {
        get { return GetStateFiles("idle").Count > 0; }
    }

    public IReadOnlyList<string> GetStateFiles(string state)
    {
        if (stateFiles.TryGetValue(state ?? string.Empty, out List<string> files))
        {
            return files;
        }

        return Array.Empty<string>();
    }

    public IReadOnlyList<string> GetStates()
    {
        HashSet<string> stateSet = new HashSet<string>(stateFiles.Keys, StringComparer.OrdinalIgnoreCase);
        if (visual != null)
        {
            foreach (MapElemClipDefinition clip in visual.clips.Values)
            {
                if (clip != null && GetStateFiles(clip.resourceState).Count > 0)
                {
                    stateSet.Add(clip.state);
                }
            }
        }

        List<string> states = new List<string>(stateSet);
        states.Sort(StringComparer.OrdinalIgnoreCase);
        return states;
    }

    public IReadOnlyList<string> GetStateFilesForClipState(string state)
    {
        if (visual != null && visual.TryGetClip(state, out MapElemClipDefinition clip))
        {
            return GetStateFiles(clip.resourceState);
        }

        return GetStateFiles(state);
    }

    public Sprite LoadPreviewSprite(string state = "idle")
    {
        IReadOnlyList<string> files = GetStateFiles(state);
        return files.Count == 0 ? null : MapEditorTextureLoader.LoadSprite(files[0]);
    }
}

public sealed class MapElemCatalog
{
    private const int SupportedVisualConfigVersion = 6;
    private readonly Dictionary<MapElemType, List<MapElemResourceDefinition>> resourcesByType =
        new Dictionary<MapElemType, List<MapElemResourceDefinition>>();
    private readonly Dictionary<int, MapElemResourceDefinition> resourcesByID =
        new Dictionary<int, MapElemResourceDefinition>();
    private readonly Dictionary<MapElemType, MapElemVisualDefinition> typeVisuals =
        new Dictionary<MapElemType, MapElemVisualDefinition>();
    private readonly Dictionary<int, MapElemVisualDefinition> profileVisuals =
        new Dictionary<int, MapElemVisualDefinition>();

    public string RootDirectory { get; private set; }
    public string LastError { get; private set; }
    public bool IsLoaded { get; private set; }

    public IReadOnlyDictionary<MapElemType, List<MapElemResourceDefinition>> ResourcesByType
    {
        get { return resourcesByType; }
    }

    public bool Reload(string rootDirectory, out string message)
    {
        resourcesByType.Clear();
        resourcesByID.Clear();
        typeVisuals.Clear();
        profileVisuals.Clear();
        RootDirectory = string.Empty;
        IsLoaded = false;
        LastError = string.Empty;

        if (string.IsNullOrWhiteSpace(rootDirectory) || !Directory.Exists(rootDirectory))
        {
            message = "MapElem 目录不存在";
            LastError = message;
            return false;
        }

        RootDirectory = Path.GetFullPath(rootDirectory);
        LoadVisualConfig();

        string[] typeDirectories = Directory.GetDirectories(RootDirectory);
        foreach (string typeDirectory in typeDirectories)
        {
            string typeName = Path.GetFileName(typeDirectory);
            if (string.Equals(typeName, "MapElemVisualConfig.json", StringComparison.OrdinalIgnoreCase)
                || !MapElemTypeUtility.TryParse(typeName, out MapElemType type))
            {
                continue;
            }

            List<MapElemResourceDefinition> typeResources = GetOrCreateTypeList(type);
            foreach (string idDirectory in Directory.GetDirectories(typeDirectory))
            {
                if (!int.TryParse(Path.GetFileName(idDirectory), out int assetID)
                    || !IsPlaceableAssetID(assetID))
                {
                    continue;
                }

                MapElemResourceDefinition definition = CreateResource(type, typeName, assetID, idDirectory);
                if (!definition.HasIdle || resourcesByID.ContainsKey(assetID))
                {
                    continue;
                }

                typeResources.Add(definition);
                resourcesByID[assetID] = definition;
            }

            AddSingleSpriteResources(type, typeName, typeDirectory, typeResources);
            typeResources.Sort((left, right) => left.assetID.CompareTo(right.assetID));
        }

        int validCount = 0;
        foreach (List<MapElemResourceDefinition> resources in resourcesByType.Values)
        {
            validCount += resources.Count;
        }

        if (validCount == 0)
        {
            message = "MapElem 目录中未找到包含 idle 图片的元素";
            LastError = message;
            return false;
        }

        IsLoaded = true;
        message = string.Format("已加载 {0} 个地图元素", validCount);
        if (!string.IsNullOrWhiteSpace(LastError))
        {
            message += "；" + LastError;
        }
        return true;
    }

    public bool TryGet(int assetID, out MapElemResourceDefinition definition)
    {
        return resourcesByID.TryGetValue(assetID, out definition);
    }

    public IReadOnlyList<MapElemResourceDefinition> GetResources(MapElemType type)
    {
        if (resourcesByType.TryGetValue(type, out List<MapElemResourceDefinition> resources))
        {
            return resources;
        }

        return Array.Empty<MapElemResourceDefinition>();
    }

    public List<MapElemType> GetTypes()
    {
        List<MapElemType> types = new List<MapElemType>();
        foreach (var pair in resourcesByType)
        {
            if (pair.Value != null && pair.Value.Count > 0)
            {
                types.Add(pair.Key);
            }
        }
        types.Sort((left, right) => string.CompareOrdinal(left.ToString(), right.ToString()));
        return types;
    }

    private MapElemResourceDefinition CreateResource(MapElemType type, string typeName, int assetID, string idDirectory)
    {
        MapElemResourceDefinition definition = new MapElemResourceDefinition
        {
            type = type,
            typeName = typeName,
            assetID = assetID,
            rootDirectory = idDirectory,
            visual = GetVisualDefinition(type, assetID),
        };

        foreach (string stateDirectory in Directory.GetDirectories(idDirectory))
        {
            string state = Path.GetFileName(stateDirectory);
            AddPngFiles(definition, state, stateDirectory);
        }

        return definition;
    }

    private void AddSingleSpriteResources(
        MapElemType type,
        string typeName,
        string typeDirectory,
        List<MapElemResourceDefinition> typeResources)
    {
        foreach (string file in Directory.GetFiles(typeDirectory, "*.png", SearchOption.TopDirectoryOnly))
        {
            string name = Path.GetFileNameWithoutExtension(file);
            if (!int.TryParse(name, out int assetID)
                || !IsPlaceableAssetID(assetID)
                || resourcesByID.ContainsKey(assetID))
            {
                continue;
            }

            MapElemResourceDefinition definition = new MapElemResourceDefinition
            {
                type = type,
                typeName = typeName,
                assetID = assetID,
                rootDirectory = typeDirectory,
                visual = GetVisualDefinition(type, assetID),
            };
            AddFiles(definition, "idle", new[] { file });
            typeResources.Add(definition);
            resourcesByID[assetID] = definition;
        }
    }

    private void AddPngFiles(MapElemResourceDefinition definition, string state, string directory)
    {
        AddFiles(definition, state, Directory.GetFiles(directory, "*.png", SearchOption.TopDirectoryOnly));
    }

    private void AddFiles(MapElemResourceDefinition definition, string state, IEnumerable<string> files)
    {
        List<string> result = new List<string>(files);
        result.Sort(StringComparer.OrdinalIgnoreCase);
        if (result.Count > 0)
        {
            definition.stateFiles[state] = result;
        }
    }

    private List<MapElemResourceDefinition> GetOrCreateTypeList(MapElemType type)
    {
        if (!resourcesByType.TryGetValue(type, out List<MapElemResourceDefinition> result))
        {
            result = new List<MapElemResourceDefinition>();
            resourcesByType[type] = result;
        }

        return result;
    }

    private static bool IsPlaceableAssetID(int assetID)
    {
        return assetID > 2;
    }

    private void LoadVisualConfig()
    {
        string path = Path.Combine(RootDirectory, "MapElemVisualConfig.json");
        if (!File.Exists(path))
        {
            LastError = "未找到 MapElemVisualConfig.json，动画时长将显示为未配置";
            return;
        }

        try
        {
            MapElemVisualConfigTable table = JsonUtility.FromJson<MapElemVisualConfigTable>(File.ReadAllText(path));
            if (table == null || table.version != SupportedVisualConfigVersion)
            {
                LastError = string.Format(
                    "MapElemVisualConfig.json 版本不支持，期望 {0}，实际 {1}",
                    SupportedVisualConfigVersion,
                    table != null ? table.version : -1);
                return;
            }

            Vector3 defaultPosition = ReadVector(table.defaults != null ? table.defaults.localPosition : null, Vector3.zero);
            Vector3 defaultScale = ReadVector(table.defaults != null ? table.defaults.localScale : null, Vector3.one);
            bool defaultActive = table.defaults == null || table.defaults.rendererActive;
            bool defaultEnabled = table.defaults == null || table.defaults.rendererEnabled;
            if (!TryCreateDefaultIdleClip(
                    table.defaults != null ? table.defaults.defaultAnimation : null,
                    out MapElemClipDefinition defaultIdleClip))
            {
                LastError = "MapElemVisualConfig.json 默认动画配置无效";
                return;
            }

            if (table.typeDefaults != null)
            {
                foreach (MapElemVisualTypeDefaultConfig row in table.typeDefaults)
                {
                    if (row == null || !MapElemTypeUtility.TryParse(row.type, out MapElemType type))
                    {
                        continue;
                    }

                    MapElemVisualDefinition visual = CreateVisualDefinition(
                        defaultPosition,
                        defaultScale,
                        defaultActive,
                        defaultEnabled,
                        defaultIdleClip,
                        row);
                    typeVisuals[type] = visual;
                }
            }

            if (table.profileGroups != null)
            {
                foreach (MapElemVisualProfileGroupConfig row in table.profileGroups)
                {
                    if (row == null || row.ids == null || !MapElemTypeUtility.TryParse(row.type, out MapElemType type))
                    {
                        continue;
                    }

                    if (!typeVisuals.TryGetValue(type, out MapElemVisualDefinition typeVisual))
                    {
                        typeVisual = CreateFallbackVisual(defaultPosition, defaultScale, defaultActive, defaultEnabled);
                    }

                    foreach (int id in row.ids)
                    {
                        MapElemVisualDefinition visual = typeVisual.Clone();
                        visual.localPosition = ReadVector(row.localPosition, visual.localPosition);
                        if (row.overrideSortingOrder)
                        {
                            visual.sortingOrder = row.sortingOrder;
                        }
                        if (row.overrideRendererActive)
                        {
                            visual.rendererActive = row.rendererActive;
                        }
                        if (row.overrideRendererEnabled)
                        {
                            visual.rendererEnabled = row.rendererEnabled;
                        }
                        MergeClips(visual, row.clips);
                        visual.hasConfig = true;
                        profileVisuals[id] = visual;
                    }
                }
            }
        }
        catch (Exception exception)
        {
            LastError = "MapElemVisualConfig.json 解析失败: " + exception.Message;
        }
    }

    private MapElemVisualDefinition GetVisualDefinition(MapElemType type, int assetID)
    {
        if (profileVisuals.TryGetValue(assetID, out MapElemVisualDefinition profile))
        {
            return profile.Clone();
        }

        if (typeVisuals.TryGetValue(type, out MapElemVisualDefinition typeVisual))
        {
            return typeVisual.Clone();
        }

        return CreateFallbackVisual(Vector3.zero, Vector3.one, true, true);
    }

    private static MapElemVisualDefinition CreateVisualDefinition(
        Vector3 position,
        Vector3 scale,
        bool active,
        bool enabled,
        MapElemClipDefinition defaultIdleClip,
        MapElemVisualTypeDefaultConfig row)
    {
        MapElemVisualDefinition result = CreateFallbackVisual(
            ReadVector(row.localPosition, position),
            scale,
            active,
            enabled);
        result.sortingOrder = row.sortingOrder;
        result.hasConfig = true;
        MergeClips(result, row.clips);
        if (result.clips.Count == 0)
        {
            result.clips["idle"] = defaultIdleClip.Clone();
        }
        return result;
    }

    private static MapElemVisualDefinition CreateFallbackVisual(Vector3 position, Vector3 scale, bool active, bool enabled)
    {
        return new MapElemVisualDefinition
        {
            localPosition = position,
            localScale = scale,
            rendererActive = active,
            rendererEnabled = enabled,
        };
    }

    private static void MergeClips(MapElemVisualDefinition visual, MapElemClipConfig[] rows)
    {
        if (rows == null)
        {
            return;
        }

        foreach (MapElemClipConfig row in rows)
        {
            if (row == null || string.IsNullOrWhiteSpace(row.state))
            {
                continue;
            }

            visual.clips[row.state] = new MapElemClipDefinition
            {
                state = row.state,
                resourceState = string.IsNullOrWhiteSpace(row.resourceState) ? row.state : row.resourceState,
                duration = Mathf.Max(0f, row.duration),
                loop = row.loop,
                isSequence = !row.holdFirstFrame,
                completionState = row.completionState,
                hasTiming = true,
            };
        }
    }

    private static bool TryCreateDefaultIdleClip(
        MapElemDefaultAnimationConfig row,
        out MapElemClipDefinition clip)
    {
        clip = null;
        if (row == null || !IsDesignValue(row.duration) || row.duration <= 0f)
        {
            return false;
        }

        clip = new MapElemClipDefinition
        {
            state = "idle",
            resourceState = "idle",
            duration = row.duration,
            loop = row.loop,
            isSequence = true,
            hasTiming = true,
        };
        return true;
    }

    private static bool IsDesignValue(float value)
    {
        return !float.IsNaN(value)
            && !float.IsInfinity(value)
            && Mathf.Abs(value - Mathf.Round(value * 1000f) / 1000f) <= 0.00001f;
    }

    private static Vector3 ReadVector(float[] values, Vector3 fallback)
    {
        return values != null && values.Length == 3
            ? new Vector3(values[0], values[1], values[2])
            : fallback;
    }
}

public static class MapElemTypeUtility
{
    public static bool TryParse(string name, out MapElemType type)
    {
        if (!string.IsNullOrWhiteSpace(name)
            && Enum.TryParse(name, true, out type)
            && type != MapElemType.None
            && type != MapElemType.Team1Pos
            && type != MapElemType.Team2Pos
            && type != MapElemType.Team3Pos
            && type != MapElemType.Building_Team1
            && type != MapElemType.Building_Team2
            && type != MapElemType.Building_Team3)
        {
            return true;
        }

        type = MapElemType.None;
        return false;
    }
}

public static class MapEditorTextureLoader
{
    private sealed class CacheEntry
    {
        public Sprite sprite;
        public long fileLength;
        public DateTime lastWriteTimeUtc;
    }

    private static readonly Dictionary<string, CacheEntry> Cache =
        new Dictionary<string, CacheEntry>(StringComparer.OrdinalIgnoreCase);

    public static Sprite LoadSprite(string path, bool reloadIfChanged = false)
    {
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
        {
            return null;
        }

        string fullPath = Path.GetFullPath(path);
        FileInfo fileInfo = new FileInfo(fullPath);
        if (Cache.TryGetValue(fullPath, out CacheEntry cached))
        {
            if (!reloadIfChanged
                || (cached.fileLength == fileInfo.Length
                    && cached.lastWriteTimeUtc == fileInfo.LastWriteTimeUtc))
            {
                return cached.sprite;
            }

            ReleaseSprite(cached.sprite);
            Cache.Remove(fullPath);
        }

        try
        {
            byte[] data = File.ReadAllBytes(fullPath);
            Texture2D texture = new Texture2D(2, 2, TextureFormat.RGBA32, false);
            if (!texture.LoadImage(data, false))
            {
                UnityEngine.Object.Destroy(texture);
                return null;
            }

            Sprite sprite = Sprite.Create(
                texture,
                new Rect(0, 0, texture.width, texture.height),
                Vector2.zero,
                100f);
            sprite.name = Path.GetFileNameWithoutExtension(fullPath);
            Cache[fullPath] = new CacheEntry
            {
                sprite = sprite,
                fileLength = fileInfo.Length,
                lastWriteTimeUtc = fileInfo.LastWriteTimeUtc,
            };
            return sprite;
        }
        catch (Exception exception)
        {
            Debug.LogWarning("加载外部 Sprite 失败: " + fullPath + ", " + exception.Message);
            return null;
        }
    }

    public static void ReleaseAll()
    {
        foreach (CacheEntry entry in Cache.Values)
        {
            ReleaseSprite(entry.sprite);
        }
        Cache.Clear();
    }

    private static void ReleaseSprite(Sprite sprite)
    {
        if (sprite == null)
        {
            return;
        }

        Texture texture = sprite.texture;
        UnityEngine.Object.Destroy(sprite);
        if (texture != null)
        {
            UnityEngine.Object.Destroy(texture);
        }
    }
}
