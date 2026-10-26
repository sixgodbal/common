using System;
using System.Collections.Generic;
using System.Runtime.Serialization;
using UnityEngine;

[Serializable]
public class MapFile
{
    public int ID;
    public int col;
    public int row;
    public List<int> team1SpawnPos;
    public List<int> team2SpawnPos;
    [OptionalField]
    public List<int> team3SpawnPos;
    public List<int> team1Building;
    public List<int> team2Building;


    public int[] floorArr;
    public int[] wallArr;
    public int[] brickArr;
    public int[] moveBrickArr;
    public int[] composeWallArr;
    public int[] doorArr;
    public BuildingInfo[] buildingInfoArr;
    public int[] buildingArr;
    public int[] grassArr;
    public int[] riverArr;
    public int[] pinFloorArr;
    public int[] spikeWallArr;
    public int[] totemArr;
}

[Serializable]
public class BuildingInfo
{
    public int posIndex;
    public int team;//0:team1 1:team2 2:team3
    public int assetID;

}

public enum TeamEnum
{
    None = -1,
    TEAM_1 = 0,
    TEAM_2 = 1,
    TEAM_3 = 2,
    Neutal = 8
}

public class GridID
{
    public int x;
    public int y;

    public GridID(int _x, int _y)
    {
        x = _x;
        y = _y;
    }
}
