using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlantRefuler : MonoBehaviour
{
    // Player Variables
    Player pr;
    // How far the player can be to start the cutscene
    public float reach = 1.5f;
    float distanceFromPlayer;
    // Start is called before the first frame update
    void Start()
    {
        pr = GameObject.FindGameObjectWithTag("Player").GetComponent<Player>();
    }

    // Update is called once per frame
    void Update()
    {
        // Check the distance of the Plantern and the Player
        distanceFromPlayer = Vector2.Distance(transform.position, pr.transform.position);
        if (distanceFromPlayer <= reach)
        {
            // While within range, if they
            if (Input.GetKeyDown(KeyCode.Space))
            {
                // The Cost of a Plant is equal to half the maxMoney you can get
                float cost = Mathf.Floor(pr.plantables[pr.currentPlant].maxMoney / 2);
                // Check if they have enough money, if they do the amount of that plant goes up by 1
                if (cost <= pr.money)
                {
                    pr.money -= cost;
                    pr.plantables[pr.currentPlant].amount++;
                    // Update Plant UI
                    pr.SendPlantInfo();
                }
                // Otherwise, nothing happens
                else
                {
                    Debug.Log("Not Enough Money");
                }
            }
        }
    }
}
