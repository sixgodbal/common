using System.Collections.Generic;
using UnityEngine;

namespace Candy
{
    public class EditorLine : MonoBehaviour
    {
        private const string RuntimeLineRootName = "RuntimeEditorLineRoot";

        public Color sideColor = Color.white;
        public Color insideColor = Color.red;

        public float width = 1.0f;
        public float height = 1.0f;

        public float mapHeight = 13;
        public float mapWidth = 15;
        public Transform mapTransform;

        [Header("运行时辅助线")]
        public bool showRuntimeLine = true;
        public float runtimeLineWidth = 0.04f;
        public int runtimeSortingOrder = 10000;
        public float runtimeZOffset = 0f;

        private readonly List<LineRenderer> runtimeLines = new List<LineRenderer>();
        private Transform runtimeLineRoot;
        private Material runtimeLineMaterial;
        private bool runtimeLineVisible = true;

        public void SetMapSize(int col, int row)
        {
            mapWidth = col;
            mapHeight = row;
            RefreshRuntimeLines();
        }

        public void SetRuntimeLinesVisible(bool visible)
        {
            runtimeLineVisible = visible;
            if (runtimeLineRoot != null)
            {
                runtimeLineRoot.gameObject.SetActive(showRuntimeLine && runtimeLineVisible);
            }
        }

        public bool IsRuntimeLinesVisible()
        {
            return showRuntimeLine && runtimeLineVisible && runtimeLineRoot != null && runtimeLineRoot.gameObject.activeSelf;
        }

        private void OnEnable()
        {
            RefreshRuntimeLines();
        }

        private void Start()
        {
            RefreshRuntimeLines();
        }

        private void OnDestroy()
        {
            if (runtimeLineMaterial != null)
            {
                Destroy(runtimeLineMaterial);
                runtimeLineMaterial = null;
            }
        }

        private void OnDrawGizmos()
        {
            if (width <= 1e-1f || height <= 1e-1f || mapTransform == null)
            {
                return;
            }

            Vector3 startPos = mapTransform.position - new Vector3(width / 2f, height / 2f, 0f);
            Gizmos.color = insideColor;

            for (float y = 0f; y < mapHeight; y += height)
            {
                Gizmos.DrawLine(new Vector3(0f, y, -1f) + startPos, new Vector3(mapWidth, y, -1f) + startPos);
            }

            for (float x = 0f; x < mapWidth; x += width)
            {
                Gizmos.DrawLine(new Vector3(x, 0f, -1f) + startPos, new Vector3(x, mapHeight, -1f) + startPos);
            }

            Gizmos.color = sideColor;
            Gizmos.DrawLine(new Vector3(0f, 0f, -1f) + startPos, new Vector3(mapWidth, 0f, -1f) + startPos);
            Gizmos.DrawLine(new Vector3(mapWidth, 0f, -1f) + startPos, new Vector3(mapWidth, mapHeight, -1f) + startPos);
            Gizmos.DrawLine(new Vector3(mapWidth, mapHeight, -1f) + startPos, new Vector3(0f, mapHeight, -1f) + startPos);
            Gizmos.DrawLine(new Vector3(0f, mapHeight, -1f) + startPos, new Vector3(0f, 0f, -1f) + startPos);
        }

        private void RefreshRuntimeLines()
        {
            if (!Application.isPlaying)
            {
                return;
            }

            EnsureRuntimeLineRoot();
            if (runtimeLineRoot == null)
            {
                return;
            }

            if (!showRuntimeLine || width <= 1e-1f || height <= 1e-1f)
            {
                runtimeLineRoot.gameObject.SetActive(false);
                SetRuntimeLineCount(0);
                return;
            }

            Vector3 startPos = new Vector3(-width / 2f, -height / 2f, runtimeZOffset);
            int lineCount = GetInsideLineCount(mapHeight, height) + GetInsideLineCount(mapWidth, width) + 4;
            SetRuntimeLineCount(lineCount);

            int lineIndex = 0;
            for (float y = height; y < mapHeight; y += height)
            {
                SetLineRenderer(
                    runtimeLines[lineIndex++],
                    insideColor,
                    new Vector3(0f, y, runtimeZOffset) + startPos,
                    new Vector3(mapWidth, y, runtimeZOffset) + startPos);
            }

            for (float x = width; x < mapWidth; x += width)
            {
                SetLineRenderer(
                    runtimeLines[lineIndex++],
                    insideColor,
                    new Vector3(x, 0f, runtimeZOffset) + startPos,
                    new Vector3(x, mapHeight, runtimeZOffset) + startPos);
            }

            SetLineRenderer(
                runtimeLines[lineIndex++],
                sideColor,
                new Vector3(0f, 0f, runtimeZOffset) + startPos,
                new Vector3(mapWidth, 0f, runtimeZOffset) + startPos);
            SetLineRenderer(
                runtimeLines[lineIndex++],
                sideColor,
                new Vector3(mapWidth, 0f, runtimeZOffset) + startPos,
                new Vector3(mapWidth, mapHeight, runtimeZOffset) + startPos);
            SetLineRenderer(
                runtimeLines[lineIndex++],
                sideColor,
                new Vector3(mapWidth, mapHeight, runtimeZOffset) + startPos,
                new Vector3(0f, mapHeight, runtimeZOffset) + startPos);
            SetLineRenderer(
                runtimeLines[lineIndex],
                sideColor,
                new Vector3(0f, mapHeight, runtimeZOffset) + startPos,
                new Vector3(0f, 0f, runtimeZOffset) + startPos);

            runtimeLineRoot.gameObject.SetActive(runtimeLineVisible);
        }

        private int GetInsideLineCount(float length, float step)
        {
            int count = 0;
            for (float position = step; position < length; position += step)
            {
                count++;
            }

            return count;
        }

        private void EnsureRuntimeLineRoot()
        {
            if (runtimeLineRoot != null)
            {
                return;
            }

            Transform lineParent = mapTransform != null ? mapTransform : transform;
            Transform existingRoot = lineParent.Find(RuntimeLineRootName);
            if (existingRoot != null)
            {
                runtimeLineRoot = existingRoot;
                return;
            }

            GameObject rootObj = new GameObject(RuntimeLineRootName);
            runtimeLineRoot = rootObj.transform;
            runtimeLineRoot.SetParent(lineParent, false);
            runtimeLineRoot.localPosition = Vector3.zero;
            runtimeLineRoot.localRotation = Quaternion.identity;
            runtimeLineRoot.localScale = Vector3.one;
        }

        private void SetRuntimeLineCount(int targetCount)
        {
            while (runtimeLines.Count < targetCount)
            {
                runtimeLines.Add(CreateRuntimeLineRenderer(runtimeLines.Count));
            }

            for (int i = 0; i < runtimeLines.Count; i++)
            {
                if (runtimeLines[i] != null)
                {
                    runtimeLines[i].gameObject.SetActive(i < targetCount);
                }
            }
        }

        private LineRenderer CreateRuntimeLineRenderer(int index)
        {
            GameObject lineObj = new GameObject("RuntimeLine_" + index);
            lineObj.transform.SetParent(runtimeLineRoot, false);

            LineRenderer lineRenderer = lineObj.AddComponent<LineRenderer>();
            lineRenderer.useWorldSpace = false;
            lineRenderer.positionCount = 2;
            lineRenderer.startWidth = runtimeLineWidth;
            lineRenderer.endWidth = runtimeLineWidth;
            lineRenderer.alignment = LineAlignment.View;
            lineRenderer.textureMode = LineTextureMode.Stretch;
            lineRenderer.sortingOrder = runtimeSortingOrder;
            lineRenderer.sharedMaterial = GetRuntimeLineMaterial();
            return lineRenderer;
        }

        private void SetLineRenderer(LineRenderer lineRenderer, Color color, Vector3 start, Vector3 end)
        {
            if (lineRenderer == null)
            {
                return;
            }

            lineRenderer.startColor = color;
            lineRenderer.endColor = color;
            lineRenderer.startWidth = runtimeLineWidth;
            lineRenderer.endWidth = runtimeLineWidth;
            lineRenderer.sortingOrder = runtimeSortingOrder;
            lineRenderer.SetPosition(0, start);
            lineRenderer.SetPosition(1, end);
        }

        private Material GetRuntimeLineMaterial()
        {
            if (runtimeLineMaterial != null)
            {
                return runtimeLineMaterial;
            }

            Shader shader = Shader.Find("Sprites/Default");
            if (shader == null)
            {
                shader = Shader.Find("Unlit/Color");
            }

            if (shader == null)
            {
                Debug.LogError("运行时辅助线缺少可用 Shader。");
                return null;
            }

            runtimeLineMaterial = new Material(shader);
            runtimeLineMaterial.name = "RuntimeEditorLineMaterial";
            return runtimeLineMaterial;
        }
    }
}
