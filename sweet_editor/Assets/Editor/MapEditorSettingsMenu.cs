#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;

public static class MapEditorSettingsMenu
{
    [MenuItem("Tools/MapEditor/配置外部资源目录")]
    private static void ConfigureDirectories()
    {
        MapEditorSettingsData settings = MapEditorSettingsStore.Current;
        settings.mapElemDirectory = EditorUtility.OpenFolderPanel("选择 MapElem 目录", settings.mapElemDirectory, string.Empty);
        if (string.IsNullOrWhiteSpace(settings.mapElemDirectory))
        {
            return;
        }

        settings.mapDirectory = EditorUtility.OpenFolderPanel("选择 Map 目录", settings.mapDirectory, string.Empty);
        if (string.IsNullOrWhiteSpace(settings.mapDirectory))
        {
            return;
        }

        settings.mapPreviewDirectory = EditorUtility.OpenFolderPanel("选择 MapPreview 目录", settings.mapPreviewDirectory, string.Empty);
        if (string.IsNullOrWhiteSpace(settings.mapPreviewDirectory))
        {
            return;
        }

        MapEditorSettingsValidation validation = MapEditorSettingsStore.Validate(settings);
        if (!validation.IsFullyValid)
        {
            EditorUtility.DisplayDialog(
                "资源目录无效",
                string.Format("MapElem: {0}\nMap: {1}\nMapPreview: {2}",
                    validation.mapElemMessage,
                    validation.mapMessage,
                    validation.mapPreviewMessage),
                "确定");
            return;
        }

        if (MapEditorSettingsStore.Save(settings, true))
        {
            Debug.Log("地图编辑器外部资源目录配置已保存");
        }
    }
}
#endif
