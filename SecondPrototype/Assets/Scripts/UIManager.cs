using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using TMPro;

public class UIManager : MonoBehaviour
{
    // Prefabs
    public GameObject UIPrefab;
    public GameObject Cursor;
    // PlantUI Elements
    public GameObject PlantSpacer;
    public List<GameObject> PlantUIList = new List<GameObject>();
    // Player Variables
    Player pr;
    // Start is called before the first frame update
    void Start()
    {
        pr = GameObject.FindGameObjectWithTag("Player").GetComponent<Player>();
        GetPlayerPlants();
    }

    void Update()
    {
        Cursor.transform.position = PlantUIList[pr.currentPlant].transform.position + new Vector3(0,250,0);
    }
    void GetPlayerPlants()
    {
        for (int i = 0; i < pr.plantables.Length; i++)
        {
            GameObject newPlantUI = Instantiate(UIPrefab) as GameObject;
            TextMeshProUGUI plantText = newPlantUI.GetComponentInChildren<TextMeshProUGUI>();
            plantText.text = pr.plantables[i].Name + "\nAmount: " + pr.plantables[i].amount;
            newPlantUI.transform.SetParent(PlantSpacer.transform, false);
            PlantUIList.Add(newPlantUI);
        }
    }
}
