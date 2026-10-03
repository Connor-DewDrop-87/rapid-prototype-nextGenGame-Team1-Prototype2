using System.Collections;
using System.Collections.Generic;
using Unity.VisualScripting;
using UnityEngine;

public class Planterns : MonoBehaviour
{
    // Player Variables
    Player pr;
    // How far the player can be to start the cutscene
    public float reach = 1.5f;
    float distanceFromPlayer;
    public enum States
    {
        BARREN,
        PLANETED,
        PULLEDOUT
    }

    public States state;
    public Plant plant;
    public GameObject maxMoneyTimer;
    // Start is called before the first frame update
    void Start()
    {
        pr = GameObject.FindGameObjectWithTag("Player").GetComponent<Player>();
        maxMoneyTimer.transform.localScale = new Vector3(0, 0.1225f, 1);
    }

    // Update is called once per frame
    void Update()
    {
        // Check the distance of the Plantern and the Player
        distanceFromPlayer = Vector2.Distance(transform.position, pr.transform.position);
        switch (state)
        {
            case States.BARREN:
                // Check if the player is in range of the Planterns
                if (distanceFromPlayer <= reach)
                {
                    // If Space is Pressed, the Plantern becomes Planted with the Plant the Player has
                    if (Input.GetKeyDown(KeyCode.Space))
                    {
                        if (pr.plantables[pr.currentPlant].amount<=0)
                        {
                            pr.plantables[pr.currentPlant].amount = 0;
                            Debug.Log("No Plants Left");
                            pr.SendPlantInfo();
                            return;
                        }
                        pr.plantables[pr.currentPlant].amount--;
                        // Update Plant UI
                        pr.SendPlantInfo();
                        // Copy Plant Data Necessary
                        plant.Name = pr.plantables[pr.currentPlant].Name;
                        plant.maxMoney = pr.plantables[pr.currentPlant].maxMoney;
                        plant.harvestTime = pr.plantables[pr.currentPlant].harvestTime;
                        plant.currentTime = 0;
                        state = States.PLANETED;
                    }
                }
                break;
            case States.PLANETED:
                // Increase the time of the Plant unless it is at or greater than the Harvest Time
                // If its above the Harvest Time, the time is set to the Harvest Time
                if (plant.currentTime >= plant.harvestTime)
                {
                    plant.currentTime = plant.harvestTime;
                }
                else
                {
                    plant.currentTime += Time.deltaTime;
                }
                // Increase, or decrease, the MoneyTimer based on how the plant is doing
                maxMoneyTimer.transform.localScale = new Vector3(CheckMoney()/plant.maxMoney, 0.1225f, 1);
                // Check if the player is in range of the Planterns
                if (distanceFromPlayer <= reach)
                {
                    // If Space is Pressed, the Plantern has its plant pulled out
                    if (Input.GetKeyDown(KeyCode.Space))
                    {
                        pr.money += CheckMoney();
                        state = States.PULLEDOUT;
                    }
                }
                break;
            case States.PULLEDOUT:
                // Reset the Timer Scale
                maxMoneyTimer.transform.localScale = new Vector3(0, 0.1225f, 1);
                plant = new Plant();
                state = States.BARREN;
                break;
                
        }
        
    }

    float CheckMoney()
    {
        float money = 0;
        // Use the Vertex Formula to Calculate how much money the player gets
        // The Harvest Time is not exact to Y=0 but close and informs the player that money goes down
        money = -1*(Mathf.Pow(plant.currentTime-(plant.harvestTime/2),2))+(plant.maxMoney);
        money = Mathf.Round(money);
        return money;
    }
}
