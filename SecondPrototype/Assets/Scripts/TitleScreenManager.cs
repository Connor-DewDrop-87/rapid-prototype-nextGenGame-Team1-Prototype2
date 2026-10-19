using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using TMPro;

public class TitleScreenManager : MonoBehaviour
{
    public GameManager GM;
    public TextMeshProUGUI HighScore;
    void Update()
    {
        if (GM == null)
        {
            GM = GameObject.Find("GameManager").GetComponent<GameManager>();
            return;
        }
        HighScore.text = $"High Score: {GM.previousScore}";
    }
    public void GoToGame()
    {
        SceneManager.LoadScene("BaseGame");
    }
}
