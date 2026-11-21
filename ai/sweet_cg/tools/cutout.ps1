param(
  [string]$Config = ".\\tools\\cutout.json",
  [string]$Suffix = "_cut",
  [int]$Tolerance = 24
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$code = @"
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public static class BgCut
{
    public static int Cut(string inPath, string outPath, int tol)
    {
        using (var src = new Bitmap(inPath))
        {
            int w = src.Width, h = src.Height;
            var bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb);
            using (var gg = Graphics.FromImage(bmp)) { gg.DrawImage(src, 0, 0, w, h); }

            var rect = new Rectangle(0, 0, w, h);
            var data = bmp.LockBits(rect, ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
            int stride = data.Stride;
            var buf = new byte[stride * h];
            Marshal.Copy(data.Scan0, buf, 0, buf.Length);

            int so = 2 * stride + 2 * 4;
            byte b0 = buf[so], g0 = buf[so + 1], r0 = buf[so + 2];

            var seen = new bool[w * h];
            var stack = new Stack<int>();
            for (int x = 0; x < w; x++) { stack.Push(x); stack.Push((h - 1) * w + x); }
            for (int y = 0; y < h; y++) { stack.Push(y * w); stack.Push(y * w + w - 1); }

            int cleared = 0;
            while (stack.Count > 0)
            {
                int idx = stack.Pop();
                if (seen[idx]) continue;
                seen[idx] = true;
                int px = idx % w, py = idx / w;
                int o = py * stride + px * 4;
                int d = Math.Abs(buf[o + 2] - r0) + Math.Abs(buf[o + 1] - g0) + Math.Abs(buf[o] - b0);
                if (d > tol) continue;
                buf[o + 3] = 0;
                cleared++;
                if (px > 0) stack.Push(idx - 1);
                if (px < w - 1) stack.Push(idx + 1);
                if (py > 0) stack.Push(idx - w);
                if (py < h - 1) stack.Push(idx + w);
            }

            Marshal.Copy(buf, 0, data.Scan0, buf.Length);
            bmp.UnlockBits(data);
            bmp.Save(outPath, ImageFormat.Png);
            bmp.Dispose();
            return cleared;
        }
    }
}
"@

if (-not ("BgCut" -as [type])) { Add-Type -TypeDefinition $code -ReferencedAssemblies System.Drawing }
Add-Type -AssemblyName System.Drawing

$root  = (Resolve-Path ".").Path
$items = [IO.File]::ReadAllText((Resolve-Path $Config).Path, [Text.Encoding]::UTF8) | ConvertFrom-Json

foreach ($it in $items) {
  $p = Join-Path $root ($it.file -replace '^\.\\', '')
  if (-not (Test-Path $p)) { Write-Output "MISS $p"; continue }
  $o = [IO.Path]::Combine([IO.Path]::GetDirectoryName($p), [IO.Path]::GetFileNameWithoutExtension($p) + $Suffix + ".png")
  $n = [BgCut]::Cut($p, $o, $Tolerance)
  Write-Output ("OK  {0}  cleared={1}" -f [IO.Path]::GetFileName($o), $n)
}
