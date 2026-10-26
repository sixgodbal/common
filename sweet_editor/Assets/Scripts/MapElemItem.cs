using System;
using System.Collections.Generic;
using UnityEngine;

public class MapElemItem : MonoBehaviour
{
    private const int HighestSortingOrder = short.MaxValue;

    public int assetID;
    public MapElemType type;
    public MapElemType visualType;
    public SpriteRenderer render;
    public int buildingTeam = -1;

    private MapElemResourceDefinition resourceDefinition;
    private string currentState;
    private List<Sprite> currentSprites;
    private MapElemClipDefinition currentClip;
    private int currentFrame;
    private float animationTime;
    private bool animationPlaying;

    private void Awake()
    {
        if (render == null)
        {
            render = GetComponentInChildren<SpriteRenderer>(true);
        }

        if (render == null)
        {
            Debug.LogError("地图元素 SpriteRenderer 为空");
        }
    }

    public void InitializeExternal(MapElemResourceDefinition definition, MapElemType editorType, int team)
    {
        resourceDefinition = definition;
        assetID = definition != null ? definition.assetID : assetID;
        visualType = definition != null ? definition.type : editorType;
        type = editorType;
        buildingTeam = team;

        if (definition == null || definition.visual == null || render == null)
        {
            return;
        }

        MapElemVisualDefinition visual = definition.visual;
        render.transform.localPosition = visual.localPosition;
        render.transform.localScale = visual.localScale;
        render.gameObject.SetActive(visual.rendererActive);
        render.enabled = visual.rendererEnabled;
        render.sortingOrder = visual.sortingOrder;
        PlayState("idle");
    }

    public void SetLayer(int layer)
    {
        if (render == null)
        {
            return;
        }

        if (type == MapElemType.Team1Pos
            || type == MapElemType.Team2Pos
            || type == MapElemType.Team3Pos)
        {
            render.sortingOrder = HighestSortingOrder;
        }
        else if (type != MapElemType.Floor)
        {
            render.sortingOrder += layer;
        }
    }

    public virtual void SetIndex(int index)
    {
    }

    public bool PlayState(string state)
    {
        if (resourceDefinition == null || render == null || string.IsNullOrWhiteSpace(state))
        {
            return false;
        }

        if (!resourceDefinition.visual.TryGetClip(state, out MapElemClipDefinition clip))
        {
            clip = new MapElemClipDefinition
            {
                state = state,
                resourceState = state,
                isSequence = true,
                hasTiming = false,
            };
        }

        IReadOnlyList<string> files = resourceDefinition.GetStateFiles(clip.resourceState);
        if (files.Count == 0)
        {
            return false;
        }

        currentSprites = new List<Sprite>(files.Count);
        foreach (string file in files)
        {
            Sprite sprite = MapEditorTextureLoader.LoadSprite(file);
            if (sprite != null)
            {
                currentSprites.Add(sprite);
            }
        }

        if (currentSprites.Count == 0)
        {
            return false;
        }

        currentState = state;
        currentClip = clip;
        currentFrame = 0;
        animationTime = 0f;
        animationPlaying = currentSprites.Count > 1
            && currentClip.isSequence
            && currentClip.hasTiming
            && currentClip.duration > 0f;
        render.sprite = currentSprites[0];
        return true;
    }

    private void Update()
    {
        if (!animationPlaying || currentSprites == null || currentSprites.Count <= 1 || currentClip == null)
        {
            return;
        }

        float frameDuration = Mathf.Max(currentClip.duration / currentSprites.Count, 0.01f);
        animationTime += Time.unscaledDeltaTime;
        while (animationTime >= frameDuration)
        {
            animationTime -= frameDuration;
            currentFrame++;
            if (currentFrame < currentSprites.Count)
            {
                render.sprite = currentSprites[currentFrame];
                continue;
            }

            if (currentClip.loop)
            {
                currentFrame = 0;
                render.sprite = currentSprites[currentFrame];
                continue;
            }

            animationPlaying = false;
            if (!string.IsNullOrWhiteSpace(currentClip.completionState))
            {
                PlayState(currentClip.completionState);
            }
            else
            {
                currentFrame = currentSprites.Count - 1;
                render.sprite = currentSprites[currentFrame];
            }
            break;
        }
    }

    public MapElemResourceDefinition GetResourceDefinition()
    {
        return resourceDefinition;
    }

    public string GetCurrentState()
    {
        return currentState;
    }
}

public enum MapElemType
{
    None,
    Team1Pos,
    Team2Pos,

    Floor,
    Wall,
    Brick,
    MoveBrick,
    ComposeWall,
    Door,
    Building_Team1,
    Building_Team2,
    Grass,
    Yhc,
    PinFloor,
    River,
    PropFloor,
    SpikeWallUp,
    SpikeWallDown,
    SpikeWallLeft,
    SpikeWallRight,
    Totem,
    Bun,
    Sculpture,
    WoodenBrick,
    PoisonFloor,
    Building_Team3,
    Team3Pos,
    SculptureStoneFloor,
}
