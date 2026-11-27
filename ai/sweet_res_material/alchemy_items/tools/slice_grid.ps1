param(
  [Parameter(Mandatory=$true)][string]$Sheet,
  [Parameter(Mandatory=$true)][string]$OutDir,
  [string]$Prefix = "sheet",
  [int]$Cols = 4,
  [int]$Rows = 3,
  [string]$Names = "",
  [int]$Cell = 256,
  [double]$Fill = 0.94,
  [int]$Tolerance = 38,
  [int]$MinArea = 400
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$code = @"
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public class GridCutter
{
    public class Box { public int MinX, MinY, MaxX, MaxY, Area; public int W { get { return MaxX - MinX + 1; } } public int H { get { return MaxY - MinY + 1; } } }

    public static int CutBackground(string inPath, string outPath, int tol)
    {
        int w, h, stride;
        byte[] buf;
        using (var src = new Bitmap(inPath))
        {
            w = src.Width; h = src.Height;
            using (var bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb))
            {
                using (var g = Graphics.FromImage(bmp)) { g.DrawImage(src, 0, 0, w, h); }
                var rect = new Rectangle(0, 0, w, h);
                var data = bmp.LockBits(rect, ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
                stride = data.Stride;
                buf = new byte[stride * h];
                Marshal.Copy(data.Scan0, buf, 0, buf.Length);
                bmp.UnlockBits(data);
            }
        }

        int so = 2 * stride + 2 * 4;
        int b0 = buf[so], g0 = buf[so + 1], r0 = buf[so + 2];
        bool[] bg = new bool[w * h];
        var stack = new Stack<int>();
        PushBorder(stack, bg, buf, w, h, stride, tol, r0, g0, b0);

        int cleared = 0;
        while (stack.Count > 0)
        {
            int idx = stack.Pop();
            int px = idx % w, py = idx / w;
            buf[py * stride + px * 4 + 3] = 0;
            cleared++;
            if (px > 0) TryPush(stack, bg, buf, w, stride, tol, r0, g0, b0, idx - 1);
            if (px < w - 1) TryPush(stack, bg, buf, w, stride, tol, r0, g0, b0, idx + 1);
            if (py > 0) TryPush(stack, bg, buf, w, stride, tol, r0, g0, b0, idx - w);
            if (py < h - 1) TryPush(stack, bg, buf, w, stride, tol, r0, g0, b0, idx + w);
        }

        using (var bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb))
        {
            var rect = new Rectangle(0, 0, w, h);
            var data = bmp.LockBits(rect, ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
            Marshal.Copy(buf, 0, data.Scan0, buf.Length);
            bmp.UnlockBits(data);
            bmp.Save(outPath, ImageFormat.Png);
        }
        return cleared;
    }

    static void PushBorder(Stack<int> stack, bool[] bg, byte[] buf, int w, int h, int stride, int tol, int r0, int g0, int b0)
    {
        for (int x = 0; x < w; x++)
        {
            TryPush(stack, bg, buf, w, stride, tol, r0, g0, b0, x);
            TryPush(stack, bg, buf, w, stride, tol, r0, g0, b0, (h - 1) * w + x);
        }
        for (int y = 0; y < h; y++)
        {
            TryPush(stack, bg, buf, w, stride, tol, r0, g0, b0, y * w);
            TryPush(stack, bg, buf, w, stride, tol, r0, g0, b0, y * w + w - 1);
        }
    }

    static void TryPush(Stack<int> stack, bool[] bg, byte[] buf, int w, int stride, int tol, int r0, int g0, int b0, int idx)
    {
        if (bg[idx]) return;
        int o = (idx / w) * stride + (idx % w) * 4;
        int d = Math.Abs(buf[o + 2] - r0) + Math.Abs(buf[o + 1] - g0) + Math.Abs(buf[o] - b0);
        if (d > tol) return;
        bg[idx] = true;
        stack.Push(idx);
    }

    public static Box[] AnalyzeCells(string path, int cols, int rows, int minArea)
    {
        int w, h, stride;
        byte[] buf;
        using (var src = new Bitmap(path))
        {
            w = src.Width; h = src.Height;
            using (var bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb))
            {
                using (var g = Graphics.FromImage(bmp)) { g.DrawImage(src, 0, 0, w, h); }
                var rect = new Rectangle(0, 0, w, h);
                var data = bmp.LockBits(rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
                stride = data.Stride;
                buf = new byte[stride * h];
                Marshal.Copy(data.Scan0, buf, 0, buf.Length);
                bmp.UnlockBits(data);
            }
        }

        var result = new Box[cols * rows];
        for (int r = 0; r < rows; r++)
        {
            for (int c = 0; c < cols; c++)
            {
                int x0 = (int)Math.Floor((double)w * c / cols);
                int x1 = (int)Math.Floor((double)w * (c + 1) / cols);
                int y0 = (int)Math.Floor((double)h * r / rows);
                int y1 = (int)Math.Floor((double)h * (r + 1) / rows);
                var box = new Box { MinX = int.MaxValue, MinY = int.MaxValue, MaxX = -1, MaxY = -1 };
                for (int y = y0; y < y1; y++)
                {
                    int row = y * stride;
                    for (int x = x0; x < x1; x++)
                    {
                        if (buf[row + x * 4 + 3] <= 8) continue;
                        box.Area++;
                        if (x < box.MinX) box.MinX = x;
                        if (x > box.MaxX) box.MaxX = x;
                        if (y < box.MinY) box.MinY = y;
                        if (y > box.MaxY) box.MaxY = y;
                    }
                }
                if (box.Area >= minArea) result[r * cols + c] = box;
            }
        }
        return result;
    }

    public static void SaveCrop(string path, Box b, int cell, string outPath, double fill)
    {
        using (var src = new Bitmap(path))
        using (var dst = new Bitmap(cell, cell, PixelFormat.Format32bppArgb))
        {
            using (var g = Graphics.FromImage(dst))
            {
                g.Clear(Color.Transparent);
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                g.CompositingQuality = CompositingQuality.HighQuality;
                g.SmoothingMode = SmoothingMode.HighQuality;
                double s = Math.Min(cell * fill / b.W, cell * fill / b.H);
                int dw = Math.Max(1, (int)Math.Round(b.W * s));
                int dh = Math.Max(1, (int)Math.Round(b.H * s));
                int dx = (cell - dw) / 2, dy = (cell - dh) / 2;
                using (var ia = new ImageAttributes())
                {
                    ia.SetWrapMode(WrapMode.TileFlipXY);
                    g.DrawImage(src, new Rectangle(dx, dy, dw, dh), b.MinX, b.MinY, b.W, b.H, GraphicsUnit.Pixel, ia);
                }
            }
            dst.Save(outPath, ImageFormat.Png);
        }
    }
}
"@

if (-not ("GridCutter" -as [type])) { Add-Type -TypeDefinition $code -ReferencedAssemblies System.Drawing }
Add-Type -AssemblyName System.Drawing

if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }

$sheetPath = (Resolve-Path $Sheet).Path
$cutPath = Join-Path (Split-Path $sheetPath -Parent) ([IO.Path]::GetFileNameWithoutExtension($sheetPath) + "_cut.png")
$cleared = [GridCutter]::CutBackground($sheetPath, $cutPath, $Tolerance)
Write-Output ("cut -> {0}  cleared={1}" -f $cutPath, $cleared)

$boxes = [GridCutter]::AnalyzeCells($cutPath, $Cols, $Rows, $MinArea)

$nameList = @()
if ($Names) { $nameList = @($Names -split "," | ForEach-Object { $_.Trim() }) }

$index = @()
for ($r = 0; $r -lt $Rows; $r++) {
  for ($c = 0; $c -lt $Cols; $c++) {
    $i = $r * $Cols + $c
    $name = if ($i -lt $nameList.Count) { $nameList[$i] } else { "r$($r+1)c$($c+1)" }
    if (-not $name -or $name -eq "-" -or $name -eq "empty") { continue }
    $box = $boxes[$i]
    if (-not $box) { Write-Output "MISS r$($r+1)c$($c+1) ($name)"; continue }
    $out = Join-Path (Resolve-Path $OutDir).Path ("{0}.png" -f $name)
    [GridCutter]::SaveCrop($cutPath, $box, $Cell, $out, $Fill)
    $index += [pscustomobject]@{ file = "$name.png"; name = $name; row = $r + 1; col = $c + 1; srcW = $box.W; srcH = $box.H; srcX = $box.MinX; srcY = $box.MinY }
    Write-Output ("OK  {0}.png  (r{1}c{2}  {3}x{4})" -f $name, ($r + 1), ($c + 1), $box.W, $box.H)
  }
}

$idxPath = Join-Path (Resolve-Path $OutDir).Path ("{0}_index.json" -f $Prefix)
$index | ConvertTo-Json -Depth 4 | Set-Content -Path $idxPath -Encoding UTF8
Write-Output "index -> $idxPath"
