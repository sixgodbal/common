using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;
using Candy;

public class Team
{
    public int id;
    public MapElemItem data;

    public Team(int _id, MapElemItem _data)
    {
        id = _id;
        data = _data;
    }
}

public enum PendingActionType
{
    None,
    CreateNewMap,
    ResizeMap,
    ClearMap,
    SaveMap,
}

public class ViewManager : MonoBehaviour
{
    private sealed class PlacementPreviewEntry
    {
        public GameObject previewObject;
        public MapElemItem item;
        public int baseSortingOrder;
    }

    private const int MinCol = 15;
    private const int MinRow = 13;
    private const int MaxCol = 50;
    private const int MaxRow = 50;
    private const float CameraPadding = 1.5f;
    private const float PreviewPadding = 0.6f;
    private const float CameraLoosePadding = 0.5f;
    private const float MinZoomSize = 4.5f;
    private const float MaxZoomSize = 60f;
    private const float ZoomStep = 1.2f;
    private const float MaxLooseDistance = 4f;
    private const float DragThreshold = 0.001f;
    private const int PreviewWidth = 1000;
    private const int PreviewHeight = 768;
    private const int PreviewPaddingPixels = 24;
    private const float PlacementPreviewAlpha = 0.45f;
    private const int UndoHistoryLimit = 50;
    private const int BuildingTeamCount = 3;

    public static ViewManager Instance;
    public bool isArtMode;
    public Camera previewCamera;
    public Transform rootTransform;
    public int curAssetID = 1;
    public int curBuildingTeam = -1;
    public Text mapNameText;
    public Dropdown fullDropdown;
    public GameObject mapItemPrefab;
    public Transform mapItemsParentTrans;
    public GameObject tipsObj;

    private List<MapItem> mapItems;
    private int fullTypeIndex;

    private Animator tipsAnimator;
    private Text tipsText;
    private Camera mainCamera;
    private EventSystem eventSystem;
    private EditorLine editorLine;
    private Canvas cachedCanvas;
    private RectTransform canvasRect;
    private RectTransform controlPanelRect;

    private Dictionary<int, MapElemItem> prefabDict = new Dictionary<int, MapElemItem>();
    private MapElemItem mapElemTemplate;

    private Dictionary<int, MapElemItem> floorDict = new Dictionary<int, MapElemItem>();
    private Dictionary<int, MapElemItem> pinFloorDict = new Dictionary<int, MapElemItem>();
    private Dictionary<int, MapElemItem> wallDict = new Dictionary<int, MapElemItem>();
    private Dictionary<int, MapElemItem> spikeWallDict = new Dictionary<int, MapElemItem>();
    private Dictionary<int, MapElemItem> riverDict = new Dictionary<int, MapElemItem>();
    private Dictionary<int, MapElemItem> brickDict = new Dictionary<int, MapElemItem>();
    private Dictionary<int, MapElemItem> moveBrickDict = new Dictionary<int, MapElemItem>();
    private Dictionary<int, MapElemItem> composeWallDict = new Dictionary<int, MapElemItem>();
    private Dictionary<int, MapElemItem> doorDict = new Dictionary<int, MapElemItem>();
    private Dictionary<int, MapElemItem> grassDict = new Dictionary<int, MapElemItem>();
    private Dictionary<int, MapElemItem> totemDict = new Dictionary<int, MapElemItem>();

    private Team[] buildingArr = new Team[BuildingTeamCount];
    private List<Team> team1SpawnPosList = new List<Team>();
    private List<Team> team2SpawnPosList = new List<Team>();
    private List<Team> team3SpawnPosList = new List<Team>();

    private Vector3 rootPos;

    private readonly int gridSize = 1;
    private readonly float halfGridSize = 0.5f;

    private int currentCol = MinCol;
    private int currentRow = MinRow;
    private int[,] gridsLayer;

    private MapBounds bounds;
    private FileHelper fileHelper;
    private string mapDirectory;
    private string mapPreviewDirectory;
    private string currentMapID = string.Empty;

    private bool isPanning;
    private bool ignorePaintUntilMouseUp;
    private Vector3 lastPanWorldPos;
    private float fitViewSize;

    private bool deleteMode;
    private bool touchPainting;
    private bool touchMulti;
    private bool touchBlocked;
    private bool hasLastPaintGrid;
    private GridID lastPaintGrid;
    private Vector2 lastPinchMidpoint;
    private float lastPinchDistance;
    private Vector2 touchStartPosition;
    private bool touchPainted;
    private float nextMapPreviewRefreshTime;
    private readonly List<RaycastResult> uiRaycastResults = new List<RaycastResult>();

    private readonly List<PlacementPreviewEntry> placementPreviews = new List<PlacementPreviewEntry>();
    private readonly List<GridID> placementGridBuffer = new List<GridID>();
    private int placementPreviewAssetID = int.MinValue;
    private int placementPreviewBuildingTeam = int.MinValue;
    private bool placementPreviewUnavailable;

    private readonly List<MapSnapshot> undoHistory = new List<MapSnapshot>();
    private MapSnapshot activeElementEditSnapshot;
    private int activeElementEditMouseButton = -1;

    private MapSnapshot pendingSnapshot;
    private PendingActionType pendingActionType;
    private int pendingCol;
    private int pendingRow;
    private string pendingMapID = string.Empty;

    private InputField widthInputField;
    private InputField heightInputField;
    private InputField mapIDInputField;
    private Text currentSizeText;
    private Button newMapButton;
    private Button applySizeButton;
    private Button undoButton;
    private Button pickMapElemButton;
    private Button fitMapButton;
    private Button centerMapButton;
    private ScrollRect mapFileScrollRect;
    private Text pickMapElemButtonText;
    private ColorBlock pickMapElemButtonColors;
    private bool isPickingMapElem;
    private Texture2D mapElemPickerCursorTexture;
    private GameObject confirmDialog;
    private Text confirmMessageText;
    private Button confirmOkButton;
    private Button confirmCancelButton;

    private void Awake()
    {
        Instance = this;
        fileHelper = new FileHelper();
        MapEditorSettingsStore.Load();
        ApplyResourceDirectories(MapEditorSettingsStore.Current);
        MapEditorSettingsStore.Changed += OnResourceDirectoriesChanged;
        mainCamera = Camera.main;
        eventSystem = EventSystem.current;
        editorLine = rootTransform.GetComponent<EditorLine>();

        tipsObj.SetActive(false);
        tipsAnimator = tipsObj.transform.GetComponent<Animator>();
        tipsText = tipsObj.transform.GetComponent<Text>();

        InitFullDropdown();
        CacheCanvasInfo();
        CreateOrBindRuntimeControls();
        MapEditorSettingsPanel.EnsureInstance();
        MobileControlsPanel.EnsureInstance();

        mapItems = new List<MapItem>();
        UpdateMapFileScrollView();
    }

    private void Start()
    {
        Vector3 pos = rootTransform.localPosition;
        rootPos = new Vector3(pos.x - halfGridSize, pos.y - halfGridSize, pos.z);

        ApplyMapSizeInternal(currentCol, currentRow);
        FitCameraToMap();
        SyncRuntimeFields();
        LoadPrefabs();
    }

    private void OnDestroy()
    {
        MapEditorSettingsStore.Changed -= OnResourceDirectoriesChanged;
        SetMapElemPickerCursor(false);
        if (mapElemPickerCursorTexture != null)
        {
            Destroy(mapElemPickerCursorTexture);
            mapElemPickerCursorTexture = null;
        }
        ResetPlacementPreview();
        MapEditorThumbnailCache.Clear();
    }

    private void OnDisable()
    {
        SetMapElemPickerCursor(false);
    }

    private void OnEnable()
    {
        if (isPickingMapElem)
        {
            SetMapElemPickerCursor(true);
        }
    }

    private void OnResourceDirectoriesChanged()
    {
        ClearUndoHistory();
        ResetPlacementPreview();
        ApplyResourceDirectories(MapEditorSettingsStore.Current);
        UpdateMapFileScrollView();
    }

    private void ApplyResourceDirectories(MapEditorSettingsData settings)
    {
        mapDirectory = settings == null ? string.Empty : settings.mapDirectory;
        mapPreviewDirectory = settings == null ? string.Empty : settings.mapPreviewDirectory;
    }

    private void Update()
    {
        FinalizeElementEditIfNeeded();
        HandleUndoShortcut();
        HandleMapElemPickerShortcut();
        if (AndroidSupport.IsAndroid)
        {
            HandleTouchInput();
        }
        else
        {
            HandleCameraNavigation();
            HandlePaintInput();
        }

        UpdatePlacementPreview();
        UpdateMapPreviewVisibility();
    }

    private void InitFullDropdown()
    {
        List<string> dropList = new List<string>
        {
            "单个",
            "整行",
            "一行(奇)",
            "一行(偶)",
            "整列",
            "一列(奇)",
            "一列(偶)",
            "全部",
        };

        fullDropdown.ClearOptions();
        fullDropdown.AddOptions(dropList);
        fullDropdown.onValueChanged.RemoveAllListeners();
        fullDropdown.onValueChanged.AddListener(v => { fullTypeIndex = v; });
    }

    private void CacheCanvasInfo()
    {
        cachedCanvas = FindObjectOfType<Canvas>();
        if (cachedCanvas != null)
        {
            canvasRect = cachedCanvas.GetComponent<RectTransform>();
        }

        if (mapNameText != null)
        {
            mapIDInputField = mapNameText.GetComponentInParent<InputField>();
            controlPanelRect = mapNameText.transform.parent as RectTransform;
        }

        if (mapItemsParentTrans != null)
        {
            mapFileScrollRect = mapItemsParentTrans.GetComponentInParent<ScrollRect>();
        }
    }

    private void LoadPrefabs()
    {
        prefabDict.Clear();
        foreach (int assetID in new[] { 1, 2, 3 })
        {
            GameObject prefab = Resources.Load<GameObject>("Prefabs/" + assetID);
            MapElemItem item = prefab == null ? null : prefab.GetComponent<MapElemItem>();
            if (item == null)
            {
                continue;
            }

            item.assetID = assetID;
            prefabDict[assetID] = item;
        }

        GameObject templatePrefab = Resources.Load<GameObject>("Prefabs/MapElemTemplate");
        mapElemTemplate = templatePrefab == null ? null : templatePrefab.GetComponent<MapElemItem>();
        if (mapElemTemplate == null)
        {
            Debug.LogWarning("未找到通用地图元素模板 Prefabs/MapElemTemplate，将使用运行时后备模板");
        }
    }

    private void CreateOrBindRuntimeControls()
    {
        if (mapNameText == null || mapNameText.transform.parent == null)
        {
            return;
        }

        RectTransform mapIdRoot = mapNameText.transform.parent.GetComponent<RectTransform>();
        RectTransform canvas = mapIdRoot.parent as RectTransform;
        if (canvas == null)
        {
            return;
        }

        widthInputField = FindChildComponent<InputField>(canvas, "WidthInputRuntime");
        heightInputField = FindChildComponent<InputField>(canvas, "HeightInputRuntime");
        currentSizeText = FindChildComponent<Text>(canvas, "CurrentSizeRuntimeText");
        newMapButton = FindChildButton(canvas, "NewMapRuntimeButton");
        applySizeButton = FindChildButton(canvas, "ApplySizeRuntimeButton");
        undoButton = FindChildButton(canvas, "UndoRuntimeButton");
        pickMapElemButton = FindChildButton(canvas, "PickMapElemRuntimeButton");
        fitMapButton = FindChildButton(canvas, "FitMapRuntimeButton");
        centerMapButton = FindChildButton(canvas, "CenterMapRuntimeButton");
        ConfigureMapElemPickerButton();
        confirmDialog = FindChildGameObject(canvas, "ConfirmDialogRuntime");
        ConfigureNumericInput(widthInputField, MinCol);
        ConfigureNumericInput(heightInputField, MinRow);

        confirmMessageText = FindChildComponent<Text>(confirmDialog.transform as RectTransform, "Message");
        confirmOkButton = FindChildButton(confirmDialog.transform as RectTransform, "ConfirmButton");
        confirmCancelButton = FindChildButton(confirmDialog.transform as RectTransform, "CancelButton");

        bool missingControls = widthInputField == null ||
                               heightInputField == null ||
                               currentSizeText == null ||
                               newMapButton == null ||
                               applySizeButton == null ||
                               undoButton == null ||
                               pickMapElemButton == null ||
                               fitMapButton == null ||
                               centerMapButton == null ||
                               confirmDialog == null ||
                               confirmMessageText == null ||
                               confirmOkButton == null ||
                               confirmCancelButton == null;
        if (missingControls)
        {
            Debug.LogError("运行时固定UI未配置完整，请先在Unity编辑器执行 Tools/MapEditor/生成固定运行时UI。");
            return;
        }

        confirmDialog.SetActive(false);
    }

    private void ConfigureMapElemPickerButton()
    {
        if (pickMapElemButton == null)
        {
            return;
        }

        pickMapElemButtonText = pickMapElemButton.GetComponentInChildren<Text>(true);
        pickMapElemButtonColors = pickMapElemButton.colors;
        UpdateMapElemPickerButtonState();
    }

    private void ConfigureNumericInput(InputField inputField, int defaultValue)
    {
        if (inputField == null)
        {
            return;
        }

        inputField.contentType = InputField.ContentType.IntegerNumber;
        inputField.text = defaultValue.ToString();
        if (inputField.placeholder != null)
        {
            Text placeholder = inputField.placeholder.GetComponent<Text>();
            if (placeholder != null)
            {
                placeholder.text = defaultValue.ToString();
            }
        }
    }

    private void HandleCameraNavigation()
    {
        if (mainCamera == null
            || MapEditorSettingsPanel.BlocksMapInput
            || MapElemAnimationViewer.IsVisible
            || (confirmDialog != null && confirmDialog.activeSelf)
            || IsPointerOverUI())
        {
            if (!Input.GetMouseButton(2))
            {
                isPanning = false;
                ignorePaintUntilMouseUp = false;
            }
            return;
        }

        float scroll = Input.mouseScrollDelta.y;
        if (Mathf.Abs(scroll) > Mathf.Epsilon)
        {
            ZoomCamera(scroll);
        }

        if (Input.GetMouseButtonDown(2))
        {
            isPanning = true;
            ignorePaintUntilMouseUp = true;
            lastPanWorldPos = GetWorldPointOnMapPlane();
        }

        if (Input.GetMouseButton(2) && isPanning)
        {
            Vector3 worldPos = GetWorldPointOnMapPlane();
            Vector3 delta = lastPanWorldPos - worldPos;
            if (delta.sqrMagnitude > DragThreshold)
            {
                mainCamera.transform.position += delta;
                ClampCameraPosition(mainCamera);
                lastPanWorldPos = GetWorldPointOnMapPlane();
            }
        }

        if (Input.GetMouseButtonUp(2))
        {
            isPanning = false;
            ignorePaintUntilMouseUp = false;
        }
    }

    private void UpdatePlacementPreview()
    {
        bool blocked = mainCamera == null
            || MapEditorSettingsPanel.BlocksMapInput
            || MapElemAnimationViewer.IsVisible
            || MapEditorBootstrap.BlocksInput
            || isPickingMapElem
            || (confirmDialog != null && confirmDialog.activeSelf)
            || isPanning
            || Input.GetMouseButton(2)
            || deleteMode
            || touchPainting
            || touchMulti
            || MobileControlsPanel.BlocksPoint(Input.mousePosition)
            || IsPointerOverUI();
        if (blocked)
        {
            HidePlacementPreview();
            return;
        }

        Vector2 mousePosition = GetMouseClickPos();
        if (!GetGridIDByPos(mousePosition, out GridID gridID))
        {
            HidePlacementPreview();
            return;
        }

        BuildPlacementGridIDs(gridID, placementGridBuffer);
        if (placementGridBuffer.Count == 0 || !EnsurePlacementPreviews(placementGridBuffer.Count))
        {
            HidePlacementPreview();
            return;
        }

        int team1PreviewCount = team1SpawnPosList.Count;
        int team2PreviewCount = team2SpawnPosList.Count;
        int team3PreviewCount = team3SpawnPosList.Count;
        for (int i = 0; i < placementPreviews.Count; i++)
        {
            PlacementPreviewEntry preview = placementPreviews[i];
            if (i >= placementGridBuffer.Count)
            {
                preview.previewObject.SetActive(false);
                continue;
            }

            GridID previewGridID = placementGridBuffer[i];
            preview.previewObject.transform.localPosition = GetPositionByGrid(previewGridID);
            if (preview.item.type == MapElemType.Team1Pos)
            {
                if (GetTeam(team1SpawnPosList, IDToIndex(previewGridID)) != null)
                {
                    team1PreviewCount--;
                }
                preview.item.SetIndex(++team1PreviewCount);
            }
            else if (preview.item.type == MapElemType.Team2Pos)
            {
                if (GetTeam(team2SpawnPosList, IDToIndex(previewGridID)) != null)
                {
                    team2PreviewCount--;
                }
                preview.item.SetIndex(++team2PreviewCount);
            }
            else if (preview.item.type == MapElemType.Team3Pos)
            {
                if (GetTeam(team3SpawnPosList, IDToIndex(previewGridID)) != null)
                {
                    team3PreviewCount--;
                }
                preview.item.SetIndex(++team3PreviewCount);
            }

            if (preview.item.render != null)
            {
                int layer = preview.item.type == MapElemType.Floor ? 0 : GetViewLayer(previewGridID);
                preview.item.render.sortingOrder = preview.baseSortingOrder;
                preview.item.SetLayer(layer);
            }
            preview.previewObject.SetActive(true);
        }
    }

    private bool EnsurePlacementPreviews(int requiredCount)
    {
        bool selectionChanged = placementPreviewAssetID != curAssetID
            || placementPreviewBuildingTeam != curBuildingTeam;
        if (selectionChanged)
        {
            DestroyPlacementPreviewObjects();
            placementPreviewAssetID = curAssetID;
            placementPreviewBuildingTeam = curBuildingTeam;
            placementPreviewUnavailable = false;
        }

        if (placementPreviewUnavailable)
        {
            return false;
        }

        while (placementPreviews.Count < requiredCount)
        {
            MapElemItem previewItem = CreatePlacementPreviewItem(
                placementPreviewAssetID,
                placementPreviewBuildingTeam,
                out GameObject previewObject);
            if (previewItem == null || previewObject == null)
            {
                placementPreviewUnavailable = true;
                return false;
            }

            PlacementPreviewEntry preview = new PlacementPreviewEntry
            {
                previewObject = previewObject,
                item = previewItem,
                baseSortingOrder = previewItem.render != null ? previewItem.render.sortingOrder : 0,
            };
            PreparePlacementPreview(previewObject);
            previewObject.SetActive(false);
            placementPreviews.Add(preview);
        }

        return true;
    }

    private void BuildPlacementGridIDs(GridID anchor, List<GridID> target)
    {
        target.Clear();
        switch (fullTypeIndex)
        {
            case 0:
                target.Add(anchor);
                break;
            case 1:
                AddRowGridIDs(anchor.y, target, -1);
                break;
            case 2:
                AddRowGridIDs(anchor.y, target, 1);
                break;
            case 3:
                AddRowGridIDs(anchor.y, target, 0);
                break;
            case 4:
                AddColumnGridIDs(anchor.x, target, -1);
                break;
            case 5:
                AddColumnGridIDs(anchor.x, target, 1);
                break;
            case 6:
                AddColumnGridIDs(anchor.x, target, 0);
                break;
            case 7:
                for (int y = 0; y < currentRow; y++)
                {
                    AddRowGridIDs(y, target, -1);
                }
                break;
            default:
                target.Add(anchor);
                break;
        }
    }

    private void AddColumnGridIDs(int column, List<GridID> target, int rowRemainder)
    {
        for (int y = 0; y < currentRow; y++)
        {
            if (rowRemainder < 0 || y % 2 == rowRemainder)
            {
                target.Add(new GridID(column, y));
            }
        }
    }

    private void AddRowGridIDs(int row, List<GridID> target, int columnRemainder)
    {
        for (int x = 0; x < currentCol; x++)
        {
            if (columnRemainder < 0 || x % 2 == columnRemainder)
            {
                target.Add(new GridID(x, row));
            }
        }
    }

    private MapElemItem CreatePlacementPreviewItem(int assetID, int buildingTeam, out GameObject previewObject)
    {
        previewObject = null;
        MapElemItem previewItem;
        if (prefabDict.TryGetValue(assetID, out MapElemItem prefab))
        {
            previewObject = Instantiate(prefab.gameObject, rootTransform);
            previewItem = previewObject.GetComponent<MapElemItem>();
        }
        else
        {
            if (MapSelector.ActiveCatalog == null
                || !MapSelector.ActiveCatalog.TryGet(assetID, out MapElemResourceDefinition resource))
            {
                return null;
            }

            if (mapElemTemplate != null)
            {
                previewObject = Instantiate(mapElemTemplate.gameObject, rootTransform);
                previewItem = previewObject.GetComponent<MapElemItem>();
            }
            else
            {
                previewObject = new GameObject("MapElemPlacementPreview");
                previewObject.transform.SetParent(rootTransform, false);
                GameObject spriteObject = new GameObject("Sprite");
                spriteObject.transform.SetParent(previewObject.transform, false);
                SpriteRenderer renderer = spriteObject.AddComponent<SpriteRenderer>();
                previewItem = previewObject.AddComponent<MapElemItem>();
                previewItem.render = renderer;
            }

            previewObject.SetActive(true);
            previewItem.InitializeExternal(resource, GetEditorType(resource.type, buildingTeam), buildingTeam);
        }

        if (previewItem == null || previewItem.render == null || previewItem.render.sprite == null)
        {
            if (previewObject != null)
            {
                previewObject.SetActive(false);
                Destroy(previewObject);
                previewObject = null;
            }
            return null;
        }

        previewObject.name = "PlacementPreview_" + assetID;
        return previewItem;
    }

    private void PreparePlacementPreview(GameObject previewObject)
    {
        foreach (SpriteRenderer renderer in previewObject.GetComponentsInChildren<SpriteRenderer>(true))
        {
            Color color = renderer.color;
            color.a *= PlacementPreviewAlpha;
            renderer.color = color;
        }

        foreach (Graphic graphic in previewObject.GetComponentsInChildren<Graphic>(true))
        {
            Color color = graphic.color;
            color.a *= PlacementPreviewAlpha;
            graphic.color = color;
            graphic.raycastTarget = false;
        }

        foreach (Collider collider in previewObject.GetComponentsInChildren<Collider>(true))
        {
            collider.enabled = false;
        }
        foreach (Collider2D collider in previewObject.GetComponentsInChildren<Collider2D>(true))
        {
            collider.enabled = false;
        }
    }

    private void HidePlacementPreview()
    {
        foreach (PlacementPreviewEntry preview in placementPreviews)
        {
            if (preview.previewObject != null && preview.previewObject.activeSelf)
            {
                preview.previewObject.SetActive(false);
            }
        }
    }

    /// <summary>
    /// 地图数量多时，只加载滚动区域附近的预览图；滚出后释放，避免手机内存占用过高。
    /// </summary>
    private void UpdateMapPreviewVisibility()
    {
        if (mapItems == null || mapItems.Count == 0)
        {
            return;
        }

        if (Time.unscaledTime < nextMapPreviewRefreshTime)
        {
            return;
        }
        nextMapPreviewRefreshTime = Time.unscaledTime + 0.2f;

        RectTransform viewport = mapFileScrollRect != null
            ? mapFileScrollRect.viewport
            : null;
        if (viewport == null)
        {
            foreach (MapItem item in mapItems)
            {
                if (item != null)
                {
                    item.ShowPreview();
                }
            }
            return;
        }

        Rect viewRect = viewport.rect;
        viewRect.yMin -= 120f;
        viewRect.yMax += 120f;
        Vector3[] corners = new Vector3[4];

        for (int i = 0; i < mapItems.Count; i++)
        {
            MapItem item = mapItems[i];
            if (item == null)
            {
                continue;
            }

            RectTransform itemRect = item.transform as RectTransform;
            if (itemRect == null)
            {
                continue;
            }

            itemRect.GetWorldCorners(corners);
            float minX = float.MaxValue;
            float maxX = float.MinValue;
            float minY = float.MaxValue;
            float maxY = float.MinValue;
            for (int corner = 0; corner < corners.Length; corner++)
            {
                Vector3 local = viewport.InverseTransformPoint(corners[corner]);
                if (local.x < minX) minX = local.x;
                if (local.x > maxX) maxX = local.x;
                if (local.y < minY) minY = local.y;
                if (local.y > maxY) maxY = local.y;
            }

            bool visible = minX < viewRect.xMax
                && maxX > viewRect.xMin
                && minY < viewRect.yMax
                && maxY > viewRect.yMin;
            if (visible)
            {
                item.ShowPreview();
            }
            else
            {
                item.HidePreview();
            }
        }
    }

    private void DestroyPlacementPreviewObjects()
    {
        foreach (PlacementPreviewEntry preview in placementPreviews)
        {
            if (preview.previewObject == null)
            {
                continue;
            }

            preview.previewObject.SetActive(false);
            Destroy(preview.previewObject);
        }
        placementPreviews.Clear();
    }

    private void ResetPlacementPreview()
    {
        DestroyPlacementPreviewObjects();
        placementPreviewAssetID = int.MinValue;
        placementPreviewBuildingTeam = int.MinValue;
        placementPreviewUnavailable = false;
    }

    private void HandlePaintInput()
    {
        if (mainCamera == null
            || MapEditorSettingsPanel.BlocksMapInput
            || MapElemAnimationViewer.IsVisible
            || (confirmDialog != null && confirmDialog.activeSelf))
        {
            return;
        }

        if (isPickingMapElem)
        {
            HandleMapElemPickerInput();
            return;
        }

        if (ignorePaintUntilMouseUp)
        {
            if (!Input.GetMouseButton(0))
            {
                ignorePaintUntilMouseUp = false;
            }
            return;
        }

        if (IsPointerOverUI())
        {
            return;
        }

        if (Input.GetMouseButton(0))
        {
            Vector2 clickPos = GetMouseClickPos();
            if (!GetGridIDByPos(clickPos, out GridID gridID))
            {
                return;
            }

            BeginElementEditIfNeeded(0);
            BuildPlacementGridIDs(gridID, placementGridBuffer);
            foreach (GridID placementGridID in placementGridBuffer)
            {
                CreateMapElemObj(curAssetID, placementGridID);
            }
        }
        else if (Input.GetMouseButton(1))
        {
            Vector2 clickPos = GetMouseClickPos();
            if (GetGridIDByPos(clickPos, out GridID gridID))
            {
                BeginElementEditIfNeeded(1);
                DelMapElem(GetCurrentMapElemType(), IDToIndex(gridID));
            }
        }
    }

    private void HandleTouchInput()
    {
        if (MapEditorBootstrap.BlocksInput)
        {
            touchPainting = false;
            touchMulti = false;
            touchBlocked = Input.touchCount > 0;
            hasLastPaintGrid = false;
            return;
        }

        if (MapEditorSettingsPanel.BlocksMapInput
            || MapElemAnimationViewer.IsVisible
            || (confirmDialog != null && confirmDialog.activeSelf))
        {
            touchPainting = false;
            touchMulti = false;
            touchBlocked = Input.touchCount > 0;
            hasLastPaintGrid = false;
            return;
        }

        int touchCount = Input.touchCount;
        if (touchCount == 0)
        {
            ResetTouchState();
            return;
        }

        Touch first = Input.GetTouch(0);
        if (isPickingMapElem)
        {
            HandleTouchPicker(first, touchCount);
            return;
        }

        if (touchCount >= 2)
        {
            Touch second = Input.GetTouch(1);
            if (!touchMulti)
            {
                touchMulti = true;
                touchPainting = false;
                hasLastPaintGrid = false;
                lastPinchMidpoint = (first.position + second.position) * 0.5f;
                lastPinchDistance = Vector2.Distance(first.position, second.position);
            }
            else
            {
                Vector2 midpoint = (first.position + second.position) * 0.5f;
                float distance = Vector2.Distance(first.position, second.position);
                HandleTouchPinch(lastPinchMidpoint, midpoint, lastPinchDistance, distance);
                lastPinchMidpoint = midpoint;
                lastPinchDistance = distance;
            }
            return;
        }

        if (touchMulti || touchBlocked)
        {
            if (first.phase == TouchPhase.Ended || first.phase == TouchPhase.Canceled)
            {
                ResetTouchState();
            }
            return;
        }

        switch (first.phase)
        {
            case TouchPhase.Began:
                if (IsTouchOverUi(first.position)
                    || MobileControlsPanel.BlocksPoint(first.position))
                {
                    touchBlocked = true;
                    return;
                }

                touchPainting = true;
                touchPainted = false;
                touchStartPosition = first.position;
                hasLastPaintGrid = false;
                BeginElementEditIfNeeded(deleteMode ? 1 : 0);
                break;

            case TouchPhase.Moved:
            case TouchPhase.Stationary:
                if (!touchPainting)
                {
                    break;
                }

                if (!touchPainted)
                {
                    float threshold = Mathf.Max(12f, Screen.height * 0.015f);
                    if (Vector2.Distance(first.position, touchStartPosition) < threshold)
                    {
                        break;
                    }

                    touchPainted = true;
                    PaintAtScreen(touchStartPosition, true);
                    PaintAtScreen(first.position, false);
                }
                else
                {
                    PaintAtScreen(first.position, false);
                }
                break;

            case TouchPhase.Ended:
                if (touchPainting && !touchPainted)
                {
                    PaintAtScreen(touchStartPosition, true);
                }
                ResetTouchState();
                break;

            case TouchPhase.Canceled:
                ResetTouchState();
                break;
        }
    }

    private void HandleTouchPicker(Touch touch, int touchCount)
    {
        if (touchCount != 1)
        {
            touchBlocked = true;
            return;
        }

        if (touch.phase != TouchPhase.Began)
        {
            return;
        }

        if (IsTouchOverUi(touch.position) || MobileControlsPanel.BlocksPoint(touch.position))
        {
            return;
        }

        if (!GetGridIDByScreenPos(touch.position, out GridID gridID))
        {
            return;
        }

        if (!TryGetMapElemAt(IDToIndex(gridID), out MapElemItem item))
        {
            ShowTips("该格子没有地图元素");
            return;
        }

        SelectMapElem(item.assetID, item.buildingTeam);
        touchBlocked = true;
        ShowTips(string.Format("当前地图元素：{0}", item.assetID));
    }

    private void ResetTouchState()
    {
        touchPainting = false;
        touchMulti = false;
        touchBlocked = false;
        touchPainted = false;
        hasLastPaintGrid = false;
    }

    private void HandleTouchPinch(Vector2 previousMidpoint, Vector2 midpoint, float previousDistance, float distance)
    {
        if (mainCamera == null || previousDistance < 1f || distance < 1f)
        {
            return;
        }

        Vector3 before = ScreenToMapLocal(previousMidpoint);
        mainCamera.orthographicSize = Mathf.Clamp(
            mainCamera.orthographicSize * (previousDistance / distance),
            MinZoomSize,
            Mathf.Max(MaxZoomSize, fitViewSize));
        Vector3 after = ScreenToMapLocal(midpoint);
        mainCamera.transform.position += before - after;
        ClampCameraPosition(mainCamera);
    }

    private void PaintAtScreen(Vector2 screenPosition, bool force)
    {
        if (MapEditorBootstrap.BlocksInput
            || MobileControlsPanel.BlocksPoint(screenPosition))
        {
            hasLastPaintGrid = false;
            return;
        }

        if (IsTouchOverUi(screenPosition))
        {
            hasLastPaintGrid = false;
            return;
        }

        if (!GetGridIDByScreenPos(screenPosition, out GridID gridID))
        {
            hasLastPaintGrid = false;
            return;
        }

        if (fullTypeIndex != 0 && !force)
        {
            lastPaintGrid = gridID;
            hasLastPaintGrid = true;
            return;
        }

        if (!force && hasLastPaintGrid)
        {
            PaintGridLine(lastPaintGrid, gridID);
        }
        else
        {
            PaintGrid(gridID);
        }

        lastPaintGrid = gridID;
        hasLastPaintGrid = true;
    }

    private void PaintGrid(GridID gridID)
    {
        if (deleteMode)
        {
            DelMapElem(GetCurrentMapElemType(), IDToIndex(gridID));
            return;
        }

        CreateMapElemObj(curAssetID, gridID);
    }

    private void PaintGridLine(GridID from, GridID to)
    {
        int x0 = from.x;
        int y0 = from.y;
        int x1 = to.x;
        int y1 = to.y;
        int dx = Mathf.Abs(x1 - x0);
        int dy = Mathf.Abs(y1 - y0);
        int sx = x0 < x1 ? 1 : -1;
        int sy = y0 < y1 ? 1 : -1;
        int error = dx - dy;

        while (true)
        {
            if (x0 != from.x || y0 != from.y)
            {
                PaintGrid(new GridID(x0, y0));
            }

            if (x0 == x1 && y0 == y1)
            {
                break;
            }

            int doubled = 2 * error;
            if (doubled > -dy)
            {
                error -= dy;
                x0 += sx;
            }
            if (doubled < dx)
            {
                error += dx;
                y0 += sy;
            }
        }
    }

    private Vector3 ScreenToMapLocal(Vector2 screenPosition)
    {
        float distance = Mathf.Abs(mainCamera.transform.position.z - rootTransform.position.z);
        Vector3 world = mainCamera.ScreenToWorldPoint(
            new Vector3(screenPosition.x, screenPosition.y, distance));
        return world - rootPos;
    }

    private bool GetGridIDByScreenPos(Vector2 screenPosition, out GridID gridID)
    {
        if (mainCamera == null)
        {
            gridID = new GridID(0, 0);
            return false;
        }

        return GetGridIDByPos(ScreenToMapLocal(screenPosition), out gridID);
    }

    private bool IsTouchOverUi(Vector2 screenPosition)
    {
        if (eventSystem == null)
        {
            return false;
        }

        PointerEventData eventData = new PointerEventData(eventSystem);
        eventData.position = screenPosition;
        uiRaycastResults.Clear();
        eventSystem.RaycastAll(eventData, uiRaycastResults);
        return uiRaycastResults.Count > 0;
    }

    public void ToggleDeleteMode()
    {
        SetDeleteMode(!deleteMode);
    }

    public void SetDeleteMode(bool active)
    {
        if (deleteMode == active)
        {
            return;
        }

        deleteMode = active;
        if (deleteMode && isPickingMapElem)
        {
            SetMapElemPickerActive(false);
        }

        ResetPlacementPreview();
        ShowTips(deleteMode ? "删除模式：单指拖动删除当前类别元素" : "已退出删除模式");
    }

    public void ZoomByStep(float direction)
    {
        if (mainCamera == null)
        {
            return;
        }

        float size = direction > 0f
            ? mainCamera.orthographicSize / ZoomStep
            : mainCamera.orthographicSize * ZoomStep;
        mainCamera.orthographicSize = Mathf.Clamp(
            size,
            MinZoomSize,
            Mathf.Max(MaxZoomSize, fitViewSize));
        ClampCameraPosition(mainCamera);
    }

    public string GetMobileStatusText()
    {
        string mode = deleteMode
            ? "删除模式"
            : (isPickingMapElem ? "选取模式" : "绘制模式");
        return string.Format("{0} · 元素 {1} · 单指绘制，双指缩放/平移", mode, curAssetID);
    }

    public bool IsDeleteMode
    {
        get { return deleteMode; }
    }

    public bool IsPickingMapElem
    {
        get { return isPickingMapElem; }
    }

    public bool IsConfirmOpen
    {
        get { return confirmDialog != null && confirmDialog.activeSelf; }
    }

    public void ToggleMapElemPicker()
    {
        if (!isPickingMapElem)
        {
            deleteMode = false;
        }

        SetMapElemPickerActive(!isPickingMapElem);
        ShowTips(isPickingMapElem ? "元素选取已开启" : "元素选取已取消");
    }

    public void SelectMapElem(int assetID, int buildingTeam)
    {
        curAssetID = assetID;
        curBuildingTeam = buildingTeam;
        deleteMode = false;
        SetMapElemPickerActive(false);
        ResetPlacementPreview();
    }

    private void SetMapElemPickerActive(bool active)
    {
        isPickingMapElem = active;
        if (isPickingMapElem)
        {
            HidePlacementPreview();
        }
        SetMapElemPickerCursor(isPickingMapElem);
        UpdateMapElemPickerButtonState();
    }

    private void SetMapElemPickerCursor(bool active)
    {
        if (!active)
        {
            Cursor.SetCursor(null, Vector2.zero, CursorMode.Auto);
            return;
        }

        if (mapElemPickerCursorTexture == null)
        {
            mapElemPickerCursorTexture = CreateMapElemPickerCursorTexture();
        }

        Cursor.SetCursor(mapElemPickerCursorTexture, new Vector2(3f, 28f), CursorMode.Auto);
    }

    private Texture2D CreateMapElemPickerCursorTexture()
    {
        const int size = 32;
        Texture2D texture = new Texture2D(size, size, TextureFormat.RGBA32, false);
        texture.name = "MapElemPickerCursor";
        texture.filterMode = FilterMode.Point;
        texture.wrapMode = TextureWrapMode.Clamp;

        Color[] pixels = new Color[size * size];
        Color outlineColor = new Color(0.04f, 0.07f, 0.08f, 1f);
        Color bodyColor = new Color(0.86f, 0.96f, 0.96f, 1f);
        Color liquidColor = new Color(0.08f, 0.68f, 0.62f, 1f);

        DrawCursorCircle(pixels, size, 23, 23, 7, outlineColor);
        DrawCursorCircle(pixels, size, 23, 23, 5, bodyColor);
        DrawCursorCircle(pixels, size, 23, 23, 3, liquidColor);

        for (int i = 4; i <= 21; i++)
        {
            for (int offset = -2; offset <= 2; offset++)
            {
                SetCursorPixel(pixels, size, i + offset, i - offset, outlineColor);
            }
        }

        for (int i = 6; i <= 20; i++)
        {
            for (int offset = -1; offset <= 1; offset++)
            {
                SetCursorPixel(pixels, size, i + offset, i - offset, bodyColor);
            }
        }

        for (int i = 2; i <= 6; i++)
        {
            SetCursorPixel(pixels, size, i, i, outlineColor);
            SetCursorPixel(pixels, size, i + 1, i, outlineColor);
        }
        SetCursorPixel(pixels, size, 3, 3, liquidColor);
        SetCursorPixel(pixels, size, 4, 4, liquidColor);

        texture.SetPixels(pixels);
        texture.Apply(false, false);
        return texture;
    }

    private void DrawCursorCircle(Color[] pixels, int size, int centerX, int centerY, int radius, Color color)
    {
        int radiusSquared = radius * radius;
        for (int y = -radius; y <= radius; y++)
        {
            for (int x = -radius; x <= radius; x++)
            {
                if (x * x + y * y <= radiusSquared)
                {
                    SetCursorPixel(pixels, size, centerX + x, centerY + y, color);
                }
            }
        }
    }

    private void SetCursorPixel(Color[] pixels, int size, int x, int y, Color color)
    {
        if (x < 0 || x >= size || y < 0 || y >= size)
        {
            return;
        }

        pixels[y * size + x] = color;
    }

    private void UpdateMapElemPickerButtonState()
    {
        if (pickMapElemButton == null)
        {
            return;
        }

        ColorBlock colors = pickMapElemButtonColors;
        if (isPickingMapElem)
        {
            Color activeColor = new Color(0.1f, 0.48f, 0.44f, 1f);
            colors.normalColor = activeColor;
            colors.highlightedColor = new Color(0.18f, 0.56f, 0.52f, 1f);
            colors.selectedColor = activeColor;
        }
        pickMapElemButton.colors = colors;

        if (pickMapElemButtonText != null)
        {
            pickMapElemButtonText.text = isPickingMapElem ? "取消选取（I）" : "选取元素（I）";
        }
    }

    private void HandleMapElemPickerShortcut()
    {
        if (!Input.GetKeyDown(KeyCode.I))
        {
            return;
        }

        bool blocked = MapEditorSettingsPanel.BlocksMapInput
            || MapElemAnimationViewer.IsVisible
            || MapEditorBootstrap.BlocksInput
            || (confirmDialog != null && confirmDialog.activeSelf)
            || IsInputFieldFocused();
        if (blocked)
        {
            return;
        }

        ToggleMapElemPicker();
    }

    private void HandleMapElemPickerInput()
    {
        if (Input.GetKeyDown(KeyCode.Escape))
        {
            SetMapElemPickerActive(false);
            ShowTips("元素选取已取消");
            return;
        }

        if (!Input.GetMouseButtonDown(0) || IsPointerOverUI())
        {
            return;
        }

        Vector2 clickPos = GetMouseClickPos();
        if (!GetGridIDByPos(clickPos, out GridID gridID))
        {
            return;
        }

        if (!TryGetMapElemAt(IDToIndex(gridID), out MapElemItem item))
        {
            ShowTips("该格子没有地图元素");
            return;
        }

        SelectMapElem(item.assetID, item.buildingTeam);
        ignorePaintUntilMouseUp = true;
        ShowTips(string.Format("当前地图元素：{0}", item.assetID));
    }

    private void BeginElementEditIfNeeded(int mouseButton)
    {
        if (activeElementEditSnapshot != null)
        {
            return;
        }

        activeElementEditSnapshot = CaptureCurrentSnapshot(false);
        activeElementEditMouseButton = mouseButton;
    }

    private void FinalizeElementEditIfNeeded()
    {
        if (activeElementEditSnapshot == null || IsEditPointerActive())
        {
            return;
        }

        MapSnapshot snapshotBeforeEdit = activeElementEditSnapshot;
        activeElementEditSnapshot = null;
        activeElementEditMouseButton = -1;

        MapSnapshot currentSnapshot = CaptureCurrentSnapshot(false);
        if (!snapshotBeforeEdit.HasSameContent(currentSnapshot))
        {
            PushUndoSnapshot(snapshotBeforeEdit);
        }
    }

    private bool IsEditPointerActive()
    {
        if (AndroidSupport.IsAndroid)
        {
            return Input.touchCount > 0;
        }

        return Input.GetMouseButton(activeElementEditMouseButton);
    }

    private void PushUndoSnapshot(MapSnapshot snapshot)
    {
        if (snapshot == null)
        {
            return;
        }

        if (undoHistory.Count >= UndoHistoryLimit)
        {
            undoHistory.RemoveAt(0);
        }
        undoHistory.Add(snapshot);
    }

    private void HandleUndoShortcut()
    {
        bool controlPressed = Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl);
        if (!controlPressed || !Input.GetKeyDown(KeyCode.Z))
        {
            return;
        }

        bool blocked = activeElementEditSnapshot != null
            || Input.GetMouseButton(0)
            || Input.GetMouseButton(1)
            || MapEditorSettingsPanel.BlocksMapInput
            || MapElemAnimationViewer.IsVisible
            || MapEditorBootstrap.BlocksInput
            || (confirmDialog != null && confirmDialog.activeSelf)
            || IsInputFieldFocused();
        if (blocked)
        {
            return;
        }

        UndoLastElementEdit();
    }

    public void UndoLastElementEdit()
    {
        if (activeElementEditSnapshot != null)
        {
            return;
        }

        if (undoHistory.Count == 0)
        {
            ShowTips("没有可撤销的地图元素修改");
            return;
        }

        int lastIndex = undoHistory.Count - 1;
        MapSnapshot snapshot = undoHistory[lastIndex];
        undoHistory.RemoveAt(lastIndex);
        ApplySnapshotToScene(snapshot, false);
        ShowTips("已撤销上一步地图元素修改");
    }

    private bool IsInputFieldFocused()
    {
        if (eventSystem == null || eventSystem.currentSelectedGameObject == null)
        {
            return false;
        }

        return eventSystem.currentSelectedGameObject.GetComponentInParent<InputField>() != null;
    }

    private void ClearUndoHistory()
    {
        undoHistory.Clear();
        activeElementEditSnapshot = null;
        activeElementEditMouseButton = -1;
    }

    public void FullToMap()
    {
        int size = currentCol * currentRow;
        for (int i = 0; i < size; i++)
        {
            CreateMapElemObj(curAssetID, IndexToID(i));
        }
    }

    public void UpdateMapFileScrollView()
    {
        ConfigureMapListLayout();
        foreach (var item in mapItems)
        {
            Destroy(item.gameObject);
        }
        mapItems.Clear();
        MapEditorThumbnailCache.Clear();
        nextMapPreviewRefreshTime = 0f;

        if (string.IsNullOrWhiteSpace(mapDirectory) || !Directory.Exists(mapDirectory))
        {
            ShowTips("地图目录不可用，请先配置外部 Map 目录");
            return;
        }

        DirectoryInfo fdir = new DirectoryInfo(mapDirectory);
        FileInfo[] file = fdir.GetFiles("*.bytes", SearchOption.TopDirectoryOnly);

        if (file.Length != 0)
        {
            foreach (FileInfo f in file)
            {
                MapItem mapItem = Instantiate(mapItemPrefab, mapItemsParentTrans).GetComponent<MapItem>();
                string mapID = Path.GetFileNameWithoutExtension(f.Name);
                mapItem.SetName(mapID);
                mapItem.SetPreview(Path.Combine(mapPreviewDirectory ?? string.Empty, mapID + ".png"));
                mapItem.SetSelectEnable(string.Equals(mapID, currentMapID, System.StringComparison.Ordinal));
                mapItems.Add(mapItem);
            }
            ShowTips(string.Format("找到{0}个地图，地图目录为：{1}", mapItems.Count, mapDirectory));
        }
        else
        {
            ShowTips("未发现地图，地图目录为：" + mapDirectory);
        }
    }

    private void ConfigureMapListLayout()
    {
        if (mapItemsParentTrans == null)
        {
            return;
        }

        VerticalLayoutGroup layout = mapItemsParentTrans.GetComponent<VerticalLayoutGroup>();
        if (layout != null)
        {
            layout.padding = new RectOffset(6, 6, 6, 6);
            layout.spacing = 8f;
            layout.childAlignment = TextAnchor.UpperCenter;
            layout.childControlWidth = true;
            layout.childControlHeight = true;
            layout.childForceExpandWidth = true;
            layout.childForceExpandHeight = false;
        }

        ContentSizeFitter fitter = mapItemsParentTrans.GetComponent<ContentSizeFitter>();
        if (fitter != null)
        {
            fitter.horizontalFit = ContentSizeFitter.FitMode.Unconstrained;
            fitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;
        }
    }

    public void ShowTips(string content)
    {
        if (!tipsObj.activeSelf)
        {
            tipsObj.SetActive(true);
        }
        tipsText.text = content;
        tipsAnimator.Play("tips", 0, 0);
    }

    private string GetMapIDText()
    {
        if (mapIDInputField != null)
        {
            return mapIDInputField.text.Trim();
        }

        return mapNameText == null ? string.Empty : mapNameText.text.Trim();
    }

    private void SetMapIDText(string mapID)
    {
        string value = mapID ?? string.Empty;
        if (mapIDInputField != null)
        {
            mapIDInputField.text = value;
            return;
        }

        if (mapNameText != null)
        {
            mapNameText.text = value;
        }
    }

    public void SaveMap()
    {
        string mapName = GetMapIDText();
        if (mapName == "")
        {
            ShowTips("地图名称不可为空");
            return;
        }

        MapSnapshot snapshot = CaptureCurrentSnapshot(true);
        if (snapshot == null)
        {
            return;
        }

        if (!int.TryParse(mapName, out _))
        {
            ShowTips("地图ID必须为数字");
            return;
        }

        if (string.IsNullOrWhiteSpace(mapDirectory) || !Directory.Exists(mapDirectory))
        {
            ShowTips("地图目录不可用，请先配置外部 Map 目录");
            return;
        }

        SetPendingAction(
            PendingActionType.SaveMap,
            snapshot,
            currentCol,
            currentRow,
            mapName,
            string.Format("是否将当前内容保存到地图ID {0} 中？", mapName));
    }

    private void SavePendingMap()
    {
        if (pendingSnapshot == null || !int.TryParse(pendingMapID, out int mapID))
        {
            ShowTips("待保存的地图数据无效");
            return;
        }

        if (string.IsNullOrWhiteSpace(mapDirectory) || !Directory.Exists(mapDirectory))
        {
            ShowTips("地图目录不可用，请先配置外部 Map 目录");
            return;
        }

        bool success = fileHelper.WriteMapFile(mapDirectory, pendingMapID, pendingSnapshot.ToMapFile(mapID));
        if (success)
        {
            currentMapID = pendingMapID;
            CreatePreviewPng(pendingMapID);
            UpdateMapFileScrollView();
        }
    }

    /// <summary>
    /// 把当前编辑中的地图直接导出为单个 &lt;ID&gt;.bytes，不需要先保存，也不会带上其他地图。
    /// Android 10+ 会写到系统下载目录 Download/MapEditor/。
    /// </summary>
    public void ExportCurrentMap()
    {
        string mapIDText = GetMapIDText();
        if (string.IsNullOrWhiteSpace(mapIDText))
        {
            ShowTips("请先输入或加载地图ID");
            return;
        }

        if (!int.TryParse(mapIDText, out int mapID))
        {
            ShowTips("地图ID必须为数字");
            return;
        }

        MapSnapshot snapshot = CaptureCurrentSnapshot(true);
        if (snapshot == null)
        {
            return;
        }

        try
        {
            MapFile mapFile = snapshot.ToMapFile(mapID);
            byte[] data = fileHelper.Compress(fileHelper.Serialize(mapFile));
            string exportDirectory = Path.Combine(Application.persistentDataPath, "Export");
            Directory.CreateDirectory(exportDirectory);

            string fileName = mapID.ToString() + ".bytes";
            string filePath = Path.Combine(exportDirectory, fileName);
            File.WriteAllBytes(filePath, data);

            string savedPath = AndroidSupport.SaveFileToDownloads(
                filePath,
                fileName,
                "application/octet-stream");
            ShowTips(string.IsNullOrWhiteSpace(savedPath)
                ? "已导出到应用目录: " + filePath
                : "已导出当前地图: " + savedPath);
        }
        catch (System.Exception exception)
        {
            Debug.LogError("导出当前地图失败: " + exception);
            ShowTips("导出当前地图失败: " + exception.Message);
        }
    }

    public void SelectMap(string mapID)
    {
        SetMapIDText(mapID);
        LoadMap(mapID);
    }

    public void GotoMap()
    {
        string mapID = GetMapIDText();
        if (string.IsNullOrWhiteSpace(mapID))
        {
            ShowTips("请输入要跳转的地图ID");
            return;
        }

        int targetIndex = mapItems.FindIndex(item => item != null
            && item.nameText != null
            && string.Equals(item.nameText.text, mapID, System.StringComparison.Ordinal));
        if (targetIndex < 0)
        {
            ShowTips(string.Format("未找到地图ID：{0}", mapID));
            return;
        }

        ScrollToMapItem(targetIndex);
        SelectMap(mapID);
        mapItems[targetIndex].SetSelectEnable(true);
    }

    private void ScrollToMapItem(int targetIndex)
    {
        if (mapFileScrollRect == null && mapItemsParentTrans != null)
        {
            mapFileScrollRect = mapItemsParentTrans.GetComponentInParent<ScrollRect>();
        }

        if (mapFileScrollRect == null || targetIndex < 0 || targetIndex >= mapItems.Count)
        {
            return;
        }

        Canvas.ForceUpdateCanvases();
        mapFileScrollRect.StopMovement();
        mapFileScrollRect.verticalNormalizedPosition = mapItems.Count <= 1
            ? 1f
            : 1f - (float)targetIndex / (mapItems.Count - 1);
    }

    public void LoadMap(string mapID)
    {
        if (mapItems.Count == 0)
        {
            ShowTips("地图不存在");
            return;
        }

        foreach (var item in mapItems)
        {
            item.SetSelectEnable(false);
        }

        MapFile file = fileHelper.ReadMapFile(mapDirectory, mapID);
        if (file == null)
        {
            string fullName = string.Format("{0}/{1}.bytes", mapDirectory, mapID);
            ShowTips(string.Format("读取失败,地图格式损坏! 路径: {0}", fullName));
            return;
        }

        if (!ValidateLoadedMap(file))
        {
            return;
        }

        currentMapID = mapID;
        SetMapIDText(mapID);
        ClearUndoHistory();
        ApplySnapshotToScene(CreateSnapshotFromMapFile(file), true);
        ShowTips(string.Format("读取成功! 地图id:{0}", file.ID));
    }

    public void CreateNewMapWithInputs()
    {
        string mapID = GetMapIDText();
        if (mapID == "")
        {
            ShowTips("地图名称不可为空");
            return;
        }

        if (!TryGetTargetSize(out int targetCol, out int targetRow))
        {
            return;
        }

        if (!int.TryParse(mapID, out _))
        {
            ShowTips("地图ID必须为数字");
            return;
        }

        MapSnapshot snapshot = CaptureCurrentSnapshot(false);
        pendingMapID = mapID;
        if (snapshot.HasAnyContent)
        {
            SetPendingAction(PendingActionType.CreateNewMap, snapshot, targetCol, targetRow, mapID, "当前地图存在内容，确认新建空白地图并清空当前内容吗？");
            return;
        }

        CreateBlankMap(mapID, targetCol, targetRow);
    }

    public void ApplyResizeFromInputs()
    {
        if (!TryGetTargetSize(out int targetCol, out int targetRow))
        {
            return;
        }

        if (targetCol == currentCol && targetRow == currentRow)
        {
            ShowTips("地图尺寸未变化");
            return;
        }

        MapSnapshot snapshot = CaptureCurrentSnapshot(false);
        bool willCrop = targetCol < currentCol || targetRow < currentRow;
        bool cropHasContent = willCrop && SnapshotWillCropContent(snapshot, targetCol, targetRow);
        if (cropHasContent)
        {
            SetPendingAction(PendingActionType.ResizeMap, snapshot, targetCol, targetRow, currentMapID, "缩小地图会裁掉右侧或上侧内容，确认继续吗？");
            return;
        }

        ClearUndoHistory();
        ApplySnapshotToScene(ResizeSnapshot(snapshot, targetCol, targetRow), true);
        ShowTips(string.Format("地图尺寸已更新为 {0} x {1}", targetCol, targetRow));
    }

    public void RequestClearCurrentMap()
    {
        MapSnapshot snapshot = CaptureCurrentSnapshot(false);
        if (snapshot.HasAnyContent)
        {
            SetPendingAction(PendingActionType.ClearMap, snapshot, currentCol, currentRow, currentMapID, "确认清空当前地图内容吗？");
            return;
        }

        ClearUndoHistory();
        CleanAllElems();
        ShowTips("地图已清空");
    }

    public void ConfirmPendingAction()
    {
        switch (pendingActionType)
        {
            case PendingActionType.CreateNewMap:
                CreateBlankMap(pendingMapID, pendingCol, pendingRow);
                break;
            case PendingActionType.ResizeMap:
                ClearUndoHistory();
                ApplySnapshotToScene(ResizeSnapshot(pendingSnapshot, pendingCol, pendingRow), true);
                ShowTips(string.Format("地图尺寸已更新为 {0} x {1}", pendingCol, pendingRow));
                break;
            case PendingActionType.ClearMap:
                ClearUndoHistory();
                CleanAllElems();
                ShowTips("地图已清空");
                break;
            case PendingActionType.SaveMap:
                SavePendingMap();
                break;
        }

        ClearPendingAction();
    }

    public void CancelPendingAction()
    {
        ClearPendingAction();
    }

    public void FitCameraToMap()
    {
        if (mainCamera == null)
        {
            return;
        }

        fitViewSize = CalculateFitOrthographicSize(mainCamera, CameraPadding);
        mainCamera.orthographicSize = Mathf.Clamp(fitViewSize, MinZoomSize, MaxZoomSize);
        CenterCameraOnMap();
    }

    public void CenterCameraOnMap()
    {
        if (mainCamera == null)
        {
            return;
        }

        mainCamera.transform.position = GetCenteredCameraPosition(mainCamera);
        ClampCameraPosition(mainCamera);
    }

    public void OpenMapFolder()
    {
        PngCompressor.Instance.OpenMapFolder();
    }

    public void CreateAllMapFilesPreview()
    {
        StartCoroutine(SaveAllPreviewCoroutine());
    }

    public void CompressPngs()
    {
        PngCompressor.Instance.CompressAllMapPngs();
    }

    public void CleanAllElems()
    {
        SetMapElemPickerActive(false);
        DestroyAllFromDict(floorDict);
        DestroyAllFromDict(wallDict);
        DestroyAllFromDict(brickDict);
        DestroyAllFromDict(moveBrickDict);
        DestroyAllFromDict(composeWallDict);
        DestroyAllFromDict(doorDict);
        DestroyAllFromDict(pinFloorDict);
        DestroyAllFromDict(riverDict);
        DestroyAllFromDict(spikeWallDict);
        DestroyAllFromDict(totemDict);
        DestroyAllFromDict(grassDict);

        foreach (var item in buildingArr)
        {
            if (item != null)
            {
                Destroy(item.data.gameObject);
            }
        }
        buildingArr = new Team[BuildingTeamCount];

        DestroyAllTeams(team1SpawnPosList);
        DestroyAllTeams(team2SpawnPosList);
        DestroyAllTeams(team3SpawnPosList);
    }

    private void DestroyAllFromDict(Dictionary<int, MapElemItem> dict)
    {
        foreach (var item in dict.Values)
        {
            if (item != null)
            {
                Destroy(item.gameObject);
            }
        }
        dict.Clear();
    }

    private void DestroyAllTeams(List<Team> teams)
    {
        foreach (var item in teams)
        {
            if (item != null && item.data != null)
            {
                Destroy(item.data.gameObject);
            }
        }
        teams.Clear();
    }

    private bool ValidateLoadedMap(MapFile file)
    {
        if (file.col < MinCol || file.row < MinRow || file.col > MaxCol || file.row > MaxRow)
        {
            ShowTips(string.Format("地图尺寸不支持: {0} x {1}", file.col, file.row));
            return false;
        }

        int size = file.col * file.row;
        if (!ValidateArrayLength(file.floorArr, size) ||
            !ValidateArrayLength(file.wallArr, size) ||
            !ValidateArrayLength(file.brickArr, size) ||
            !ValidateArrayLength(file.moveBrickArr, size) ||
            !ValidateArrayLength(file.composeWallArr, size) ||
            !ValidateArrayLength(file.doorArr, size))
        {
            ShowTips("地图文件损坏，数组长度异常");
            return false;
        }

        return true;
    }

    private bool ValidateArrayLength(int[] array, int size)
    {
        return array != null && array.Length == size;
    }

    private MapElemType GetCurrentMapElemType()
    {
        if (prefabDict.TryGetValue(curAssetID, out MapElemItem item))
        {
            return item.type;
        }

        if (MapSelector.ActiveCatalog != null
            && MapSelector.ActiveCatalog.TryGet(curAssetID, out MapElemResourceDefinition resource))
        {
            return GetEditorType(resource.type, curBuildingTeam);
        }

        return MapElemType.None;
    }

    private void CreateMapElemObj(int assetID, GridID gridID)
    {
        CreateMapElemObj(assetID, gridID, curBuildingTeam);
    }

    private void CreateMapElemObj(int assetID, GridID gridID, int buildingTeam)
    {
        if (assetID == 0)
        {
            return;
        }

        if (prefabDict.TryGetValue(assetID, out MapElemItem prefab))
        {
            GameObject prefabObject = Instantiate(prefab.gameObject, rootTransform);
            prefabObject.name = prefab.name;
            prefabObject.transform.localPosition = GetPositionByGrid(gridID);
            prefabObject.SetActive(true);

            MapElemItem prefabItem = prefabObject.GetComponent<MapElemItem>();
            CreateMapElem(prefabItem, gridID);
            return;
        }

        if (MapSelector.ActiveCatalog == null
            || !MapSelector.ActiveCatalog.TryGet(assetID, out MapElemResourceDefinition resource))
        {
            Debug.LogWarning("assetID not find in external MapElem:" + assetID);
            return;
        }

        GameObject obj;
        MapElemItem mapElemItem;
        if (mapElemTemplate != null)
        {
            obj = Instantiate(mapElemTemplate.gameObject, rootTransform);
            mapElemItem = obj.GetComponent<MapElemItem>();
        }
        else
        {
            obj = new GameObject("MapElemTemplate");
            obj.transform.SetParent(rootTransform, false);
            GameObject spriteObject = new GameObject("Sprite");
            spriteObject.transform.SetParent(obj.transform, false);
            SpriteRenderer renderer = spriteObject.AddComponent<SpriteRenderer>();
            mapElemItem = obj.AddComponent<MapElemItem>();
            mapElemItem.render = renderer;
        }

        obj.name = "MapElem_" + assetID;
        obj.transform.localPosition = GetPositionByGrid(gridID);
        obj.SetActive(true);
        mapElemItem.InitializeExternal(resource, GetEditorType(resource.type, buildingTeam), buildingTeam);
        if (mapElemItem.render == null || mapElemItem.render.sprite == null)
        {
            Destroy(obj);
            return;
        }

        CreateMapElem(mapElemItem, gridID);
    }

    private MapElemType GetEditorType(MapElemType resourceType, int buildingTeam)
    {
        if ((resourceType == MapElemType.Bun || resourceType == MapElemType.Sculpture)
            && buildingTeam >= 0
            && buildingTeam < BuildingTeamCount)
        {
            switch (buildingTeam)
            {
                case 0:
                    return MapElemType.Building_Team1;
                case 1:
                    return MapElemType.Building_Team2;
                case 2:
                    return MapElemType.Building_Team3;
            }
        }

        return resourceType;
    }

    private void CreateMapElem(MapElemItem item, GridID id)
    {
        int index = IDToIndex(id);
        MapElemType type = item.type;

        DelMapElem(type, index);

        switch (type)
        {
            case MapElemType.Floor:
            case MapElemType.PropFloor:
            case MapElemType.PoisonFloor:
            case MapElemType.SculptureStoneFloor:
                floorDict[index] = item;
                break;
            case MapElemType.Wall:
                wallDict[index] = item;
                break;
            case MapElemType.Brick:
            case MapElemType.WoodenBrick:
                brickDict[index] = item;
                break;
            case MapElemType.MoveBrick:
                moveBrickDict[index] = item;
                break;
            case MapElemType.ComposeWall:
                composeWallDict[index] = item;
                break;
            case MapElemType.River:
                riverDict[index] = item;
                break;
            case MapElemType.SpikeWallUp:
            case MapElemType.SpikeWallLeft:
            case MapElemType.SpikeWallRight:
            case MapElemType.SpikeWallDown:
                spikeWallDict[index] = item;
                break;
            case MapElemType.Totem:
                totemDict[index] = item;
                break;
            case MapElemType.PinFloor:
                pinFloorDict[index] = item;
                break;
            case MapElemType.Door:
                doorDict[index] = item;
                break;
            case MapElemType.Building_Team1:
                SetBuilding(0, index, item);
                break;
            case MapElemType.Building_Team2:
                SetBuilding(1, index, item);
                break;
            case MapElemType.Building_Team3:
                SetBuilding(2, index, item);
                break;
            case MapElemType.Team1Pos:
                team1SpawnPosList.Add(new Team(index, item));
                UpdateTeamIndex(team1SpawnPosList);
                break;
            case MapElemType.Team2Pos:
                team2SpawnPosList.Add(new Team(index, item));
                UpdateTeamIndex(team2SpawnPosList);
                break;
            case MapElemType.Team3Pos:
                team3SpawnPosList.Add(new Team(index, item));
                UpdateTeamIndex(team3SpawnPosList);
                break;
            case MapElemType.Grass:
                grassDict[index] = item;
                break;
        }

        item.SetLayer(GetViewLayer(id));
    }

    private void SetBuilding(int teamIndex, int index, MapElemItem item)
    {
        Team oldBuilding = buildingArr[teamIndex];
        if (oldBuilding != null && oldBuilding.data != null)
        {
            Destroy(oldBuilding.data.gameObject);
        }

        buildingArr[teamIndex] = new Team(index, item);
    }

    private void UpdateTeamIndex(List<Team> teams)
    {
        for (int i = 0; i < teams.Count; i++)
        {
            teams[i].data.SetIndex(i + 1);
        }
    }

    private void DelMapElem(MapElemType type, int index)
    {
        if (type == MapElemType.Brick || type == MapElemType.WoodenBrick || type == MapElemType.Wall || type == MapElemType.MoveBrick ||
            type == MapElemType.ComposeWall || type == MapElemType.Door || type == MapElemType.Grass ||
            type == MapElemType.River || type == MapElemType.SpikeWallLeft || type == MapElemType.SpikeWallRight ||
            type == MapElemType.SpikeWallUp || type == MapElemType.SpikeWallDown || type == MapElemType.PinFloor ||
            type == MapElemType.Totem)
        {
            RemoveDictItem(brickDict, index);
            RemoveDictItem(wallDict, index);
            RemoveDictItem(moveBrickDict, index);
            RemoveDictItem(composeWallDict, index);
            RemoveDictItem(spikeWallDict, index);
            RemoveDictItem(totemDict, index);
            RemoveDictItem(pinFloorDict, index);
            RemoveDictItem(riverDict, index);
            RemoveDictItem(doorDict, index);
            RemoveDictItem(grassDict, index);
        }
        else if (type == MapElemType.Floor || type == MapElemType.PropFloor || type == MapElemType.PoisonFloor
            || type == MapElemType.SculptureStoneFloor)
        {
            RemoveDictItem(floorDict, index);
        }
        else if (type == MapElemType.Team1Pos)
        {
            RemoveTeam(team1SpawnPosList, index);
        }
        else if (type == MapElemType.Team2Pos)
        {
            RemoveTeam(team2SpawnPosList, index);
        }
        else if (type == MapElemType.Team3Pos)
        {
            RemoveTeam(team3SpawnPosList, index);
        }
        else if (type == MapElemType.Building_Team1)
        {
            RemoveBuilding(0, index);
        }
        else if (type == MapElemType.Building_Team2)
        {
            RemoveBuilding(1, index);
        }
        else if (type == MapElemType.Building_Team3)
        {
            RemoveBuilding(2, index);
        }
    }

    private void RemoveDictItem(Dictionary<int, MapElemItem> dict, int index)
    {
        if (!dict.ContainsKey(index))
        {
            return;
        }

        Destroy(dict[index].gameObject);
        dict.Remove(index);
    }

    private void RemoveTeam(List<Team> teams, int index)
    {
        Team team = GetTeam(teams, index);
        if (team == null)
        {
            return;
        }

        Destroy(team.data.gameObject);
        teams.Remove(team);
        UpdateTeamIndex(teams);
    }

    private void RemoveBuilding(int teamIndex, int index)
    {
        Team team = buildingArr[teamIndex];
        if (team == null || team.id != index)
        {
            return;
        }

        Destroy(team.data.gameObject);
        buildingArr[teamIndex] = null;
    }

    private Team GetTeam(List<Team> teams, int index)
    {
        foreach (var item in teams)
        {
            if (item.id == index)
            {
                return item;
            }
        }
        return null;
    }

    private bool TryGetMapElemAt(int index, out MapElemItem selected)
    {
        selected = null;
        int selectedSortingOrder = int.MinValue;

        foreach (Team building in buildingArr)
        {
            if (building != null && building.id == index)
            {
                ConsiderMapElemCandidate(building.data, ref selected, ref selectedSortingOrder);
            }
        }

        Team team1Spawn = GetTeam(team1SpawnPosList, index);
        Team team2Spawn = GetTeam(team2SpawnPosList, index);
        Team team3Spawn = GetTeam(team3SpawnPosList, index);
        ConsiderMapElemCandidate(team1Spawn == null ? null : team1Spawn.data, ref selected, ref selectedSortingOrder);
        ConsiderMapElemCandidate(team2Spawn == null ? null : team2Spawn.data, ref selected, ref selectedSortingOrder);
        ConsiderMapElemCandidate(team3Spawn == null ? null : team3Spawn.data, ref selected, ref selectedSortingOrder);

        ConsiderMapElemCandidate(totemDict, index, ref selected, ref selectedSortingOrder);
        ConsiderMapElemCandidate(grassDict, index, ref selected, ref selectedSortingOrder);
        ConsiderMapElemCandidate(doorDict, index, ref selected, ref selectedSortingOrder);
        ConsiderMapElemCandidate(composeWallDict, index, ref selected, ref selectedSortingOrder);
        ConsiderMapElemCandidate(moveBrickDict, index, ref selected, ref selectedSortingOrder);
        ConsiderMapElemCandidate(brickDict, index, ref selected, ref selectedSortingOrder);
        ConsiderMapElemCandidate(wallDict, index, ref selected, ref selectedSortingOrder);
        ConsiderMapElemCandidate(spikeWallDict, index, ref selected, ref selectedSortingOrder);
        ConsiderMapElemCandidate(riverDict, index, ref selected, ref selectedSortingOrder);
        ConsiderMapElemCandidate(pinFloorDict, index, ref selected, ref selectedSortingOrder);
        ConsiderMapElemCandidate(floorDict, index, ref selected, ref selectedSortingOrder);
        return selected != null;
    }

    private void ConsiderMapElemCandidate(
        Dictionary<int, MapElemItem> source,
        int index,
        ref MapElemItem selected,
        ref int selectedSortingOrder)
    {
        if (source.TryGetValue(index, out MapElemItem candidate))
        {
            ConsiderMapElemCandidate(candidate, ref selected, ref selectedSortingOrder);
        }
    }

    private void ConsiderMapElemCandidate(
        MapElemItem candidate,
        ref MapElemItem selected,
        ref int selectedSortingOrder)
    {
        if (candidate == null)
        {
            return;
        }

        int sortingOrder = candidate.render == null ? int.MinValue : candidate.render.sortingOrder;
        if (selected == null || sortingOrder > selectedSortingOrder)
        {
            selected = candidate;
            selectedSortingOrder = sortingOrder;
        }
    }

    private Vector3 GetMouseClickPos()
    {
        return ScreenToMapLocal(Input.mousePosition);
    }

    private bool PosInMapBounds(Vector3 pos)
    {
        return pos.x >= bounds.minX && pos.x <= bounds.maxX && pos.y >= bounds.minY && pos.y <= bounds.maxY;
    }

    public int GetViewLayer(GridID id)
    {
        return gridsLayer[id.x, id.y];
    }

    private bool GetGridIDByPos(Vector2 pos, out GridID id)
    {
        id = new GridID(0, 0);
        if (!PosInMapBounds(pos))
        {
            return false;
        }

        id.x = (int)pos.x / gridSize;
        id.y = (int)pos.y / gridSize;
        return id.x >= 0 && id.x < currentCol && id.y >= 0 && id.y < currentRow;
    }

    private Vector2 GetPositionByGrid(GridID id)
    {
        return new Vector2(id.x * gridSize, id.y * gridSize);
    }

    private int IDToIndex(GridID id)
    {
        return id.y * currentCol + id.x;
    }

    private GridID IndexToID(int index)
    {
        return new GridID(index % currentCol, index / currentCol);
    }

    private bool CheckMap()
    {
        if (team1SpawnPosList.Count == 0)
        {
            ShowTips("没有设置队伍1的出生点");
            return false;
        }

        if (team2SpawnPosList.Count == 0)
        {
            ShowTips("没有设置队伍2的出生点");
            return false;
        }

        if (buildingArr[0] == null && buildingArr[1] != null)
        {
            ShowTips("没有设置队伍1的建筑");
            return false;
        }

        if (buildingArr[1] == null && buildingArr[0] != null)
        {
            ShowTips("没有设置队伍2的建筑");
            return false;
        }

        return true;
    }

    private MapFile CreateMapFile(string name, bool validateMap)
    {
        if (validateMap && !CheckMap())
        {
            return null;
        }

        if (!int.TryParse(name, out int id))
        {
            ShowTips("地图ID必须为数字");
            return null;
        }

        return CaptureCurrentSnapshot(validateMap).ToMapFile(id);
    }

    private MapSnapshot CaptureCurrentSnapshot(bool validateMap)
    {
        if (validateMap && !CheckMap())
        {
            return null;
        }

        MapSnapshot snapshot = new MapSnapshot(currentCol, currentRow);
        FillSnapshotLayer(snapshot.floorArr, floorDict);
        FillSnapshotLayer(snapshot.wallArr, wallDict);
        FillSnapshotLayer(snapshot.brickArr, brickDict);
        FillSnapshotLayer(snapshot.moveBrickArr, moveBrickDict);
        FillSnapshotLayer(snapshot.composeWallArr, composeWallDict);
        FillSnapshotLayer(snapshot.doorArr, doorDict);
        FillSnapshotLayer(snapshot.riverArr, riverDict);
        FillSnapshotLayer(snapshot.pinFloorArr, pinFloorDict);
        FillSnapshotLayer(snapshot.spikeWallArr, spikeWallDict);
        FillSnapshotLayer(snapshot.grassArr, grassDict);
        FillSnapshotLayer(snapshot.totemArr, totemDict);

        foreach (var item in team1SpawnPosList)
        {
            snapshot.team1SpawnPos.Add(item.id);
        }

        foreach (var item in team2SpawnPosList)
        {
            snapshot.team2SpawnPos.Add(item.id);
        }

        foreach (var item in team3SpawnPosList)
        {
            snapshot.team3SpawnPos.Add(item.id);
        }

        for (int i = 0; i < buildingArr.Length; i++)
        {
            if (buildingArr[i] == null)
            {
                continue;
            }

            snapshot.buildingInfoArr[i] = new BuildingInfo
            {
                team = i,
                assetID = buildingArr[i].data.assetID,
                posIndex = buildingArr[i].id
            };
        }

        return snapshot;
    }

    private void FillSnapshotLayer(int[] target, Dictionary<int, MapElemItem> source)
    {
        foreach (var kv in source)
        {
            if (kv.Key >= 0 && kv.Key < target.Length)
            {
                target[kv.Key] = kv.Value.assetID;
            }
        }
    }

    private MapSnapshot CreateSnapshotFromMapFile(MapFile file)
    {
        MapSnapshot snapshot = new MapSnapshot(file.col, file.row);
        CopyArray(file.floorArr, snapshot.floorArr);
        CopyArray(file.wallArr, snapshot.wallArr);
        CopyArray(file.brickArr, snapshot.brickArr);
        CopyArray(file.moveBrickArr, snapshot.moveBrickArr);
        CopyArray(file.composeWallArr, snapshot.composeWallArr);
        CopyArray(file.doorArr, snapshot.doorArr);
        CopyArray(file.riverArr, snapshot.riverArr);
        CopyArray(file.pinFloorArr, snapshot.pinFloorArr);
        CopyArray(file.spikeWallArr, snapshot.spikeWallArr);
        CopyArray(file.grassArr, snapshot.grassArr);
        CopyArray(file.totemArr, snapshot.totemArr);

        if (file.team1SpawnPos != null)
        {
            snapshot.team1SpawnPos.AddRange(file.team1SpawnPos);
        }

        if (file.team2SpawnPos != null)
        {
            snapshot.team2SpawnPos.AddRange(file.team2SpawnPos);
        }

        if (file.team3SpawnPos != null)
        {
            snapshot.team3SpawnPos.AddRange(file.team3SpawnPos);
        }

        if (file.buildingInfoArr != null)
        {
            for (int i = 0; i < file.buildingInfoArr.Length; i++)
            {
                BuildingInfo src = file.buildingInfoArr[i];
                if (src == null || src.team < 0 || src.team >= BuildingTeamCount)
                {
                    continue;
                }

                snapshot.buildingInfoArr[src.team] = new BuildingInfo
                {
                    team = src.team,
                    assetID = src.assetID,
                    posIndex = src.posIndex
                };
            }
        }

        return snapshot;
    }

    private void CopyArray(int[] source, int[] target)
    {
        if (source == null)
        {
            return;
        }

        int copyLength = Mathf.Min(source.Length, target.Length);
        System.Array.Copy(source, target, copyLength);
    }

    private bool SnapshotWillCropContent(MapSnapshot snapshot, int targetCol, int targetRow)
    {
        if (snapshot == null)
        {
            return false;
        }

        for (int y = 0; y < snapshot.row; y++)
        {
            for (int x = 0; x < snapshot.col; x++)
            {
                if (x < targetCol && y < targetRow)
                {
                    continue;
                }

                int index = y * snapshot.col + x;
                if (snapshot.HasContentAt(index))
                {
                    return true;
                }
            }
        }

        return false;
    }

    private MapSnapshot ResizeSnapshot(MapSnapshot source, int targetCol, int targetRow)
    {
        MapSnapshot resized = new MapSnapshot(targetCol, targetRow);
        if (source == null)
        {
            return resized;
        }

        int copyCol = Mathf.Min(source.col, targetCol);
        int copyRow = Mathf.Min(source.row, targetRow);
        for (int y = 0; y < copyRow; y++)
        {
            for (int x = 0; x < copyCol; x++)
            {
                int oldIndex = y * source.col + x;
                int newIndex = y * targetCol + x;
                resized.floorArr[newIndex] = source.floorArr[oldIndex];
                resized.wallArr[newIndex] = source.wallArr[oldIndex];
                resized.brickArr[newIndex] = source.brickArr[oldIndex];
                resized.moveBrickArr[newIndex] = source.moveBrickArr[oldIndex];
                resized.composeWallArr[newIndex] = source.composeWallArr[oldIndex];
                resized.doorArr[newIndex] = source.doorArr[oldIndex];
                resized.riverArr[newIndex] = source.riverArr[oldIndex];
                resized.pinFloorArr[newIndex] = source.pinFloorArr[oldIndex];
                resized.spikeWallArr[newIndex] = source.spikeWallArr[oldIndex];
                resized.grassArr[newIndex] = source.grassArr[oldIndex];
                resized.totemArr[newIndex] = source.totemArr[oldIndex];
            }
        }

        CopyTeamPositions(resized.team1SpawnPos, source.team1SpawnPos, source.col, targetCol, targetRow);
        CopyTeamPositions(resized.team2SpawnPos, source.team2SpawnPos, source.col, targetCol, targetRow);
        CopyTeamPositions(resized.team3SpawnPos, source.team3SpawnPos, source.col, targetCol, targetRow);

        int buildingCount = Mathf.Min(source.buildingInfoArr.Length, resized.buildingInfoArr.Length);
        for (int i = 0; i < buildingCount; i++)
        {
            BuildingInfo building = source.buildingInfoArr[i];
            if (building == null)
            {
                continue;
            }

            GridID oldID = new GridID(building.posIndex % source.col, building.posIndex / source.col);
            if (oldID.x >= targetCol || oldID.y >= targetRow)
            {
                continue;
            }

            resized.buildingInfoArr[i] = new BuildingInfo
            {
                team = building.team,
                assetID = building.assetID,
                posIndex = oldID.y * targetCol + oldID.x
            };
        }

        return resized;
    }

    private void CopyTeamPositions(List<int> target, List<int> source, int sourceCol, int targetCol, int targetRow)
    {
        foreach (var index in source)
        {
            GridID id = new GridID(index % sourceCol, index / sourceCol);
            if (id.x >= targetCol || id.y >= targetRow)
            {
                continue;
            }

            target.Add(id.y * targetCol + id.x);
        }
    }

    private void CreateBlankMap(string mapID, int col, int row)
    {
        ClearUndoHistory();
        currentMapID = mapID;
        SetMapIDText(mapID);
        MapSnapshot snapshot = new MapSnapshot(col, row);
        ApplySnapshotToScene(snapshot, true);
        ShowTips(string.Format("已新建空白地图 {0}，尺寸 {1} x {2}", mapID, col, row));
    }

    private void ApplySnapshotToScene(MapSnapshot snapshot, bool resetView)
    {
        if (snapshot == null)
        {
            return;
        }

        CleanAllElems();
        ApplyMapSizeInternal(snapshot.col, snapshot.row);

        CreateLayerObjects(snapshot.floorArr);
        CreateLayerObjects(snapshot.wallArr);
        CreateLayerObjects(snapshot.brickArr);
        CreateLayerObjects(snapshot.moveBrickArr);
        CreateLayerObjects(snapshot.composeWallArr);
        CreateLayerObjects(snapshot.doorArr);
        CreateLayerObjects(snapshot.pinFloorArr);
        CreateLayerObjects(snapshot.spikeWallArr);
        CreateLayerObjects(snapshot.riverArr);
        CreateLayerObjects(snapshot.grassArr);
        CreateLayerObjects(snapshot.totemArr);

        for (int i = 0; i < snapshot.buildingInfoArr.Length; i++)
        {
            BuildingInfo building = snapshot.buildingInfoArr[i];
            if (building != null
                && building.team >= 0
                && building.team < BuildingTeamCount)
            {
                CreateMapElemObj(
                    building.assetID,
                    IndexToID(building.posIndex),
                    building.team);
            }
        }

        foreach (var index in snapshot.team1SpawnPos)
        {
            CreateMapElemObj(1, IndexToID(index));
        }

        foreach (var index in snapshot.team2SpawnPos)
        {
            CreateMapElemObj(2, IndexToID(index));
        }

        foreach (var index in snapshot.team3SpawnPos)
        {
            CreateMapElemObj(3, IndexToID(index));
        }

        SyncRuntimeFields();
        if (resetView)
        {
            FitCameraToMap();
        }
        UpdatePreviewCamera();
    }

    private void CreateLayerObjects(int[] layer)
    {
        if (layer == null)
        {
            return;
        }

        for (int i = 0; i < layer.Length; i++)
        {
            CreateMapElemObj(layer[i], IndexToID(i));
        }
    }

    private void ApplyMapSizeInternal(int col, int row)
    {
        currentCol = col;
        currentRow = row;
        gridsLayer = new int[currentCol, currentRow];
        for (int x = 0; x < currentCol; x++)
        {
            for (int y = 0; y < currentRow; y++)
            {
                gridsLayer[x, y] = (currentRow - y) * 100 + currentCol - x;
            }
        }

        bounds = new MapBounds
        {
            minX = 0,
            minY = 0,
            maxX = currentCol * gridSize,
            maxY = currentRow * gridSize,
        };

        if (editorLine != null)
        {
            editorLine.SetMapSize(currentCol, currentRow);
        }
    }

    private void SyncRuntimeFields()
    {
        if (widthInputField != null)
        {
            widthInputField.text = currentCol.ToString();
        }

        if (heightInputField != null)
        {
            heightInputField.text = currentRow.ToString();
        }

        if (currentSizeText != null)
        {
            currentSizeText.text = string.Format("当前尺寸: {0} x {1}", currentCol, currentRow);
        }
    }

    private bool TryGetTargetSize(out int col, out int row)
    {
        col = 0;
        row = 0;

        if (widthInputField == null || heightInputField == null)
        {
            ShowTips("尺寸输入框未初始化");
            return false;
        }

        if (!int.TryParse(widthInputField.text, out col) || !int.TryParse(heightInputField.text, out row))
        {
            ShowTips("请输入合法的地图尺寸");
            return false;
        }

        if (col < MinCol || row < MinRow || col > MaxCol || row > MaxRow)
        {
            ShowTips(string.Format("地图尺寸范围为 {0}x{1} 到 {2}x{3}", MinCol, MinRow, MaxCol, MaxRow));
            return false;
        }

        return true;
    }

    private void SetPendingAction(PendingActionType type, MapSnapshot snapshot, int col, int row, string mapID, string message)
    {
        pendingActionType = type;
        pendingSnapshot = snapshot;
        pendingCol = col;
        pendingRow = row;
        pendingMapID = mapID;
        if (confirmDialog != null)
        {
            confirmDialog.SetActive(true);
        }
        if (confirmMessageText != null)
        {
            confirmMessageText.text = message;
        }
    }

    private void ClearPendingAction()
    {
        pendingActionType = PendingActionType.None;
        pendingSnapshot = null;
        pendingCol = 0;
        pendingRow = 0;
        pendingMapID = string.Empty;
        if (confirmDialog != null)
        {
            confirmDialog.SetActive(false);
        }
    }

    private IEnumerator SaveAllPreviewCoroutine()
    {
        if (string.IsNullOrWhiteSpace(mapDirectory) || string.IsNullOrWhiteSpace(mapPreviewDirectory))
        {
            ShowTips("请先配置 Map 和 MapPreview 目录");
            yield break;
        }

        foreach (var item in mapItems)
        {
            string mapName = item.nameText.text;
            LoadMap(mapName);
            yield return new WaitForSeconds(0.5f);

            bool success = fileHelper.WriteMapFile(mapDirectory, mapName, CreateMapFile(mapName, true));
            if (success)
            {
                CreatePreviewPng(mapName);
            }
        }

        ShowTips("保存地图数：" + mapItems.Count);
    }

    private void CreatePreviewPng(string filename)
    {
        if (previewCamera == null)
        {
            return;
        }

        UpdatePreviewCamera();
        bool restoreRuntimeLine = editorLine != null && editorLine.IsRuntimeLinesVisible();
        RenderTexture rt = new RenderTexture(PreviewWidth, PreviewHeight, 16);
        Texture2D texture = null;

        try
        {
            if (editorLine != null)
            {
                editorLine.SetRuntimeLinesVisible(false);
            }

            previewCamera.targetTexture = rt;
            previewCamera.Render();

            RenderTexture.active = rt;
            texture = new Texture2D(PreviewWidth, PreviewHeight, TextureFormat.RGBA32, false);
            texture.ReadPixels(new Rect(0, 0, texture.width, texture.height), 0, 0);
            texture.Apply();

            byte[] pngBytes = EncodeTrimmedPreview(texture);
            if (string.IsNullOrWhiteSpace(mapPreviewDirectory))
            {
                ShowTips("MapPreview 目录不可用");
                return;
            }

            if (!Directory.Exists(mapPreviewDirectory))
            {
                Directory.CreateDirectory(mapPreviewDirectory);
            }

            string path = Path.Combine(mapPreviewDirectory, filename + ".png");
            File.WriteAllBytes(path, pngBytes);

            if (!AndroidSupport.IsAndroid)
            {
                PngCompressor.Instance.CompressPngByPath(path);
            }
        }
        finally
        {
            RenderTexture.active = null;
            previewCamera.targetTexture = null;

            if (editorLine != null)
            {
                editorLine.SetRuntimeLinesVisible(restoreRuntimeLine);
            }

            rt.Release();
            Destroy(rt);

            if (texture != null)
            {
                Destroy(texture);
            }
        }
    }

    private void UpdatePreviewCamera()
    {
        if (previewCamera == null)
        {
            return;
        }

        previewCamera.orthographic = true;
        previewCamera.orthographicSize = Mathf.Clamp(CalculateFitOrthographicSize(previewCamera, PreviewPadding), MinZoomSize, MaxZoomSize);
        Vector3 pos = GetMapCenterWorld();
        pos.z = previewCamera.transform.position.z;
        previewCamera.transform.position = pos;
    }

    private byte[] EncodeTrimmedPreview(Texture2D source)
    {
        if (source == null)
        {
            return new byte[0];
        }

        RectInt contentRect = FindOpaqueBounds(source);
        if (contentRect.width <= 0 || contentRect.height <= 0)
        {
            return source.EncodeToPNG();
        }

        RectInt paddedRect = ExpandRect(contentRect, PreviewPaddingPixels, source.width, source.height);
        if (paddedRect.width >= source.width && paddedRect.height >= source.height)
        {
            return source.EncodeToPNG();
        }

        Texture2D trimmed = new Texture2D(paddedRect.width, paddedRect.height, TextureFormat.RGBA32, false);
        trimmed.SetPixels(source.GetPixels(paddedRect.x, paddedRect.y, paddedRect.width, paddedRect.height));
        trimmed.Apply();
        byte[] pngBytes = trimmed.EncodeToPNG();
        Destroy(trimmed);
        return pngBytes;
    }

    private RectInt FindOpaqueBounds(Texture2D texture)
    {
        Color32[] pixels = texture.GetPixels32();
        int minX = texture.width;
        int minY = texture.height;
        int maxX = -1;
        int maxY = -1;

        for (int y = 0; y < texture.height; y++)
        {
            int rowOffset = y * texture.width;
            for (int x = 0; x < texture.width; x++)
            {
                if (pixels[rowOffset + x].a == 0)
                {
                    continue;
                }

                if (x < minX)
                {
                    minX = x;
                }
                if (x > maxX)
                {
                    maxX = x;
                }
                if (y < minY)
                {
                    minY = y;
                }
                if (y > maxY)
                {
                    maxY = y;
                }
            }
        }

        if (maxX < minX || maxY < minY)
        {
            return new RectInt(0, 0, texture.width, texture.height);
        }

        return new RectInt(minX, minY, maxX - minX + 1, maxY - minY + 1);
    }

    private RectInt ExpandRect(RectInt rect, int paddingPixels, int maxWidth, int maxHeight)
    {
        int minX = Mathf.Max(0, rect.xMin - paddingPixels);
        int minY = Mathf.Max(0, rect.yMin - paddingPixels);
        int maxX = Mathf.Min(maxWidth, rect.xMax + paddingPixels);
        int maxY = Mathf.Min(maxHeight, rect.yMax + paddingPixels);
        return new RectInt(minX, minY, maxX - minX, maxY - minY);
    }

    private void ZoomCamera(float scrollDelta)
    {
        if (mainCamera == null)
        {
            return;
        }

        Vector3 beforeZoom = GetWorldPointOnMapPlane();
        if (scrollDelta > 0)
        {
            mainCamera.orthographicSize /= ZoomStep;
        }
        else
        {
            mainCamera.orthographicSize *= ZoomStep;
        }

        mainCamera.orthographicSize = Mathf.Clamp(mainCamera.orthographicSize, MinZoomSize, Mathf.Max(MaxZoomSize, fitViewSize));

        Vector3 afterZoom = GetWorldPointOnMapPlane();
        Vector3 delta = beforeZoom - afterZoom;
        mainCamera.transform.position += delta;
        ClampCameraPosition(mainCamera);
    }

    private Vector3 GetWorldPointOnMapPlane()
    {
        Vector3 mousePosition = Input.mousePosition;
        float distance = Mathf.Abs(mainCamera.transform.position.z - rootTransform.position.z);
        return mainCamera.ScreenToWorldPoint(new Vector3(mousePosition.x, mousePosition.y, distance));
    }

    private void ClampCameraPosition(Camera cameraToClamp)
    {
        if (cameraToClamp == null)
        {
            return;
        }

        float aspect = cameraToClamp.aspect;
        float halfHeight = cameraToClamp.orthographicSize;
        float halfWidth = halfHeight * aspect;
        float mapWidth = currentCol * gridSize;
        float mapHeight = currentRow * gridSize;

        float minX = rootTransform.position.x - CameraLoosePadding;
        float minY = rootTransform.position.y - CameraLoosePadding;
        float maxX = minX + mapWidth;
        float maxY = minY + mapHeight;

        float clampMinX = minX - MaxLooseDistance + halfWidth;
        float clampMaxX = maxX + MaxLooseDistance - halfWidth;
        float clampMinY = minY - MaxLooseDistance + halfHeight;
        float clampMaxY = maxY + MaxLooseDistance - halfHeight;

        Vector3 pos = cameraToClamp.transform.position;
        if (clampMinX > clampMaxX)
        {
            pos.x = GetCenteredCameraPosition(cameraToClamp).x;
        }
        else
        {
            pos.x = Mathf.Clamp(pos.x, clampMinX, clampMaxX);
        }

        if (clampMinY > clampMaxY)
        {
            pos.y = (minY + maxY) * 0.5f;
        }
        else
        {
            pos.y = Mathf.Clamp(pos.y, clampMinY, clampMaxY);
        }

        cameraToClamp.transform.position = pos;
    }

    private float CalculateFitOrthographicSize(Camera targetCamera, float padding)
    {
        if (targetCamera == null)
        {
            return MinZoomSize;
        }

        float mapWidth = currentCol * gridSize + padding * 2f;
        float mapHeight = currentRow * gridSize + padding * 2f;

        float visibleWidth = Screen.width;
        float visibleHeight = Screen.height;
        if (canvasRect != null)
        {
            visibleWidth -= GetControlPanelScreenWidth();
        }

        if (visibleWidth <= 0)
        {
            visibleWidth = Screen.width;
        }
        if (visibleHeight <= 0)
        {
            visibleHeight = Screen.height;
        }

        float aspect = visibleWidth / Mathf.Max(visibleHeight, 1f);
        float widthBased = mapWidth / (2f * Mathf.Max(aspect, 0.01f));
        float heightBased = mapHeight / 2f;
        return Mathf.Max(widthBased, heightBased);
    }

    private float GetControlPanelScreenWidth()
    {
        if (canvasRect == null)
        {
            return 0f;
        }

        Camera uiCamera = cachedCanvas != null && cachedCanvas.renderMode != RenderMode.ScreenSpaceOverlay ? cachedCanvas.worldCamera : null;
        float minX = float.MaxValue;
        float maxX = float.MinValue;
        int childCount = canvasRect.childCount;
        Vector3[] corners = new Vector3[4];

        for (int i = 0; i < childCount; i++)
        {
            RectTransform child = canvasRect.GetChild(i) as RectTransform;
            if (child == null || !child.gameObject.activeInHierarchy)
            {
                continue;
            }

            if (tipsObj != null && child.gameObject == tipsObj)
            {
                continue;
            }

            if (confirmDialog != null && child.gameObject == confirmDialog)
            {
                continue;
            }

            child.GetWorldCorners(corners);
            Vector2 min = RectTransformUtility.WorldToScreenPoint(uiCamera, corners[0]);
            Vector2 max = RectTransformUtility.WorldToScreenPoint(uiCamera, corners[3]);
            if (max.x <= Screen.width * 0.5f)
            {
                continue;
            }

            minX = Mathf.Min(minX, min.x);
            maxX = Mathf.Max(maxX, max.x);
        }

        if (minX == float.MaxValue || maxX <= minX)
        {
            return 0f;
        }

        return Mathf.Clamp(maxX - minX, 0f, Screen.width);
    }

    private Vector3 GetMapCenterWorld()
    {
        return rootTransform.position + new Vector3((currentCol - 1) * 0.5f, (currentRow - 1) * 0.5f, 0f);
    }

    private Vector3 GetCenteredCameraPosition(Camera targetCamera)
    {
        Vector3 targetPosition = GetMapCenterWorld();
        targetPosition.x += GetVisibleAreaHorizontalOffset(targetCamera);
        targetPosition.z = targetCamera.transform.position.z;
        return targetPosition;
    }

    // 将地图中心对齐到扣除右侧控制区后的可见区域中心。
    private float GetVisibleAreaHorizontalOffset(Camera targetCamera)
    {
        if (targetCamera == null || targetCamera != mainCamera || Screen.width <= 0)
        {
            return 0f;
        }

        float controlWidth = GetControlPanelScreenWidth();
        if (controlWidth <= 0f)
        {
            return 0f;
        }

        float worldViewWidth = targetCamera.orthographicSize * targetCamera.aspect * 2f;
        float normalizedWidth = Mathf.Clamp01(controlWidth / Screen.width);
        return worldViewWidth * normalizedWidth * 0.5f;
    }

    private bool IsPointerOverUI()
    {
        if (eventSystem == null)
        {
            return false;
        }

        if (Input.touchCount > 0)
        {
            return eventSystem.IsPointerOverGameObject(Input.GetTouch(0).fingerId);
        }

        return eventSystem.IsPointerOverGameObject();
    }

    private T FindChildComponent<T>(RectTransform parent, string childName) where T : Component
    {
        if (parent == null)
        {
            return null;
        }

        Transform child = parent.Find(childName);
        if (child == null)
        {
            return null;
        }

        return child.GetComponent<T>();
    }

    private Button FindChildButton(RectTransform parent, string childName)
    {
        return FindChildComponent<Button>(parent, childName);
    }

    private GameObject FindChildGameObject(RectTransform parent, string childName)
    {
        if (parent == null)
        {
            return null;
        }

        Transform child = parent.Find(childName);
        return child == null ? null : child.gameObject;
    }

}

public class MapBounds
{
    public float minX;
    public float maxX;
    public float minY;
    public float maxY;
}

public class MapSnapshot
{
    public readonly int col;
    public readonly int row;

    public readonly int[] floorArr;
    public readonly int[] wallArr;
    public readonly int[] brickArr;
    public readonly int[] moveBrickArr;
    public readonly int[] composeWallArr;
    public readonly int[] doorArr;
    public readonly int[] riverArr;
    public readonly int[] pinFloorArr;
    public readonly int[] spikeWallArr;
    public readonly int[] grassArr;
    public readonly int[] totemArr;

    public List<int> team1SpawnPos = new List<int>();
    public List<int> team2SpawnPos = new List<int>();
    public List<int> team3SpawnPos = new List<int>();
    public BuildingInfo[] buildingInfoArr = new BuildingInfo[3];

    public MapSnapshot(int col, int row)
    {
        this.col = col;
        this.row = row;
        int size = col * row;
        floorArr = new int[size];
        wallArr = new int[size];
        brickArr = new int[size];
        moveBrickArr = new int[size];
        composeWallArr = new int[size];
        doorArr = new int[size];
        riverArr = new int[size];
        pinFloorArr = new int[size];
        spikeWallArr = new int[size];
        grassArr = new int[size];
        totemArr = new int[size];
    }

    public bool HasAnyContent
    {
        get
        {
            if (team1SpawnPos.Count > 0 || team2SpawnPos.Count > 0 || team3SpawnPos.Count > 0)
            {
                return true;
            }

            for (int i = 0; i < buildingInfoArr.Length; i++)
            {
                if (buildingInfoArr[i] != null)
                {
                    return true;
                }
            }

            for (int i = 0; i < floorArr.Length; i++)
            {
                if (HasContentAt(i))
                {
                    return true;
                }
            }

            return false;
        }
    }

    public bool HasContentAt(int index)
    {
        return floorArr[index] != 0 ||
               wallArr[index] != 0 ||
               brickArr[index] != 0 ||
               moveBrickArr[index] != 0 ||
               composeWallArr[index] != 0 ||
               doorArr[index] != 0 ||
               riverArr[index] != 0 ||
               pinFloorArr[index] != 0 ||
               spikeWallArr[index] != 0 ||
               grassArr[index] != 0 ||
               totemArr[index] != 0;
    }

    public bool HasSameContent(MapSnapshot other)
    {
        return other != null
            && col == other.col
            && row == other.row
            && ArraysEqual(floorArr, other.floorArr)
            && ArraysEqual(wallArr, other.wallArr)
            && ArraysEqual(brickArr, other.brickArr)
            && ArraysEqual(moveBrickArr, other.moveBrickArr)
            && ArraysEqual(composeWallArr, other.composeWallArr)
            && ArraysEqual(doorArr, other.doorArr)
            && ArraysEqual(riverArr, other.riverArr)
            && ArraysEqual(pinFloorArr, other.pinFloorArr)
            && ArraysEqual(spikeWallArr, other.spikeWallArr)
            && ArraysEqual(grassArr, other.grassArr)
            && ArraysEqual(totemArr, other.totemArr)
            && ListsEqual(team1SpawnPos, other.team1SpawnPos)
            && ListsEqual(team2SpawnPos, other.team2SpawnPos)
            && ListsEqual(team3SpawnPos, other.team3SpawnPos)
            && BuildingsEqual(buildingInfoArr, other.buildingInfoArr);
    }

    private static bool ArraysEqual(int[] first, int[] second)
    {
        if (first == null || second == null || first.Length != second.Length)
        {
            return first == second;
        }

        for (int i = 0; i < first.Length; i++)
        {
            if (first[i] != second[i])
            {
                return false;
            }
        }

        return true;
    }

    private static bool ListsEqual(List<int> first, List<int> second)
    {
        if (first == null || second == null || first.Count != second.Count)
        {
            return first == second;
        }

        for (int i = 0; i < first.Count; i++)
        {
            if (first[i] != second[i])
            {
                return false;
            }
        }

        return true;
    }

    private static bool BuildingsEqual(BuildingInfo[] first, BuildingInfo[] second)
    {
        if (first == null || second == null || first.Length != second.Length)
        {
            return first == second;
        }

        for (int i = 0; i < first.Length; i++)
        {
            BuildingInfo firstBuilding = first[i];
            BuildingInfo secondBuilding = second[i];
            if (firstBuilding == null || secondBuilding == null)
            {
                if (firstBuilding != secondBuilding)
                {
                    return false;
                }
                continue;
            }

            if (firstBuilding.team != secondBuilding.team
                || firstBuilding.assetID != secondBuilding.assetID
                || firstBuilding.posIndex != secondBuilding.posIndex)
            {
                return false;
            }
        }

        return true;
    }

    public MapFile ToMapFile(int id)
    {
        return new MapFile
        {
            ID = id,
            col = col,
            row = row,
            team1SpawnPos = new List<int>(team1SpawnPos),
            team2SpawnPos = new List<int>(team2SpawnPos),
            team3SpawnPos = new List<int>(team3SpawnPos),
            floorArr = (int[])floorArr.Clone(),
            wallArr = (int[])wallArr.Clone(),
            brickArr = (int[])brickArr.Clone(),
            moveBrickArr = (int[])moveBrickArr.Clone(),
            composeWallArr = (int[])composeWallArr.Clone(),
            doorArr = (int[])doorArr.Clone(),
            buildingInfoArr = CloneBuildingInfo(),
            grassArr = (int[])grassArr.Clone(),
            riverArr = (int[])riverArr.Clone(),
            pinFloorArr = (int[])pinFloorArr.Clone(),
            spikeWallArr = (int[])spikeWallArr.Clone(),
            totemArr = (int[])totemArr.Clone()
        };
    }

    private BuildingInfo[] CloneBuildingInfo()
    {
        List<BuildingInfo> result = new List<BuildingInfo>(buildingInfoArr.Length);
        for (int i = 0; i < buildingInfoArr.Length; i++)
        {
            if (buildingInfoArr[i] == null)
            {
                continue;
            }

            result.Add(new BuildingInfo
            {
                team = buildingInfoArr[i].team,
                assetID = buildingInfoArr[i].assetID,
                posIndex = buildingInfoArr[i].posIndex
            });
        }

        return result.ToArray();
    }
}
