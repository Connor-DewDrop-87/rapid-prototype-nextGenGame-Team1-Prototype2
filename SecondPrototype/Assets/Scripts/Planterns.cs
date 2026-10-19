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
    public SpriteRenderer plantGrowingSprite;
    // Start is called before the first frame update
    void Start()
    {
        pr = GameObject.FindGameObjectWithTag("Player").GetComponent<Player>();
        plantGrowingSprite.sprite = null;
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
                        plant.plantSprites.Clear();
                        foreach (Sprite pl in pr.plantables[pr.currentPlant].plantSprites)
                        {
                            plant.plantSprites.Add(pl);
                        }
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
                // Update the Plant Sprites over time
                UpdatePlantSprites();
                // Check if the player is in range of the Planterns
                if (distanceFromPlayer <= reach)
                {
                    // If Space is Pressed, the Plantern has its plant pulled out
                    if (Input.GetKeyDown(KeyCode.Space))
                    {
                        float profit = CheckMoney();
                        // Make sure the Profit is not Negative
                        if (profit < 0)
                        {
                            profit = 0;
                        }
                        pr.money += profit;
                        state = States.PULLEDOUT;
                    }
                }
                break;
            case States.PULLEDOUT:
                // Reset the Timer Scale
                plant = new Plant();
                // Reset the Plant Sprites
                plantGrowingSprite.sprite = null;
                plantGrowingSprite.color = Color.white;
                state = States.BARREN;
                break;
                
        }
        // When the timer hits 0, Pull Out All the Plants if they are not already Barren
        if (pr.uiRef.timer.timerRunning==false && state != States.BARREN)
        {
            state = States.PULLEDOUT;
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

    public void UpdatePlantSprites()
    {
        // New Plant
        if (plant.currentTime >= 0)
        {
            plantGrowingSprite.sprite = plant.plantSprites[0];
        }
        // Sprouting
        if (plant.currentTime >= plant.harvestTime/ 4f)
        {
            plantGrowingSprite.sprite = plant.plantSprites[1];
        }
        // Growing
        if (plant.currentTime >= plant.harvestTime*3f / 8f)
        {
            plantGrowingSprite.sprite = plant.plantSprites[2];
        }
        // Full Grown
        if (plant.currentTime >= plant.harvestTime / 2f)
        {
            plantGrowingSprite.sprite = plant.plantSprites[3];
        }
        // Rotting
    }
}
