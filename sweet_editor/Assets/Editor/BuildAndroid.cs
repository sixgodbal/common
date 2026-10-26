#if UNITY_EDITOR
using System;
using System.Diagnostics;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;
using UnityEngine.Rendering;
using Debug = UnityEngine.Debug;

/// <summary>
/// Android APK 构建入口。菜单：Tools/MapEditor/构建 Android APK
/// 命令行：Unity.exe -batchmode -quit -buildTarget Android -executeMethod BuildAndroid.BuildApk
/// </summary>
public static class BuildAndroid
{
    private const string PackageName = "com.sixgod.mapeditor";
    private const string OutputRelativePath = "Builds/Android/MapEditor.apk";
    private const string KeystoreFileName = "mapeditor.keystore";
    private const string KeystorePassword = "mapeditor";
    private const string KeyAlias = "mapeditor";

    [MenuItem("Tools/MapEditor/构建 Android APK")]
    public static void BuildApk()
    {
        ConfigurePlayerSettings();

        string projectRoot = Directory.GetParent(Application.dataPath).FullName;
        string outputPath = Path.Combine(projectRoot, OutputRelativePath);
        Directory.CreateDirectory(Path.GetDirectoryName(outputPath));

        EditorBuildSettings.scenes = new[]
        {
            new EditorBuildSettingsScene("Assets/Scenes/Main.unity", true),
        };

        BuildPlayerOptions options = new BuildPlayerOptions
        {
            scenes = new[] { "Assets/Scenes/Main.unity" },
            locationPathName = outputPath,
            target = BuildTarget.Android,
            options = BuildOptions.None,
        };

        Debug.Log("[BuildAndroid] 开始构建: " + outputPath);
        BuildReport report = BuildPipeline.BuildPlayer(options);
        BuildSummary summary = report.summary;
        if (summary.result != BuildResult.Succeeded)
        {
            Debug.LogError(string.Format(
                "[BuildAndroid] 构建失败: {0}, 错误数 {1}, 输出 {2}",
                summary.result,
                summary.totalErrors,
                summary.outputPath));
            if (Application.isBatchMode)
            {
                EditorApplication.Exit(1);
            }
            return;
        }

        Debug.Log(string.Format(
            "[BuildAndroid] 构建成功: {0} ({1:F1} MB)",
            Path.GetFullPath(outputPath),
            new FileInfo(outputPath).Length / (1024f * 1024f)));
        if (Application.isBatchMode)
        {
            EditorApplication.Exit(0);
        }
    }

    private static void ConfigurePlayerSettings()
    {
        if (!EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android))
        {
            throw new InvalidOperationException("切换到 Android 构建目标失败，请确认已安装 Android Build Support。");
        }

        PlayerSettings.companyName = "SixGod";
        PlayerSettings.productName = "MapEditor";
        PlayerSettings.bundleVersion = "1.0.0";
        PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, PackageName);
        PlayerSettings.Android.bundleVersionCode = 1;

        PlayerSettings.defaultInterfaceOrientation = UIOrientation.AutoRotation;
        PlayerSettings.allowedAutorotateToPortrait = false;
        PlayerSettings.allowedAutorotateToPortraitUpsideDown = false;
        PlayerSettings.allowedAutorotateToLandscapeLeft = true;
        PlayerSettings.allowedAutorotateToLandscapeRight = true;

        PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel24;
        PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel32;
        PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.Mono2x);
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARMv7;
        PlayerSettings.SetManagedStrippingLevel(BuildTargetGroup.Android, ManagedStrippingLevel.Disabled);
        PlayerSettings.SetApiCompatibilityLevel(
            BuildTargetGroup.Android,
            ApiCompatibilityLevel.NET_Standard_2_0);

        PlayerSettings.Android.forceInternetPermission = false;
        PlayerSettings.Android.forceSDCardPermission = false;

        PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.Android, false);
        PlayerSettings.SetGraphicsAPIs(
            BuildTarget.Android,
            new[] { GraphicsDeviceType.OpenGLES3 });

        EditorUserBuildSettings.buildAppBundle = false;
        EditorUserBuildSettings.exportAsGoogleAndroidProject = false;
        EditorUserBuildSettings.androidBuildType = AndroidBuildType.Release;

        EnsureKeystore();
        AssetDatabase.SaveAssets();
    }

    private static void EnsureKeystore()
    {
        try
        {
            string androidDirectory = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                ".android");
            Directory.CreateDirectory(androidDirectory);
            string keystorePath = Path.Combine(androidDirectory, KeystoreFileName);

            if (!File.Exists(keystorePath))
            {
                string keytool = Path.Combine(
                    EditorApplication.applicationContentsPath,
                    "PlaybackEngines/AndroidPlayer/OpenJDK/bin/keytool.exe");
                if (!File.Exists(keytool))
                {
                    keytool = Path.Combine(
                        EditorApplication.applicationContentsPath,
                        "PlaybackEngines/AndroidPlayer/OpenJDK/bin/keytool");
                }

                if (!File.Exists(keytool))
                {
                    Debug.LogWarning("[BuildAndroid] 未找到 keytool，将使用 Unity 默认调试签名。");
                    PlayerSettings.Android.useCustomKeystore = false;
                    return;
                }

                string arguments = string.Format(
                    "-genkeypair -v -keystore \"{0}\" -storepass {1} -keypass {1} -alias {2} -keyalg RSA -keysize 2048 -validity 10000 -dname \"CN=MapEditor, OU=Dev, O=SixGod, L=Local, ST=Local, C=CN\"",
                    keystorePath,
                    KeystorePassword,
                    KeyAlias);
                ProcessStartInfo startInfo = new ProcessStartInfo
                {
                    FileName = keytool,
                    Arguments = arguments,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                };
                using (Process process = Process.Start(startInfo))
                {
                    string output = process.StandardOutput.ReadToEnd();
                    string error = process.StandardError.ReadToEnd();
                    process.WaitForExit();
                    if (process.ExitCode != 0 || !File.Exists(keystorePath))
                    {
                        Debug.LogWarning("[BuildAndroid] 生成签名失败，将使用默认调试签名: " + error);
                        PlayerSettings.Android.useCustomKeystore = false;
                        return;
                    }
                    Debug.Log("[BuildAndroid] 已生成签名: " + keystorePath + "\n" + output);
                }
            }

            PlayerSettings.Android.useCustomKeystore = true;
            PlayerSettings.Android.keystoreName = keystorePath;
            PlayerSettings.Android.keystorePass = KeystorePassword;
            PlayerSettings.Android.keyaliasName = KeyAlias;
            PlayerSettings.Android.keyaliasPass = KeystorePassword;
        }
        catch (Exception exception)
        {
            Debug.LogWarning("[BuildAndroid] 配置签名失败，将使用默认调试签名: " + exception.Message);
            PlayerSettings.Android.useCustomKeystore = false;
        }
    }
}
#endif
