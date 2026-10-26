using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

public class MapItem : MonoBehaviour, IPointerClickHandler
{
    private const float ItemHeight = 92f;
    private const int PreviewThumbnailSize = 320;

    public Text nameText;
    public GameObject isSelectObj;
    public Image previewImage;

    private string previewPath;
    private bool previewLoaded;

    private void Awake()
    {
        ConfigureLayout();
    }

    private void OnDestroy()
    {
        HidePreview();
    }

    public void SetName(string name)
    {
        if (nameText != null)
        {
            nameText.text = name;
        }
        if (isSelectObj != null)
        {
            isSelectObj.SetActive(false);
        }
    }

    public void SetPreview(string path)
    {
        if (previewImage == null)
        {
            previewImage = GetComponentInChildren<Image>();
        }

        if (previewImage == null)
        {
            return;
        }

        HidePreview();
        previewPath = path;
        previewImage.preserveAspect = true;
        previewImage.sprite = null;
        previewImage.color = new Color(1f, 1f, 1f, 0f);
    }

    /// <summary>
    /// 由 ViewManager 根据滚动可视区域调用，避免一次性解码全部分辨率预览图。
    /// </summary>
    public void ShowPreview()
    {
        if (previewLoaded || previewImage == null || string.IsNullOrWhiteSpace(previewPath))
        {
            return;
        }

        Sprite preview = MapEditorThumbnailCache.Acquire(previewPath, PreviewThumbnailSize);
        previewImage.sprite = preview;
        previewImage.color = preview == null ? new Color(1f, 1f, 1f, 0f) : Color.white;
        previewLoaded = true;
    }

    public void HidePreview()
    {
        if (!previewLoaded)
        {
            return;
        }

        MapEditorThumbnailCache.Release(previewPath, PreviewThumbnailSize);
        previewLoaded = false;
        if (previewImage != null)
        {
            previewImage.sprite = null;
            previewImage.color = new Color(1f, 1f, 1f, 0f);
        }
    }

    public void SetSelectEnable(bool enable)
    {
        if (isSelectObj != null)
        {
            isSelectObj.SetActive(enable);
        }
    }

    public void OnPointerClick(PointerEventData eventData)
    {
        if (ViewManager.Instance != null)
        {
            ViewManager.Instance.SelectMap(nameText.text);
        }

        if (isSelectObj != null)
        {
            isSelectObj.SetActive(true);
        }
    }

    private void ConfigureLayout()
    {
        RectTransform rootRect = transform as RectTransform;
        if (rootRect != null)
        {
            rootRect.sizeDelta = new Vector2(280f, ItemHeight);
        }

        LayoutElement layoutElement = GetComponent<LayoutElement>();
        if (layoutElement == null)
        {
            layoutElement = gameObject.AddComponent<LayoutElement>();
        }
        layoutElement.minHeight = 84f;
        layoutElement.preferredHeight = ItemHeight;
        layoutElement.preferredWidth = 280f;
        layoutElement.flexibleWidth = 1f;

        RectTransform backgroundRect = nameText != null ? nameText.transform.parent as RectTransform : null;
        if (backgroundRect == null)
        {
            return;
        }

        backgroundRect.anchorMin = Vector2.zero;
        backgroundRect.anchorMax = Vector2.one;
        backgroundRect.offsetMin = new Vector2(4f, 4f);
        backgroundRect.offsetMax = new Vector2(-4f, -4f);

        Image backgroundImage = backgroundRect.GetComponent<Image>();
        if (backgroundImage != null)
        {
            backgroundImage.color = new Color(0.94f, 0.95f, 0.96f, 0.98f);
            backgroundImage.raycastTarget = true;
        }

        RectTransform nameRect = nameText.rectTransform;
        nameRect.anchorMin = new Vector2(0f, 0f);
        nameRect.anchorMax = new Vector2(0f, 1f);
        nameRect.pivot = new Vector2(0.5f, 0.5f);
        nameRect.anchoredPosition = new Vector2(34f, 0f);
        nameRect.sizeDelta = new Vector2(56f, -16f);
        nameText.alignment = TextAnchor.MiddleCenter;
        nameText.fontSize = 18;
        nameText.resizeTextForBestFit = true;
        nameText.resizeTextMinSize = 12;
        nameText.resizeTextMaxSize = 18;
        nameText.color = new Color(0.16f, 0.18f, 0.2f, 1f);
        nameText.raycastTarget = false;

        Transform previewTransform = backgroundRect.Find("Preview");
        if (previewTransform == null)
        {
            GameObject previewObject = new GameObject("Preview", typeof(RectTransform), typeof(CanvasRenderer), typeof(Image));
            previewObject.layer = gameObject.layer;
            previewTransform = previewObject.transform;
            previewTransform.SetParent(backgroundRect, false);
        }

        previewImage = previewTransform.GetComponent<Image>();
        RectTransform previewRect = previewTransform as RectTransform;
        previewRect.anchorMin = Vector2.zero;
        previewRect.anchorMax = Vector2.one;
        previewRect.offsetMin = new Vector2(66f, 8f);
        previewRect.offsetMax = new Vector2(-6f, -8f);
        previewImage.preserveAspect = true;
        previewImage.raycastTarget = true;
        previewTransform.SetSiblingIndex(1);

        if (isSelectObj != null)
        {
            RectTransform selectRect = isSelectObj.transform as RectTransform;
            selectRect.anchorMin = Vector2.zero;
            selectRect.anchorMax = Vector2.one;
            selectRect.offsetMin = Vector2.zero;
            selectRect.offsetMax = Vector2.zero;
            Image selectImage = isSelectObj.GetComponent<Image>();
            if (selectImage != null)
            {
                selectImage.color = new Color(0.2f, 0.65f, 0.35f, 0.25f);
                selectImage.raycastTarget = false;
            }
            isSelectObj.transform.SetAsLastSibling();
        }
    }
}
