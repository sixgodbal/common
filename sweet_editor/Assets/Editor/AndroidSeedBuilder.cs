#if UNITY_EDITOR
using System;
using System.IO;
using System.IO.Compression;
using UnityEditor;
using UnityEngine;

/// <summary>
/// 把 Demo 工程里的 MapElem / Map / MapPreview 打成 StreamingAssets/MapEditorSeed.zip，
/// Android 首次启动时解压到应用目录，做到安装即可编辑。
/// </summary>
public static class AndroidSeedBuilder
{
    private const string DefaultDataRoot = "D:/sixgod/gitproject/test/Code/Demo/Assets/Data";
    private const string SourceRootPrefKey = "MapEditor.SeedSourceRoot";
    private const string DestinationRelativePath = "Assets/StreamingAssets/MapEditorSeed.zip";

    [MenuItem("Tools/MapEditor/设置 Android 内置资源源目录")]
    private static void SelectSourceRoot()
    {
        string current = GetDataRoot();
        string selected = EditorUtility.OpenFolderPanel(
            "选择 Data 目录（其下应包含 Map 与 Sprites/MapElem）",
            current,
            string.Empty);
        if (string.IsNullOrWhiteSpace(selected))
        {
            return;
        }

        EditorPrefs.SetString(SourceRootPrefKey, selected.Replace('\\', '/'));
        Debug.Log("[MapEditor] Android 内置资源源目录已设置为: " + selected);
    }

    [MenuItem("Tools/MapEditor/重新生成 Android 内置资源包")]
    public static void BuildSeed()
    {
        string dataRoot = GetDataRoot();
        string mapElemDirectory = Path.Combine(dataRoot, "Sprites/MapElem");
        string mapDirectory = Path.Combine(dataRoot, "Map");
        string previewDirectory = Path.Combine(dataRoot, "Sprites/MapPreview");

        if (!Directory.Exists(mapElemDirectory)
            || !Directory.Exists(mapDirectory)
            || !Directory.Exists(previewDirectory))
        {
            string message = string.Format(
                "资源目录不完整：\nMapElem: {0}\nMap: {1}\nMapPreview: {2}\n\n请先用 Tools/MapEditor/设置 Android 内置资源源目录 选择正确的 Data 目录。",
                mapElemDirectory,
                mapDirectory,
                previewDirectory);
            Debug.LogError("[MapEditor] " + message);
            if (!Application.isBatchMode)
            {
                EditorUtility.DisplayDialog("生成 Android 资源包失败", message, "确定");
            }
            return;
        }

        string projectRoot = Directory.GetParent(Application.dataPath).FullName;
        string destination = Path.Combine(projectRoot, DestinationRelativePath);
        string temporary = destination + ".tmp";
        if (File.Exists(temporary))
        {
            File.Delete(temporary);
        }

        Directory.CreateDirectory(Path.GetDirectoryName(destination));
        int entries = 0;
        try
        {
            using (FileStream stream = new FileStream(temporary, FileMode.Create, FileAccess.Write))
            using (ZipArchive archive = new ZipArchive(stream, ZipArchiveMode.Create))
            {
                entries += AddDirectory(archive, mapElemDirectory, "MapElem", new[] { ".png", ".json" }, true);
                entries += AddDirectory(archive, mapDirectory, "Map", new[] { ".bytes" }, false);
                entries += AddDirectory(archive, previewDirectory, "MapPreview", new[] { ".png" }, false);
            }

            if (File.Exists(destination))
            {
                File.Delete(destination);
            }
            File.Move(temporary, destination);
        }
        catch (Exception exception)
        {
            if (File.Exists(temporary))
            {
                File.Delete(temporary);
            }
            Debug.LogError("[MapEditor] 生成 Android 资源包失败: " + exception);
            return;
        }

        AssetDatabase.ImportAsset(DestinationRelativePath, ImportAssetOptions.ForceUpdate);
        long size = new FileInfo(destination).Length;
        string result = string.Format(
            "已生成 {0}\n条目: {1}\n大小: {2:F1} MB",
            DestinationRelativePath,
            entries,
            size / (1024f * 1024f));
        Debug.Log("[MapEditor] " + result);
        if (!Application.isBatchMode)
        {
            EditorUtility.DisplayDialog("Android 内置资源包", result, "确定");
        }
    }

    private static string GetDataRoot()
    {
        string configured = EditorPrefs.GetString(SourceRootPrefKey, string.Empty);
        if (!string.IsNullOrWhiteSpace(configured))
        {
            return configured;
        }

        // 优先使用与 MapEditor 同级的 Demo 工程，方便整体移动工程目录。
        string projectRoot = Directory.GetParent(Application.dataPath).FullName;
        string sibling = Path.GetFullPath(Path.Combine(projectRoot, "..", "Demo", "Assets", "Data"));
        if (Directory.Exists(sibling))
        {
            return sibling.Replace('\\', '/');
        }

        return DefaultDataRoot.Replace('\\', '/');
    }

    private static int AddDirectory(
        ZipArchive archive,
        string sourceDirectory,
        string prefix,
        string[] extensions,
        bool recursive)
    {
        int count = 0;
        string basePath = Path.GetFullPath(sourceDirectory);
        string[] files = Directory.GetFiles(
            basePath,
            "*",
            recursive ? SearchOption.AllDirectories : SearchOption.TopDirectoryOnly);
        foreach (string file in files)
        {
            if (Array.IndexOf(extensions, Path.GetExtension(file).ToLowerInvariant()) < 0)
            {
                continue;
            }

            string relative = file.Substring(basePath.Length)
                .TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
                .Replace('\\', '/');
            string entryName = prefix + "/" + relative;
            ZipArchiveEntry entry = archive.CreateEntry(
                entryName,
                System.IO.Compression.CompressionLevel.NoCompression);
            using (Stream output = entry.Open())
            using (FileStream input = File.OpenRead(file))
            {
                input.CopyTo(output);
            }
            count++;
        }

        return count;
    }
}
#endif
