using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

/// <summary>
/// 地图列表缩略图缓存。按引用计数释放纹理，避免手机上一次性解码 425 张预览图导致内存爆炸。
/// </summary>
public static class MapEditorThumbnailCache
{
    private sealed class Entry
    {
        public Sprite sprite;
        public int references;
    }

    private static readonly Dictionary<string, Entry> Cache =
        new Dictionary<string, Entry>(StringComparer.OrdinalIgnoreCase);

    public static Sprite Acquire(string path, int maxSize)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return null;
        }

        string key = BuildKey(path, maxSize);
        if (Cache.TryGetValue(key, out Entry entry))
        {
            entry.references++;
            return entry.sprite;
        }

        Sprite sprite = LoadSprite(path, maxSize);
        Cache[key] = new Entry
        {
            sprite = sprite,
            references = 1,
        };
        return sprite;
    }

    public static void Release(string path, int maxSize)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        string key = BuildKey(path, maxSize);
        if (!Cache.TryGetValue(key, out Entry entry))
        {
            return;
        }

        entry.references--;
        if (entry.references > 0)
        {
            return;
        }

        Cache.Remove(key);
        DestroySprite(entry.sprite);
    }

    public static void Clear()
    {
        foreach (Entry entry in Cache.Values)
        {
            DestroySprite(entry.sprite);
        }
        Cache.Clear();
    }

    private static string BuildKey(string path, int maxSize)
    {
        return path + "|" + maxSize.ToString();
    }

    private static Sprite LoadSprite(string path, int maxSize)
    {
        if (!File.Exists(path))
        {
            return null;
        }

        Texture2D texture = null;
        try
        {
            byte[] data = File.ReadAllBytes(path);
            Texture2D source = new Texture2D(2, 2, TextureFormat.RGBA32, false);
            if (!source.LoadImage(data, false))
            {
                UnityEngine.Object.Destroy(source);
                return null;
            }

            texture = source;
            if (maxSize > 0 && Mathf.Max(source.width, source.height) > maxSize)
            {
                float scale = (float)maxSize / Mathf.Max(source.width, source.height);
                int width = Mathf.Max(1, Mathf.RoundToInt(source.width * scale));
                int height = Mathf.Max(1, Mathf.RoundToInt(source.height * scale));

                RenderTexture temporary = RenderTexture.GetTemporary(
                    width,
                    height,
                    0,
                    RenderTextureFormat.ARGB32);
                RenderTexture previous = RenderTexture.active;
                try
                {
                    Graphics.Blit(source, temporary);
                    RenderTexture.active = temporary;
                    Texture2D scaled = new Texture2D(width, height, TextureFormat.RGBA32, false);
                    scaled.ReadPixels(new Rect(0f, 0f, width, height), 0, 0);
                    scaled.Apply(false, false);
                    texture = scaled;
                }
                finally
                {
                    RenderTexture.active = previous;
                    RenderTexture.ReleaseTemporary(temporary);
                }

                UnityEngine.Object.Destroy(source);
            }

            Sprite sprite = Sprite.Create(
                texture,
                new Rect(0f, 0f, texture.width, texture.height),
                new Vector2(0.5f, 0.5f),
                100f);
            sprite.name = Path.GetFileNameWithoutExtension(path) + "_thumb";
            texture = null;
            return sprite;
        }
        catch (Exception exception)
        {
            Debug.LogWarning("加载地图缩略图失败: " + path + ", " + exception.Message);
            if (texture != null)
            {
                UnityEngine.Object.Destroy(texture);
            }
            return null;
        }
    }

    private static void DestroySprite(Sprite sprite)
    {
        if (sprite == null)
        {
            return;
        }

        Texture texture = sprite.texture;
        UnityEngine.Object.Destroy(sprite);
        if (texture != null)
        {
            UnityEngine.Object.Destroy(texture);
        }
    }
}
