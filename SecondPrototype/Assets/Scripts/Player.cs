using System.Collections;
using System.Collections.Generic;
//using UnityEditor.Sprites;
using UnityEngine;
using TMPro;

public class Player : MonoBehaviour
{
    public Vector2 move;
    public float moveSpeed = 1;
    Rigidbody2D rbd2;
    Transform cameraPosition;
    public Plant[] plantables;
    public int currentPlant;
    public int maxPlants;
    public float money;
    public UIManager uiRef;
    // Start is called before the first frame update
    void Start()
    {
        rbd2 = GetComponent<Rigidbody2D>();
        currentPlant = 0;
        maxPlants = plantables.Length - 1;
        uiRef = GameObject.Find("UI").GetComponent<UIManager>();
    }

    // Update is called once per frame
    void Update()
    {
        // Movement of the player and Camera Code was taken from a Project in Game Engines 
        move.x = Input.GetAxisRaw("Horizontal");
        move.y = Input.GetAxisRaw("Vertical");
        rbd2.MovePosition(rbd2.position + move * moveSpeed * Time.deltaTime);
        PlantSelect();
    }
    void LateUpdate()
    {
        cameraPosition = GameObject.FindGameObjectWithTag("MainCamera").GetComponent<Transform>();
        cameraPosition.position = new Vector3(transform.position.x, transform.position.y, transform.position.z - 10);
    }

    public void SendPlantInfo()
    {
        for (int i = 0; i < plantables.Length; i++)
        {
            GameObject plantUIChanged = uiRef.PlantUIList[i];
            TextMeshProUGUI plantText = plantUIChanged.GetComponentInChildren<TextMeshProUGUI>();
            plantText.text = plantables[i].Name + "\nAmount: " + plantables[i].amount;
        }
    }
    void PlantSelect()
    {
        // Plant 1
        if (Input.GetKeyDown(KeyCode.Alpha1))
        {
            currentPlant = 0;
        }
        // Plant 2
        if (Input.GetKeyDown(KeyCode.Alpha2))
        {
            currentPlant = 1;
        }
        // Plant 3
        if (Input.GetKeyDown(KeyCode.Alpha3))
        {
            currentPlant = 2;
        }
        // Plant 4
        if (Input.GetKeyDown(KeyCode.Alpha4))
        {
            currentPlant = 3;
        }

        if (currentPlant > maxPlants)
        {
            currentPlant = maxPlants;
        }

    }
}
