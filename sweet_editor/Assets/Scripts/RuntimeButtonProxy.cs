using UnityEngine;
using UnityEngine.Events;
using UnityEngine.EventSystems;

public class RuntimeButtonProxy : MonoBehaviour, IPointerClickHandler
{
    private UnityAction handler;

    public void SetHandler(UnityAction action)
    {
        handler = action;
    }

    public void OnPointerClick(PointerEventData eventData)
    {
        if (handler != null)
        {
            handler.Invoke();
            eventData.Use();
        }
    }
}
