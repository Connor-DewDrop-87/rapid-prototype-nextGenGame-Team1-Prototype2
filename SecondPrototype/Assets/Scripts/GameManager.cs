using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

public class GameManager : MonoBehaviour
{
    public static GameManager Instance;
    public float previousScore;
    // Keep GameManager Between Scenes
    private void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }

        Instance = this;
        DontDestroyOnLoad(gameObject);
    }

    
    public void ExitGame()
    {
        // Get the Player's Money
        float newScore = GameObject.Find("Player").GetComponent<Player>().money;
        // Check if it's greater than the previous score, if it is replace it
        if (newScore >  previousScore)
        {
            previousScore = newScore;
        }
        SceneManager.LoadScene("TitleScene");
    }
}
