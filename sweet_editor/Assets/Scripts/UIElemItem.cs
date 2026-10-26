using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

public class UIElemItem : MonoBehaviour, IPointerClickHandler
{
    public int assetID;
    public MapElemType type;
    public int buildingTeam = -1;

    private MapElemResourceDefinition resourceDefinition;

    public void OnPointerClick(PointerEventData eventData)
    {
        if (ViewManager.Instance != null)
        {
            ViewManager.Instance.SelectMapElem(assetID, buildingTeam);
        }

        if (eventData.clickCount >= 2 && resourceDefinition != null)
        {
            MapElemAnimationViewer.Show(resourceDefinition);
            eventData.Use();
        }
    }

    public void SetResource(
        int assetID,
        MapElemType type,
        int buildingTeam,
        MapElemResourceDefinition resource,
        Sprite preview)
    {
        this.assetID = assetID;
        this.type = type;
        this.buildingTeam = buildingTeam;
        resourceDefinition = resource;
        SetImg(assetID, preview);
    }

    public void SetImg(int assetID, Sprite newSprite)
    {
        this.assetID = assetID;
        Image image = GetComponentInChildren<Image>();
        if (image == null)
        {
            return;
        }

        image.sprite = newSprite;
        image.preserveAspect = true;
        if (newSprite == null)
        {
            image.color = new Color(1f, 1f, 1f, 0f);
            return;
        }

        image.color = Color.white;
        image.SetNativeSize();
        RectTransform imageTransform = image.rectTransform;
        Vector2 size = imageTransform.sizeDelta;
        float scale = Mathf.Min(100f / Mathf.Max(size.x, 1f), 50f / Mathf.Max(size.y, 1f), 1f);
        imageTransform.sizeDelta = size * scale;
    }
}
