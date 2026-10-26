using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Threading;
using UnityEngine;
using UnityEngine.Networking;

/// <summary>
/// Android 平台相关的路径、内置资源、导出与自检逻辑。
/// 桌面端不会执行这里的 Android 分支，原有流程保持不变。
/// </summary>
public static class AndroidSupport
{
    public const string SeedFileName = "MapEditorSeed.zip";
    public const string SeedMarkerName = ".map_editor_seed_v1";
    public const string RootFolderName = "MapEditor";
    public const string MapElemFolderName = "MapElem";
    public const string MapFolderName = "Map";
    public const string MapPreviewFolderName = "MapPreview";

    public static bool IsAndroid
    {
        get { return Application.platform == RuntimePlatform.Android; }
    }

    public static string RootDirectory
    {
        get { return Path.Combine(Application.persistentDataPath, RootFolderName); }
    }

    public static string MapElemDirectory
    {
        get { return Path.Combine(RootDirectory, MapElemFolderName); }
    }

    public static string MapDirectory
    {
        get { return Path.Combine(RootDirectory, MapFolderName); }
    }

    public static string MapPreviewDirectory
    {
        get { return Path.Combine(RootDirectory, MapPreviewFolderName); }
    }

    public static string SeedMarkerPath
    {
        get { return Path.Combine(RootDirectory, SeedMarkerName); }
    }

    public static string SeedBundlePath
    {
        get { return Path.Combine(Application.streamingAssetsPath, SeedFileName); }
    }

    public static bool SeedReady
    {
        get { return File.Exists(SeedMarkerPath); }
    }

    public static bool DirectoriesReady
    {
        get
        {
            return Directory.Exists(MapElemDirectory)
                && Directory.Exists(MapDirectory)
                && Directory.Exists(MapPreviewDirectory);
        }
    }

    public static MapEditorSettingsData CreateDefaultSettings()
    {
        return new MapEditorSettingsData
        {
            mapElemDirectory = MapElemDirectory,
            mapDirectory = MapDirectory,
            mapPreviewDirectory = MapPreviewDirectory,
        };
    }

    public static void ApplyDefaultPathsIfEmpty(MapEditorSettingsData settings)
    {
        if (settings == null)
        {
            return;
        }

        if (string.IsNullOrWhiteSpace(settings.mapElemDirectory))
        {
            settings.mapElemDirectory = MapElemDirectory;
        }
        if (string.IsNullOrWhiteSpace(settings.mapDirectory))
        {
            settings.mapDirectory = MapDirectory;
        }
        if (string.IsNullOrWhiteSpace(settings.mapPreviewDirectory))
        {
            settings.mapPreviewDirectory = MapPreviewDirectory;
        }
    }

    public static int CountFiles(string directory, string pattern)
    {
        try
        {
            return Directory.Exists(directory)
                ? Directory.GetFiles(directory, pattern, SearchOption.AllDirectories).Length
                : 0;
        }
        catch
        {
            return 0;
        }
    }

    public static void WriteSeedMarker()
    {
        Directory.CreateDirectory(RootDirectory);
        File.WriteAllText(
            SeedMarkerPath,
            string.Format("seed v1 {0:yyyy-MM-dd HH:mm:ss}\n", DateTime.Now));
    }

    /// <summary>
    /// Android 下 StreamingAssets 在 APK 内部，必须用 UnityWebRequest 读取。
    /// </summary>
    public static IEnumerator LoadSeedBundle(Action<byte[]> onSuccess, Action<string> onError)
    {
        string path = SeedBundlePath;
        if (IsAndroid)
        {
            using (UnityWebRequest request = UnityWebRequest.Get(path))
            {
                yield return request.SendWebRequest();
                if (request.result != UnityWebRequest.Result.Success)
                {
                    if (onError != null)
                    {
                        onError(request.error + " (" + path + ")");
                    }
                    yield break;
                }

                if (onSuccess != null)
                {
                    onSuccess(request.downloadHandler.data);
                }
            }
            yield break;
        }

        try
        {
            if (onSuccess != null)
            {
                onSuccess(File.ReadAllBytes(path));
            }
        }
        catch (Exception exception)
        {
            if (onError != null)
            {
                onError(exception.Message);
            }
        }
    }

    public sealed class SeedExtractionState
    {
        public volatile bool done;
        public volatile bool failed;
        public string error;
        public int total;
        public int processed;
        public int extracted;
        public int skipped;
    }

    public static SeedExtractionState ExtractSeedAsync(byte[] zipBytes)
    {
        SeedExtractionState state = new SeedExtractionState();
        Thread thread = new Thread(delegate ()
        {
            try
            {
                Directory.CreateDirectory(RootDirectory);
                string rootFull = Path.GetFullPath(RootDirectory);
                using (MemoryStream memory = new MemoryStream(zipBytes, false))
                using (ZipArchive archive = new ZipArchive(memory, ZipArchiveMode.Read))
                {
                    state.total = archive.Entries.Count;
                    foreach (ZipArchiveEntry entry in archive.Entries)
                    {
                        if (string.IsNullOrEmpty(entry.Name))
                        {
                            state.processed++;
                            continue;
                        }

                        string relative = entry.FullName.Replace('\\', '/');
                        string destination = Path.GetFullPath(Path.Combine(
                            rootFull,
                            relative.Replace('/', Path.DirectorySeparatorChar)));

                        if (!destination.StartsWith(rootFull + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                        {
                            state.processed++;
                            continue;
                        }

                        string directory = Path.GetDirectoryName(destination);
                        if (!string.IsNullOrEmpty(directory))
                        {
                            Directory.CreateDirectory(directory);
                        }

                        if (File.Exists(destination))
                        {
                            state.skipped++;
                        }
                        else
                        {
                            entry.ExtractToFile(destination, false);
                            state.extracted++;
                        }

                        state.processed++;
                    }
                }
            }
            catch (Exception exception)
            {
                state.failed = true;
                state.error = exception.ToString();
            }
            finally
            {
                state.done = true;
            }
        });

        thread.IsBackground = true;
        thread.Start();
        return state;
    }

    public sealed class ExportState
    {
        public volatile bool done;
        public volatile bool failed;
        public string error;
        public int total;
        public int processed;
        public string status = "正在打包地图…";
    }

    /// <summary>
    /// 把 Map 与 MapPreview 目录打成 zip，方便直接从手机下载目录拷回电脑。
    /// </summary>
    public static ExportState CreateExportZipAsync(string mapDirectory, string previewDirectory, string zipPath)
    {
        ExportState state = new ExportState();
        Thread thread = new Thread(delegate ()
        {
            try
            {
                List<string> files = new List<string>();
                if (!string.IsNullOrWhiteSpace(mapDirectory) && Directory.Exists(mapDirectory))
                {
                    files.AddRange(Directory.GetFiles(mapDirectory, "*.bytes", SearchOption.TopDirectoryOnly));
                }
                if (!string.IsNullOrWhiteSpace(previewDirectory) && Directory.Exists(previewDirectory))
                {
                    files.AddRange(Directory.GetFiles(previewDirectory, "*.png", SearchOption.TopDirectoryOnly));
                }

                state.total = files.Count;
                string directory = Path.GetDirectoryName(zipPath);
                if (!string.IsNullOrEmpty(directory))
                {
                    Directory.CreateDirectory(directory);
                }
                if (File.Exists(zipPath))
                {
                    File.Delete(zipPath);
                }

                using (FileStream stream = new FileStream(zipPath, FileMode.Create, FileAccess.Write))
                using (ZipArchive archive = new ZipArchive(stream, ZipArchiveMode.Create))
                {
                    foreach (string file in files)
                    {
                        bool isMap = string.Equals(
                            Path.GetExtension(file),
                            ".bytes",
                            StringComparison.OrdinalIgnoreCase);
                        string entryName = string.Format(
                            "{0}/{1}",
                            isMap ? MapFolderName : MapPreviewFolderName,
                            Path.GetFileName(file));
                        ZipArchiveEntry entry = archive.CreateEntry(
                            entryName,
                            isMap
                                ? System.IO.Compression.CompressionLevel.Optimal
                                : System.IO.Compression.CompressionLevel.Fastest);
                        using (Stream entryStream = entry.Open())
                        using (FileStream source = File.OpenRead(file))
                        {
                            source.CopyTo(entryStream);
                        }

                        state.processed++;
                        state.status = string.Format("正在打包地图… {0}/{1}", state.processed, state.total);
                    }

                    string readme = string.Format(
                        "MapEditor Android 导出\r\n时间: {0:yyyy-MM-dd HH:mm:ss}\r\nMap: {1} 个\r\nMapPreview: {2} 个\r\n\r\n直接解压后覆盖电脑上的 Map 与 MapPreview 目录即可。\r\n",
                        DateTime.Now,
                        state.total,
                        CountFiles(previewDirectory, "*.png"));
                    ZipArchiveEntry readmeEntry = archive.CreateEntry(
                        "README.txt",
                        System.IO.Compression.CompressionLevel.Optimal);
                    using (StreamWriter writer = new StreamWriter(readmeEntry.Open()))
                    {
                        writer.Write(readme);
                    }
                }
            }
            catch (Exception exception)
            {
                state.failed = true;
                state.error = exception.ToString();
            }
            finally
            {
                state.done = true;
            }
        });

        thread.IsBackground = true;
        thread.Start();
        return state;
    }

    /// <summary>
    /// 把文件写入系统“下载”目录（Android 10+ 使用 MediaStore，无需额外权限）。
    /// 返回形如 Download/MapEditor/xxx.zip 的显示路径；失败返回空字符串。
    /// </summary>
    public static string SaveFileToDownloads(string sourcePath, string displayName, string mimeType)
    {
        if (!IsAndroid || string.IsNullOrWhiteSpace(sourcePath) || !File.Exists(sourcePath))
        {
            return string.Empty;
        }

        try
        {
            using (AndroidJavaClass version = new AndroidJavaClass("android.os.Build$VERSION"))
            {
                int sdkInt = version.GetStatic<int>("SDK_INT");
                if (sdkInt < 29)
                {
                    return string.Empty;
                }
            }

            using (AndroidJavaClass unityPlayer = new AndroidJavaClass("com.unity3d.player.UnityPlayer"))
            using (AndroidJavaObject activity = unityPlayer.GetStatic<AndroidJavaObject>("currentActivity"))
            using (AndroidJavaObject resolver = activity.Call<AndroidJavaObject>("getContentResolver"))
            using (AndroidJavaClass downloads = new AndroidJavaClass("android.provider.MediaStore$Downloads"))
            using (AndroidJavaObject collection = downloads.GetStatic<AndroidJavaObject>("EXTERNAL_CONTENT_URI"))
            using (AndroidJavaObject values = new AndroidJavaObject("android.content.ContentValues"))
            {
                values.Call("put", "_display_name", displayName);
                values.Call("put", "mime_type", mimeType);
                values.Call("put", "relative_path", "Download/MapEditor");

                using (AndroidJavaObject uri = resolver.Call<AndroidJavaObject>("insert", collection, values))
                {
                    if (uri == null)
                    {
                        return string.Empty;
                    }

                    using (AndroidJavaObject output = resolver.Call<AndroidJavaObject>("openOutputStream", uri))
                    {
                        if (output == null)
                        {
                            return string.Empty;
                        }

                        byte[] buffer = new byte[256 * 1024];
                        sbyte[] signed = new sbyte[buffer.Length];
                        using (FileStream source = File.OpenRead(sourcePath))
                        {
                            int read;
                            while ((read = source.Read(buffer, 0, buffer.Length)) > 0)
                            {
                                Buffer.BlockCopy(buffer, 0, signed, 0, read);
                                output.Call("write", signed, 0, read);
                            }
                        }
                        output.Call("flush");
                        output.Call("close");
                    }

                    return "Download/MapEditor/" + displayName;
                }
            }
        }
        catch (Exception exception)
        {
            Debug.LogWarning("写入下载目录失败: " + exception.Message);
            return string.Empty;
        }
    }

    public static string BuildDiagnostics()
    {
        MapEditorSettingsData settings = MapEditorSettingsStore.Current;
        System.Text.StringBuilder builder = new System.Text.StringBuilder();
        builder.AppendLine("== MapEditor Android 诊断 ==");
        builder.AppendLine("Screen: " + Screen.width + " x " + Screen.height + "  dpi=" + Screen.dpi);
        builder.AppendLine("persistentDataPath: " + Application.persistentDataPath);
        builder.AppendLine("streamingAssetsPath: " + Application.streamingAssetsPath);
        builder.AppendLine("应用目录: " + RootDirectory);
        builder.AppendLine("内置资源标记: " + (SeedReady ? "已导入" : "未导入"));
        builder.AppendLine("MapElem: " + settings.mapElemDirectory);
        builder.AppendLine("  png 数量: " + CountFiles(settings.mapElemDirectory, "*.png"));
        builder.AppendLine("Map: " + settings.mapDirectory);
        builder.AppendLine("  bytes 数量: " + CountFiles(settings.mapDirectory, "*.bytes"));
        builder.AppendLine("MapPreview: " + settings.mapPreviewDirectory);
        builder.AppendLine("  png 数量: " + CountFiles(settings.mapPreviewDirectory, "*.png"));
        builder.AppendLine("托管内存: " + (GC.GetTotalMemory(false) / (1024 * 1024)) + " MB");
        builder.AppendLine("序列化自检: " + RunSerializationSelfTest());
        return builder.ToString();
    }

    /// <summary>
    /// 启动时做一次 BinaryFormatter 往返测试，确认 IL2CPP 下端序列化可用。
    /// </summary>
    public static string RunSerializationSelfTest()
    {
        try
        {
            FileHelper helper = new FileHelper();
            int size = 15 * 13;
            MapFile file = new MapFile
            {
                ID = 1,
                col = 15,
                row = 13,
                floorArr = new int[size],
                wallArr = new int[size],
                brickArr = new int[size],
                moveBrickArr = new int[size],
                composeWallArr = new int[size],
                doorArr = new int[size],
                grassArr = new int[size],
                riverArr = new int[size],
                pinFloorArr = new int[size],
                spikeWallArr = new int[size],
                totemArr = new int[size],
                team1SpawnPos = new List<int> { 0 },
                team2SpawnPos = new List<int> { 1 },
                team3SpawnPos = new List<int>(),
                buildingInfoArr = new BuildingInfo[]
                {
                    new BuildingInfo { team = 0, assetID = 4501, posIndex = 0 },
                },
            };
            file.floorArr[0] = 42;

            byte[] data = helper.Compress(helper.Serialize(file));
            MapFile copy = helper.DeSerialize<MapFile>(helper.DeCompress(data));
            bool ok = copy != null
                && copy.ID == 1
                && copy.col == 15
                && copy.row == 13
                && copy.floorArr != null
                && copy.floorArr.Length == size
                && copy.floorArr[0] == 42
                && copy.team1SpawnPos != null
                && copy.team1SpawnPos.Count == 1
                && copy.buildingInfoArr != null
                && copy.buildingInfoArr.Length == 1
                && copy.buildingInfoArr[0] != null
                && copy.buildingInfoArr[0].assetID == 4501;
            return ok ? "OK" : "结果不一致";
        }
        catch (Exception exception)
        {
            return "失败: " + exception.GetType().Name + ": " + exception.Message;
        }
    }
}
