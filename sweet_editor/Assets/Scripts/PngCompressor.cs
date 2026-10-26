using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

public class PngCompressor : MonoBehaviour
{
    private static PngCompressor instance;
    public static PngCompressor Instance 
    { 
        get 
        {
            if (instance == null)
            {
                GameObject go = new GameObject("PngCompressor");
                instance = go.AddComponent<PngCompressor>();
                DontDestroyOnLoad(go);
            }
            return instance;
        }
    }
    
    private bool isCompressing = false;
    private int currentFileIndex = 0;
    private int totalFiles = 0;
    private string currentFileName = "";
    
    private static string GetPngquantPath()
    {
        if (AndroidSupport.IsAndroid)
        {
            return string.Empty;
        }

        // StreamingAssets路径在编辑器和打包后都可用
        string pngquantPath = Path.Combine(Application.streamingAssetsPath, "libs/Pngyu/pngquant/pngquant.exe");
        
        if (!File.Exists(pngquantPath))
        {
            // 如果StreamingAssets中没有，尝试旧路径（兼容性）
            string oldPath = Path.Combine(Application.dataPath, "libs/Pngyu/pngquant/pngquant.exe");
            if (File.Exists(oldPath))
            {
                UnityEngine.Debug.LogWarning($"使用旧路径: {oldPath}，建议将libs移动到StreamingAssets");
                return oldPath;
            }
            
            UnityEngine.Debug.LogError($"pngquant工具未找到: {pngquantPath}");
        }
        else
        {
            UnityEngine.Debug.Log($"找到pngquant工具: {pngquantPath}");
        }
        
        return pngquantPath;
    }
    
    private static string GetPreviewPath()
    {
        return MapEditorSettingsStore.Current.mapPreviewDirectory;
    }
    
    public void OpenMapFolder()
    {
        string mapFilesPath = MapEditorSettingsStore.Current.mapDirectory;
        
        if (string.IsNullOrWhiteSpace(mapFilesPath) || !Directory.Exists(mapFilesPath))
        {
            ShowMessage("Map 目录不可用，请先配置外部资源目录");
            return;
        }

        if (AndroidSupport.IsAndroid)
        {
            ShowMessage("地图文件目录: " + mapFilesPath);
            return;
        }
        
        // Windows平台打开文件夹
        #if UNITY_EDITOR_WIN || UNITY_STANDALONE_WIN
            System.Diagnostics.Process.Start("explorer.exe", mapFilesPath.Replace("/", "\\"));
        #elif UNITY_EDITOR_OSX || UNITY_STANDALONE_OSX
            System.Diagnostics.Process.Start("open", mapFilesPath);
        #else
            ShowMessage($"地图文件路径: {mapFilesPath}");
        #endif
        
        ShowMessage($"已打开地图存储目录: {mapFilesPath}");
    }
    
    public void ShowPathInfo()
    {
        string info = "路径诊断信息:\n";
        info += $"Application.dataPath: {Application.dataPath}\n";
        info += $"Application.persistentDataPath: {Application.persistentDataPath}\n";
        info += $"Application.streamingAssetsPath: {Application.streamingAssetsPath}\n";
        info += $"当前目录: {Directory.GetCurrentDirectory()}\n";
        info += $"父目录: {Directory.GetParent(Application.dataPath).FullName}\n";
        info += $"\nMap路径: {MapEditorSettingsStore.Current.mapDirectory}\n";
        info += $"MapPreview路径: {GetPreviewPath()}\n";
        info += $"\npngquant路径: {GetPngquantPath()}\n";
        info += $"pngquant是否存在: {File.Exists(GetPngquantPath())}\n";
        
        UnityEngine.Debug.Log(info);
        ShowMessage("路径信息已输出到控制台");
    }
    
    
    private static bool CompressPngFile(string inputPath, string outputPath = null, int quality = 85)
    {
        if (AndroidSupport.IsAndroid)
        {
            return false;
        }

        if (!File.Exists(inputPath))
        {
            UnityEngine.Debug.LogError($"输入文件不存在: {inputPath}");
            return false;
        }
        
        string pngquantPath = GetPngquantPath();
        if (!File.Exists(pngquantPath))
        {
            UnityEngine.Debug.LogError($"pngquant工具不存在: {pngquantPath}");
            return false;
        }
        
        if (string.IsNullOrEmpty(outputPath))
        {
            outputPath = inputPath;
        }
        
        try
        {
            // 记录原始文件大小
            long originalSize = new FileInfo(inputPath).Length;
            
            // 使用简化的参数格式，让pngquant自动生成输出文件
            ProcessStartInfo startInfo = new ProcessStartInfo
            {
                FileName = pngquantPath,
                Arguments = $"{quality} --force --ext .png \"{inputPath}\"",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                WorkingDirectory = Path.GetDirectoryName(inputPath)
            };
            
            using (Process process = Process.Start(startInfo))
            {
                string output = process.StandardOutput.ReadToEnd();
                string error = process.StandardError.ReadToEnd();
                process.WaitForExit();
                
                if (process.ExitCode == 0)
                {
                    // pngquant默认会覆盖原文件（因为使用了--ext .png）
                    FileInfo compressedFile = new FileInfo(inputPath);
                    long compressedSize = compressedFile.Length;
                    
                    // 如果压缩后的文件更大（理论上不会发生，因为pngquant会自动处理）
                    if (compressedSize >= originalSize)
                    {
                        UnityEngine.Debug.LogWarning($"文件未压缩或压缩效果不佳: {Path.GetFileName(inputPath)} | 大小: {originalSize/1024}KB");
                        return false;
                    }
                    
                    float compressionRatio = (1 - (float)compressedSize / originalSize) * 100;
                    UnityEngine.Debug.Log($"成功压缩: {Path.GetFileName(inputPath)} | 压缩率: {compressionRatio:F1}% | {originalSize/1024}KB -> {compressedSize/1024}KB");
                    return true;
                }
                else
                {
                    UnityEngine.Debug.LogError($"压缩失败: {Path.GetFileName(inputPath)} | 退出码: {process.ExitCode} | 错误: {error}");
                    return false;
                }
            }
        }
        catch (Exception ex)
        {
            UnityEngine.Debug.LogError($"执行pngquant时出错: {ex.Message}");
            return false;
        }
    }
    
    private static CompressResult CompressAllPngsInFolder(string folderPath, int quality = 85)
    {
        CompressResult result = new CompressResult();
        
        if (!Directory.Exists(folderPath))
        {
            UnityEngine.Debug.LogError($"文件夹不存在: {folderPath}");
            return result;
        }
        
        string[] pngFiles = Directory.GetFiles(folderPath, "*.png");
        result.totalCount = pngFiles.Length;
        
        if (pngFiles.Length == 0)
        {
            UnityEngine.Debug.LogWarning($"文件夹中没有PNG文件: {folderPath}");
            return result;
        }
        
        UnityEngine.Debug.Log($"开始压缩 {pngFiles.Length} 个PNG文件...");
        
        foreach (string pngFile in pngFiles)
        {
            // 直接压缩文件，pngquant会自动覆盖原文件
            bool success = CompressPngFile(pngFile, null, quality);
            
            if (success)
            {
                result.successCount++;
            }
            else
            {
                result.failedCount++;
            }
        }
        
        UnityEngine.Debug.Log($"压缩完成! 成功: {result.successCount}, 跳过: {result.skippedCount}, 失败: {result.failedCount}");
        return result;
    }
    
    public void CompressAllMapPngs()
    {
        if (AndroidSupport.IsAndroid)
        {
            ShowMessage("Android 版暂不支持 pngquant 压缩，已跳过");
            return;
        }

        if (isCompressing)
        {
            ShowMessage("正在压缩中，请稍后...");
            return;
        }
        
        string mapFilesPath = GetPreviewPath();
        
        if (string.IsNullOrWhiteSpace(mapFilesPath) || !Directory.Exists(mapFilesPath))
        {
            ShowMessage("MapPreview文件夹不存在");
            return;
        }
        
        string[] pngFiles = Directory.GetFiles(mapFilesPath, "*.png");
        
        if (pngFiles.Length == 0)
        {
            ShowMessage("MapPreview文件夹中没有找到PNG文件");
            return;
        }
        
        // 计算总文件大小
        long totalSize = 0;
        foreach (string file in pngFiles)
        {
            totalSize += new FileInfo(file).Length;
        }
        float totalSizeMB = totalSize / (1024f * 1024f);
        
        // 预估时间（每MB大约2秒）
        int estimatedSeconds = Mathf.CeilToInt(totalSizeMB * 2);
        string estimatedTime = "";
        if (estimatedSeconds < 60)
        {
            estimatedTime = $"{estimatedSeconds}秒";
        }
        else
        {
            int minutes = estimatedSeconds / 60;
            int seconds = estimatedSeconds % 60;
            estimatedTime = $"{minutes}分{seconds}秒";
        }
        
        ShowMessage($"发现 {pngFiles.Length} 个PNG文件，总大小 {totalSizeMB:F1}MB\n预计压缩时间：{estimatedTime}\n开始压缩...");
        
        // 启动异步压缩
        StartCoroutine(CompressAllMapPngsAsync(mapFilesPath, pngFiles));
    }
    
    private IEnumerator CompressAllMapPngsAsync(string mapFilesPath, string[] pngFiles)
    {
        isCompressing = true;
        totalFiles = pngFiles.Length;
        currentFileIndex = 0;
        
        CompressResult result = new CompressResult();
        result.totalCount = pngFiles.Length;
        
        DateTime startTime = DateTime.Now;
        
        // 使用Task在后台线程压缩
        Task<CompressResult> compressionTask = Task.Run(() =>
        {
            CompressResult taskResult = new CompressResult();
            taskResult.totalCount = pngFiles.Length;
            
            foreach (string pngFile in pngFiles)
            {
                currentFileName = Path.GetFileName(pngFile);
                currentFileIndex++;
                
                bool success = CompressPngFile(pngFile, null, 85);
                if (success)
                {
                    taskResult.successCount++;
                }
                else
                {
                    taskResult.failedCount++;
                }
            }
            
            return taskResult;
        });
        
        // 等待任务完成，同时显示进度
        while (!compressionTask.IsCompleted)
        {
            if (currentFileIndex > 0 && currentFileIndex % 5 == 0)
            {
                ShowMessage($"正在压缩... ({currentFileIndex}/{totalFiles}) - {currentFileName}");
            }
            yield return new WaitForSeconds(0.5f);
        }
        
        result = compressionTask.Result;
        
        TimeSpan duration = DateTime.Now - startTime;
        string timeStr = $"{(int)duration.TotalMinutes}分{duration.Seconds}秒";
        
        string message = "";
        if (result.totalCount == 0)
        {
            message = "MapPreview文件夹中没有找到PNG文件";
        }
        else
        {
            message = $"压缩完成！成功压缩了 {result.successCount} 个PNG文件";
            if (result.failedCount > 0)
            {
                message += $"，失败 {result.failedCount} 个";
            }
            message += $"\n耗时：{timeStr}";
        }
        
        ShowMessage(message);
        isCompressing = false;
    }
    
    private void ShowMessage(string message)
    {
        if (ViewManager.Instance != null)
        {
            ViewManager.Instance.ShowTips(message);
        }
        else
        {
            UnityEngine.Debug.Log(message);
        }
    }
    
    public void CompressSinglePng(string fileName)
    {
        if (AndroidSupport.IsAndroid)
        {
            ShowMessage("Android 版暂不支持 pngquant 压缩，已跳过");
            return;
        }

        if (isCompressing)
        {
            ShowMessage("正在压缩中，请稍后...");
            return;
        }
        
        if (string.IsNullOrEmpty(fileName))
        {
            ShowMessage("文件名不能为空");
            return;
        }
        
        // 确保文件名有.png扩展名
        if (!fileName.EndsWith(".png", StringComparison.OrdinalIgnoreCase))
        {
            fileName = fileName + ".png";
        }
        
        string mapFilesPath = GetPreviewPath();
        if (string.IsNullOrWhiteSpace(mapFilesPath))
        {
            ShowMessage("MapPreview目录不可用，请先配置外部资源目录");
            return;
        }
        
        string filePath = Path.Combine(mapFilesPath, fileName);
        
        if (!File.Exists(filePath))
        {
            ShowMessage($"文件不存在: {fileName}");
            return;
        }
        
        StartCoroutine(CompressSinglePngAsync(filePath, fileName));
    }
    
    public void CompressPngByPath(string filePath)
    {
        if (AndroidSupport.IsAndroid)
        {
            return;
        }

        if (isCompressing)
        {
            ShowMessage("正在压缩中，请稍后...");
            return;
        }
        
        if (string.IsNullOrEmpty(filePath))
        {
            ShowMessage("文件路径不能为空");
            return;
        }
        
        if (!File.Exists(filePath))
        {
            ShowMessage($"文件不存在: {filePath}");
            return;
        }
        
        if (!filePath.EndsWith(".png", StringComparison.OrdinalIgnoreCase))
        {
            ShowMessage("只能压缩PNG文件");
            return;
        }
        
        string fileName = Path.GetFileName(filePath);
        StartCoroutine(CompressSinglePngAsync(filePath, fileName));
    }
    
    private IEnumerator CompressSinglePngAsync(string filePath, string fileName)
    {
        isCompressing = true;
        
        // 获取原始文件大小
        long originalSize = new FileInfo(filePath).Length;
        float originalSizeMB = originalSize / (1024f * 1024f);
        
        ShowMessage($"开始压缩: {fileName} ({originalSizeMB:F2}MB)");
        
        DateTime startTime = DateTime.Now;
        bool success = false;
        
        // 在后台线程执行压缩
        Task<bool> compressionTask = Task.Run(() =>
        {
            return CompressPngFile(filePath, null, 85);
        });
        
        // 等待完成
        while (!compressionTask.IsCompleted)
        {
            yield return new WaitForSeconds(0.1f);
        }
        
        success = compressionTask.Result;
        
        TimeSpan duration = DateTime.Now - startTime;
        
        if (success)
        {
            // 获取压缩后的文件大小
            long newSize = new FileInfo(filePath).Length;
            float newSizeMB = newSize / (1024f * 1024f);
            float compressionRatio = (1 - (float)newSize / originalSize) * 100;
            
            ShowMessage($"压缩成功: {fileName}\n大小: {originalSizeMB:F2}MB -> {newSizeMB:F2}MB\n压缩率: {compressionRatio:F1}%\n耗时: {duration.TotalSeconds:F1}秒");
        }
        else
        {
            ShowMessage($"压缩失败或跳过: {fileName}");
        }
        
        isCompressing = false;
    }
    
    private class CompressResult
    {
        public int totalCount = 0;
        public int successCount = 0;
        public int skippedCount = 0;
        public int failedCount = 0;
    }
}
