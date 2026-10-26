using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class MapSelector : MonoBehaviour
{
    public static MapElemCatalog ActiveCatalog { get; private set; }
    public Dropdown mapDropdown;
    public Transform root;
    public GameObject uiItem;

    private readonly MapElemCatalog catalog = new MapElemCatalog();
    private readonly List<GameObject> objects = new List<GameObject>();
    private readonly List<MapElemCategory> categories = new List<MapElemCategory>();
    private bool refreshing;

    private void Awake()
    {
        ActiveCatalog = catalog;
        if (mapDropdown != null)
        {
            mapDropdown.onValueChanged.RemoveAllListeners();
            mapDropdown.onValueChanged.AddListener(OnCategoryChanged);
        }

        MapEditorSettingsStore.Changed += OnSettingsChanged;
        RefreshCatalog();
    }

    private void OnDestroy()
    {
        MapEditorSettingsStore.Changed -= OnSettingsChanged;
        if (ActiveCatalog == catalog)
        {
            ActiveCatalog = null;
        }
    }

    public void RefreshCatalog()
    {
        MapElemAnimationViewer.Close();
        DestroyAllObjects();
        categories.Clear();
        if (mapDropdown == null || uiItem == null || root == null)
        {
            return;
        }

        MapEditorSettingsData settings = MapEditorSettingsStore.Current;
        bool externalCatalogLoaded = catalog.Reload(settings.mapElemDirectory, out string message);
        categories.Add(new MapElemCategory("出生点", MapElemType.Team1Pos, -1, true));
        if (externalCatalogLoaded)
        {
            foreach (MapElemType type in catalog.GetTypes())
            {
                if (type == MapElemType.Bun)
                {
                    categories.Add(new MapElemCategory("Bun", type, -2));
                }
                else if (type == MapElemType.Sculpture)
                {
                    categories.Add(new MapElemCategory("Sculpture", type, -2));
                }
                else
                {
                    categories.Add(new MapElemCategory(type.ToString(), type, -1));
                }
            }
        }

        refreshing = true;
        mapDropdown.ClearOptions();
        List<string> labels = new List<string>();
        foreach (MapElemCategory category in categories)
        {
            labels.Add(category.label);
        }
        mapDropdown.AddOptions(labels);
        mapDropdown.SetValueWithoutNotify(0);
        refreshing = false;
        CreateUIItems(0);
        ViewManager.Instance?.ShowTips(message);
    }

    private void OnApplicationQuit()
    {
        MapEditorTextureLoader.ReleaseAll();
    }

    private void OnSettingsChanged()
    {
        RefreshCatalog();
    }

    private void OnCategoryChanged(int value)
    {
        if (refreshing)
        {
            return;
        }

        CreateUIItems(value);
    }

    private void CreateUIItems(int categoryIndex)
    {
        DestroyAllObjects();
        if (categoryIndex < 0 || categoryIndex >= categories.Count)
        {
            return;
        }

        MapElemCategory category = categories[categoryIndex];
        if (category.isSpawnCategory)
        {
            CreateUIItem(1, MapElemType.Team1Pos, -1, null, Resources.Load<Sprite>("Sprites/1"));
            CreateUIItem(2, MapElemType.Team2Pos, -1, null, Resources.Load<Sprite>("Sprites/2"));
            CreateUIItem(3, MapElemType.Team3Pos, -1, null, Resources.Load<Sprite>("Sprites/3"));
            return;
        }

        foreach (MapElemResourceDefinition resource in catalog.GetResources(category.type))
        {
            int buildingTeam = category.buildingTeam;
            if ((category.type == MapElemType.Bun || category.type == MapElemType.Sculpture)
                && buildingTeam == -2)
            {
                buildingTeam = GetBuildingTeam(resource.assetID);
            }
            CreateUIItem(resource.assetID, category.type, buildingTeam, resource, resource.LoadPreviewSprite());
        }
    }

    private int GetBuildingTeam(int assetID)
    {
        if (assetID == 4501 || assetID == 4503)
        {
            return 0;
        }

        if (assetID == 4502 || assetID == 4504)
        {
            return 1;
        }

        if (assetID == 4505 || assetID == 4506)
        {
            return 2;
        }

        return -1;
    }

    private void CreateUIItem(
        int assetID,
        MapElemType type,
        int buildingTeam,
        MapElemResourceDefinition resource,
        Sprite sprite)
    {
        GameObject itemObject = Instantiate(uiItem, root);
        UIElemItem item = itemObject.GetComponent<UIElemItem>();
        if (item == null)
        {
            Destroy(itemObject);
            return;
        }

        item.SetResource(assetID, type, buildingTeam, resource, sprite);
        objects.Add(itemObject);
    }

    private void DestroyAllObjects()
    {
        foreach (GameObject item in objects)
        {
            if (item != null)
            {
                Destroy(item);
            }
        }
        objects.Clear();
    }

    private sealed class MapElemCategory
    {
        public readonly string label;
        public readonly MapElemType type;
        public readonly int buildingTeam;
        public readonly bool isSpawnCategory;

        public MapElemCategory(string label, MapElemType type, int buildingTeam, bool isSpawnCategory = false)
        {
            this.label = label;
            this.type = type;
            this.buildingTeam = buildingTeam;
            this.isSpawnCategory = isSpawnCategory;
        }
    }
}
