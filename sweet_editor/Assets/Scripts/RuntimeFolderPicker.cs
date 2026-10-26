using System;
using System.Runtime.InteropServices;
using System.Text;

public static class RuntimeFolderPicker
{
    public static bool IsSupported
    {
        get
        {
#if UNITY_EDITOR || UNITY_STANDALONE_WIN
            return true;
#else
            return false;
#endif
        }
    }

    public static string PickFolder(string title, string initialDirectory)
    {
#if UNITY_EDITOR
        return PickFolderInEditor(title, initialDirectory);
#elif UNITY_STANDALONE_WIN
        return PickFolderOnWindows(title, initialDirectory);
#else
        return string.Empty;
#endif
    }

#if UNITY_EDITOR
    private static string PickFolderInEditor(string title, string initialDirectory)
    {
        Type editorUtilityType = Type.GetType("UnityEditor.EditorUtility, UnityEditor");
        if (editorUtilityType == null)
        {
            return string.Empty;
        }

        var method = editorUtilityType.GetMethod(
            "OpenFolderPanel",
            new[] { typeof(string), typeof(string), typeof(string) });
        if (method == null)
        {
            return string.Empty;
        }

        object result = method.Invoke(null, new object[]
        {
            title,
            initialDirectory ?? string.Empty,
            string.Empty,
        });
        return result as string ?? string.Empty;
    }
#endif

#if UNITY_STANDALONE_WIN && !UNITY_EDITOR
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct BrowseInfo
    {
        public IntPtr hwndOwner;
        public IntPtr pidlRoot;
        public IntPtr displayName;
        public string title;
        public uint flags;
        public IntPtr callback;
        public IntPtr lParam;
        public int image;
    }

    private const uint ReturnOnlyFileSystemDirs = 0x00000001;
    private const uint NewDialogStyle = 0x00000040;
    private const uint BrowseInitialized = 1;
    private const uint SetSelectionUnicode = 0x00000467;

    private delegate int BrowseCallback(IntPtr window, uint message, IntPtr itemIdList, IntPtr data);

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr SHBrowseForFolder(ref BrowseInfo browseInfo);

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    private static extern bool SHGetPathFromIDList(IntPtr itemIdList, StringBuilder path);

    [DllImport("ole32.dll")]
    private static extern void CoTaskMemFree(IntPtr item);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr SendMessage(IntPtr window, uint message, IntPtr parameter, string data);

    private static string PickFolderOnWindows(string title, string initialDirectory)
    {
        IntPtr displayName = Marshal.AllocHGlobal(520);
        IntPtr initialPath = IntPtr.Zero;
        BrowseCallback callback = OnBrowse;
        if (!string.IsNullOrWhiteSpace(initialDirectory))
        {
            initialPath = Marshal.StringToHGlobalUni(initialDirectory);
        }

        BrowseInfo browseInfo = new BrowseInfo
        {
            displayName = displayName,
            title = string.IsNullOrWhiteSpace(title) ? "选择目录" : title,
            flags = ReturnOnlyFileSystemDirs | NewDialogStyle,
            callback = Marshal.GetFunctionPointerForDelegate(callback),
            lParam = initialPath,
        };

        IntPtr itemIdList = IntPtr.Zero;
        try
        {
            itemIdList = SHBrowseForFolder(ref browseInfo);
            if (itemIdList == IntPtr.Zero)
            {
                return string.Empty;
            }

            StringBuilder path = new StringBuilder(4096);
            return SHGetPathFromIDList(itemIdList, path) ? path.ToString() : string.Empty;
        }
        finally
        {
            if (itemIdList != IntPtr.Zero)
            {
                CoTaskMemFree(itemIdList);
            }
            if (initialPath != IntPtr.Zero)
            {
                Marshal.FreeHGlobal(initialPath);
            }
            Marshal.FreeHGlobal(displayName);
            GC.KeepAlive(callback);
        }
    }

    private static int OnBrowse(IntPtr window, uint message, IntPtr itemIdList, IntPtr data)
    {
        if (message == BrowseInitialized && data != IntPtr.Zero)
        {
            string initialDirectory = Marshal.PtrToStringUni(data);
            SendMessage(window, SetSelectionUnicode, new IntPtr(1), initialDirectory);
        }
        return 0;
    }
#endif
}
