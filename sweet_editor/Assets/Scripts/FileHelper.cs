using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Formatters.Binary;

public class FileHelper
{
    public byte[] Serialize<T>(T msg)
    {
        using (MemoryStream ms = new MemoryStream())
        {
            try
            {
                BinaryFormatter bf = new BinaryFormatter();
                bf.Serialize(ms, msg);
                ms.Seek(0, SeekOrigin.Begin);
                return ms.ToArray();
            }
            catch (SerializationException e)
            {
                Console.WriteLine("Serialize Fail");
                throw;
            }
        }
    }
    public T DeSerialize<T>(byte[] bytes)
    {
        using (MemoryStream ms = new MemoryStream(bytes))
        {
            try
            {
                BinaryFormatter bf = new BinaryFormatter();
                T msg = (T)bf.Deserialize(ms);
                return msg;
            }
            catch (SerializationException e)
            {
                Console.WriteLine("Deserialize Fail");
                throw;
            }
        }
    }

    public byte[] Compress(byte[] input)
    {
        using (MemoryStream outMS = new MemoryStream())
        {
            using (GZipStream gzs = new GZipStream(outMS, CompressionMode.Compress, true))
            {
                gzs.Write(input, 0, input.Length);
                gzs.Close();
                return outMS.ToArray();
            }
        }
    }
    public byte[] DeCompress(byte[] input)
    {
        using (MemoryStream inputMS = new MemoryStream(input))
        {
            using (MemoryStream outMs = new MemoryStream())
            {
                using (GZipStream gzs = new GZipStream(inputMS, CompressionMode.Decompress))
                {
                    byte[] bytes = new byte[1024];
                    int len = 0;
                    while ((len = gzs.Read(bytes, 0, bytes.Length)) > 0)
                    {
                        outMs.Write(bytes, 0, len);
                    }
                    gzs.Close();
                    return outMs.ToArray();
                }
            }
        }
    }

    public bool WriteMapFile(string path, string name, MapFile mapData)
    {
        if(mapData == null)
        {
            return false;
        }

        if(!Directory.Exists(path))
        {
            Directory.CreateDirectory(path);
        }

        byte[] data = Compress(Serialize(mapData));
        string fullName = string.Format("{0}/{1}.bytes", path, name);
        FileStream saveFile = new FileStream(fullName, FileMode.Create, FileAccess.Write);
        saveFile.Write(data, 0, data.Length);
        saveFile.Close();
        ViewManager.Instance.ShowTips(string.Format("保存成功！路径: {0}", fullName));
        return true;
    }

    public MapFile ReadMapFile(string path, string name)
    {
        string fullName = string.Format("{0}/{1}.bytes", path, name);
        FileStream loadFile;
        try
        {
            loadFile = new FileStream(fullName, FileMode.Open, FileAccess.Read);

        }
        catch (Exception)
        {
            ViewManager.Instance.ShowTips(string.Format("地图不存在! 路径: {0}", fullName));
            return null;
        }
        byte[] data = new byte[loadFile.Length];
        loadFile.Read(data, 0, data.Length);
        loadFile.Close();
        byte[] deCompressData = DeCompress(data);
        MapFile file = DeSerialize<MapFile>(deCompressData);
        return file;
    }
}
