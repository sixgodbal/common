
using UnityEngine.UI;

public class TeamSpawnPosItem : MapElemItem
{
    public Text indexText;

    public override void SetIndex(int index)
    {
        base.SetIndex(index);
        indexText.text = index.ToString();
        indexText.gameObject.SetActive(true);
    }
}